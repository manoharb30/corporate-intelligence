"""Backfill Form 4 filings from EDGAR quarterly master index.

Usage:
    python backfill_quarterly.py --year 2024 --quarter 3 --dry-run
    python backfill_quarterly.py --year 2024 --quarter 3 --apply
    python backfill_quarterly.py --year 2024 --quarter 3 --month 7 --apply
    python backfill_quarterly.py --year 2024 --quarter 3 --month 8 --apply --workers 7
"""

import argparse
import asyncio
import json
import logging
import os
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime

import requests

sys.path.insert(0, ".")
from app.db.neo4j_client import Neo4jClient
from ingestion.sec_edgar.parsers.form4_parser import Form4Parser

EDGAR_HEADERS = {"User-Agent": "LookInsight research@lookinsight.ai"}
WORKERS = 5
CHECKPOINT_DIR = os.path.join(os.path.dirname(__file__), "backfill_checkpoints")
ERROR_LOG_DIR = os.path.join(os.path.dirname(__file__), "backfill_errors")
parser = Form4Parser()

# ── Logging setup ────────────────────────────────────────────────────────────
os.makedirs(ERROR_LOG_DIR, exist_ok=True)

logger = logging.getLogger("backfill")
logger.setLevel(logging.INFO)

console_handler = logging.StreamHandler()
console_handler.setLevel(logging.INFO)
console_handler.setFormatter(logging.Formatter("%(message)s"))
logger.addHandler(console_handler)

# File handler added per-run in main()
error_logger = logging.getLogger("backfill.errors")
error_logger.setLevel(logging.WARNING)

# ── Thread-safe rate limit flag ──────────────────────────────────────────────
rate_limit_event = threading.Event()

# ── Neo4j keepalive ──────────────────────────────────────────────────────────
_keepalive_active = False


async def _keepalive_ping():
    """Send a lightweight query every 30s to keep the Aura connection alive."""
    global _keepalive_active
    while _keepalive_active:
        try:
            await Neo4jClient.execute_query("RETURN 1")
        except Exception:
            pass
        await asyncio.sleep(30)


def checkpoint_path(year: int, quarter: int) -> str:
    os.makedirs(CHECKPOINT_DIR, exist_ok=True)
    return os.path.join(CHECKPOINT_DIR, f"checkpoint_{year}_Q{quarter}.json")


def load_checkpoint(year: int, quarter: int) -> set:
    path = checkpoint_path(year, quarter)
    if os.path.exists(path):
        with open(path) as f:
            data = json.load(f)
        return set(data.get("processed", []))
    return set()


def save_checkpoint(year: int, quarter: int, processed: set):
    path = checkpoint_path(year, quarter)
    tmp_path = path + ".tmp"
    with open(tmp_path, "w") as f:
        json.dump({
            "processed": list(processed),
            "count": len(processed),
            "last_updated": datetime.utcnow().isoformat()
        }, f)
    os.replace(tmp_path, path)  # Atomic write — prevents corruption on crash


def fetch_quarterly_index(year: int, quarter: int) -> list[dict]:
    """Fetch quarterly master.idx and return Form 4 filings."""
    url = f"https://www.sec.gov/Archives/edgar/full-index/{year}/QTR{quarter}/master.idx"
    logger.info(f"Downloading index from {url}...")
    resp = requests.get(url, headers=EDGAR_HEADERS, timeout=60)
    if resp.status_code == 429:
        logger.error("RATE LIMITED (429) on index download. Exiting.")
        return []
    if resp.status_code != 200:
        logger.error(f"Failed to fetch index: HTTP {resp.status_code}")
        return []

    filings = []
    for line in resp.text.split("\n"):
        if "|" not in line:
            continue
        parts = line.strip().split("|")
        if len(parts) < 5 or parts[2].strip() != "4":
            continue
        accession = parts[4].strip().split("/")[-1].replace(".txt", "")
        filings.append({
            "cik": parts[0].strip(),
            "company_name": parts[1].strip(),
            "date_filed": parts[3].strip(),
            "accession": accession,
            "txt_url": f"https://www.sec.gov/Archives/{parts[4].strip()}",
        })
    return filings


def fetch_and_parse(filing: dict) -> dict:
    """Fetch one filing, extract XML, parse."""
    if rate_limit_event.is_set():
        return {"filing": filing, "result": None, "rate_limited": True, "error": None}
    try:
        time.sleep(1.0)
        resp = requests.get(filing["txt_url"], headers=EDGAR_HEADERS, timeout=15)
        if resp.status_code == 429:
            rate_limit_event.set()
            return {"filing": filing, "result": None, "rate_limited": True, "error": "HTTP 429"}
        if resp.status_code != 200:
            return {
                "filing": filing, "result": None, "rate_limited": False,
                "error": f"HTTP {resp.status_code}"
            }
        if "<ownershipDocument>" not in resp.text:
            return {
                "filing": filing, "result": None, "rate_limited": False,
                "error": "No ownershipDocument in response"
            }
        s = resp.text.index("<ownershipDocument>")
        e = resp.text.index("</ownershipDocument>") + len("</ownershipDocument>")
        xml = '<?xml version="1.0"?>\n' + resp.text[s:e]
        result = parser.parse_form4(xml, filing["accession"], filing["date_filed"])
        if not result:
            return {
                "filing": filing, "result": None, "rate_limited": False,
                "error": "Parser returned None"
            }
        ps = [t for t in result.transactions if t.transaction_code in ("P", "S")]
        if not ps:
            return {"filing": filing, "result": None, "rate_limited": False, "error": None}  # No P/S — normal skip
        return {"filing": filing, "result": result, "rate_limited": False, "error": None}
    except requests.Timeout:
        return {
            "filing": filing, "result": None, "rate_limited": False,
            "error": f"Timeout fetching {filing['txt_url']}"
        }
    except Exception as exc:
        return {
            "filing": filing, "result": None, "rate_limited": False,
            "error": f"{type(exc).__name__}: {str(exc)[:200]}"
        }


async def store_batch(batch: list[dict], max_retries: int = 2) -> tuple[int, int]:
    """Store a batch of parsed results in Neo4j.

    Returns:
        (stored_count, failed_count)
    """
    stored = 0
    failed = 0
    for item in batch:
        result = item["result"]
        filing = item["filing"]
        issuer_cik = result.issuer_cik.zfill(10) if result.issuer_cik else filing["cik"].zfill(10)
        issuer_name = result.issuer_name or filing["company_name"]

        for idx, txn in enumerate(result.transactions):
            if txn.transaction_code not in ("P", "S"):
                continue

            txn_id = f"{result.accession_number}_{idx}"
            price_source = "filing"

            pct = None
            try:
                if txn.transaction_code == "S" and (txn.shares_after_transaction + txn.shares) > 0:
                    pct = round(txn.shares / (txn.shares_after_transaction + txn.shares) * 100, 1)
                elif txn.transaction_code == "P" and txn.shares_after_transaction > 0:
                    pct = round(txn.shares / txn.shares_after_transaction * 100, 1)
            except (TypeError, ZeroDivisionError):
                pct = None

            params = {
                "cik": issuer_cik, "company_name": issuer_name,
                "txn_id": txn_id, "accession": result.accession_number,
                "filing_date": filing["date_filed"], "txn_date": txn.transaction_date,
                "code": txn.transaction_code, "type": txn.transaction_type,
                "security": txn.security_title, "shares": txn.shares,
                "price": txn.price_per_share, "total": txn.total_value,
                "after": txn.shares_after_transaction, "own_type": txn.ownership_type,
                "deriv": txn.is_derivative, "name": result.insider.name,
                "title": result.insider.title, "insider_cik": result.insider.cik,
                "is_plan": result.is_10b5_1, "price_source": price_source, "pct": pct,
                "is_officer": result.insider.is_officer,
                "is_director": result.insider.is_director,
                "is_ten_percent_owner": result.insider.is_ten_percent_owner,
            }

            query = """
                MERGE (c:Company {cik: $cik})
                ON CREATE SET c.name = $company_name
                SET c.name = COALESCE(c.name, $company_name)
                MERGE (t:InsiderTransaction {id: $txn_id})
                SET t.accession_number = $accession, t.filing_date = $filing_date,
                    t.transaction_date = $txn_date, t.transaction_code = $code,
                    t.transaction_type = $type, t.security_title = $security,
                    t.shares = $shares, t.price_per_share = $price,
                    t.total_value = $total, t.shares_after_transaction = $after,
                    t.ownership_type = $own_type, t.is_derivative = $deriv,
                    t.insider_name = $name, t.insider_title = $title,
                    t.insider_cik = $insider_cik, t.is_10b5_1 = $is_plan,
                    t.is_officer = $is_officer, t.is_director = $is_director,
                    t.is_ten_percent_owner = $is_ten_percent_owner,
                    t.price_source = $price_source, t.pct_of_position_traded = $pct
                MERGE (c)-[:INSIDER_TRADE_OF]->(t)
                WITH t
                MERGE (p:Person {normalized_name: toLower($name)})
                ON CREATE SET p.name = $name, p.id = randomUUID()
                MERGE (p)-[:TRADED_BY]->(t)
            """

            for attempt in range(max_retries + 1):
                try:
                    await Neo4jClient.execute_query(query, params)
                    stored += 1
                    break
                except Exception as exc:
                    if attempt < max_retries:
                        error_logger.warning(
                            f"Neo4j retry {attempt + 1}/{max_retries} for {txn_id}: "
                            f"{type(exc).__name__}: {str(exc)[:100]}"
                        )
                        await asyncio.sleep(1.0 * (attempt + 1))  # Backoff
                    else:
                        error_logger.error(
                            f"FAILED to store {txn_id} after {max_retries + 1} attempts: "
                            f"{type(exc).__name__}: {str(exc)[:200]}"
                        )
                        failed += 1

    return stored, failed


async def verify_batch_stored(accession_numbers: list[str]) -> int:
    """Verify that transactions from a batch actually exist in Neo4j.

    Returns:
        Number of transactions found in Neo4j for the given accessions.
    """
    try:
        result = await Neo4jClient.execute_query("""
            MATCH (t:InsiderTransaction)
            WHERE t.accession_number IN $accessions
            RETURN count(t) as cnt
        """, {"accessions": accession_numbers})
        if result and len(result) > 0:
            return result[0]["cnt"]
    except Exception as exc:
        error_logger.warning(f"Verification query failed: {type(exc).__name__}: {str(exc)[:100]}")
    return -1  # Unknown — verification failed


async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--year", type=int, required=True)
    ap.add_argument("--quarter", type=int, required=True)
    ap.add_argument("--month", type=int, default=None, help="Filter to specific month (e.g., 7 for July)")
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--workers", type=int, default=WORKERS, help="Number of fetch workers (default: 5)")
    args = ap.parse_args()

    workers = min(args.workers, 8)  # Cap at 8 to stay under SEC 10/sec limit

    is_apply = args.apply
    if not is_apply and not args.dry_run:
        logger.error("Specify --apply or --dry-run")
        return

    mode = "APPLY" if is_apply else "DRY RUN"

    # Validate month if provided
    if args.month:
        quarter_months = {1: [1, 2, 3], 2: [4, 5, 6], 3: [7, 8, 9], 4: [10, 11, 12]}
        valid_months = quarter_months.get(args.quarter, [])
        if args.month not in valid_months:
            logger.error(f"Month {args.month} is not in Q{args.quarter} (valid: {valid_months})")
            return

    # Setup per-run error log file
    run_timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    month_suffix = f"_M{args.month}" if args.month else ""
    error_log_path = os.path.join(
        ERROR_LOG_DIR, f"errors_{args.year}_Q{args.quarter}{month_suffix}_{run_timestamp}.log"
    )
    file_handler = logging.FileHandler(error_log_path)
    file_handler.setLevel(logging.WARNING)
    file_handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
    error_logger.addHandler(file_handler)

    month_label = f" (month {args.month} only)" if args.month else ""
    logger.info(f"Mode: {mode}")
    logger.info(f"Quarter: {args.year} Q{args.quarter}{month_label}")
    logger.info(f"Workers: {workers}")
    logger.info(f"Error log: {error_log_path}")

    # Fetch quarterly index
    filings = fetch_quarterly_index(args.year, args.quarter)
    logger.info(f"Form 4 filings in index: {len(filings):,}")

    if not filings:
        return

    # Filter by month if specified
    if args.month:
        month_prefix = f"{args.year}-{args.month:02d}"
        filings = [f for f in filings if f["date_filed"].startswith(month_prefix)]
        logger.info(f"Filtered to month {args.month}: {len(filings):,} filings")

    # Load checkpoint — skip already-processed filings
    processed = load_checkpoint(args.year, args.quarter)
    if processed:
        before = len(filings)
        filings = [f for f in filings if f["accession"] not in processed]
        logger.info(
            f"Checkpoint: {len(processed):,} already processed, "
            f"{before - len(filings):,} skipped, {len(filings):,} remaining"
        )

    if not filings:
        logger.info("All filings already processed!")
        return

    if is_apply:
        await Neo4jClient.connect()
        # Start keepalive task to prevent Aura idle disconnects
        global _keepalive_active
        _keepalive_active = True
        asyncio.create_task(_keepalive_ping())
        logger.info("Neo4j keepalive started (30s interval)")

    # ── Fetch + parse + store incrementally ──────────────────────────────────
    total_filings = len(filings) + len(processed)
    logger.info(f"Fetching and parsing with {workers} workers...")
    start = time.time()

    pending_batch = []
    pending_accessions = []
    total_ps_filings = 0
    total_ps_trades = 0
    stored = 0
    store_failed = 0
    fetch_errors = 0
    skipped = 0
    done = len(processed)
    store_batches = 0
    verified_count = 0

    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = {executor.submit(fetch_and_parse, f): f for f in filings}
        for future in as_completed(futures):
            result = future.result()

            if result.get("rate_limited"):
                executor.shutdown(wait=False, cancel_futures=True)
                logger.warning("\n  *** RATE LIMITED BY SEC — stopping immediately ***")
                break

            accession = result["filing"]["accession"]

            # Log errors (but don't stop)
            if result["error"]:
                error_logger.warning(
                    f"Fetch error [{accession}] CIK={result['filing']['cik']}: {result['error']}"
                )
                fetch_errors += 1

            if result["result"]:
                total_ps_filings += 1
                ps_count = sum(1 for t in result["result"].transactions if t.transaction_code in ("P", "S"))
                total_ps_trades += ps_count
                pending_batch.append(result)
                pending_accessions.append(accession)

                # Store every 100 parsed results
                if is_apply and len(pending_batch) >= 100:
                    batch_stored, batch_failed = await store_batch(pending_batch)
                    stored += batch_stored
                    store_failed += batch_failed
                    store_batches += 1

                    # Verify batch landed in Neo4j
                    batch_accessions = [item["result"].accession_number for item in pending_batch]
                    unique_accessions = list(set(batch_accessions))
                    neo4j_count = await verify_batch_stored(unique_accessions)
                    if neo4j_count >= 0:
                        verified_count += neo4j_count
                        if neo4j_count < batch_stored:
                            error_logger.warning(
                                f"Verification mismatch: stored {batch_stored} but Neo4j has {neo4j_count} "
                                f"for batch {store_batches}"
                            )

                    processed.update(pending_accessions)
                    save_checkpoint(args.year, args.quarter, processed)
                    pending_batch = []
                    pending_accessions = []
            else:
                processed.add(accession)
                if not result["error"]:  # No error means normal skip (no P/S trades)
                    skipped += 1

            done += 1
            if done % 50 == 0:
                elapsed = round(time.time() - start, 1)
                remaining_count = total_filings - done
                pct = done / total_filings * 100
                speed = (done - len(processed) + len(filings)) / elapsed if elapsed > 0 else 0
                remaining_time = remaining_count / speed if speed > 0 else 0
                logger.info(
                    f"  {done:>6,}/{total_filings:,} ({pct:.0f}%) — "
                    f"{total_ps_filings} P/S found — "
                    f"{stored:,} stored ({store_failed} failed) — "
                    f"{elapsed:.0f}s elapsed — ~{remaining_time:.0f}s remaining"
                )

    # Store any remaining batch
    if is_apply and pending_batch:
        batch_stored, batch_failed = await store_batch(pending_batch)
        stored += batch_stored
        store_failed += batch_failed
        store_batches += 1
        processed.update(pending_accessions)

    # Save final checkpoint
    save_checkpoint(args.year, args.quarter, processed)

    if not is_apply:
        stored = total_ps_trades

    total_time = round(time.time() - start, 1)
    hit_rate_limit = rate_limit_event.is_set()

    # ── Summary ──────────────────────────────────────────────────────────────
    summary = f"""
{'=' * 60}
  BACKFILL {'STOPPED' if hit_rate_limit else 'COMPLETE'} ({mode})
  Quarter: {args.year} Q{args.quarter}{month_label}
  Filings: {total_filings:,} ({len(processed):,} checkpointed)
  With P/S: {total_ps_filings:,} ({total_ps_trades:,} trades)
  {'Stored' if is_apply else 'Would store'}: {stored:,}
  Store failures: {store_failed:,}
  Fetch errors: {fetch_errors:,}
  Skipped (no P/S): {skipped:,}
  Verified in Neo4j: {verified_count:,}
  Total time: {total_time}s ({total_time/60:.1f} min)
  Error log: {error_log_path}
{'=' * 60}
"""
    logger.info(summary)

    # Log summary to error file too for record keeping
    error_logger.info(summary)

    if store_failed > 0:
        logger.warning(
            f"  {store_failed} trades failed to store — check {error_log_path}"
        )

    if fetch_errors > 0:
        logger.warning(
            f"  {fetch_errors} fetch errors — check {error_log_path}"
        )

    if is_apply:
        # Final verification — total count in Neo4j for this quarter
        try:
            quarter_start = f"{args.year}-{(args.quarter - 1) * 3 + 1:02d}-01"
            quarter_end = f"{args.year}-{args.quarter * 3:02d}-31"
            result = await Neo4jClient.execute_query("""
                MATCH (t:InsiderTransaction)
                WHERE t.filing_date >= $start AND t.filing_date <= $end
                  AND t.transaction_code IN ['P', 'S']
                RETURN count(t) as total
            """, {"start": quarter_start, "end": quarter_end})
            if result and len(result) > 0:
                neo4j_total = result[0]["total"]
                logger.info(f"  Neo4j verification: {neo4j_total:,} P/S trades for {args.year} Q{args.quarter}")
                if neo4j_total < stored:
                    error_logger.error(
                        f"VERIFICATION FAILED: Stored {stored:,} but Neo4j only has {neo4j_total:,} "
                        f"for {args.year} Q{args.quarter}"
                    )
        except Exception as exc:
            error_logger.warning(f"Final verification failed: {type(exc).__name__}: {str(exc)[:100]}")

        _keepalive_active = False
        await Neo4jClient.disconnect()


if __name__ == "__main__":
    asyncio.run(main())
