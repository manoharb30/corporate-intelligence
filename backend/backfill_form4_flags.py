"""Backfill missing role flags on InsiderTransaction nodes.

The Form 4 parser already extracts is_officer / is_director / is_ten_percent_owner,
but the storage layer never persisted them. This script:

1. Queries Neo4j for all unique accession_numbers (one per Form 4 filing)
2. For each accession, fetches the Form 4 XML from EDGAR
3. Parses with the existing Form4Parser
4. Updates ALL InsiderTransaction nodes for that accession with the role flags

Standalone — does not modify any existing services or scanner code.

Usage:
    python backfill_form4_flags.py --apply
    python backfill_form4_flags.py --dry-run --limit 10
    python backfill_form4_flags.py --apply --workers 5
"""

import argparse
import asyncio
import json
import logging
import os
import sys
from datetime import datetime
from typing import Optional

import httpx

sys.path.insert(0, ".")
from app.db.neo4j_client import Neo4jClient
from ingestion.sec_edgar.parsers.form4_parser import Form4Parser

CHECKPOINT_DIR = os.path.join(os.path.dirname(__file__), "backfill_checkpoints")
ERROR_LOG_DIR = os.path.join(os.path.dirname(__file__), "backfill_errors")
CHECKPOINT_FILE = "checkpoint_form4_flags.json"
SEC_USER_AGENT = "LookInsight research@lookinsight.ai"
SEC_HTML_TIMEOUT = 15.0
SEC_REQUEST_DELAY = 1.5
DEFAULT_WORKERS = 5

os.makedirs(ERROR_LOG_DIR, exist_ok=True)
os.makedirs(CHECKPOINT_DIR, exist_ok=True)

logger = logging.getLogger("form4_flags_backfill")
logger.setLevel(logging.INFO)
console = logging.StreamHandler(stream=sys.stdout)
console.setFormatter(logging.Formatter("%(message)s"))
logger.addHandler(console)
sys.stdout.reconfigure(line_buffering=True)

parser = Form4Parser()


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


async def get_unique_accessions(only_missing: bool = True, limit: int = 0) -> list[dict]:
    """Get unique accession_numbers from InsiderTransaction nodes that need flag backfill.

    Args:
        only_missing: if True, only return accessions where role flags are NULL
        limit: 0 = no limit
    """
    where_clause = ""
    if only_missing:
        where_clause = "WHERE t.is_officer IS NULL"

    limit_clause = f"LIMIT {limit}" if limit > 0 else ""

    query = f"""
        MATCH (c:Company)-[:INSIDER_TRADE_OF]->(t:InsiderTransaction)
        {where_clause}
        WITH t.accession_number AS accession, t.insider_cik AS insider_cik, c.cik AS issuer_cik
        WHERE accession IS NOT NULL
        RETURN DISTINCT accession, insider_cik, issuer_cik
        {limit_clause}
    """
    results = await Neo4jClient.execute_query(query, {})
    return [
        {"accession": r["accession"], "insider_cik": r["insider_cik"], "issuer_cik": r["issuer_cik"]}
        for r in results
    ]


async def fetch_form4_xml(accession: str, cik: str, error_logger: logging.Logger) -> Optional[str]:
    """Fetch the Form 4 .txt file from EDGAR and extract embedded XML."""
    if not accession or not cik:
        return None

    cik_clean = cik.lstrip("0") if cik else ""
    accession_clean = accession.replace("-", "")
    if not cik_clean or not accession_clean:
        return None

    url = f"https://www.sec.gov/Archives/edgar/data/{cik_clean}/{accession_clean}/{accession}.txt"

    async with httpx.AsyncClient(
        headers={"User-Agent": SEC_USER_AGENT, "Accept-Encoding": "gzip"},
        timeout=SEC_HTML_TIMEOUT,
        follow_redirects=True,
    ) as client:
        try:
            resp = await client.get(url)
            if resp.status_code != 200:
                return None
            text = resp.text
            if "<ownershipDocument>" not in text:
                return None
            s = text.index("<ownershipDocument>")
            e = text.index("</ownershipDocument>") + len("</ownershipDocument>")
            return '<?xml version="1.0"?>\n' + text[s:e]
        except Exception as e:
            error_logger.warning(f"Fetch failed for {accession}: {type(e).__name__}: {str(e)[:100]}")
            return None


async def fetch_and_extract_flags(
    record: dict,
    sem: asyncio.Semaphore,
    error_logger: logging.Logger,
):
    """Fetch one Form 4 and extract role flags. Rate-limited by semaphore.

    Returns:
        (accession, flags_dict, error)
        flags_dict: {is_officer, is_director, is_ten_percent_owner}
        error: None on success, error string on failure
    """
    accession = record["accession"]
    # Try insider_cik first (the filer), fall back to issuer_cik
    for cik_field in ["insider_cik", "issuer_cik"]:
        cik = record.get(cik_field, "")
        if not cik:
            continue

        async with sem:
            await asyncio.sleep(SEC_REQUEST_DELAY)
            xml = await fetch_form4_xml(accession, cik, error_logger)
            if xml is None:
                continue

        try:
            result = parser.parse_form4(xml, accession, "")
        except Exception as e:
            error_logger.warning(f"Parse failed for {accession}: {type(e).__name__}: {str(e)[:100]}")
            return accession, None, "parse_error"

        if result and result.insider:
            flags = {
                "is_officer": result.insider.is_officer,
                "is_director": result.insider.is_director,
                "is_ten_percent_owner": result.insider.is_ten_percent_owner,
            }
            return accession, flags, None

    return accession, None, "fetch_failed_all_ciks"


async def update_flags(accession: str, flags: dict) -> bool:
    """Update all InsiderTransaction nodes for an accession with role flags."""
    try:
        await Neo4jClient.execute_write("""
            MATCH (t:InsiderTransaction {accession_number: $accession})
            SET t.is_officer = $is_officer,
                t.is_director = $is_director,
                t.is_ten_percent_owner = $is_ten_percent_owner
        """, {
            "accession": accession,
            "is_officer": flags["is_officer"],
            "is_director": flags["is_director"],
            "is_ten_percent_owner": flags["is_ten_percent_owner"],
        })
        return True
    except Exception as e:
        logger.warning(f"Update failed for {accession}: {e}")
        return False


async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--workers", type=int, default=DEFAULT_WORKERS, help="Parallel workers (default 5)")
    ap.add_argument("--limit", type=int, default=0, help="Limit to N accessions (0 = all)")
    ap.add_argument("--only-missing", action="store_true", default=True, help="Only process accessions missing flags (default)")
    args = ap.parse_args()

    if not args.apply and not args.dry_run:
        logger.error("Specify --apply or --dry-run")
        return

    is_apply = args.apply
    workers = max(1, min(args.workers, 8))

    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    error_log_path = os.path.join(ERROR_LOG_DIR, f"errors_form4_flags_{timestamp}.log")
    file_handler = logging.FileHandler(error_log_path)
    file_handler.setLevel(logging.WARNING)
    file_handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
    error_logger = logging.getLogger("form4_flags_backfill.errors")
    error_logger.setLevel(logging.WARNING)
    error_logger.addHandler(file_handler)

    logger.info(f"Mode: {'APPLY' if is_apply else 'DRY RUN'}")
    logger.info(f"Workers: {workers}")
    logger.info(f"Error log: {error_log_path}")

    await Neo4jClient.connect()

    # Get accessions to process
    logger.info("Querying Neo4j for accessions needing flags...")
    accessions = await get_unique_accessions(only_missing=args.only_missing, limit=args.limit)
    logger.info(f"Found {len(accessions):,} unique accessions")

    if not accessions:
        logger.info("Nothing to do.")
        await Neo4jClient.disconnect()
        return

    # Load checkpoint
    processed = load_checkpoint()
    if processed:
        before = len(accessions)
        accessions = [a for a in accessions if a["accession"] not in processed]
        logger.info(f"Checkpoint: {len(processed):,} already processed, {before - len(accessions):,} skipped, {len(accessions):,} remaining")

    if not accessions:
        logger.info("All accessions already processed!")
        await Neo4jClient.disconnect()
        return

    # Process in batches of 100 with parallel fetch
    sem = asyncio.Semaphore(workers)
    BATCH_SIZE = 100

    total_updated = 0
    total_failed = 0
    start_time = datetime.utcnow()

    for batch_start in range(0, len(accessions), BATCH_SIZE):
        batch = accessions[batch_start:batch_start + BATCH_SIZE]
        batch_num = batch_start // BATCH_SIZE + 1
        total_batches = (len(accessions) + BATCH_SIZE - 1) // BATCH_SIZE

        # Parallel fetch
        fetch_tasks = [fetch_and_extract_flags(r, sem, error_logger) for r in batch]
        results = await asyncio.gather(*fetch_tasks)

        # Sequential update (Neo4j writes serialized)
        batch_updated = 0
        batch_failed = 0
        for accession, flags, error in results:
            if error or flags is None:
                batch_failed += 1
                processed.add(accession)  # don't retry failed ones
                continue

            if is_apply:
                ok = await update_flags(accession, flags)
                if ok:
                    batch_updated += 1
                    processed.add(accession)
                else:
                    batch_failed += 1
            else:
                batch_updated += 1
                processed.add(accession)

        total_updated += batch_updated
        total_failed += batch_failed

        # Save checkpoint after each batch
        save_checkpoint(processed)

        # Progress
        elapsed = (datetime.utcnow() - start_time).total_seconds()
        done = batch_start + len(batch)
        speed = done / elapsed if elapsed > 0 else 0
        remaining = (len(accessions) - done) / speed if speed > 0 else 0
        logger.info(
            f"  Batch {batch_num}/{total_batches} ({done}/{len(accessions)}) — "
            f"updated {batch_updated} failed {batch_failed} — "
            f"total: {total_updated} updated, {total_failed} failed — "
            f"~{remaining:.0f}s remaining"
        )

    # Save final checkpoint
    save_checkpoint(processed)

    elapsed = (datetime.utcnow() - start_time).total_seconds()
    logger.info(f"""
{'=' * 60}
  FORM 4 FLAGS BACKFILL {'COMPLETE' if is_apply else 'DRY RUN'}
  Accessions processed: {len(accessions):,}
  Updated: {total_updated:,}
  Failed: {total_failed:,}
  Total time: {elapsed:.0f}s ({elapsed/60:.1f} min)
  Error log: {error_log_path}
{'=' * 60}
""")

    await Neo4jClient.disconnect()


if __name__ == "__main__":
    asyncio.run(main())
