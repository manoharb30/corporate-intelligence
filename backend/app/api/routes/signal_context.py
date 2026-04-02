"""Signal context endpoint — pulls surrounding graph context for a signal."""

from fastapi import APIRouter, Query

from app.services.signal_context_service import SignalContextService

router = APIRouter()


@router.get("/{cik}")
async def get_signal_context(
    cik: str,
    signal_date: str = Query(..., description="Signal date YYYY-MM-DD"),
    direction: str = Query("buy", description="buy or sell"),
    insider_names: str = Query("", description="Semicolon-separated insider names"),
):
    """Get surrounding context for a signal from the graph."""
    names = [n.strip() for n in insider_names.split(";") if n.strip()] if insider_names else []
    return await SignalContextService.get_context(
        cik=cik,
        signal_date=signal_date,
        insider_names=names,
        direction=direction,
    )
