"""Snapshot endpoints — live signal scorecards (15-min in-memory cache)."""

from fastapi import APIRouter, Query

from app.services.snapshot_service import SnapshotService

router = APIRouter()


@router.get("/weekly")
async def get_weekly_snapshot(
    days: int = Query(default=30, ge=1, le=90),
    date: str = Query(default=None, description="Filter to signals on this date (YYYY-MM-DD)"),
):
    """Signal scorecard, computed live with a 15-min in-memory cache."""
    return await SnapshotService.get_weekly_snapshot(days=days, date=date)
