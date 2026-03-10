"""
Daily backfill script - runs scanners one day at a time to avoid throttling.

Usage:
    cd backend
    source venv/bin/activate
    python backfill_daily.py --scanner form4 --start 2026-03-03 --end 2026-03-08
    python backfill_daily.py --scanner activist --start 2026-03-03 --end 2026-03-08
"""

import argparse
import asyncio
import logging
from datetime import datetime, timedelta

from app.db.neo4j_client import Neo4jClient

logger = logging.getLogger(__name__)


async def set_checkpoint(scanner_id: str, date: str):
    await Neo4jClient.execute_query(
        """
        MERGE (s:ScannerState {scanner_id: $scanner_id})
        SET s.last_checkpoint = $date
        """,
        {"scanner_id": scanner_id, "date": date},
    )


async def get_checkpoint(scanner_id: str) -> str:
    results = await Neo4jClient.execute_query(
        """
        MATCH (s:ScannerState {scanner_id: $scanner_id})
        RETURN s.last_checkpoint as last_checkpoint
        """,
        {"scanner_id": scanner_id},
    )
    if results and results[0].get("last_checkpoint"):
        return results[0]["last_checkpoint"]
    return None


async def run_form4_one_day(date_str: str) -> dict:
    """Run Form 4 scanner for a single day."""
    from ingestion.sec_edgar.edgar_client import SECEdgarClient
    from app.services.insider_trading_service import InsiderTradingService
    from scanner.form4_scanner import (
        filter_investment_vehicles,
        filter_non_companies,
        filter_already_scanned,
        detect_and_alert,
        FORM4_LIMIT_PER_COMPANY,
        INTER_COMPANY_DELAY,
    )

    next_date = (datetime.strptime(date_str, "%Y-%m-%d") + timedelta(days=1)).strftime("%Y-%m-%d")

    counts = {
        "companies_discovered": 0,
        "companies_scanned": 0,
        "transactions_stored": 0,
        "alerts_created": 0,
        "errors": 0,
    }

    # 1. Discover filers for just this one day
    client = SECEdgarClient()
    try:
        # Use EFTS with tight date range
        import httpx
        seen_ciks = {}
        from_idx = 0

        while len(seen_ciks) < 500:
            params = {
                "forms": "4",
                "dateRange": "custom",
                "startdt": date_str,
                "enddt": next_date,
                "from": str(from_idx),
            }
            url = f"{client.FULL_TEXT_SEARCH_URL}?{httpx.QueryParams(params)}"
            response = await client._request(url)
            data = response.json()
            hits = data.get("hits", {}).get("hits", [])
            if not hits:
                break

            for hit in hits:
                source = hit.get("_source", {})
                ciks = source.get("ciks", [])
                display_names = source.get("display_names", [])
                for i, cik in enumerate(ciks):
                    if cik not in seen_ciks:
                        name = display_names[i] if i < len(display_names) else ""
                        seen_ciks[cik] = name

            from_idx += len(hits)
            if len(hits) < 100:
                break
    finally:
        await client.close()

    filers = [{"cik": cik, "name": name} for cik, name in seen_ciks.items()]
    counts["companies_discovered"] = len(filers)
    logger.info(f"  Discovered {len(filers)} filers for {date_str}")

    if not filers:
        return counts

    # 2. Fast filter: only keep companies already known as "operating" in Neo4j,
    #    OR unknown companies (give them benefit of the doubt).
    #    Skip the slow SEC entity_type lookup — most companies are already cached.
    ciks = [f["cik"] for f in filers]
    known_non_operating = set()
    known_excluded_sic = set()

    # Batch check entity_type + SIC from Neo4j (fast, no SEC calls)
    results = await Neo4jClient.execute_query(
        """
        UNWIND $ciks AS cik
        MATCH (c:Company {cik: cik})
        RETURN c.cik as cik, c.entity_type as entity_type, c.sic as sic
        """,
        {"ciks": ciks},
    )
    for r in results:
        if r.get("entity_type") and r["entity_type"] != "operating":
            known_non_operating.add(r["cik"])
        if r.get("sic") and r["sic"] in {"6726", "6722", "6221", "6199", "6211", "6770"}:
            known_excluded_sic.add(r["cik"])

    filers = [
        f for f in filers
        if f["cik"] not in known_non_operating and f["cik"] not in known_excluded_sic
    ]
    logger.info(f"  After Neo4j filter: {len(filers)} (removed {len(known_non_operating)} non-operating, {len(known_excluded_sic)} investment vehicles)")

    # Filter already scanned
    await Neo4jClient.reconnect()
    filers = await filter_already_scanned(filers, date_str)
    logger.info(f"  After already-scanned filter: {len(filers)}")

    if not filers:
        return counts

    # 3. Reconnect and scan
    await Neo4jClient.reconnect()

    affected_ciks = set()
    for i, filer in enumerate(filers):
        cik = filer["cik"]
        name = filer["name"]
        try:
            result = await InsiderTradingService.scan_and_store_company(
                cik=cik, company_name=name, limit=FORM4_LIMIT_PER_COMPANY
            )
            stored = result.get("transactions_stored", 0)
            counts["transactions_stored"] += stored
            counts["companies_scanned"] += 1
            affected_ciks.add(cik)
            if stored > 0:
                logger.info(f"    [{counts['companies_scanned']}/{len(filers)}] {name}: {stored} txns")
        except Exception as e:
            counts["errors"] += 1
            logger.error(f"    Error: {name} ({cik}): {e}")

        if i < len(filers) - 1:
            await asyncio.sleep(INTER_COMPANY_DELAY)

    # 4. Detect clusters
    if affected_ciks:
        await Neo4jClient.reconnect()
        alerts = await detect_and_alert(affected_ciks)
        counts["alerts_created"] = alerts

    return counts


async def run_activist_one_day(date_str: str) -> dict:
    """Run activist scanner for a single day."""
    from ingestion.sec_edgar.edgar_client import SECEdgarClient
    from ingestion.sec_edgar.parsers.schedule13_parser import parse_schedule_13d
    from app.services.activist_filing_service import ActivistFilingService
    from app.services.alert_service import AlertService
    from scanner.activist_scanner import SEC_REQUEST_DELAY, SEC_USER_AGENT, SEC_HTML_TIMEOUT
    import httpx

    next_date = (datetime.strptime(date_str, "%Y-%m-%d") + timedelta(days=1)).strftime("%Y-%m-%d")

    counts = {
        "filings_discovered": 0,
        "filings_stored": 0,
        "filings_skipped": 0,
        "alerts_created": 0,
        "errors": 0,
    }

    # 1. Discover 13D filings for this day
    client = SECEdgarClient()
    try:
        import httpx as httpx_mod
        filings = []
        from_idx = 0

        while True:
            params = {
                "forms": "SC 13D,SC 13D/A",
                "dateRange": "custom",
                "startdt": date_str,
                "enddt": next_date,
                "from": str(from_idx),
            }
            url = f"{client.FULL_TEXT_SEARCH_URL}?{httpx_mod.QueryParams(params)}"
            response = await client._request(url)
            data = response.json()
            hits = data.get("hits", {}).get("hits", [])
            if not hits:
                break

            for hit in hits:
                source = hit.get("_source", {})
                filings.append({
                    "accession_number": source.get("file_num", hit.get("_id", "")),
                    "cik": source.get("ciks", [""])[0] if source.get("ciks") else "",
                    "company_name": source.get("display_names", [""])[0] if source.get("display_names") else "",
                    "filing_date": source.get("file_date", date_str),
                    "filing_url": f"https://www.sec.gov/Archives/edgar/data/{source.get('ciks', [''])[0]}/{hit.get('_id', '').replace('-', '')}/{hit.get('_id', '')}-index.htm" if source.get("ciks") else "",
                })

            from_idx += len(hits)
            if len(hits) < 100:
                break
    finally:
        await client.close()

    counts["filings_discovered"] = len(filings)
    logger.info(f"  Discovered {len(filings)} 13D filings for {date_str}")

    if not filings:
        return counts

    # 2. Check which ones are already stored
    for filing in filings:
        try:
            # Check if already stored
            existing = await Neo4jClient.execute_query(
                "MATCH (a:ActivistFiling {accession_number: $acc}) RETURN a.accession_number",
                {"acc": filing["accession_number"]},
            )
            if existing:
                counts["filings_skipped"] += 1
                continue

            # Fetch and parse
            async with httpx.AsyncClient(
                headers={"User-Agent": SEC_USER_AGENT},
                timeout=SEC_HTML_TIMEOUT,
            ) as http:
                resp = await http.get(filing["filing_url"])
                if resp.status_code != 200:
                    counts["filings_skipped"] += 1
                    continue

                parsed = parse_schedule_13d(resp.text, filing["filing_url"])
                if not parsed:
                    counts["filings_skipped"] += 1
                    continue

                await ActivistFilingService.store_filing(parsed)
                counts["filings_stored"] += 1
                logger.info(f"    Stored: {parsed.company_name} ({parsed.ownership_percent}%)")

            await asyncio.sleep(SEC_REQUEST_DELAY)

        except Exception as e:
            counts["errors"] += 1
            logger.error(f"    Error processing filing: {e}")

    return counts


async def main(scanner: str, start_date: str, end_date: str):
    await Neo4jClient.connect()

    current = datetime.strptime(start_date, "%Y-%m-%d")
    end = datetime.strptime(end_date, "%Y-%m-%d")

    total = {
        "days_processed": 0,
        "companies_scanned": 0,
        "transactions_stored": 0,
        "filings_stored": 0,
        "alerts_created": 0,
        "errors": 0,
    }

    while current < end:
        date_str = current.strftime("%Y-%m-%d")
        logger.info(f"\n{'='*60}")
        logger.info(f"Processing {scanner} for {date_str}")
        logger.info(f"{'='*60}")

        try:
            if scanner == "form4":
                result = run_form4_one_day(date_str)
            elif scanner == "activist":
                result = run_activist_one_day(date_str)
            else:
                raise ValueError(f"Unknown scanner: {scanner}")

            result = await result
            total["days_processed"] += 1
            total["companies_scanned"] += result.get("companies_scanned", 0)
            total["transactions_stored"] += result.get("transactions_stored", 0)
            total["filings_stored"] += result.get("filings_stored", 0)
            total["alerts_created"] += result.get("alerts_created", 0)
            total["errors"] += result.get("errors", 0)

            # Update checkpoint to this date
            scanner_id = "form4_scanner" if scanner == "form4" else "activist_scanner"
            await set_checkpoint(scanner_id, date_str)
            logger.info(f"  Checkpoint updated to {date_str}")

        except Exception as e:
            logger.error(f"  Day {date_str} failed: {e}")
            total["errors"] += 1

        current += timedelta(days=1)

        # Brief pause between days
        if current < end:
            logger.info("  Waiting 5s before next day...")
            await asyncio.sleep(5)

    logger.info(f"\n{'='*60}")
    logger.info(f"BACKFILL COMPLETE")
    for k, v in total.items():
        logger.info(f"  {k}: {v}")
    logger.info(f"{'='*60}")


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    # Suppress noisy httpx logs
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)

    parser = argparse.ArgumentParser(description="Daily backfill scanner")
    parser.add_argument("--scanner", choices=["form4", "activist"], required=True)
    parser.add_argument("--start", required=True, help="Start date YYYY-MM-DD")
    parser.add_argument("--end", required=True, help="End date YYYY-MM-DD (exclusive)")
    args = parser.parse_args()

    asyncio.run(main(args.scanner, args.start, args.end))
