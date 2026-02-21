"""
Real-Time Form 4 Scanner

Polls SEC EDGAR for new Form 4 filings, stores trades, detects insider
buying clusters, and creates alerts. Designed to run as a cron job
every 10 minutes via Railway.

Usage:
    python -m scanner.form4_scanner
"""

import asyncio
import logging
import sys
from datetime import datetime, timedelta

from app.db.neo4j_client import Neo4jClient
from app.services.alert_service import AlertService
from app.services.insider_cluster_service import InsiderClusterService
from app.services.insider_trading_service import InsiderTradingService
from ingestion.sec_edgar.edgar_client import SECEdgarClient

logger = logging.getLogger(__name__)

# Scanner constants
SCANNER_ID = "form4_scanner"
INTER_COMPANY_DELAY = 0.5  # seconds between companies (rate limiting)
MAX_EFTS_RESULTS = 2000
FORM4_LIMIT_PER_COMPANY = 10  # Only fetch recent filings per run
LARGE_PURCHASE_THRESHOLD = 500_000  # $500K

# SIC codes for investment vehicles we want to skip
EXCLUDED_SIC_CODES = {
    "6726",  # Investment Offices, Not Elsewhere Classified
    "6722",  # Management Investment Companies, Open-End
    "6726",  # Investment Offices
    "6221",  # Commodity Contracts Dealers, Brokers
    "6199",  # Finance Services
    "6211",  # Security Brokers, Dealers, and Flotation Companies
    "6770",  # Blank Checks
}


async def get_checkpoint() -> str:
    """
    Read the last successful poll timestamp from Neo4j ScannerState node.
    Defaults to yesterday if no checkpoint exists.
    """
    query = """
        MATCH (s:ScannerState {scanner_id: $scanner_id})
        RETURN s.last_checkpoint as last_checkpoint
    """
    results = await Neo4jClient.execute_query(query, {"scanner_id": SCANNER_ID})

    if results and results[0].get("last_checkpoint"):
        return results[0]["last_checkpoint"]

    # Default: yesterday
    return (datetime.utcnow() - timedelta(days=1)).strftime("%Y-%m-%d")


async def update_checkpoint(checkpoint: str, status: str, counts: dict) -> None:
    """
    Update the ScannerState node with run metadata.
    Uses MERGE so first run creates the node.
    """
    now = datetime.utcnow().isoformat()

    query = """
        MERGE (s:ScannerState {scanner_id: $scanner_id})
        SET s.last_checkpoint = $checkpoint,
            s.last_run_at = $now,
            s.last_status = $status,
            s.companies_scanned = $companies_scanned,
            s.transactions_stored = $transactions_stored,
            s.alerts_created = $alerts_created,
            s.total_runs = COALESCE(s.total_runs, 0) + 1,
            s.last_error = $last_error
    """

    await Neo4jClient.execute_query(query, {
        "scanner_id": SCANNER_ID,
        "checkpoint": checkpoint,
        "now": now,
        "status": status,
        "companies_scanned": counts.get("companies_scanned", 0),
        "transactions_stored": counts.get("transactions_stored", 0),
        "alerts_created": counts.get("alerts_created", 0),
        "last_error": counts.get("last_error"),
    })


async def filter_investment_vehicles(filers: list[dict]) -> list[dict]:
    """
    Remove investment funds/vehicles using SIC codes.

    Checks Neo4j first for companies we already know. For unknown companies,
    fetches SIC from EDGAR. Skips any with SIC in EXCLUDED_SIC_CODES.
    """
    if not filers:
        return []

    ciks = [f["cik"] for f in filers]

    # Batch lookup SIC codes from Neo4j for known companies
    query = """
        UNWIND $ciks AS cik
        MATCH (c:Company {cik: cik})
        WHERE c.sic IS NOT NULL
        RETURN c.cik as cik, c.sic as sic
    """
    results = await Neo4jClient.execute_query(query, {"ciks": ciks})
    known_sics = {r["cik"]: r["sic"] for r in results}

    # For unknown companies, fetch SIC from EDGAR (batched with rate limiting)
    unknown_ciks = [f for f in filers if f["cik"] not in known_sics]
    if unknown_ciks:
        client = SECEdgarClient()
        try:
            for filer in unknown_ciks:
                try:
                    info = await client.get_company_info(filer["cik"])
                    if info.sic:
                        known_sics[filer["cik"]] = info.sic
                except Exception:
                    pass  # Can't determine SIC — allow through
        finally:
            await client.close()

    # Filter out excluded SIC codes
    filtered = []
    excluded_count = 0
    for filer in filers:
        sic = known_sics.get(filer["cik"])
        if sic and sic in EXCLUDED_SIC_CODES:
            excluded_count += 1
            logger.debug(f"Skipping investment vehicle: {filer['name']} (SIC {sic})")
        else:
            filtered.append(filer)

    if excluded_count:
        logger.info(f"Filtered out {excluded_count} investment vehicles by SIC code")

    return filtered


async def discover_form4_filers(since_date: str) -> list[dict]:
    """Discover companies that filed Form 4s since the checkpoint."""
    client = SECEdgarClient()
    try:
        return await client.get_recent_form4_filers(
            since_date=since_date,
            max_results=MAX_EFTS_RESULTS,
        )
    finally:
        await client.close()


async def filter_already_scanned(filers: list[dict], since_date: str) -> list[dict]:
    """
    Filter out companies that already have insider trades filed on/after since_date.

    This avoids re-scanning companies we already processed in a previous run.
    Only returns companies with NO trades filed since the checkpoint.
    """
    if not filers:
        return []

    ciks = [f["cik"] for f in filers]

    query = """
        UNWIND $ciks AS cik
        OPTIONAL MATCH (c:Company {cik: cik})-[:INSIDER_TRADE_OF]->(t:InsiderTransaction)
        WHERE t.filing_date >= $since_date
        WITH cik, count(t) AS recent_count
        WHERE recent_count = 0
        RETURN cik
    """
    results = await Neo4jClient.execute_query(query, {
        "ciks": ciks,
        "since_date": since_date,
    })

    new_ciks = {r["cik"] for r in results}
    filtered = [f for f in filers if f["cik"] in new_ciks]

    logger.info(
        f"Filtered {len(filers)} filers -> {len(filtered)} need scanning "
        f"({len(filers) - len(filtered)} already have recent data)"
    )
    return filtered


async def scan_company_form4s(cik: str, name: str) -> dict:
    """Fetch and store recent Form 4 filings for one company."""
    return await InsiderTradingService.scan_and_store_company(
        cik=cik,
        company_name=name,
        limit=FORM4_LIMIT_PER_COMPANY,
    )


async def detect_and_alert(affected_ciks: set[str]) -> int:
    """
    Run cluster detection on affected companies and create alerts.

    Returns the number of alerts created.
    """
    alerts_created = 0

    # Detect insider buying clusters (last 30 days, medium+)
    clusters = await InsiderClusterService.detect_clusters(
        days=30,
        window_days=30,
        min_level="medium",
    )

    # Filter to only affected CIKs
    relevant_clusters = [c for c in clusters if c.cik in affected_ciks]

    for cluster in relevant_clusters:
        alert_id = await AlertService.create_alert(
            alert_type="insider_cluster",
            severity=cluster.signal_level,
            cik=cluster.cik,
            name=cluster.company_name,
            ticker=cluster.ticker,
            title=f"Insider Cluster: {cluster.num_buyers} buyers at {cluster.company_name}",
            description=cluster.signal_summary,
        )
        if alert_id:
            alerts_created += 1
            logger.info(f"Alert created: {cluster.signal_level} cluster at {cluster.company_name}")

    # Check for large individual purchases (>$500K) in affected companies
    for cik in affected_ciks:
        try:
            await _check_large_purchases(cik)
        except Exception as e:
            logger.warning(f"Large purchase check failed for {cik}: {e}")

    return alerts_created


async def _check_large_purchases(cik: str) -> None:
    """Check a single company for large recent purchases and create alerts."""
    query = """
        MATCH (c:Company {cik: $cik})-[:INSIDER_TRADE_OF]->(t:InsiderTransaction)
        WHERE t.transaction_code = 'P'
          AND t.total_value >= $threshold
          AND t.filing_date >= $since
        RETURN c.name as company_name,
               c.tickers as tickers,
               t.insider_name as insider_name,
               t.total_value as total_value
        ORDER BY t.total_value DESC
        LIMIT 1
    """
    since = (datetime.utcnow() - timedelta(days=1)).strftime("%Y-%m-%d")
    results = await Neo4jClient.execute_query(query, {
        "cik": cik,
        "threshold": LARGE_PURCHASE_THRESHOLD,
        "since": since,
    })

    for r in results:
        name = r["company_name"] or cik
        tickers = r.get("tickers")
        ticker = tickers[0] if tickers and isinstance(tickers, list) else None
        insider = r["insider_name"] or "Unknown"
        value = r["total_value"] or 0

        await AlertService.create_alert(
            alert_type="large_purchase",
            severity="medium",
            cik=cik,
            name=name,
            ticker=ticker,
            title=f"Large Purchase: {insider} bought ${value:,.0f} of {name}",
            description=f"{insider} purchased ${value:,.0f} worth of shares",
        )


async def run_scanner() -> dict:
    """
    Orchestrate the full scanner flow.

    Returns a summary dict with counts.
    """
    await Neo4jClient.connect()

    counts = {
        "companies_discovered": 0,
        "companies_scanned": 0,
        "transactions_stored": 0,
        "alerts_created": 0,
        "errors": 0,
        "last_error": None,
    }

    checkpoint = await get_checkpoint()
    today = datetime.utcnow().strftime("%Y-%m-%d")
    logger.info(f"Scanner starting — checkpoint: {checkpoint}")

    try:
        # 1. Discover Form 4 filers since checkpoint
        all_filers = await discover_form4_filers(checkpoint)
        counts["companies_discovered"] = len(all_filers)
        logger.info(f"Discovered {len(all_filers)} companies with new Form 4 filings")

        if not all_filers:
            logger.info("No new Form 4 filings found. Updating checkpoint and exiting.")
            await update_checkpoint(today, "success_empty", counts)
            return counts

        # 1b. Filter out investment vehicles (funds, trusts, etc.)
        all_filers = await filter_investment_vehicles(all_filers)

        # 1c. Filter out companies we already scanned since checkpoint
        filers = await filter_already_scanned(all_filers, checkpoint)

        if not filers:
            logger.info("All companies already scanned. Updating checkpoint and exiting.")
            await update_checkpoint(today, "success_empty", counts)
            return counts

        # 2. Scan each company's Form 4s
        affected_ciks = set()
        for i, filer in enumerate(filers):
            cik = filer["cik"]
            name = filer["name"]

            try:
                result = await scan_company_form4s(cik, name)
                stored = result.get("transactions_stored", 0)
                counts["transactions_stored"] += stored
                counts["companies_scanned"] += 1
                affected_ciks.add(cik)

                if stored > 0:
                    logger.info(
                        f"[{counts['companies_scanned']}/{len(filers)}] "
                        f"{name}: {stored} transactions"
                    )
            except Exception as e:
                counts["errors"] += 1
                counts["last_error"] = str(e)
                logger.error(f"Error scanning {name} ({cik}): {e}")

            # Rate limiting
            if i < len(filers) - 1:
                await asyncio.sleep(INTER_COMPANY_DELAY)

        # 3. Detect clusters and create alerts
        if affected_ciks:
            alerts = await detect_and_alert(affected_ciks)
            counts["alerts_created"] = alerts

        # 4. Update checkpoint
        status = "success" if counts["errors"] == 0 else "partial_success"
        await update_checkpoint(today, status, counts)

        logger.info(
            f"Scanner complete — "
            f"{counts['companies_scanned']} companies, "
            f"{counts['transactions_stored']} transactions, "
            f"{counts['alerts_created']} alerts, "
            f"{counts['errors']} errors"
        )

        return counts

    except Exception as e:
        logger.error(f"Scanner failed: {e}")
        counts["last_error"] = str(e)
        try:
            await update_checkpoint(checkpoint, "error", counts)
        except Exception:
            pass
        raise


def _is_weekend() -> bool:
    """Check if today is Saturday (5) or Sunday (6)."""
    return datetime.utcnow().weekday() >= 5


def main():
    """Entry point for `python -m scanner.form4_scanner`."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    if _is_weekend():
        logger.info("=== Form 4 Scanner: Weekend — skipping ===")
        sys.exit(0)

    logger.info("=== Form 4 Scanner Starting ===")

    try:
        result = asyncio.run(run_scanner())
        errors = result.get("errors", 0)
        if errors > 0:
            logger.warning(f"Completed with {errors} errors")
            sys.exit(1)
        logger.info("=== Form 4 Scanner Complete ===")
        sys.exit(0)
    except Exception as e:
        logger.error(f"Scanner crashed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
