"""API endpoints for event detail with LLM analysis and party linking."""

from fastapi import APIRouter, HTTPException

from app.services.event_detail_service import EventDetailService
from app.services.party_linker_service import PartyLinkerService

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

    Example:
        GET /api/event-detail/0001193125-23-237963
    """
    result = await EventDetailService.get_event_detail(accession_number)

    if not result:
        raise HTTPException(status_code=404, detail="Event not found")

    return result
