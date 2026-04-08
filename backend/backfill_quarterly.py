"""Backfill a full quarter of Form 4 filings from EDGAR quarterly master index.

Usage:
    python backfill_quarterly.py --year 2024 --quarter 4 --dry-run
    python backfill_quarterly.py --year 2024 --quarter 4 --apply
"""

import argparse
import asyncio
import json
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests

sys.path.insert(0, ".")
from app.db.neo4j_client import Neo4jClient
from ingestion.sec_edgar.parsers.form4_parser import Form4Parser

EDGAR_HEADERS = {"User-Agent": "LookInsight research@lookinsight.ai"}
WORKERS = 5
CHECKPOINT_DIR = os.path.join(os.path.dirname(__file__), "backfill_checkpoints")
parser = Form4Parser()


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
    with open(path, "w") as f:
        json.dump({"processed": list(processed), "count": len(processed)}, f)


def fetch_quarterly_index(year: int, quarter: int) -> list[dict]:
    """Fetch quarterly master.idx and return Form 4 filings."""
    url = f"https://www.sec.gov/Archives/edgar/full-index/{year}/QTR{quarter}/master.idx"
    print(f"Downloading index from {url}...", flush=True)
    resp = requests.get(url, headers=EDGAR_HEADERS, timeout=60)
    if resp.status_code == 429:
        print(f"RATE LIMITED (429) on index download. Exiting.", flush=True)
        return []
    if resp.status_code != 200:
        print(f"Failed to fetch index: HTTP {resp.status_code}", flush=True)
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


rate_limited = False

def fetch_and_parse(filing: dict) -> dict:
    """Fetch one filing, extract XML, parse."""
    global rate_limited
    if rate_limited:
        return {"filing": filing, "result": None, "rate_limited": True}
    try:
        time.sleep(1.0)  # 1 second delay per request — stays well under SEC 10/sec limit
        resp = requests.get(filing["txt_url"], headers=EDGAR_HEADERS, timeout=15)
        if resp.status_code == 429:
            rate_limited = True
            return {"filing": filing, "result": None, "rate_limited": True}
        if resp.status_code != 200 or "<ownershipDocument>" not in resp.text:
            return {"filing": filing, "result": None, "rate_limited": False}
        s = resp.text.index("<ownershipDocument>")
        e = resp.text.index("</ownershipDocument>") + len("</ownershipDocument>")
        xml = '<?xml version="1.0"?>\n' + resp.text[s:e]
        result = parser.parse_form4(xml, filing["accession"], filing["date_filed"])
        if not result:
            return {"filing": filing, "result": None, "rate_limited": False}
        ps = [t for t in result.transactions if t.transaction_code in ("P", "S")]
        if not ps:
            return {"filing": filing, "result": None, "rate_limited": False}
        return {"filing": filing, "result": result, "rate_limited": False}
    except Exception:
        return {"filing": filing, "result": None, "rate_limited": False}


async def store_batch(batch: list[dict]) -> int:
    """Store a batch of parsed results in Neo4j."""
    stored = 0
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
            except Exception:
                pass

            try:
                await Neo4jClient.execute_query("""
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
                        t.price_source = $price_source, t.pct_of_position_traded = $pct
                    MERGE (c)-[:INSIDER_TRADE_OF]->(t)
                    WITH t
                    MERGE (p:Person {normalized_name: toLower($name)})
                    ON CREATE SET p.name = $name, p.id = randomUUID()
                    MERGE (p)-[:TRADED_BY]->(t)
                """, {
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
                })
                stored += 1
            except Exception:
                pass

    return stored


async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--year", type=int, required=True)
    ap.add_argument("--quarter", type=int, required=True)
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    is_apply = args.apply
    if not is_apply and not args.dry_run:
        print("Specify --apply or --dry-run")
        return

    mode = "APPLY" if is_apply else "DRY RUN"
    print(f"Mode: {mode}", flush=True)
    print(f"Quarter: {args.year} Q{args.quarter}", flush=True)

    # Fetch quarterly index
    print(f"Fetching quarterly index...", flush=True)
    filings = fetch_quarterly_index(args.year, args.quarter)
    print(f"Form 4 filings: {len(filings):,}", flush=True)

    if not filings:
        return

    # Load checkpoint — skip already-processed filings
    processed = load_checkpoint(args.year, args.quarter)
    if processed:
        before = len(filings)
        filings = [f for f in filings if f["accession"] not in processed]
        print(f"Checkpoint: {len(processed):,} already processed, {before - len(filings):,} skipped, {len(filings):,} remaining", flush=True)

    if not filings:
        print("All filings already processed!", flush=True)
        return

    if is_apply:
        await Neo4jClient.connect()

    # Fetch + parse + store incrementally
    total_filings = len(filings) + len(processed)
    print(f"Fetching and parsing with {WORKERS} workers...", flush=True)
    start = time.time()

    pending_batch = []
    pending_accessions = []
    total_ps_filings = 0
    total_ps_trades = 0
    stored = 0
    skipped = 0
    done = len(processed)
    store_batches = 0

    hit_rate_limit = False
    with ThreadPoolExecutor(max_workers=WORKERS) as executor:
        futures = {executor.submit(fetch_and_parse, f): f for f in filings}
        for future in as_completed(futures):
            result = future.result()
            if result.get("rate_limited"):
                hit_rate_limit = True
                executor.shutdown(wait=False, cancel_futures=True)
                print(f"\n  *** RATE LIMITED BY SEC — stopping immediately ***", flush=True)
                break
            accession = result["filing"]["accession"]
            if result["result"]:
                total_ps_filings += 1
                total_ps_trades += sum(1 for t in result["result"].transactions if t.transaction_code in ("P", "S"))
                pending_batch.append(result)
                pending_accessions.append(accession)
                # Store every 100 parsed results
                if is_apply and len(pending_batch) >= 100:
                    await Neo4jClient.reconnect()
                    batch_stored = await store_batch(pending_batch)
                    stored += batch_stored
                    store_batches += 1
                    processed.update(pending_accessions)
                    save_checkpoint(args.year, args.quarter, processed)
                    pending_batch = []
                    pending_accessions = []
            else:
                processed.add(accession)
                skipped += 1
            done += 1
            if done % 50 == 0:
                elapsed = round(time.time() - start, 1)
                remaining_count = total_filings - done
                pct = done / total_filings * 100
                speed = (done - len(processed) + len(processed)) / elapsed if elapsed > 0 else 0
                remaining_time = remaining_count / speed if speed > 0 else 0
                print(f"  {done:>6,}/{total_filings:,} ({pct:.0f}%) — {total_ps_filings} P/S found — {stored:,} stored — {elapsed:.0f}s elapsed — ~{remaining_time:.0f}s remaining", flush=True)

    # Store any remaining batch
    if is_apply and pending_batch:
        await Neo4jClient.reconnect()
        batch_stored = await store_batch(pending_batch)
        stored += batch_stored
        store_batches += 1
        processed.update(pending_accessions)

    # Save final checkpoint
    save_checkpoint(args.year, args.quarter, processed)

    if not is_apply:
        stored = total_ps_trades

    total_time = round(time.time() - start, 1)
    print(f"\n{'STOPPED (rate limited)' if hit_rate_limit else 'Complete'}: {total_time}s", flush=True)
    print(f"  Fetched: {done:,}/{total_filings:,}", flush=True)
    print(f"  P/S filings: {total_ps_filings:,} ({total_ps_trades:,} trades)", flush=True)
    print(f"  Stored: {stored:,} trades in {store_batches} batches", flush=True)
    print(f"  Skipped: {skipped:,}", flush=True)
    print(f"  Checkpoint: {len(processed):,} total processed", flush=True)

    print(f"""
{'=' * 60}
  BACKFILL {'STOPPED' if hit_rate_limit else 'COMPLETE'} ({mode})
  Quarter: {args.year} Q{args.quarter}
  Filings: {total_filings:,} ({len(processed):,} checkpointed)
  With P/S: {total_ps_filings:,} ({total_ps_trades:,} trades)
  {'Stored' if is_apply else 'Would store'}: {stored:,}
  Total time: {total_time}s ({total_time/60:.1f} min)
{'=' * 60}
""", flush=True)

    if is_apply:
        await Neo4jClient.disconnect()


if __name__ == "__main__":
    asyncio.run(main())
