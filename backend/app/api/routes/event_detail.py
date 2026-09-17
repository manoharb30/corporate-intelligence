"""API endpoint for insider cluster signal detail."""

from fastapi import APIRouter, HTTPException

from app.services.insider_cluster_service import InsiderClusterService
from app.services.research_note_service import ResearchNoteService

router = APIRouter()


@router.get("/{accession_number}")
async def get_event_detail(accession_number: str):
    """Get detailed signal information with buyer proof and SEC EDGAR links.

    Only handles CLUSTER- and SELL-CLUSTER- accession numbers.

    Example:
        GET /api/event-detail/CLUSTER-0002035989-2026-03-13
    """
    if not (accession_number.startswith("CLUSTER-") or accession_number.startswith("SELL-CLUSTER-")):
        raise HTTPException(status_code=404, detail="Signal not found")

    result = await InsiderClusterService.get_cluster_detail(accession_number)

    if not result:
        raise HTTPException(status_code=404, detail="Signal not found")

    # Research notes are anchored on Company, so a name reviewed BEFORE it ever
    # signalled carries its note through to here. Composed at the API layer
    # rather than inside get_cluster_detail: that keeps the service's Neo4j
    # surface to a single client, which its unit tests patch by module.
    cik = (result.get("company") or {}).get("cik")
    result["research_notes"] = await ResearchNoteService.get_notes(cik) if cik else []

    return result
