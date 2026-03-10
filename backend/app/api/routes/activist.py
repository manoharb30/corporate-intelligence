"""API routes for Schedule 13D activist filings."""

import logging
from typing import Optional

from fastapi import APIRouter, Query

from app.services.activist_filing_service import ActivistFilingService

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("")
async def list_activist_filings(
    days: int = Query(90, ge=1, le=365, description="Look back N days"),
    signal_level: Optional[str] = Query(None, description="Filter by HIGH, MEDIUM, or LOW"),
    limit: int = Query(50, ge=1, le=200, description="Max results"),
):
    """List recent 13D activist filings."""
    filings = await ActivistFilingService.get_filings(
        days=days,
        signal_level=signal_level.upper() if signal_level else None,
        limit=limit,
    )
    return {"filings": [dict(f) for f in filings], "count": len(filings)}


@router.get("/stats")
async def activist_stats():
    """Get summary stats for activist filings."""
    total = await ActivistFilingService.get_filing_count()
    return {"total_filings": total}


@router.get("/company/{cik}")
async def filings_by_company(
    cik: str,
    days: int = Query(365, ge=1, le=1825, description="Look back N days"),
    limit: int = Query(50, ge=1, le=200),
):
    """Get 13D filings targeting a specific company."""
    filings = await ActivistFilingService.get_filings(
        target_cik=cik,
        days=days,
        limit=limit,
    )
    return {"filings": [dict(f) for f in filings], "count": len(filings)}


@router.get("/filing/{accession_number:path}")
async def filing_detail(accession_number: str):
    """Get full details for a single activist filing."""
    detail = await ActivistFilingService.get_filing_detail(accession_number)
    if not detail:
        return {"error": "Filing not found"}, 404
    return detail
