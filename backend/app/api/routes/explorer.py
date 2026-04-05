"""Graph explorer endpoints — interactive graph visualization data."""

from fastapi import APIRouter, Query, HTTPException

from app.services.explorer_service import ExplorerService

router = APIRouter()


@router.get("/search")
async def search(
    q: str = Query(..., min_length=2, description="Search query"),
    mode: str = Query("company", description="company or person"),
):
    """Autocomplete search for companies or persons."""
    return await ExplorerService.search(q, mode)


@router.get("/graph")
async def get_graph(
    q: str = Query(..., description="Ticker, company name, or person name"),
    mode: str = Query("company", description="company or person"),
):
    """Get graph data (nodes + edges) for a company or person."""
    if mode == "company":
        result = await ExplorerService.get_company_graph(q)
    elif mode == "person":
        result = await ExplorerService.get_person_graph(q)
    else:
        raise HTTPException(status_code=400, detail="mode must be 'company' or 'person'")

    if not result:
        raise HTTPException(status_code=404, detail="Not found")
    return result


@router.get("/expand/person/{person_name:path}")
async def expand_person(person_name: str):
    """Get graph data for a person's connections — for expanding an existing graph."""
    result = await ExplorerService.get_person_graph(person_name)
    if not result:
        raise HTTPException(status_code=404, detail="Person not found")
    return result


@router.get("/expand/company/{ticker}")
async def expand_company(ticker: str):
    """Get graph data for a company — for expanding an existing graph."""
    result = await ExplorerService.get_company_graph(ticker)
    if not result:
        raise HTTPException(status_code=404, detail="Company not found")
    return result
