"""
8-K Event backfill script - discovers and scans 8-K filers one day at a time.

Usage:
    cd backend
    source venv/bin/activate
    python backfill_8k.py --start 2026-02-25 --end 2026-03-08
"""

import argparse
import asyncio
import logging
from datetime import datetime, timedelta

import httpx

from app.db.neo4j_client import Neo4jClient
from app.services.feed_service import FeedService
from ingestion.sec_edgar.edgar_client import SECEdgarClient

logger = logging.getLogger(__name__)

INTER_COMPANY_DELAY = 0.5  # seconds between companies


async def discover_8k_filers_for_day(date_str: str) -> list[dict]:
    """Discover companies that filed 8-Ks on a specific date."""
    client = SECEdgarClient()
    next_date = (datetime.strptime(date_str, "%Y-%m-%d") + timedelta(days=1)).strftime("%Y-%m-%d")
    seen_ciks = {}
    from_idx = 0

    try:
        while True:
            params = {
                "forms": "8-K",
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
                names = source.get("display_names", [])
                for i, cik in enumerate(ciks):
                    if cik not in seen_ciks:
                        seen_ciks[cik] = names[i] if i < len(names) else ""
            from_idx += len(hits)
            if len(hits) < 100:
                break
    finally:
        await client.close()

    return [{"cik": cik, "name": name} for cik, name in seen_ciks.items()]


async def filter_already_have_events(filers: list[dict], date_str: str) -> list[dict]:
    """Skip companies that already have events filed on/after this date."""
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
        {"ciks": ciks, "date": date_str},
    )
    new_ciks = {r["cik"] for r in results}
    filtered = [f for f in filers if f["cik"] in new_ciks]
    logger.info(
        f"  Filtered {len(filers)} -> {len(filtered)} need scanning "
        f"({len(filers) - len(filtered)} already have events)"
    )
    return filtered


async def run_8k_one_day(date_str: str) -> dict:
    """Scan 8-K filers for a single day."""
    counts = {
        "companies_discovered": 0,
        "companies_scanned": 0,
        "events_stored": 0,
        "errors": 0,
    }

    # 1. Discover filers
    filers = await discover_8k_filers_for_day(date_str)
    counts["companies_discovered"] = len(filers)
    logger.info(f"  Discovered {len(filers)} 8-K filers for {date_str}")

    if not filers:
        return counts

    # 2. Filter already scanned
    await Neo4jClient.reconnect()
    filers = await filter_already_have_events(filers, date_str)

    if not filers:
        return counts

    # 3. Scan each company
    await Neo4jClient.reconnect()
    for i, filer in enumerate(filers):
        try:
            result = await FeedService.scan_and_store_company(
                cik=filer["cik"],
                company_name=filer["name"],
                limit=5,
            )
            counts["companies_scanned"] += 1
            stored = result.get("events_stored", 0)
            counts["events_stored"] += stored
            if stored > 0:
                logger.info(
                    f"    [{counts['companies_scanned']}/{len(filers)}] "
                    f"{filer['name']}: {stored} events"
                )
        except Exception as e:
            counts["errors"] += 1
            logger.error(f"    Error: {filer['name']}: {e}")

        if i < len(filers) - 1:
            await asyncio.sleep(INTER_COMPANY_DELAY)

        # Reconnect every 100 companies to avoid Neo4j timeout
        if (i + 1) % 100 == 0:
            await Neo4jClient.reconnect()

    return counts


async def main(start_date: str, end_date: str):
    await Neo4jClient.connect()

    current = datetime.strptime(start_date, "%Y-%m-%d")
    end = datetime.strptime(end_date, "%Y-%m-%d")

    total = {
        "days_processed": 0,
        "companies_scanned": 0,
        "events_stored": 0,
        "errors": 0,
    }

    while current < end:
        date_str = current.strftime("%Y-%m-%d")
        logger.info(f"\n{'='*60}")
        logger.info(f"Processing 8-K for {date_str}")
        logger.info(f"{'='*60}")

        try:
            result = await run_8k_one_day(date_str)
            total["days_processed"] += 1
            total["companies_scanned"] += result.get("companies_scanned", 0)
            total["events_stored"] += result.get("events_stored", 0)
            total["errors"] += result.get("errors", 0)
            logger.info(f"  Day complete: {result['companies_scanned']} scanned, {result['events_stored']} events")
        except Exception as e:
            logger.error(f"  Day {date_str} failed: {e}")
            total["errors"] += 1

        current += timedelta(days=1)

        if current < end:
            logger.info("  Waiting 5s before next day...")
            await asyncio.sleep(5)

    logger.info(f"\n{'='*60}")
    logger.info("8-K BACKFILL COMPLETE")
    for k, v in total.items():
        logger.info(f"  {k}: {v}")
    logger.info(f"{'='*60}")


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)

    parser = argparse.ArgumentParser(description="8-K Event backfill")
    parser.add_argument("--start", required=True, help="Start date YYYY-MM-DD")
    parser.add_argument("--end", required=True, help="End date YYYY-MM-DD (exclusive)")
    args = parser.parse_args()

    asyncio.run(main(args.start, args.end))
