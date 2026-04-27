"""Scanner health API routes.

Trigger endpoints removed 2026-04-24 — the only supported ingest path is now
the classified pipeline (run_week.py -> ingest_genuine_p_to_neo4j.py). Direct
scanner triggers bypassed classification and polluted the DB with
NULL-classification rows.
"""

import logging

from fastapi import APIRouter

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
