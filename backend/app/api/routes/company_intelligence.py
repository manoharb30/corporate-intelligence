"""Company intelligence endpoint — comprehensive company view."""

from fastapi import APIRouter, HTTPException

from app.services.company_intelligence_service import CompanyIntelligenceService

router = APIRouter()


@router.get("/{cik}")
async def get_company_intelligence(cik: str):
    """Get everything we know about a company from the graph."""
    result = await CompanyIntelligenceService.get_intelligence(cik)
    if not result:
        raise HTTPException(status_code=404, detail="Company not found")
    return result
