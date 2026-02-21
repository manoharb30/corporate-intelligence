"""Scanner health and trigger API routes."""

import asyncio
import logging

from fastapi import APIRouter, BackgroundTasks

from app.db.neo4j_client import Neo4jClient

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/health")
async def scanner_health():
    """Get scanner state: last run timestamp, status, counts."""
    query = """
        MATCH (s:ScannerState {scanner_id: 'form4_scanner'})
        RETURN s.last_run_at as last_run_at,
               s.last_status as last_status,
               s.companies_scanned as companies_scanned,
               s.transactions_stored as transactions_stored,
               s.alerts_created as alerts_created,
               s.total_runs as total_runs,
               s.last_error as last_error
    """
    results = await Neo4jClient.execute_query(query)

    if not results:
        return {
            "status": "never_run",
            "last_run_at": None,
            "companies_scanned": 0,
            "transactions_stored": 0,
            "alerts_created": 0,
            "total_runs": 0,
            "last_error": None,
        }

    r = results[0]
    return {
        "status": r.get("last_status") or "unknown",
        "last_run_at": r.get("last_run_at"),
        "companies_scanned": r.get("companies_scanned") or 0,
        "transactions_stored": r.get("transactions_stored") or 0,
        "alerts_created": r.get("alerts_created") or 0,
        "total_runs": r.get("total_runs") or 0,
        "last_error": r.get("last_error"),
    }


async def _run_scanner():
    """Run the scanner in-process (for manual trigger)."""
    try:
        from scanner.form4_scanner import run_scanner
        await run_scanner()
    except Exception as e:
        logger.error(f"Manual scanner trigger failed: {e}")


@router.post("/trigger")
async def trigger_scanner(background_tasks: BackgroundTasks):
    """Manually trigger a scanner run via BackgroundTasks."""
    background_tasks.add_task(_run_scanner)
    return {"status": "triggered", "message": "Scanner run started in background"}
