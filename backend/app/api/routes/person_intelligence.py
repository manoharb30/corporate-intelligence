"""Person intelligence endpoint — cross-company insider activity."""

from fastapi import APIRouter, HTTPException

from app.services.person_intelligence_service import PersonIntelligenceService

router = APIRouter()


@router.get("/{person_name:path}")
async def get_person_intelligence(person_name: str):
    """Get all trading activity for a person across all companies."""
    result = await PersonIntelligenceService.get_intelligence(person_name)
    if not result:
        raise HTTPException(status_code=404, detail="Person not found")
    return result
