"""Weekly snapshot endpoint — live scorecard for recent signals."""

from fastapi import APIRouter, Query

from app.services.snapshot_service import SnapshotService
from app.services.snapshot_page_service import SnapshotPageService

router = APIRouter()


@router.get("/weekly")
async def get_weekly_snapshot(
    days: int = Query(default=14, ge=1, le=30),
):
    """Live scorecard: how recent signals are performing right now."""
    return await SnapshotService.get_weekly_snapshot(days=days)


@router.get("/week")
async def get_week_snapshot(
    start: str = Query(default="2026-03-03"),
    end: str = Query(default="2026-03-07"),
):
    """Manual weekly snapshot for a specific date range."""
    return await SnapshotPageService.get_week_snapshot(
        start_date=start, end_date=end
    )
