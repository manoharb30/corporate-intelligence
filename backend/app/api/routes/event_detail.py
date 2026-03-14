"""API endpoints for event detail with LLM analysis and party linking."""

import logging

from fastapi import APIRouter, HTTPException

from app.services.accuracy_service import AccuracyService
from app.services.compound_signal_service import CompoundSignalService
from app.services.event_detail_service import EventDetailService
from app.services.insider_cluster_service import InsiderClusterService
from app.services.party_linker_service import PartyLinkerService

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/link-parties")
async def link_all_parties():
    """
    Scan all LLM-analyzed events and link extracted parties to Company nodes.
    Creates DEAL_WITH relationships between companies.

    Example:
        POST /api/event-detail/link-parties
    """
    result = await PartyLinkerService.link_all_analyzed_events()
    return result


@router.get("/deals/{cik}")
async def get_company_deals(cik: str):
    """
    Get all deal connections for a company.

    Example:
        GET /api/event-detail/deals/0000718877
    """
    deals = await PartyLinkerService.get_company_deals(cik)
    return {"cik": cik, "total": len(deals), "deals": deals}


@router.get("/{accession_number}")
async def get_event_detail(accession_number: str):
    """
    Get detailed event information with LLM analysis and company timeline.

    Returns the event, LLM analysis (cached or freshly generated),
    and an interleaved timeline of events + insider trades.

    For 8-K signals, if LLM analysis is not cached, the analysis field
    will contain a placeholder. Use the /analysis endpoint to fetch it.

    Example:
        GET /api/event-detail/0001193125-23-237963
    """
    # Fetch confidence stats (cached 4h) for decision card badges
    # Use cached value only — don't block page load on cold computation
    try:
        confidence_stats = AccuracyService.get_confidence_stats_cached()
    except Exception as e:
        logger.warning(f"Failed to fetch confidence stats: {e}")
        confidence_stats = None

    if accession_number.startswith("COMPOUND-"):
        result = await CompoundSignalService.get_compound_detail(accession_number, confidence_stats=confidence_stats)
    elif accession_number.startswith("CLUSTER-") or accession_number.startswith("SELL-CLUSTER-"):
        result = await InsiderClusterService.get_cluster_detail(accession_number, confidence_stats=confidence_stats)
    else:
        result = await EventDetailService.get_event_detail(accession_number, confidence_stats=confidence_stats, skip_llm=True)

    if not result:
        raise HTTPException(status_code=404, detail="Event not found")

    return result


@router.get("/{accession_number}/analysis")
async def get_event_analysis(accession_number: str):
    """
    Get LLM analysis for an 8-K filing. Called separately so the main
    event detail page can load instantly while this runs in background.

    Example:
        GET /api/event-detail/0001193125-23-237963/analysis
    """
    result = await EventDetailService.get_analysis_only(accession_number)
    if not result:
        raise HTTPException(status_code=404, detail="Event not found")
    return result
