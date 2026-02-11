"""Company-related API endpoints."""

from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from app.models import (
    Company,
    CompanyCreate,
    CompanyUpdate,
    PaginatedResponse,
    OwnershipChain,
    CompanySearchResponse,
    CompanyIntelligenceResponse,
)
from app.services.company_service import CompanyService

router = APIRouter()


@router.get("", response_model=PaginatedResponse[Company])
async def list_companies(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    jurisdiction: Optional[str] = None,
    status: Optional[str] = None,
) -> PaginatedResponse[Company]:
    """List companies with optional filtering."""
    return await CompanyService.list_companies(
        page=page,
        page_size=page_size,
        jurisdiction=jurisdiction,
        status=status,
    )


@router.get("/search", response_model=CompanySearchResponse)
async def search_companies(
    q: str = Query(..., min_length=2, description="Company name or ticker to search"),
    limit: int = Query(20, ge=1, le=50),
) -> CompanySearchResponse:
    """
    Search companies by name or ticker.

    Searches both our graph database and SEC EDGAR.
    Results indicate whether each company is already in our graph (in_graph=True)
    or needs to be ingested (in_graph=False).

    Graph results appear first, followed by SEC EDGAR results.
    """
    return await CompanyService.search_combined(q, limit)


@router.get("/{company_id}/intelligence", response_model=CompanyIntelligenceResponse)
async def get_company_intelligence(company_id: str) -> CompanyIntelligenceResponse:
    """
    Get full intelligence about a company.

    Returns:
    - Officers and directors with their titles
    - Beneficial owners with ownership percentages
    - Subsidiaries
    - Parent company (if any)
    - Red flags (sanctions matches, conflicts of interest, PEPs)
    - Data freshness metadata

    This is the main endpoint to call after a user selects a company from search.
    """
    intelligence = await CompanyService.get_intelligence(company_id)
    if not intelligence:
        raise HTTPException(status_code=404, detail="Company not found")
    return intelligence


@router.get("/{company_id}", response_model=Company)
async def get_company(company_id: str) -> Company:
    """Get a company by ID."""
    company = await CompanyService.get_by_id(company_id)
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")
    return company


@router.get("/{company_id}/ownership-chain", response_model=list[OwnershipChain])
async def get_ownership_chain(
    company_id: str,
    max_depth: int = Query(10, ge=1, le=20),
) -> list[OwnershipChain]:
    """Get beneficial ownership chains for a company."""
    return await CompanyService.get_ownership_chains(company_id, max_depth)


@router.get("/{company_id}/subsidiaries", response_model=list[Company])
async def get_subsidiaries(
    company_id: str,
    max_depth: int = Query(5, ge=1, le=10),
) -> list[Company]:
    """Get subsidiaries of a company."""
    return await CompanyService.get_subsidiaries(company_id, max_depth)


@router.post("", response_model=Company, status_code=201)
async def create_company(company: CompanyCreate) -> Company:
    """Create a new company."""
    return await CompanyService.create(company)


@router.patch("/{company_id}", response_model=Company)
async def update_company(company_id: str, company: CompanyUpdate) -> Company:
    """Update a company."""
    updated = await CompanyService.update(company_id, company)
    if not updated:
        raise HTTPException(status_code=404, detail="Company not found")
    return updated


@router.delete("/{company_id}", status_code=204)
async def delete_company(company_id: str) -> None:
    """Delete a company."""
    deleted = await CompanyService.delete(company_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Company not found")
