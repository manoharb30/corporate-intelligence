"""
Schedule 13D Activist Filing Scanner

Polls SEC EDGAR for new Schedule 13D/13D-A filings, parses them,
stores ActivistFiling nodes, and creates alerts for high-signal stakes.
Designed to run as a cron job every 6 hours via Railway.

Usage:
    python -m scanner.activist_scanner
"""

import asyncio
import logging
import sys
from datetime import datetime, timedelta

import httpx

from app.db.neo4j_client import Neo4jClient
from app.services.activist_filing_service import ActivistFilingService
from app.services.alert_service import AlertService
from ingestion.sec_edgar.edgar_client import SECEdgarClient
from ingestion.sec_edgar.parsers.schedule13_parser import parse_schedule_13d

logger = logging.getLogger(__name__)

# Scanner constants
SCANNER_ID = "activist_scanner"
SEC_REQUEST_DELAY = 5.0  # seconds between SEC HTML fetches
SEC_BACKOFF_DELAY = 60.0  # seconds after consecutive 503s
MAX_CONSECUTIVE_503 = 3
MAX_EFTS_RESULTS = 5000
SEC_USER_AGENT = "CorporateIntelligence research@lookinsight.ai"
SEC_HTML_TIMEOUT = 15.0


async def get_checkpoint() -> str:
    """Read last successful poll timestamp. Defaults to 7 days ago."""
    query = """
        MATCH (s:ScannerState {scanner_id: $scanner_id})
        RETURN s.last_checkpoint as last_checkpoint
    """
    results = await Neo4jClient.execute_query(query, {"scanner_id": SCANNER_ID})

    if results and results[0].get("last_checkpoint"):
        return results[0]["last_checkpoint"]

    return (datetime.utcnow() - timedelta(days=7)).strftime("%Y-%m-%d")


async def update_checkpoint(checkpoint: str, status: str, counts: dict) -> None:
    """Update ScannerState node with run metadata."""
    now = datetime.utcnow().isoformat()

    query = """
        MERGE (s:ScannerState {scanner_id: $scanner_id})
        SET s.last_checkpoint = $checkpoint,
            s.last_run_at = $now,
            s.last_status = $status,
            s.filings_discovered = $filings_discovered,
            s.filings_stored = $filings_stored,
            s.filings_skipped = $filings_skipped,
            s.alerts_created = $alerts_created,
            s.total_runs = COALESCE(s.total_runs, 0) + 1,
            s.last_error = $last_error
    """

    await Neo4jClient.execute_query(query, {
        "scanner_id": SCANNER_ID,
        "checkpoint": checkpoint,
        "now": now,
        "status": status,
        "filings_discovered": counts.get("filings_discovered", 0),
        "filings_stored": counts.get("filings_stored", 0),
        "filings_skipped": counts.get("filings_skipped", 0),
        "alerts_created": counts.get("alerts_created", 0),
        "last_error": counts.get("last_error"),
    })


async def discover_filings(since_date: str) -> list[dict]:
    """Discover 13D/13D-A filings since checkpoint via EFTS."""
    client = SECEdgarClient()
    try:
        return await client.get_recent_13d_filers(
            since_date=since_date,
            max_results=MAX_EFTS_RESULTS,
        )
    finally:
        await client.close()


async def fetch_filing_html(filing: dict) -> str | None:
    """Fetch the rendered HTML for a single 13D filing from SEC.

    Returns the HTML string, or None on failure.
    """
    primary_doc = filing.get("primary_document", "")
    filer_cik = filing.get("filer_cik", "").lstrip("0")
    accession = filing.get("accession_number", "").replace("-", "")

    if not primary_doc or not filer_cik or not accession:
        return None

    url = f"https://www.sec.gov/Archives/edgar/data/{filer_cik}/{accession}/{primary_doc}"

    async with httpx.AsyncClient(
        headers={"User-Agent": SEC_USER_AGENT, "Accept-Encoding": "gzip"},
        timeout=SEC_HTML_TIMEOUT,
        follow_redirects=True,
    ) as client:
        try:
            resp = await client.get(url)
            if resp.status_code == 200:
                return resp.text
            logger.warning(f"SEC returned {resp.status_code} for {filing['accession_number']}")
            return None
        except httpx.TimeoutException:
            logger.warning(f"Timeout fetching {filing['accession_number']}")
            return None
        except Exception as e:
            logger.warning(f"Error fetching {filing['accession_number']}: {e}")
            return None


async def create_alert_for_filing(filing_result) -> bool:
    """Create an alert for a HIGH signal activist filing. Returns True if created."""
    target_cik = filing_result.target_cik
    if not target_cik:
        return False

    # Look up ticker from Company node
    ticker_results = await Neo4jClient.execute_query(
        "MATCH (c:Company {cik: $cik}) RETURN c.tickers AS tickers",
        {"cik": target_cik},
    )
    ticker = None
    if ticker_results:
        tickers = ticker_results[0].get("tickers")
        if tickers and isinstance(tickers, list):
            ticker = tickers[0]

    pct_str = f" ({filing_result.percentage:.1f}% stake)" if filing_result.percentage else ""
    filer = filing_result.filer_name or "Unknown filer"
    target = filing_result.target_name or "Unknown company"

    alert_id = await AlertService.create_alert(
        alert_type="activist_filing",
        severity="high",
        cik=target_cik,
        name=target,
        ticker=ticker,
        title=f"13D Activist Filing: {filer} holds{pct_str} of {target}",
        description=filing_result.purpose_text[:500] if filing_result.purpose_text else "",
        signal_id=filing_result.accession_number,
    )
    return alert_id is not None


async def run_scanner() -> dict:
    """Orchestrate the full activist scanner flow."""
    await Neo4jClient.connect()

    counts = {
        "filings_discovered": 0,
        "filings_stored": 0,
        "filings_skipped": 0,
        "alerts_created": 0,
        "errors": 0,
        "last_error": None,
    }

    checkpoint = await get_checkpoint()
    today = datetime.utcnow().strftime("%Y-%m-%d")
    logger.info(f"Activist scanner starting — checkpoint: {checkpoint}")

    try:
        # 1. Discover filings from EFTS
        all_filings = await discover_filings(checkpoint)
        counts["filings_discovered"] = len(all_filings)
        logger.info(f"Discovered {len(all_filings)} 13D filings since {checkpoint}")

        if not all_filings:
            logger.info("No new 13D filings found.")
            await update_checkpoint(today, "success_empty", counts)
            return counts

        # 2. Filter out already-stored filings
        all_accessions = [f["accession_number"] for f in all_filings]
        already_stored = await ActivistFilingService.get_already_stored_accessions(all_accessions)
        new_filings = [f for f in all_filings if f["accession_number"] not in already_stored]
        counts["filings_skipped"] = len(all_filings) - len(new_filings)

        logger.info(
            f"{len(new_filings)} new filings to process "
            f"({counts['filings_skipped']} already stored)"
        )

        if not new_filings:
            await update_checkpoint(today, "success_empty", counts)
            return counts

        # 3. Fetch, parse, store each filing
        consecutive_503 = 0

        for i, filing in enumerate(new_filings):
            acc = filing["accession_number"]

            # Rate limiting
            if i > 0:
                await asyncio.sleep(SEC_REQUEST_DELAY)

            # Back off after consecutive 503s
            if consecutive_503 >= MAX_CONSECUTIVE_503:
                logger.warning(f"Hit {MAX_CONSECUTIVE_503} consecutive 503s, cooling down {SEC_BACKOFF_DELAY}s")
                await asyncio.sleep(SEC_BACKOFF_DELAY)
                consecutive_503 = 0

            html = await fetch_filing_html(filing)
            if html is None:
                consecutive_503 += 1
                counts["errors"] += 1
                continue

            consecutive_503 = 0

            # Parse
            try:
                result = parse_schedule_13d(html, metadata=filing)
            except Exception as e:
                counts["errors"] += 1
                counts["last_error"] = f"Parse error {acc}: {e}"
                logger.error(f"Parse error for {acc}: {e}")
                continue

            # Store
            stored_acc = await ActivistFilingService.store_filing(result)
            if stored_acc:
                counts["filings_stored"] += 1
                logger.info(
                    f"[{counts['filings_stored']}/{len(new_filings)}] "
                    f"{result.filer_name} -> {result.target_name} "
                    f"({result.percentage or 0:.1f}%, {result.signal_level if hasattr(result, 'signal_level') else 'N/A'})"
                )

                # Create alert for HIGH signal filings
                from app.services.activist_filing_service import classify_signal_level
                signal = classify_signal_level(result)
                if signal == "HIGH":
                    if await create_alert_for_filing(result):
                        counts["alerts_created"] += 1
            else:
                counts["errors"] += 1
                counts["last_error"] = f"Failed to store {acc}"

        # 4. Update checkpoint
        status = "success" if counts["errors"] == 0 else "partial_success"
        await update_checkpoint(today, status, counts)

        logger.info(
            f"Activist scanner complete — "
            f"{counts['filings_stored']} stored, "
            f"{counts['filings_skipped']} skipped, "
            f"{counts['alerts_created']} alerts, "
            f"{counts['errors']} errors"
        )

        return counts

    except Exception as e:
        logger.error(f"Activist scanner failed: {e}")
        counts["last_error"] = str(e)
        try:
            await update_checkpoint(checkpoint, "error", counts)
        except Exception:
            pass
        raise


async def run_backfill(days: int = 90) -> dict:
    """Run a one-time backfill for the past N days.

    Same as run_scanner but forces the checkpoint to N days ago
    regardless of stored state.
    """
    await Neo4jClient.connect()

    since_date = (datetime.utcnow() - timedelta(days=days)).strftime("%Y-%m-%d")
    logger.info(f"Starting 13D backfill from {since_date} ({days} days)")

    # Temporarily override get_checkpoint by directly calling the scanner logic
    counts = {
        "filings_discovered": 0,
        "filings_stored": 0,
        "filings_skipped": 0,
        "alerts_created": 0,
        "errors": 0,
        "last_error": None,
    }

    all_filings = await discover_filings(since_date)
    counts["filings_discovered"] = len(all_filings)
    logger.info(f"Discovered {len(all_filings)} 13D filings for backfill")

    if not all_filings:
        return counts

    # Filter already stored
    all_accessions = [f["accession_number"] for f in all_filings]
    already_stored = await ActivistFilingService.get_already_stored_accessions(all_accessions)
    new_filings = [f for f in all_filings if f["accession_number"] not in already_stored]
    counts["filings_skipped"] = len(all_filings) - len(new_filings)

    logger.info(f"{len(new_filings)} new filings to backfill ({counts['filings_skipped']} already stored)")

    consecutive_503 = 0

    for i, filing in enumerate(new_filings):
        if i > 0:
            await asyncio.sleep(SEC_REQUEST_DELAY)

        if consecutive_503 >= MAX_CONSECUTIVE_503:
            logger.warning(f"Cooling down {SEC_BACKOFF_DELAY}s after {MAX_CONSECUTIVE_503} consecutive 503s")
            await asyncio.sleep(SEC_BACKOFF_DELAY)
            consecutive_503 = 0

        html = await fetch_filing_html(filing)
        if html is None:
            consecutive_503 += 1
            counts["errors"] += 1
            continue

        consecutive_503 = 0

        try:
            result = parse_schedule_13d(html, metadata=filing)
        except Exception as e:
            counts["errors"] += 1
            logger.error(f"Parse error: {e}")
            continue

        stored_acc = await ActivistFilingService.store_filing(result)
        if stored_acc:
            counts["filings_stored"] += 1
            if (counts["filings_stored"] % 10) == 0:
                logger.info(f"Backfill progress: {counts['filings_stored']} stored, {counts['errors']} errors")
        else:
            counts["errors"] += 1

    logger.info(
        f"Backfill complete — "
        f"{counts['filings_stored']} stored, "
        f"{counts['filings_skipped']} skipped, "
        f"{counts['errors']} errors"
    )
    return counts


def _is_weekend() -> bool:
    """Check if today is Saturday (5) or Sunday (6)."""
    return datetime.utcnow().weekday() >= 5


def main():
    """Entry point for `python -m scanner.activist_scanner`."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    if _is_weekend():
        logger.info("=== Activist Scanner: Weekend — skipping ===")
        sys.exit(0)

    logger.info("=== Activist Scanner Starting ===")

    try:
        result = asyncio.run(run_scanner())
        errors = result.get("errors", 0)
        if errors > 0:
            logger.warning(f"Completed with {errors} errors")
            sys.exit(1)
        logger.info("=== Activist Scanner Complete ===")
        sys.exit(0)
    except Exception as e:
        logger.error(f"Scanner crashed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
