"""Portfolio endpoints — Alpaca paper account trading our own signals.

Read-only: the page shows account state, positions with implementation
shortfall vs signal day-0, equity curve, and fill activity. Order execution
is operator-driven, never through the API.
"""

import httpx
from fastapi import APIRouter, HTTPException

from app.services.alpaca_portfolio_service import AlpacaPortfolioService

router = APIRouter()


@router.get("")
async def get_portfolio():
    """Full Portfolio page snapshot."""
    if not AlpacaPortfolioService.configured():
        return {"configured": False}
    try:
        return await AlpacaPortfolioService.get_snapshot()
    except httpx.HTTPError as e:
        raise HTTPException(status_code=502, detail=f"Alpaca API unreachable: {e}")
