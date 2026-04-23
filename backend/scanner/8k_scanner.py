"""
Daily 8-K Event Scanner

Polls SEC EDGAR for new 8-K filings, parses events, and stores them
in Neo4j. Picks up M&A signal items: 1.01, 2.01, 3.03, 5.01, 5.02, 5.03.

Designed to run daily after market close, alongside the Form 4 and
activist scanners. Uses checkpoint to avoid reprocessing.

Usage:
    python -m scanner.8k_scanner
"""

import asyncio
import logging
import sys
from datetime import datetime, timedelta

from app.db.neo4j_client import Neo4jClient
from app.services.feed_service import FeedService
from ingestion.sec_edgar.edgar_client import SECEdgarClient

logger = logging.getLogger(__name__)

SCANNER_ID = "8k_scanner"
INTER_COMPANY_DELAY = 0.5  # seconds between companies


async def get_checkpoint() -> str:
    """Read the last successful scan date from Neo4j. Defaults to yesterday."""
    query = """
        MATCH (s:ScannerState {scanner_id: $scanner_id})
        RETURN s.last_checkpoint as checkpoint
    """
    results = await Neo4jClient.execute_query(query, {"scanner_id": SCANNER_ID})
    if results and results[0].get("checkpoint"):
        return results[0]["checkpoint"]
    return (datetime.utcnow() - timedelta(days=1)).strftime("%Y-%m-%d")


async def update_checkpoint(checkpoint: str, status: str, counts: dict):
    """Update the scanner checkpoint in Neo4j."""
    query = """
        MERGE (s:ScannerState {scanner_id: $scanner_id})
        SET s.last_checkpoint = $checkpoint,
            s.last_run_at = $now,
            s.last_status = $status,
            s.companies_discovered = $discovered,
            s.companies_scanned = $scanned,
            s.events_stored = $events,
            s.errors = $errors,
            s.last_error = $last_error,
            s.total_runs = COALESCE(s.total_runs, 0) + 1
    """
    await Neo4jClient.execute_query(query, {
        "scanner_id": SCANNER_ID,
        "checkpoint": checkpoint,
        "now": datetime.utcnow().isoformat(),
        "status": status,
        "discovered": counts.get("companies_discovered", 0),
        "scanned": counts.get("companies_scanned", 0),
        "events": counts.get("events_stored", 0),
        "errors": counts.get("errors", 0),
        "last_error": counts.get("last_error"),
    })


async def discover_8k_filers(since_date: str) -> list[dict]:
    """Discover companies that filed 8-Ks since the checkpoint date."""
    client = SECEdgarClient()
    today = datetime.utcnow().strftime("%Y-%m-%d")

    seen_ciks = {}
    from_idx = 0

    try:
        while True:
            params = {
                "forms": "8-K",
                "dateRange": "custom",
                "startdt": since_date,
                "enddt": today,
                "from": str(from_idx),
            }
            import httpx
            url = f"{client.FULL_TEXT_SEARCH_URL}?{httpx.QueryParams(params)}"
            response = await client._request(url)
            data = response.json()

            hits = data.get("hits", {}).get("hits", [])
            if not hits:
                break

            for hit in hits:
                source = hit.get("_source", {})
                ciks = source.get("ciks", [])
                names = source.get("display_names", [])
                for i, cik in enumerate(ciks):
                    if cik not in seen_ciks:
                        import re
                        raw = names[i] if i < len(names) else ""
                        name = re.sub(r"\s*\(CIK[^)]*\)", "", raw)
                        name = re.sub(r"\s*\([A-Z0-9,\s]+\)\s*$", "", name).strip()
                        seen_ciks[cik] = name or f"CIK {cik}"

            if len(hits) >= 100:
                from_idx += 100
            else:
                break
    finally:
        await client.close()

    return [{"cik": cik, "name": name} for cik, name in seen_ciks.items()]


async def filter_already_scanned(filers: list[dict], since_date: str) -> list[dict]:
    """Skip companies that already have events filed on/after the checkpoint date."""
    if not filers:
        return []

    ciks = [f["cik"] for f in filers]
    results = await Neo4jClient.execute_query(
        """
        UNWIND $ciks AS cik
        OPTIONAL MATCH (c:Company {cik: cik})-[:FILED_EVENT]->(e:Event)
        WHERE e.filing_date >= $date
        WITH cik, count(e) AS recent_count
        WHERE recent_count = 0
        RETURN cik
        """,
        {"ciks": ciks, "date": since_date},
    )
    new_ciks = {r["cik"] for r in results}
    filtered = [f for f in filers if f["cik"] in new_ciks]
    logger.info(
        f"Filtered {len(filers)} -> {len(filtered)} need scanning "
        f"({len(filers) - len(filtered)} already have events)"
    )
    return filtered


async def run_scanner() -> dict:
    """Orchestrate the full 8-K scanner flow."""
    await Neo4jClient.connect()

    counts = {
        "companies_discovered": 0,
        "companies_scanned": 0,
        "events_stored": 0,
        "errors": 0,
        "last_error": None,
    }

    checkpoint = await get_checkpoint()
    today = datetime.utcnow().strftime("%Y-%m-%d")
    logger.info(f"8-K Scanner starting — checkpoint: {checkpoint}")

    try:
        # 1. Discover 8-K filers since checkpoint
        filers = await discover_8k_filers(checkpoint)
        counts["companies_discovered"] = len(filers)
        logger.info(f"Discovered {len(filers)} companies with new 8-K filings")

        if not filers:
            logger.info("No new 8-K filings found. Updating checkpoint.")
            await update_checkpoint(today, "success_empty", counts)
            return counts

        # 2. Filter out companies we already scanned
        filers = await filter_already_scanned(filers, checkpoint)

        if not filers:
            logger.info("All companies already scanned. Updating checkpoint.")
            await update_checkpoint(today, "success_empty", counts)
            return counts

        # 3. Reconnect before scanning phase
        logger.info("Refreshing Neo4j connection before scanning phase")
        await Neo4jClient.reconnect()

        # 4. Scan each company
        for i, filer in enumerate(filers):
            try:
                result = await FeedService.scan_and_store_company(
                    cik=filer["cik"],
                    company_name=filer["name"],
                    limit=5,
                )
                stored = result.get("events_stored", 0)
                counts["companies_scanned"] += 1
                counts["events_stored"] += stored

                if stored > 0:
                    logger.info(
                        f"[{counts['companies_scanned']}/{len(filers)}] "
                        f"{filer['name']}: {stored} events"
                    )
            except Exception as e:
                counts["errors"] += 1
                counts["last_error"] = str(e)
                logger.error(f"Error scanning {filer['name']} ({filer['cik']}): {e}")

            # Reconnect every 100 companies
            if (i + 1) % 100 == 0:
                logger.info(f"Reconnecting Neo4j after {i + 1} companies")
                await Neo4jClient.reconnect()

            # Rate limiting
            if i < len(filers) - 1:
                await asyncio.sleep(INTER_COMPANY_DELAY)

        # 5. Update checkpoint
        status = "success" if counts["errors"] == 0 else "partial_success"
        await update_checkpoint(today, status, counts)

        logger.info(
            f"8-K Scanner complete — "
            f"{counts['companies_scanned']} companies, "
            f"{counts['events_stored']} events, "
            f"{counts['errors']} errors"
        )

        return counts

    except Exception as e:
        logger.error(f"8-K Scanner failed: {e}")
        counts["last_error"] = str(e)
        try:
            await update_checkpoint(checkpoint, "error", counts)
        except Exception:
            pass
        raise


def _is_weekend() -> bool:
    return datetime.utcnow().weekday() >= 5


def main():
    """Entry point for `python -m scanner.8k_scanner`."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)

    if _is_weekend():
        logger.info("=== 8-K Scanner: Weekend — skipping ===")
        sys.exit(0)

    logger.info("=== 8-K Scanner Starting ===")

    try:
        result = asyncio.run(run_scanner())
        errors = result.get("errors", 0)
        if errors > 0:
            logger.warning(f"Completed with {errors} errors")
            sys.exit(1)
        logger.info("=== 8-K Scanner Complete ===")
        sys.exit(0)
    except Exception as e:
        logger.error(f"8-K Scanner crashed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
