"""API endpoints for 8-K events and M&A signals."""

from fastapi import APIRouter, Query

from app.services.event_service import EventService

router = APIRouter()


@router.get("/scan/{cik}")
async def scan_company_events(
    cik: str,
    company_name: str = Query(..., description="Company name"),
    limit: int = Query(20, ge=1, le=50, description="Number of filings to scan"),
):
    """
    Scan a company's 8-K filings for events.

    Returns all events found in recent 8-K filings.

    Example:
        GET /events/scan/0000320193?company_name=Apple%20Inc.
    """
    service = EventService()
    try:
        results = await service.scan_company_events(cik, company_name, limit)
        return {
            "cik": cik,
            "company_name": company_name,
            "filings_scanned": len(results),
            "results": [r.to_dict() for r in results],
        }
    finally:
        await service.close()


@router.get("/signals/{cik}")
async def get_ma_signals(
    cik: str,
    company_name: str = Query(..., description="Company name"),
    limit: int = Query(20, ge=1, le=50, description="Number of filings to scan"),
):
    """
    Get M&A signals from a company's 8-K filings.

    Returns only events that are potential M&A indicators:
    - Item 5.02: Executive changes
    - Item 2.01: Acquisitions/dispositions
    - Item 1.01: Material agreements
    - Item 5.01: Control changes
    - Item 5.03: Governance changes

    Example:
        GET /events/signals/0001124610?company_name=VMware
    """
    service = EventService()
    try:
        signals = await service.get_ma_signals(cik, company_name, limit)
        return {
            "cik": cik,
            "company_name": company_name,
            "signal_count": len(signals),
            "signals": [
                {
                    "filing_date": s.filing_date,
                    "signal_type": s.signal_type,
                    "item_number": s.item_number,
                    "description": s.description,
                    "persons_involved": s.persons_involved,
                    "accession_number": s.accession_number,
                }
                for s in signals
            ],
        }
    finally:
        await service.close()


@router.post("/ingest/{cik}")
async def ingest_company_events(
    cik: str,
    company_name: str = Query(..., description="Company name"),
    limit: int = Query(20, ge=1, le=50, description="Number of filings to scan"),
):
    """
    Scan and store a company's 8-K events in the database.

    Example:
        POST /events/ingest/0000320193?company_name=Apple%20Inc.
    """
    service = EventService()
    try:
        results = await service.scan_company_events(cik, company_name, limit)
        count = await service.store_events(results)

        ma_signal_count = sum(1 for r in results for e in r.events if e.is_ma_signal)

        return {
            "cik": cik,
            "company_name": company_name,
            "filings_scanned": len(results),
            "events_stored": count,
            "ma_signals_found": ma_signal_count,
        }
    finally:
        await service.close()


@router.get("/recent-signals")
async def get_recent_signals(
    limit: int = Query(50, ge=1, le=200, description="Maximum signals to return"),
):
    """
    Get recent M&A signals from all stored events.

    Returns signals sorted by filing date (most recent first).

    Example:
        GET /events/recent-signals
    """
    signals = await EventService.get_recent_ma_signals(limit)
    return {
        "total": len(signals),
        "signals": signals,
    }


@router.get("/company/{cik}")
async def get_company_stored_events(
    cik: str,
    limit: int = Query(20, ge=1, le=100, description="Maximum events to return"),
):
    """
    Get stored events for a specific company.

    Example:
        GET /events/company/0000320193
    """
    events = await EventService.get_company_events(cik, limit)
    return {
        "cik": cik,
        "total": len(events),
        "events": events,
    }
