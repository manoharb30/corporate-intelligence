"""Signal performance endpoints — track record / showcase page.

POST /compute endpoint was removed 2026-04-24 as part of retiring compute_all.
Signal performance is now event-driven: new clusters stored at ingest time,
maturity scored per-signal at 90d mark. Aggregate stats blend HistoricAnchor
+ RunningDelta.
"""

import csv
import io

from fastapi import APIRouter, Query
from fastapi.responses import StreamingResponse

from app.services.signal_performance_service import SignalPerformanceService

router = APIRouter()


@router.get("")
async def get_signal_performances(
    direction: str = Query(default=None, regex="^(buy)$"),  # v1.3: sell removed; all signals are buy
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


@router.get("/dashboard-stats")
async def get_dashboard_stats():
    """Precomputed dashboard hero stats — instant, no computation.

    Returns: total_signals, hit_rate, avg_alpha, beat_spy_pct, computed_at
    Updated when a signal matures (Phase D); HistoricAnchor + RunningDelta
    blend replaces the previous compute_all-driven refresh.
    """
    stats = await SignalPerformanceService.get_dashboard_stats()
    if not stats:
        return {"error": "No dashboard stats available."}
    return stats


@router.get("/download")
async def download_csv(
    direction: str = Query(default=None, regex="^(buy)$"),  # v1.3: sell removed; all signals are buy
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
        "price_day7", "price_day90",
        "return_day0", "return_day1", "return_day2", "return_day3",
        "return_day5", "return_day7",
        "spy_return_90d", "followed_by_8k", "days_to_8k",
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
