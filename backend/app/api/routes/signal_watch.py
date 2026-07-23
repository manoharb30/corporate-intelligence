"""API endpoint for Signal Watch — promise-vs-delivery record of an open signal."""

from fastapi import APIRouter, HTTPException, Query

from app.services.signal_watch_service import SignalWatchService, watch_summary

router = APIRouter()


@router.get("/{ticker}")
async def get_signal_watch(ticker: str, signal_date: str = Query(...)):
    """Watch record for one signal: management promises with verdicts,
    plus the day-indexed event trail for the 90-day window.

    Example:
        GET /api/signal-watch/SMBK?signal_date=2026-06-10
    """
    watch = await SignalWatchService.get_watch(ticker.upper(), signal_date)
    if not watch["promises"] and not watch["events"]:
        raise HTTPException(status_code=404, detail="No watch data for this signal")
    return {**watch, "summary": watch_summary(watch["promises"])}
