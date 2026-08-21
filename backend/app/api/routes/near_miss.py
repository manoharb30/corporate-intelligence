"""API endpoint for the Research Queue — clusters filtered on earnings timing.

Internal for now: registered but deliberately not linked from the frontend nav.
These are NOT signals; the caveat travels with the payload so the framing cannot
be dropped downstream.
"""

from datetime import datetime, timedelta

from fastapi import APIRouter, Query

from app.services.near_miss_service import NearMissService, CAVEAT

router = APIRouter()


@router.get("")
async def get_near_misses(days: int = Query(60, ge=1, le=365)):
    """Genuine insider clusters rejected solely by the earnings-proximity filter,
    ranked by insider commitment as a share of market cap.

    Example:
        GET /api/near-miss?days=60
    """
    since_date = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
    near_misses = await NearMissService.get_near_misses(since_date=since_date)
    return {
        "caveat": CAVEAT,
        "days": days,
        "since_date": since_date,
        "count": len(near_misses),
        "near_misses": near_misses,
    }
