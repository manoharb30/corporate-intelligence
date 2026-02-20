"""API endpoints for insider trading (Form 4) data."""

import logging

from fastapi import APIRouter, BackgroundTasks, Query

from app.services.insider_trading_service import BackfillResult, InsiderTradingService

logger = logging.getLogger(__name__)

router = APIRouter()

# Module-level backfill state (single-user app)
_backfill_state = BackfillResult()


@router.get("")
async def get_insider_trades(
    cik: str = Query(..., description="Company CIK"),
    days: int = Query(90, ge=1, le=365, description="Look back this many days"),
    limit: int = Query(50, ge=1, le=200, description="Maximum trades to return"),
):
    """
    Get insider trades for a company.

    Example:
        GET /insider-trades?cik=0000789019&days=90
    """
    trades = await InsiderTradingService.get_company_insider_trades(
        cik=cik,
        days=days,
        limit=limit,
    )

    return {
        "cik": cik,
        "total": len(trades),
        "trades": [t.to_dict() for t in trades],
    }


@router.get("/summary")
async def get_insider_trade_summary(
    cik: str = Query(..., description="Company CIK"),
    days: int = Query(90, ge=1, le=365, description="Look back this many days"),
):
    """
    Get insider trading summary with signal classification.

    Example:
        GET /insider-trades/summary?cik=0000789019
    """
    return await InsiderTradingService.get_insider_trade_summary(
        cik=cik,
        days=days,
    )


@router.post("/scan/{cik}")
async def scan_insider_trades(
    cik: str,
    company_name: str = Query(..., description="Company name"),
    limit: int = Query(50, ge=1, le=100, description="Number of Form 4 filings to scan"),
):
    """
    Scan a company's Form 4 filings and store transactions.

    Example:
        POST /insider-trades/scan/0000789019?company_name=SPLUNK+INC
    """
    result = await InsiderTradingService.scan_and_store_company(
        cik=cik,
        company_name=company_name,
        limit=limit,
    )
    return result


@router.post("/backfill")
async def backfill_insider_trades(
    background_tasks: BackgroundTasks,
    max_companies: int = Query(50, ge=1, le=1000, description="Maximum companies to backfill"),
):
    """
    Backfill insider trade data for companies missing it.

    Prioritizes HIGH signal companies first, then MEDIUM, then LOW.
    Runs in background.

    Example:
        POST /insider-trades/backfill?max_companies=50
    """
    global _backfill_state

    if _backfill_state.status == "in_progress":
        return {
            "status": "already_running",
            "message": (
                f"Backfill in progress: {_backfill_state.companies_scanned}/"
                f"{_backfill_state.total_companies} companies"
            ),
        }

    # Get prioritized list of companies missing insider data
    companies = await InsiderTradingService.get_companies_missing_insider_data()

    if not companies:
        return {
            "status": "no_work",
            "message": "All companies with M&A signals already have insider trade data",
        }

    # Limit batch size
    batch = companies[:max_companies]

    # Reset state and start
    _backfill_state = BackfillResult(status="in_progress", message="Starting backfill...")

    background_tasks.add_task(InsiderTradingService.backfill_companies, batch, _backfill_state)

    priority_counts = {"1": 0, "2": 0, "3": 0}
    for c in batch:
        priority_counts[str(c.get("priority", 3))] = priority_counts.get(str(c.get("priority", 3)), 0) + 1

    return {
        "status": "started",
        "message": f"Backfill started for {len(batch)} companies (of {len(companies)} missing data)",
        "total_missing": len(companies),
        "batch_size": len(batch),
        "priority_breakdown": {
            "high_signal": priority_counts.get("1", 0),
            "medium_signal": priority_counts.get("2", 0),
            "low_signal": priority_counts.get("3", 0),
        },
    }


@router.get("/backfill/status")
async def backfill_status():
    """
    Get the current backfill status.

    Example:
        GET /insider-trades/backfill/status
    """
    return _backfill_state.to_dict()
