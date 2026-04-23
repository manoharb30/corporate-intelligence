"""Historical 13D backfill — fetches SC 13D + SC 13D/A filings in date chunks.

Standalone script. Does NOT touch the existing scanner. Reuses:
- ingestion.sec_edgar.edgar_client.SECEdgarClient.get_recent_13d_filers (already fixed)
- ingestion.sec_edgar.parsers.schedule13_parser.parse_schedule_13d
- app.services.activist_filing_service.ActivistFilingService.store_filing (with ticker lookup)

Walks back through time in 30-day windows. Checkpoints accession_numbers after each window.

Usage:
    python backfill_13d_historical.py --start 2024-01-01 --end 2024-12-31 --apply
    python backfill_13d_historical.py --start 2024-01-01 --end 2024-01-31 --dry-run
"""

import argparse
import asyncio
import json
import logging
import os
import sys
from datetime import datetime, timedelta
from typing import Optional

import httpx

sys.path.insert(0, ".")
from app.db.neo4j_client import Neo4jClient
from app.services.activist_filing_service import ActivistFilingService
from ingestion.sec_edgar.edgar_client import SECEdgarClient
from ingestion.sec_edgar.parsers.schedule13_parser import parse_schedule_13d

CHECKPOINT_DIR = os.path.join(os.path.dirname(__file__), "backfill_checkpoints")
ERROR_LOG_DIR = os.path.join(os.path.dirname(__file__), "backfill_errors")
CHECKPOINT_FILE = "checkpoint_13d_historical.json"
SEC_USER_AGENT = "LookInsight research@lookinsight.ai"
SEC_HTML_TIMEOUT = 15.0
SEC_REQUEST_DELAY = 1.5  # seconds between SEC HTML fetches per worker
WINDOW_DAYS = 30  # process 30 days at a time
DEFAULT_WORKERS = 5  # parallel fetch workers (5 workers × 1.5s = 3.3 req/sec, well under SEC's 10/sec)

os.makedirs(ERROR_LOG_DIR, exist_ok=True)
os.makedirs(CHECKPOINT_DIR, exist_ok=True)

logger = logging.getLogger("13d_backfill")
logger.setLevel(logging.INFO)
console = logging.StreamHandler(stream=sys.stdout)
console.setFormatter(logging.Formatter("%(message)s"))
logger.addHandler(console)
sys.stdout.reconfigure(line_buffering=True)


def checkpoint_path() -> str:
    return os.path.join(CHECKPOINT_DIR, CHECKPOINT_FILE)


def load_checkpoint() -> set:
    path = checkpoint_path()
    if os.path.exists(path):
        with open(path) as f:
            data = json.load(f)
        return set(data.get("processed", []))
    return set()


def save_checkpoint(processed: set):
    path = checkpoint_path()
    tmp = path + ".tmp"
    with open(tmp, "w") as f:
        json.dump({
            "processed": list(processed),
            "count": len(processed),
            "last_updated": datetime.utcnow().isoformat(),
        }, f)
    os.replace(tmp, path)


async def fetch_filing_html(filing: dict) -> Optional[str]:
    """Fetch the rendered HTML for a single 13D filing from SEC."""
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
            return None
        except Exception:
            return None


async def fetch_and_parse_one(
    filing: dict,
    sem: asyncio.Semaphore,
    error_logger: logging.Logger,
):
    """Fetch HTML for one filing, parse it, return result. Rate-limited by semaphore."""
    async with sem:
        await asyncio.sleep(SEC_REQUEST_DELAY)
        html = await fetch_filing_html(filing)
        if html is None:
            error_logger.warning(f"Fetch error for {filing['accession_number']}")
            return filing, None, "fetch_error"
        try:
            result = parse_schedule_13d(html, metadata=filing)
            return filing, result, None
        except Exception as e:
            error_logger.warning(f"Parse error for {filing['accession_number']}: {type(e).__name__}: {str(e)[:100]}")
            return filing, None, "parse_error"


async def process_window(
    start_date: str,
    end_date: str,
    processed: set,
    is_apply: bool,
    error_logger: logging.Logger,
    workers: int = DEFAULT_WORKERS,
) -> dict:
    """Fetch + parse + store all 13D filings in a date window using parallel workers.

    Returns counts dict: {discovered, stored, skipped, errors, originals}
    """
    counts = {"discovered": 0, "stored": 0, "skipped": 0, "errors": 0, "originals": 0}

    # Use the existing SECEdgarClient with our fixed form filter
    client = SECEdgarClient(user_agent=SEC_USER_AGENT)
    try:
        # Override the search to use our window
        all_filings = []
        seen = set()
        from_idx = 0
        while True:
            params = {
                "forms": "SCHEDULE 13D",  # the fix — captures both originals and amendments
                "dateRange": "custom",
                "startdt": start_date,
                "enddt": end_date,
                "from": str(from_idx),
            }
            url = f"{client.FULL_TEXT_SEARCH_URL}?{httpx.QueryParams(params)}"
            try:
                response = await client._request(url)
                data = response.json()
                hits = data.get("hits", {}).get("hits", [])
                if not hits:
                    break

                for hit in hits:
                    source = hit.get("_source", {})
                    adsh = source.get("adsh", "")
                    if not adsh or adsh in seen:
                        continue
                    seen.add(adsh)

                    ciks = source.get("ciks", [])
                    display_names = source.get("display_names", [])
                    if len(ciks) < 2:
                        continue

                    target_cik = ciks[0]
                    filer_cik = ciks[1] if len(ciks) > 1 else ""

                    import re as _re
                    def clean_name(raw: str) -> str:
                        n = _re.sub(r"\s*\(CIK[^)]*\)", "", raw)
                        n = _re.sub(r"\s*\([A-Z0-9,\s]+\)\s*$", "", n).strip()
                        return n

                    target_name = clean_name(display_names[0]) if display_names else f"CIK {target_cik}"
                    filer_name = clean_name(display_names[1]) if len(display_names) > 1 else f"CIK {filer_cik}"

                    xsl = source.get("xsl", "")
                    primary_doc = f"{xsl}/primary_doc.xml" if xsl else "primary_doc.xml"

                    all_filings.append({
                        "accession_number": adsh,
                        "filing_type": source.get("file_type", "SCHEDULE 13D"),
                        "filing_date": source.get("file_date", ""),
                        "target_cik": target_cik,
                        "target_name": target_name,
                        "filer_cik": filer_cik,
                        "filer_name": filer_name,
                        "primary_document": primary_doc,
                    })

                if len(hits) >= 100:
                    from_idx += 100
                else:
                    break
            except Exception as e:
                error_logger.warning(f"EFTS error in window {start_date} to {end_date}: {e}")
                break
    finally:
        await client.close()

    counts["discovered"] = len(all_filings)

    # Filter out already-processed
    new_filings = [f for f in all_filings if f["accession_number"] not in processed]
    counts["skipped"] = len(all_filings) - len(new_filings)

    if not new_filings:
        return counts

    # Parallel fetch + parse using semaphore
    sem = asyncio.Semaphore(workers)
    fetch_tasks = [fetch_and_parse_one(f, sem, error_logger) for f in new_filings]
    fetched = await asyncio.gather(*fetch_tasks)

    # Now store sequentially (Neo4j writes should be serial to avoid contention)
    for filing, result, error in fetched:
        if error or result is None:
            counts["errors"] += 1
            processed.add(filing["accession_number"])
            continue

        if filing.get("filing_type") == "SCHEDULE 13D":
            counts["originals"] += 1

        if is_apply:
            stored_acc = await ActivistFilingService.store_filing(result)
            if stored_acc:
                counts["stored"] += 1
                processed.add(filing["accession_number"])
            else:
                counts["errors"] += 1
                error_logger.warning(f"Store failed for {filing['accession_number']}")
                processed.add(filing["accession_number"])
        else:
            counts["stored"] += 1
            processed.add(filing["accession_number"])

    return counts


def parse_date(s: str) -> datetime:
    return datetime.strptime(s, "%Y-%m-%d")


async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--start", required=True, help="Start date YYYY-MM-DD")
    ap.add_argument("--end", required=True, help="End date YYYY-MM-DD")
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--window-days", type=int, default=WINDOW_DAYS, help="Days per chunk (default 30)")
    ap.add_argument("--workers", type=int, default=DEFAULT_WORKERS, help=f"Parallel workers (default {DEFAULT_WORKERS})")
    args = ap.parse_args()

    if not args.apply and not args.dry_run:
        logger.error("Specify --apply or --dry-run")
        return

    is_apply = args.apply
    start_dt = parse_date(args.start)
    end_dt = parse_date(args.end)

    if start_dt > end_dt:
        logger.error("Start date must be before end date")
        return

    # Setup error log
    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    error_log_path = os.path.join(ERROR_LOG_DIR, f"errors_13d_historical_{timestamp}.log")
    file_handler = logging.FileHandler(error_log_path)
    file_handler.setLevel(logging.WARNING)
    file_handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
    error_logger = logging.getLogger("13d_backfill.errors")
    error_logger.setLevel(logging.WARNING)
    error_logger.addHandler(file_handler)

    workers = max(1, min(args.workers, 8))
    logger.info(f"Mode: {'APPLY' if is_apply else 'DRY RUN'}")
    logger.info(f"Date range: {args.start} to {args.end}")
    logger.info(f"Window: {args.window_days} days | Workers: {workers}")
    logger.info(f"Error log: {error_log_path}")

    # Load checkpoint
    processed = load_checkpoint()
    logger.info(f"Checkpoint: {len(processed):,} already processed")

    if is_apply:
        await Neo4jClient.connect()

    # Walk through windows from end_date back to start_date
    total = {"discovered": 0, "stored": 0, "skipped": 0, "errors": 0, "originals": 0}
    window_count = 0

    current_end = end_dt
    while current_end >= start_dt:
        current_start = max(current_end - timedelta(days=args.window_days - 1), start_dt)
        window_count += 1
        win_start_str = current_start.strftime("%Y-%m-%d")
        win_end_str = current_end.strftime("%Y-%m-%d")

        logger.info(f"\n[Window {window_count}] {win_start_str} to {win_end_str}")
        counts = await process_window(win_start_str, win_end_str, processed, is_apply, error_logger, workers=workers)

        for k in total:
            total[k] += counts.get(k, 0)

        logger.info(
            f"  discovered={counts['discovered']} stored={counts['stored']} "
            f"originals={counts['originals']} skipped={counts['skipped']} errors={counts['errors']}"
        )

        # Save checkpoint after each window
        save_checkpoint(processed)

        # Move to next window
        current_end = current_start - timedelta(days=1)

    logger.info(f"""
{'=' * 60}
  13D BACKFILL {'COMPLETE' if is_apply else 'DRY RUN'}
  Date range: {args.start} to {args.end}
  Windows processed: {window_count}
  Discovered: {total['discovered']:,}
  Originals: {total['originals']:,}
  Stored: {total['stored']:,}
  Skipped (already processed): {total['skipped']:,}
  Errors: {total['errors']:,}
  Error log: {error_log_path}
{'=' * 60}
""")

    if is_apply:
        await Neo4jClient.disconnect()


if __name__ == "__main__":
    asyncio.run(main())
