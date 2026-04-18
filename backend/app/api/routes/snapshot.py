"""Snapshot endpoints — precomputed signal scorecards."""

from fastapi import APIRouter, Query

from app.services.snapshot_service import SnapshotService

router = APIRouter()


@router.get("/weekly")
async def get_weekly_snapshot(
    days: int = Query(default=30, ge=1, le=90),
    date: str = Query(default=None, description="Filter to signals on this date (YYYY-MM-DD)"),
):
    """Signal scorecard. Uses precomputed blob for 30d/60d/90d, live computation for date filter."""
    return await SnapshotService.get_weekly_snapshot(days=days, date=date)


@router.post("/precompute")
async def precompute_snapshots():
    """Precompute and save snapshot blobs for 30d, 60d, 90d.

    Call after scan + signal performance compute.
    Dashboard then loads instantly from stored blobs.
    """
    return await SnapshotService.precompute_and_save()
