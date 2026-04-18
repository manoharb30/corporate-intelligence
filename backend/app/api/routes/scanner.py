"""Scanner health and trigger API routes."""

import asyncio
import logging

from fastapi import APIRouter, BackgroundTasks

from app.db.neo4j_client import Neo4jClient

router = APIRouter()
logger = logging.getLogger(__name__)


async def _get_scanner_state(scanner_id: str, fields: list[str]) -> dict:
    """Fetch ScannerState node for a given scanner."""
    returns = ", ".join(f"s.{f} as {f}" for f in fields)
    query = f"""
        MATCH (s:ScannerState {{scanner_id: $scanner_id}})
        RETURN {returns}
    """
    results = await Neo4jClient.execute_query(query, {"scanner_id": scanner_id})
    if not results:
        return None
    return dict(results[0])


@router.get("/health")
async def scanner_health():
    """Get health status for all scanners."""
    # Form 4 scanner
    form4 = await _get_scanner_state("form4_scanner", [
        "last_run_at", "last_status", "companies_scanned",
        "transactions_stored", "alerts_created", "total_runs", "last_error",
    ])
    if not form4:
        form4 = {
            "last_run_at": None, "last_status": "never_run",
            "companies_scanned": 0, "transactions_stored": 0,
            "alerts_created": 0, "total_runs": 0, "last_error": None,
        }

    # Activist scanner
    activist = await _get_scanner_state("activist_scanner", [
        "last_run_at", "last_status", "filings_discovered",
        "filings_stored", "filings_skipped", "alerts_created",
        "total_runs", "last_error",
    ])
    if not activist:
        activist = {
            "last_run_at": None, "last_status": "never_run",
            "filings_discovered": 0, "filings_stored": 0,
            "filings_skipped": 0, "alerts_created": 0,
            "total_runs": 0, "last_error": None,
        }

    # 8-K scanner
    eightk = await _get_scanner_state("8k_scanner", [
        "last_run_at", "last_status", "companies_discovered",
        "companies_scanned", "events_stored",
        "total_runs", "last_error",
    ])
    if not eightk:
        eightk = {
            "last_run_at": None, "last_status": "never_run",
            "companies_discovered": 0, "companies_scanned": 0,
            "events_stored": 0, "total_runs": 0, "last_error": None,
        }

    return {
        "form4_scanner": form4,
        "activist_scanner": activist,
        "8k_scanner": eightk,
    }


async def _run_scanner():
    """Run the Form 4 scanner in-process."""
    try:
        from scanner.form4_scanner import run_scanner
        await run_scanner()
    except Exception as e:
        logger.error(f"Manual Form 4 scanner trigger failed: {e}")


async def _run_activist_scanner():
    """Run the activist scanner in-process."""
    try:
        from scanner.activist_scanner import run_scanner
        await run_scanner()
    except Exception as e:
        logger.error(f"Manual activist scanner trigger failed: {e}")


@router.post("/trigger")
async def trigger_scanner(background_tasks: BackgroundTasks):
    """Manually trigger the Form 4 scanner."""
    background_tasks.add_task(_run_scanner)
    return {"status": "triggered", "message": "Form 4 scanner started in background"}


@router.post("/trigger/activist")
async def trigger_activist_scanner(background_tasks: BackgroundTasks):
    """Manually trigger the activist scanner."""
    background_tasks.add_task(_run_activist_scanner)
    return {"status": "triggered", "message": "Activist scanner started in background"}


async def _run_8k_scanner():
    """Run the 8-K scanner in-process."""
    try:
        import importlib
        mod = importlib.import_module("scanner.8k_scanner")
        await mod.run_scanner()
    except Exception as e:
        logger.error(f"Manual 8-K scanner trigger failed: {e}")


@router.post("/trigger/8k")
async def trigger_8k_scanner(background_tasks: BackgroundTasks):
    """Manually trigger the 8-K scanner."""
    background_tasks.add_task(_run_8k_scanner)
    return {"status": "triggered", "message": "8-K scanner started in background"}
