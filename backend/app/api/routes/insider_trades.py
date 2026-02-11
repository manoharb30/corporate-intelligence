"""API endpoints for insider trading (Form 4) data."""

from fastapi import APIRouter, Query

from app.services.insider_trading_service import InsiderTradingService

router = APIRouter()


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
