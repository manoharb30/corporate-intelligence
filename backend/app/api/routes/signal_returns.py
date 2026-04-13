"""API routes for the signal performance page.

Returns live signal data with returns computed from stored daily prices.
No yfinance calls — reads from Neo4j only.
"""

from typing import Optional

from fastapi import APIRouter, Query

from app.services.signal_return_service import SignalReturnService

router = APIRouter()


@router.get("")
async def get_signal_returns(
    direction: Optional[str] = Query(default=None, pattern="^(buy|sell)$"),
    month: Optional[int] = Query(default=None, ge=1, le=12),
    year: Optional[int] = Query(default=None, ge=2020, le=2030),
    limit: int = Query(default=2000, ge=1, le=5000),
):
    """Return all signals with computed returns from signal_date to today.

    Filters:
        - direction: "buy" or "sell"
        - month + year: filter to specific month
        - year alone: filter to specific year
        - limit: max signals returned
    """
    signals = await SignalReturnService.get_signal_returns(
        direction=direction,
        month=month,
        year=year,
        limit=limit,
    )
    return {"signals": signals, "count": len(signals)}


@router.get("/summary")
async def get_summary(
    direction: Optional[str] = Query(default=None, pattern="^(buy|sell)$"),
    month: Optional[int] = Query(default=None, ge=1, le=12),
    year: Optional[int] = Query(default=None, ge=2020, le=2030),
):
    """Return 4 stat cards for the performance page header."""
    summary = await SignalReturnService.get_summary(
        direction=direction, month=month, year=year
    )
    return summary
