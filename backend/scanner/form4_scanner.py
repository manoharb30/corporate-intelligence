"""
Real-Time Form 4 Scanner

Polls SEC EDGAR for new Form 4 filings, stores trades, detects insider
buying clusters, and creates alerts. Designed to run as a cron job
every 10 minutes via Railway.

Usage:
    python -m scanner.form4_scanner
"""

import asyncio
import json
import logging
import sys
import time
from datetime import datetime, timedelta
from typing import Optional

import yfinance as yf

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


async def filter_and_classify_filers(filers: list[dict]) -> tuple[list[dict], dict]:
    """
    Filter out investment vehicles and non-companies using a single EDGAR call
    per unknown company. Caches both SIC and entity_type to Neo4j so future
    runs resolve from cache (the "dynamic programming" optimisation).

    Returns:
        - filtered list of filers (operating companies with non-excluded SIC)
        - dict mapping cik -> {"tickers": [...], "entity_type": str, "sic": str}
          for passing to the scan phase (avoids redundant EDGAR calls later)
    """
    if not filers:
        return [], {}

    ciks = [f["cik"] for f in filers]

    # --- Step 1: Batch lookup from Neo4j (instant, zero EDGAR calls) ---
    query = """
        UNWIND $ciks AS cik
        OPTIONAL MATCH (c:Company {cik: cik})
        RETURN cik, c.sic as sic, c.entity_type as entity_type, c.tickers as tickers
    """
    results = await Neo4jClient.execute_query(query, {"ciks": ciks})
    known = {r["cik"]: {
        "sic": r.get("sic"),
        "entity_type": r.get("entity_type"),
        "tickers": r.get("tickers") or [],
    } for r in results if r.get("sic") is not None or r.get("entity_type") is not None}

    # --- Step 2: Classify known companies from cache ---
    filtered = []
    company_info = {}  # cik -> metadata, passed to scan phase
    unknown_filers = []
    rejected_cached = 0

    for filer in filers:
        cik = filer["cik"]
        info = known.get(cik)

        if info and info["sic"] is not None and info["entity_type"] is not None:
            # Fully known — apply reject rules
            if info["entity_type"] != "operating":
                rejected_cached += 1
                continue
            if info["sic"] in EXCLUDED_SIC_CODES:
                rejected_cached += 1
                continue
            # Good company — pass through
            filtered.append(filer)
            company_info[cik] = info
        else:
            # Unknown or partially known — needs EDGAR
            unknown_filers.append(filer)

    if rejected_cached:
        logger.info(f"Skipped {rejected_cached} known non-companies/investment vehicles from Neo4j cache")

    # --- Step 3: ONE EDGAR call per unknown company, cache results ---
    rejected_new = 0
    if unknown_filers:
        client = SECEdgarClient()
        try:
            for filer in unknown_filers:
                cik = filer["cik"]
                try:
                    info = await client.get_company_info(cik)
                    sic = info.sic
                    entity_type = info.entity_type
                    tickers = info.tickers or []

                    # Apply reject rules BEFORE creating the node — avoids empty shells
                    if entity_type and entity_type != "operating":
                        rejected_new += 1
                        continue
                    if sic and sic in EXCLUDED_SIC_CODES:
                        rejected_new += 1
                        continue

                    # Only cache accepted companies — prevents shell node accumulation
                    await Neo4jClient.execute_query(
                        """
                        MERGE (c:Company {cik: $cik})
                        SET c.sic = COALESCE($sic, c.sic),
                            c.entity_type = COALESCE($entity_type, c.entity_type),
                            c.tickers = COALESCE($tickers, c.tickers)
                        """,
                        {"cik": cik, "sic": sic, "entity_type": entity_type, "tickers": tickers},
                    )

                    filtered.append(filer)
                    company_info[cik] = {
                        "sic": sic,
                        "entity_type": entity_type,
                        "tickers": tickers,
                    }
                except Exception:
                    # Can't determine — allow through without cached info
                    filtered.append(filer)
        finally:
            await client.close()

    if rejected_new:
        logger.info(f"Filtered out {rejected_new} new non-companies/investment vehicles via EDGAR")

    logger.info(
        f"Classification complete: {len(filtered)} companies to scan "
        f"({rejected_cached} cached rejects, {len(unknown_filers)} checked via EDGAR, "
        f"{rejected_new} new rejects)"
    )

    return filtered, company_info


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


async def scan_company_form4s(cik: str, name: str, info: dict | None = None) -> dict:
    """Fetch and store recent Form 4 filings for one company."""
    kwargs = {
        "cik": cik,
        "company_name": name,
        "limit": FORM4_LIMIT_PER_COMPANY,
    }
    # Pass pre-fetched metadata to skip redundant EDGAR get_company_info call
    if info:
        kwargs["known_tickers"] = info.get("tickers", [])
        kwargs["known_entity_type"] = info.get("entity_type")
    return await InsiderTradingService.scan_and_store_company(**kwargs)


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
            title=f"Open Market Cluster: {cluster.num_buyers} buyers at {cluster.company_name}",
            description=cluster.signal_summary,
            signal_id=cluster.accession_number,
        )
        if alert_id:
            alerts_created += 1
            logger.info(f"Alert created: {cluster.signal_level} cluster at {cluster.company_name}")

    # Detect insider selling clusters (last 30 days, medium+)
    sell_clusters = await InsiderClusterService.detect_sell_clusters(
        days=30,
        window_days=30,
        min_level="medium",
    )

    relevant_sell_clusters = [c for c in sell_clusters if c.cik in affected_ciks]

    for cluster in relevant_sell_clusters:
        alert_id = await AlertService.create_alert(
            alert_type="insider_sell_cluster",
            severity=cluster.signal_level,
            cik=cluster.cik,
            name=cluster.company_name,
            ticker=cluster.ticker,
            title=f"Open Market Sell Cluster: {cluster.num_buyers} sellers at {cluster.company_name}",
            description=cluster.signal_summary,
            signal_id=cluster.accession_number,
        )
        if alert_id:
            alerts_created += 1
            logger.info(f"Alert created: {cluster.signal_level} sell cluster at {cluster.company_name}")

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

        today = datetime.utcnow().strftime("%Y-%m-%d")
        await AlertService.create_alert(
            alert_type="large_purchase",
            severity="medium",
            cik=cik,
            name=name,
            ticker=ticker,
            title=f"Large Open Market Purchase: {insider} bought ${value:,.0f} of {name}",
            description=f"{insider} made an open market purchase of ${value:,.0f} worth of shares",
            signal_id=f"CLUSTER-{cik}-{today}",
        )


def _fetch_price_series(ticker: str) -> Optional[list[dict]]:
    """Fetch daily close prices for a ticker from yfinance (2 years)."""
    try:
        df = yf.Ticker(ticker).history(period="2y")
        if df.empty:
            return None
        series = []
        for date, row in df.iterrows():
            close = row.get("Close")
            if close is None or close <= 0:
                continue
            series.append({
                "d": date.strftime("%Y-%m-%d"),
                "c": round(float(close), 2),
            })
        return series if series else None
    except Exception as e:
        logger.warning(f"Price fetch failed for {ticker}: {type(e).__name__}: {str(e)[:80]}")
        return None


async def update_signal_prices() -> int:
    """Update Company.price_series for all companies with signals.

    Runs after cluster detection. Only updates companies whose prices
    are stale (updated >20 hours ago or never).
    """
    logger.info("Updating daily prices for signal companies...")

    # Get all companies with signals that need price updates
    result = await Neo4jClient.execute_query("""
        MATCH (sp:SignalPerformance)
        WHERE sp.ticker IS NOT NULL AND sp.ticker <> ""
        WITH DISTINCT sp.ticker AS ticker, sp.cik AS cik
        OPTIONAL MATCH (c:Company {cik: cik})
        WHERE c.prices_updated_at IS NOT NULL
          AND c.prices_updated_at > toString(datetime() - duration({hours: 20}))
        WITH ticker, cik, c
        WHERE c IS NULL
        RETURN ticker, cik
        ORDER BY ticker
    """)

    if not result:
        logger.info("All signal prices are up to date")
        return 0

    logger.info(f"Updating prices for {len(result)} companies")
    updated = 0

    for i, r in enumerate(result):
        ticker = r["ticker"]
        cik = r["cik"]

        series = _fetch_price_series(ticker)
        if not series:
            continue

        series_json = json.dumps(series, separators=(",", ":"))
        try:
            await Neo4jClient.execute_query("""
                MATCH (c:Company {cik: $cik})
                SET c.price_series = $series_json,
                    c.prices_updated_at = $now,
                    c.price_count = $count
            """, {
                "cik": cik,
                "series_json": series_json,
                "now": datetime.utcnow().isoformat(),
                "count": len(series),
            })
            updated += 1
        except Exception as e:
            logger.warning(f"Failed to store prices for {ticker}: {e}")

        # Rate limit yfinance — 1.5s between calls
        if i < len(result) - 1:
            time.sleep(1.5)

        if (i + 1) % 25 == 0:
            logger.info(f"  Prices: {i + 1}/{len(result)} processed, {updated} updated")

    # Always update SPY for alpha calculations
    spy_series = _fetch_price_series("SPY")
    if spy_series:
        spy_json = json.dumps(spy_series, separators=(",", ":"))
        try:
            await Neo4jClient.execute_query("""
                MERGE (c:Company {ticker: 'SPY'})
                SET c.name = 'SPDR S&P 500 ETF Trust',
                    c.price_series = $series_json,
                    c.prices_updated_at = $now,
                    c.price_count = $count
            """, {
                "series_json": spy_json,
                "now": datetime.utcnow().isoformat(),
                "count": len(spy_series),
            })
            logger.info("SPY prices updated")
        except Exception as e:
            logger.warning(f"SPY price update failed: {e}")

    logger.info(f"Price update complete: {updated}/{len(result)} updated")
    return updated


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

        # 1b. Filter out companies we already scanned since checkpoint (Neo4j only, instant)
        all_filers = await filter_already_scanned(all_filers, checkpoint)

        # 1c. Filter + classify: reject non-companies/investment vehicles,
        #     cache SIC + entity_type to Neo4j, collect company_info for scan phase
        filers, company_info = await filter_and_classify_filers(all_filers)

        if not filers:
            logger.info("All companies already scanned. Updating checkpoint and exiting.")
            await update_checkpoint(today, "success_empty", counts)
            return counts

        # 2. Reconnect to Neo4j — the filtering phase can take 10+ minutes
        #    and the Aura connection may have gone stale
        logger.info("Refreshing Neo4j connection before scanning phase")
        await Neo4jClient.reconnect()

        # 3. Scan each company's Form 4s
        affected_ciks = set()
        for i, filer in enumerate(filers):
            cik = filer["cik"]
            name = filer["name"]

            try:
                result = await scan_company_form4s(cik, name, company_info.get(cik))
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

            # Reconnect every 50 companies to avoid Aura idle timeout
            if (i + 1) % 50 == 0:
                logger.info(f"Reconnecting Neo4j after {i + 1} companies")
                await Neo4jClient.reconnect()

            # Rate limiting
            if i < len(filers) - 1:
                await asyncio.sleep(INTER_COMPANY_DELAY)

        # 4. Detect clusters and create alerts
        if affected_ciks:
            alerts = await detect_and_alert(affected_ciks)
            counts["alerts_created"] = alerts

        # 5. Update daily prices for all companies with signals
        prices_updated = await update_signal_prices()
        counts["prices_updated"] = prices_updated

        # 6. Update checkpoint
        status = "success" if counts["errors"] == 0 else "partial_success"
        await update_checkpoint(today, status, counts)

        logger.info(
            f"Scanner complete — "
            f"{counts['companies_scanned']} companies, "
            f"{counts['transactions_stored']} transactions, "
            f"{counts['alerts_created']} alerts, "
            f"{prices_updated} prices updated, "
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
