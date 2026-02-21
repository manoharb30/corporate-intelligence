"""Accuracy API routes — signal accuracy tracking and reporting."""

from fastapi import APIRouter, Query

from app.services.accuracy_service import AccuracyService

router = APIRouter()


@router.get("/top-hits")
async def get_top_hits(
    limit: int = Query(3, ge=1, le=10),
):
    """Top proof-wall hits sorted by marketing impact score."""
    return await AccuracyService.get_top_hits(limit=limit)


@router.get("")
async def get_accuracy(
    lookback_days: int = Query(365, ge=30, le=730),
    min_signal_age: int = Query(30, ge=0, le=365),
    min_level: str = Query("medium"),
):
    """Full accuracy report: summary + individual signal outcomes."""
    return await AccuracyService.get_accuracy(
        lookback_days=lookback_days,
        min_signal_age_days=min_signal_age,
        min_level=min_level,
    )


@router.get("/summary")
async def get_accuracy_summary(
    lookback_days: int = Query(365, ge=30, le=730),
    min_signal_age: int = Query(30, ge=0, le=365),
    min_level: str = Query("medium"),
):
    """Aggregate accuracy stats only (no individual signals)."""
    return await AccuracyService.get_accuracy_summary(
        lookback_days=lookback_days,
        min_signal_age_days=min_signal_age,
        min_level=min_level,
    )
