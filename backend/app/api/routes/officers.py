"""API endpoints for officer/director data scanning."""

from fastapi import APIRouter, Query

from app.services.officer_scan_service import OfficerScanService

router = APIRouter()


@router.post("/scan/{cik}")
async def scan_officers(
    cik: str,
    company_name: str = Query(..., description="Company name"),
    limit: int = Query(2, ge=1, le=10, description="Number of DEF 14A filings to scan"),
):
    """
    Scan a company's DEF 14A filings and store officer/director data.

    Example:
        POST /officers/scan/0001862150?company_name=Cingulate+Inc.
    """
    result = await OfficerScanService.scan_and_store_company(
        cik=cik,
        company_name=company_name,
        limit=limit,
    )
    return result
