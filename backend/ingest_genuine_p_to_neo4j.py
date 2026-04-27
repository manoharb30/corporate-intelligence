"""Ingest GENUINE P transactions from classified JSON files into Neo4j.

Reads both _p_parsed.json (full transaction data) and _p_classified.json
(classifications), filters to GENUINE-only, writes to Neo4j using MERGE
(idempotent — safe to re-run).

Usage:
    python ingest_genuine_p_to_neo4j.py --date 2025-10-01
"""

import argparse
import asyncio
import json
import sys
import time
from datetime import datetime

sys.path.insert(0, ".")
from app.db.neo4j_client import Neo4jClient
from app.services.stock_price_service import StockPriceService
from app.services.insider_cluster_service import InsiderClusterService

sys.stdout.reconfigure(line_buffering=True)


def build_classification_lookup(classified_results: list) -> dict:
    """Build O(1) lookup dict from classified results. Key: (accession, rounded_value, insider)."""
    lookup = {}
    for r in classified_results:
        key = (r.get("accession", ""), round(r.get("total_value", 0), 2), r.get("insider", ""))
        lookup[key] = r
    return lookup


def match_classification(lookup: dict, accession: str,
                         total_value: float, insider: str) -> dict | None:
    """Find classification using O(1) dict lookup."""
    key = (accession, round(total_value, 2), insider)
    return lookup.get(key)


async def ingest_transaction(filing: dict, txn: dict, cls: dict, log) -> str:
    """Write one classified P transaction (GENUINE or AMBIGUOUS) to Neo4j.

    Strategy: match existing record by natural key first, update if found.
    Only create a new node if no existing record exists.
    This avoids creating duplicates alongside records from the scanner.

    The classification value (GENUINE/AMBIGUOUS) is preserved from the classifier;
    queries downstream (e.g., cluster detection) filter by classification='GENUINE'
    so AMBIGUOUS records don't pollute signals, but remain available for review.
    """
    insider = filing.get("insider", {})
    insider_name = insider.get("name", "")
    issuer_cik = (filing.get("issuer_cik") or "").zfill(10)
    issuer_name = filing.get("issuer_name", "")
    accession = filing["accession"]
    footnotes = filing.get("footnotes", "")
    primary_document = filing.get("primary_document", "")
    issuer_trading_symbol = (filing.get("issuer_trading_symbol") or "").strip()
    tickers = [issuer_trading_symbol] if issuer_trading_symbol else []

    shares = txn.get("shares", 0) or 0
    price = txn.get("price_per_share", 0) or 0
    txn_date = txn.get("transaction_date", "")
    now = datetime.utcnow().isoformat()

    # Normalize filing_date to ISO YYYY-MM-DD format (source JSON may have YYYYMMDD)
    raw_fd = filing.get("filing_date", "")
    if raw_fd and len(raw_fd) == 8 and raw_fd.isdigit():
        filing_date_iso = f"{raw_fd[:4]}-{raw_fd[4:6]}-{raw_fd[6:8]}"
    else:
        filing_date_iso = raw_fd

    # Common parameters for both update and create paths
    params = {
        "cik": issuer_cik,
        "company_name": issuer_name,
        "tickers": tickers,
        "accession": accession,
        "filing_date": filing_date_iso,
        "txn_date": txn_date,
        "security_title": txn.get("security_title", ""),
        "shares": shares,
        "price": price,
        "total_value": txn.get("total_value", 0),
        "shares_after": txn.get("shares_after_transaction", 0),
        "ownership_type": txn.get("ownership_type", ""),
        "ownership_nature": txn.get("ownership_nature", ""),
        "is_derivative": txn.get("is_derivative", False),
        "insider_name": insider_name,
        "insider_title": insider.get("title", ""),
        "insider_cik": insider.get("cik", ""),
        "is_10b5_1": filing.get("is_10b5_1", False),
        "is_officer": insider.get("is_officer", False),
        "is_director": insider.get("is_director", False),
        "is_ten_percent_owner": insider.get("is_ten_percent_owner", False),
        "footnotes": footnotes,
        "primary_document": primary_document,
        "classification": cls.get("classification", "GENUINE"),
        "cls_reason": cls.get("reason", "")[:500],
        "cls_rule": cls.get("rule_triggered", ""),
        "has_hostile_activist": cls.get("has_hostile_activist", False),
        "now": now,
    }

    try:
        # All records for this date were deleted before ingestion (delete-then-insert pattern),
        # so we go straight to create — no need to check for existing records.
        txn_id = f"{accession}_P_{txn_date}_{int(shares)}_{price}"
        params["txn_id"] = txn_id

        await Neo4jClient.execute_query("""
            MERGE (c:Company {cik: $cik})
            ON CREATE SET c.name = $company_name,
                          c.tickers = $tickers
            SET c.name = COALESCE(c.name, $company_name),
                c.tickers = CASE
                    WHEN c.tickers IS NULL OR size(c.tickers) = 0
                    THEN $tickers
                    ELSE c.tickers
                END

            MERGE (t:InsiderTransaction {id: $txn_id})
            ON CREATE SET t.first_ingested_at = $now
            SET t.accession_number = $accession,
                t.filing_date = $filing_date,
                t.transaction_date = $txn_date,
                t.transaction_code = 'P',
                t.transaction_type = 'Purchase',
                t.security_title = $security_title,
                t.shares = $shares,
                t.price_per_share = $price,
                t.total_value = $total_value,
                t.shares_after_transaction = $shares_after,
                t.ownership_type = $ownership_type,
                t.ownership_nature = $ownership_nature,
                t.is_derivative = $is_derivative,
                t.insider_name = $insider_name,
                t.insider_title = $insider_title,
                t.insider_cik = $insider_cik,
                t.is_10b5_1 = $is_10b5_1,
                t.is_officer = $is_officer,
                t.is_director = $is_director,
                t.is_ten_percent_owner = $is_ten_percent_owner,
                t.footnotes = $footnotes,
                t.primary_document = $primary_document,
                t.classification = $classification,
                t.classification_reason = $cls_reason,
                t.classification_rule = $cls_rule,
                t.classified_at = $now,
                t.has_hostile_activist = $has_hostile_activist

            MERGE (c)-[:INSIDER_TRADE_OF]->(t)

            WITH t
            MERGE (p:Person {normalized_name: toLower($insider_name)})
            ON CREATE SET p.name = $insider_name, p.id = randomUUID()
            MERGE (p)-[:TRADED_BY]->(t)
        """, params)
        return "inserted"
    except Exception as e:
        log(f"  ERROR storing {accession} ({insider_name}): {e}")
        return "error"


async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--date", required=True, help="Date in YYYY-MM-DD format")
    args = ap.parse_args()

    date_compact = args.date.replace("-", "")
    parsed_path = f"form4_index_{date_compact}_p_parsed.json"
    classified_path = f"form4_index_{date_compact}_p_classified.json"

    try:
        with open(parsed_path) as f:
            parsed_data = json.load(f)
        with open(classified_path) as f:
            classified_data = json.load(f)
    except FileNotFoundError as e:
        print(f"ERROR: {e}")
        sys.exit(1)

    log_path = f"/tmp/ingest_genuine_{date_compact}.log"
    log_file = open(log_path, "w", buffering=1)

    def log(msg):
        print(msg, flush=True)
        log_file.write(msg + "\n")
        log_file.flush()

    await Neo4jClient.connect()

    log(f"Date: {args.date}")
    log(f"Parsed filings: {len(parsed_data['parsed'])}")
    log(f"Classified results: {len(classified_data['results'])}")
    log(f"Log: {log_path}\n")

    # === DELETE first: remove any existing InsiderTransactions with filing_date = this date ===
    # Use ISO format (YYYY-MM-DD) to match normalized DB storage
    log(f"Deleting existing InsiderTransactions with filing_date = {args.date}...")
    del_result = await Neo4jClient.execute_query("""
        MATCH (t:InsiderTransaction)
        WHERE t.filing_date = $filing_date
        DETACH DELETE t
        RETURN count(t) AS deleted
    """, {"filing_date": args.date})
    deleted = del_result[0]["deleted"] if del_result else 0
    log(f"Deleted: {deleted} existing transactions\n")

    classified_results = classified_data["results"]
    cls_lookup = build_classification_lookup(classified_results)
    total_txns = sum(len(f.get("p_transactions", [])) for f in parsed_data["parsed"])
    log(f"Total P transactions to process: {total_txns}")

    start = time.time()
    counts = {"inserted": 0, "updated": 0, "error": 0,
              "genuine_written": 0, "ambiguous_written": 0,
              "skipped_not_genuine": 0, "skipped_no_match": 0}
    touched_companies: dict[str, str] = {}  # cik -> ticker (for post-ingest mcap enrichment)
    # Classifications we write to Neo4j (skip NOT_GENUINE, PARSE_ERROR, API_ERROR)
    # AMBIGUOUS = LLM-uncertain or structured deals (rule_triggered distinguishes)
    # FILTERED = failed earnings proximity filter (pre-trade exclusion)
    WRITE_CLASSIFICATIONS = {"GENUINE", "AMBIGUOUS", "FILTERED"}

    for filing in parsed_data["parsed"]:
        insider_name = filing.get("insider", {}).get("name", "")
        for txn in filing.get("p_transactions", []):
            total_value = txn.get("total_value", 0)
            cls = match_classification(
                cls_lookup, filing["accession"], total_value, insider_name
            )
            if cls is None:
                counts["skipped_no_match"] += 1
                log(f"  NO MATCH: {filing['accession']} / {insider_name} / ${total_value}")
                continue
            classification = cls.get("classification")
            if classification not in WRITE_CLASSIFICATIONS:
                counts["skipped_not_genuine"] += 1
                continue

            status = await ingest_transaction(filing, txn, cls, log)
            counts[status] = counts.get(status, 0) + 1
            if status == "inserted":
                cik_padded = (filing.get("issuer_cik") or "").zfill(10)
                sym = (filing.get("issuer_trading_symbol") or "").strip()
                if cik_padded and sym:
                    touched_companies[cik_padded] = sym
            # Track how many of each classification we wrote
            if classification == "GENUINE":
                counts["genuine_written"] += 1
            elif classification == "AMBIGUOUS":
                counts["ambiguous_written"] += 1
            # Label distinguishes structured-deal AMBIGUOUS vs regular LLM-AMBIGUOUS
            if classification == "AMBIGUOUS":
                rule = cls.get("rule_triggered", "")
                label = "STRUCT" if rule == "POST_CLUSTER_CHECK" else "AMBIG"
            else:
                label = status
            log(f"  {label}: {filing.get('issuer_name','')[:30]:30} {insider_name[:25]:25} ${total_value:>10,.0f}")

    # Enrich market_cap for any Company touched in this run that lacks one.
    # StockPriceService.get_market_cap() swallows its own exceptions (returns None),
    # so try/except only protects the Neo4j write path.
    log(f"\nEnriching market_cap for {len(touched_companies)} unique companies...")
    mcap_filled = 0
    mcap_skipped = 0
    mcap_errored = 0
    for cik, ticker in touched_companies.items():
        mcap = StockPriceService.get_market_cap(ticker)
        if not mcap or mcap <= 0:
            mcap_skipped += 1
            continue
        try:
            await Neo4jClient.execute_query("""
                MATCH (c:Company {cik: $cik})
                WHERE c.market_cap IS NULL OR c.market_cap = 0
                SET c.market_cap = $mcap,
                    c.market_cap_updated_at = $now
            """, {"cik": cik, "mcap": float(mcap), "now": datetime.utcnow().isoformat()})
            mcap_filled += 1
        except Exception as e:
            mcap_errored += 1
            log(f"  ERROR mcap write for {ticker} (cik={cik}): {type(e).__name__}: {str(e)[:100]}")
    log(f"  mcap filled: {mcap_filled}, no-data: {mcap_skipped}, errors: {mcap_errored}")

    # Incremental cluster detection for each touched CIK
    log(f"\nIncremental cluster detection for {len(touched_companies)} CIKs...")
    created = updated = noop = errored = 0
    for cik in touched_companies.keys():
        try:
            result = await InsiderClusterService.process_incremental(cik, args.date)
        except Exception as e:
            errored += 1
            log(f"  ERROR cluster process for cik={cik}: {type(e).__name__}: {str(e)[:100]}")
            continue
        action = result.get("action", "none")
        if action == "created":
            created += 1
            log(f"  CREATED cluster: {result['signal_id']}")
        elif action == "updated":
            updated += 1
            log(f"  UPDATED cluster: {result['signal_id']}")
        else:
            noop += 1
    log(f"  clusters created: {created}, updated: {updated}, no-op: {noop}, errors: {errored}")

    # Clean up orphaned Person nodes
    orphan_result = await Neo4jClient.execute_query("""
        MATCH (p:Person) WHERE NOT (p)-[]-()
        DELETE p
        RETURN count(p) AS deleted
    """)
    orphans_deleted = orphan_result[0]["deleted"] if orphan_result else 0
    log(f"\nOrphaned Person nodes deleted: {orphans_deleted}")

    elapsed = round(time.time() - start, 1)
    log(f"""
{'=' * 60}
  INGESTION COMPLETE (for {args.date})
  Pre-delete existing:        {deleted}
  Inserted (new):             {counts['inserted']}
  Updated (existing):         {counts['updated']}
    → GENUINE written:        {counts['genuine_written']}
    → AMBIGUOUS written:      {counts['ambiguous_written']}
  Skipped (NOT_GENUINE/other): {counts['skipped_not_genuine']}
  Skipped (no match):         {counts['skipped_no_match']}
  Errors:                     {counts['error']}
  Mcap filled / no-data / err: {mcap_filled} / {mcap_skipped} / {mcap_errored}
  Clusters created/updated/none/err: {created} / {updated} / {noop} / {errored}
  Orphan Persons cleaned: {orphans_deleted}
  Time: {elapsed}s
{'=' * 60}
""")
    log_file.close()
    await Neo4jClient.disconnect()


if __name__ == "__main__":
    asyncio.run(main())
