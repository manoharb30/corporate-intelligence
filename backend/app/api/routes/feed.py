"""API endpoints for the signal feed."""

from fastapi import APIRouter, Query, BackgroundTasks

from app.services.feed_service import FeedService, MarketScanResult

router = APIRouter()

# Module-level scan state (single-user app, no need for Redis)
_market_scan_state = MarketScanResult()


@router.get("/stats")
async def get_db_stats():
    """
    Get database statistics (node counts, relationship counts).

    Example:
        GET /feed/stats
    """
    return await FeedService.get_db_stats()


@router.get("")
async def get_feed(
    days: int = Query(7, ge=1, le=90, description="Look back this many days"),
    limit: int = Query(50, ge=1, le=200, description="Maximum signals to return"),
    min_level: str = Query("low", description="Minimum signal level: low, medium, high"),
):
    """
    Get the signal feed.

    Returns signals ranked by importance:
    - CRITICAL: HIGH signal + insider buying
    - HIGH: Material agreements with governance/exec changes
    - HIGH_BEARISH: HIGH signal + insider selling
    - MEDIUM: Material agreements alone, multiple exec changes
    - LOW: Single executive or governance changes

    Example:
        GET /feed
        GET /feed?days=30&min_level=medium
    """
    signals = await FeedService.get_feed(
        days=days,
        limit=limit,
        min_level=min_level,
    )

    # Group by level for summary (base level)
    by_level = {"high": 0, "medium": 0, "low": 0}
    by_combined = {"critical": 0, "high_bearish": 0, "high": 0, "medium": 0, "low": 0}
    for s in signals:
        by_level[s.signal_level] = by_level.get(s.signal_level, 0) + 1
        combined = s.combined_signal_level or s.signal_level
        by_combined[combined] = by_combined.get(combined, 0) + 1

    return {
        "total": len(signals),
        "by_level": by_level,
        "by_combined": by_combined,
        "signals": [s.to_dict() for s in signals],
    }


@router.get("/summary")
async def get_feed_summary():
    """
    Get summary statistics for the feed.

    Example:
        GET /feed/summary
    """
    return await FeedService.get_feed_summary()


@router.post("/scan/{cik}")
async def scan_company(
    cik: str,
    company_name: str = Query(..., description="Company name"),
    limit: int = Query(20, ge=1, le=50, description="Number of 8-K filings to scan"),
):
    """
    Scan a company's 8-K filings and store the events.

    Example:
        POST /feed/scan/0000320193?company_name=Apple%20Inc.
    """
    result = await FeedService.scan_and_store_company(
        cik=cik,
        company_name=company_name,
        limit=limit,
    )
    return result


@router.post("/market-scan")
async def market_scan(
    background_tasks: BackgroundTasks,
    days_back: int = Query(3, ge=1, le=30, description="Days back to scan (1-30)"),
):
    """
    Scan the entire market for recent 8-K filings.

    Discovers all companies that filed 8-Ks recently via SEC EFTS,
    then scans each using the existing pipeline. Runs in background.

    Example:
        POST /feed/market-scan?days_back=3
    """
    global _market_scan_state

    if _market_scan_state.status == "in_progress":
        return {
            "status": "already_running",
            "message": f"Scan in progress: {_market_scan_state.companies_scanned}/{_market_scan_state.companies_discovered} companies",
        }

    # Reset state
    _market_scan_state = MarketScanResult(status="in_progress", message="Starting market scan...")

    background_tasks.add_task(FeedService.market_scan, days_back, _market_scan_state)

    return {
        "status": "started",
        "message": f"Market scan started for last {days_back} days",
    }


@router.get("/market-scan/status")
async def market_scan_status():
    """
    Get the current market scan status.

    Example:
        GET /feed/market-scan/status
    """
    return _market_scan_state.to_dict()


@router.post("/scan-batch")
async def scan_batch(
    background_tasks: BackgroundTasks,
    filings_per_company: int = Query(10, ge=1, le=30, description="8-K filings to scan per company"),
    limit_companies: int = Query(50, ge=1, le=500, description="Maximum companies to scan"),
):
    """
    Scan multiple companies from the database and store their events.

    This scans companies that have CIKs stored in the database.
    Runs in background for large batches.

    Example:
        POST /feed/scan-batch?filings_per_company=10&limit_companies=100
    """
    from app.db.neo4j_client import Neo4jClient

    # Get companies with CIKs
    query = """
        MATCH (c:Company)
        WHERE c.cik IS NOT NULL AND c.cik <> ''
        RETURN c.cik as cik, c.name as name
        LIMIT $limit
    """

    results = await Neo4jClient.execute_query(query, {"limit": limit_companies})
    companies = [{"cik": r["cik"], "name": r["name"]} for r in results]

    if len(companies) > 20:
        # Run in background for large batches
        background_tasks.add_task(
            FeedService.scan_multiple_companies,
            companies,
            filings_per_company,
        )
        return {
            "status": "started",
            "message": f"Scanning {len(companies)} companies in background",
            "companies_queued": len(companies),
        }
    else:
        # Run synchronously for small batches
        result = await FeedService.scan_multiple_companies(
            companies,
            filings_per_company,
        )
        return {
            "status": "completed",
            **result,
        }


@router.get("/high-signals")
async def get_high_signals(
    days: int = Query(30, ge=1, le=90, description="Look back this many days"),
    limit: int = Query(20, ge=1, le=100, description="Maximum signals to return"),
):
    """
    Get only HIGH level signals.

    These are the most important signals indicating potential M&A activity:
    - Material Agreement + Governance/Executive changes
    - Acquisitions or Dispositions
    - Control Changes

    Example:
        GET /feed/high-signals
        GET /feed/high-signals?days=60
    """
    signals = await FeedService.get_feed(
        days=days,
        limit=limit,
        min_level="high",
    )

    # Filter to only high
    high_signals = [s for s in signals if s.signal_level == "high"]

    return {
        "total": len(high_signals),
        "signals": [s.to_dict() for s in high_signals],
    }
