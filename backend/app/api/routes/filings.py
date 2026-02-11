"""Filing-related API endpoints."""

from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from app.models import Filing, FilingCreate, PaginatedResponse
from app.services.filing_service import FilingService

router = APIRouter()


@router.get("", response_model=PaginatedResponse[Filing])
async def list_filings(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    form_type: Optional[str] = None,
) -> PaginatedResponse[Filing]:
    """List filings with optional filtering."""
    return await FilingService.list_filings(
        page=page,
        page_size=page_size,
        form_type=form_type,
    )


@router.get("/form-types")
async def list_form_types() -> list[dict[str, int]]:
    """List available form types with counts."""
    return await FilingService.get_form_type_counts()


@router.get("/{filing_id}", response_model=Filing)
async def get_filing(filing_id: str) -> Filing:
    """Get a filing by ID."""
    filing = await FilingService.get_by_id(filing_id)
    if not filing:
        raise HTTPException(status_code=404, detail="Filing not found")
    return filing


@router.get("/accession/{accession_number}", response_model=Filing)
async def get_filing_by_accession(accession_number: str) -> Filing:
    """Get a filing by SEC accession number."""
    filing = await FilingService.get_by_accession_number(accession_number)
    if not filing:
        raise HTTPException(status_code=404, detail="Filing not found")
    return filing


@router.get("/{filing_id}/entities")
async def get_filing_entities(filing_id: str) -> dict:
    """Get all entities mentioned in a filing."""
    return await FilingService.get_mentioned_entities(filing_id)


@router.post("", response_model=Filing, status_code=201)
async def create_filing(filing: FilingCreate) -> Filing:
    """Create a new filing record."""
    return await FilingService.create(filing)


@router.delete("/{filing_id}", status_code=204)
async def delete_filing(filing_id: str) -> None:
    """Delete a filing."""
    deleted = await FilingService.delete(filing_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Filing not found")
