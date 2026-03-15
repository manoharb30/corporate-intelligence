"""Signal performance endpoints — track record / showcase page."""

import csv
import io

from fastapi import APIRouter, Query
from fastapi.responses import StreamingResponse

from app.services.signal_performance_service import SignalPerformanceService

router = APIRouter()


@router.post("/compute")
async def compute_signal_performance(
    days: int = Query(default=365, ge=30, le=730),
):
    """Compute signal performance for all clusters and store in Neo4j.

    This is a heavy operation (fetches prices from yfinance).
    Run daily after scanner or on-demand.
    """
    result = await SignalPerformanceService.compute_all(days=days)
    return result


@router.get("")
async def get_signal_performances(
    direction: str = Query(default=None, regex="^(buy|sell)$"),
    mature_only: bool = Query(default=False),
    meaningful_only: bool = Query(default=True),
    limit: int = Query(default=500, ge=1, le=1000),
):
    """Get all stored signal performances."""
    return await SignalPerformanceService.get_all(
        direction=direction,
        mature_only=mature_only,
        meaningful_only=meaningful_only,
        limit=limit,
    )


@router.get("/summary")
async def get_summary(
    meaningful_only: bool = Query(default=True),
):
    """Aggregate stats for the showcase page header."""
    return await SignalPerformanceService.get_summary(meaningful_only=meaningful_only)


@router.get("/delayed-entry")
async def get_delayed_entry(
    meaningful_only: bool = Query(default=True),
):
    """Delayed entry analysis: avg return at each delay point."""
    return await SignalPerformanceService.get_delayed_entry_stats(meaningful_only=meaningful_only)


@router.get("/conviction-ladder")
async def get_conviction_ladder(
    meaningful_only: bool = Query(default=True),
):
    """Sell signal accuracy by insider count threshold."""
    return await SignalPerformanceService.get_conviction_ladder(meaningful_only=meaningful_only)


@router.get("/industry")
async def get_industry_breakdown(
    meaningful_only: bool = Query(default=True),
):
    """Buy signal accuracy by industry."""
    return await SignalPerformanceService.get_industry_breakdown(meaningful_only=meaningful_only)


@router.get("/download")
async def download_csv(
    direction: str = Query(default=None, regex="^(buy|sell)$"),
    mature_only: bool = Query(default=True),
    meaningful_only: bool = Query(default=True),
):
    """Download signal performances as CSV."""
    data = await SignalPerformanceService.get_all(
        direction=direction,
        mature_only=mature_only,
        meaningful_only=meaningful_only,
        limit=1000,
    )

    if not data:
        return StreamingResponse(
            io.StringIO("No data"),
            media_type="text/csv",
            headers={"Content-Disposition": "attachment; filename=signal_performance.csv"},
        )

    output = io.StringIO()
    fields = [
        "signal_id", "ticker", "company_name", "signal_date", "direction",
        "signal_level", "num_insiders", "total_value", "conviction_tier",
        "industry", "market_cap", "pct_of_mcap",
        "price_day0", "price_day1", "price_day2", "price_day3", "price_day5",
        "price_day7", "price_day30",
        "return_day0", "return_day1", "return_day2", "return_day3",
        "return_day5", "return_day7",
        "spy_return_30d", "followed_by_8k", "days_to_8k",
    ]
    writer = csv.DictWriter(output, fieldnames=fields, extrasaction="ignore")
    writer.writeheader()
    for row in data:
        writer.writerow(row)

    output.seek(0)
    return StreamingResponse(
        output,
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=signal_performance.csv"},
    )
