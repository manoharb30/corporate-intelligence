"""API endpoints for company profiles."""

from fastapi import APIRouter, HTTPException, Query

from app.services.company_profile_service import CompanyProfileService

router = APIRouter()


@router.get("/{cik}")
async def get_company_profile(cik: str):
    """
    Get complete company profile.

    Returns:
    - Basic info (name, ticker, industry)
    - Counts (subsidiaries, officers, directors, connections)
    - Signal timeline
    - Board connections to other companies
    - Officers and Directors
    - Subsidiaries

    Example:
        GET /profile/0000320193  (Apple)
        GET /profile/0001045810  (NVIDIA)
    """
    profile = await CompanyProfileService.get_profile(cik)

    if not profile:
        raise HTTPException(status_code=404, detail=f"Company not found: {cik}")

    return profile.to_dict()


@router.get("/search/companies")
async def search_companies(
    q: str = Query(..., min_length=1, description="Search query"),
    limit: int = Query(20, ge=1, le=100, description="Maximum results"),
):
    """
    Search for companies by name or ticker.

    Example:
        GET /profile/search/companies?q=Apple
        GET /profile/search/companies?q=NVDA
    """
    results = await CompanyProfileService.search_companies(q, limit)

    return {
        "query": q,
        "total": len(results),
        "results": results,
    }


@router.get("/{cik}/signals")
async def get_company_signals(
    cik: str,
    limit: int = Query(50, ge=1, le=200, description="Maximum signals"),
):
    """
    Get signal timeline for a company.

    Example:
        GET /profile/0001124610/signals  (VMware)
    """
    signals = await CompanyProfileService._get_signals(cik, limit)

    return {
        "cik": cik,
        "total": len(signals),
        "signals": signals,
    }


@router.get("/{cik}/connections")
async def get_company_connections(cik: str):
    """
    Get board connections to other companies.

    Shows which directors sit on multiple boards,
    creating connections between companies.

    Example:
        GET /profile/0000320193/connections  (Apple)
    """
    result = await CompanyProfileService._get_connections(cik)

    return {
        "cik": cik,
        "total_connections": result["count"],
        "connections": result["connections"],
    }


@router.get("/{cik}/people")
async def get_company_people(cik: str):
    """
    Get officers and directors of a company.

    Example:
        GET /profile/0000320193/people  (Apple)
    """
    officers = await CompanyProfileService._get_officers(cik, limit=20)
    directors = await CompanyProfileService._get_directors(cik, limit=20)

    return {
        "cik": cik,
        "officers": officers,
        "directors": directors,
    }


@router.get("/{cik}/subsidiaries")
async def get_company_subsidiaries(
    cik: str,
    limit: int = Query(50, ge=1, le=500, description="Maximum subsidiaries"),
):
    """
    Get subsidiaries of a company.

    Example:
        GET /profile/0000731766/subsidiaries  (UnitedHealth - has 1500+)
    """
    from app.db.neo4j_client import Neo4jClient

    # Get count first
    count_query = """
        MATCH (c:Company {cik: $cik})-[:OWNS]->(sub:Company)
        RETURN count(sub) as total
    """
    count_result = await Neo4jClient.execute_query(count_query, {"cik": cik})
    total = count_result[0]["total"] if count_result else 0

    # Get subsidiaries
    subsidiaries = await CompanyProfileService._get_subsidiaries(cik, limit)

    return {
        "cik": cik,
        "total": total,
        "showing": len(subsidiaries),
        "subsidiaries": subsidiaries,
    }
