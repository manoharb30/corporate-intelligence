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

sys.stdout.reconfigure(line_buffering=True)


def match_classification(classified_results: list, accession: str,
                         total_value: float, insider: str) -> dict | None:
    """Find classification for a transaction by matching on accession + value + insider."""
    for r in classified_results:
        if (r.get("accession") == accession
            and abs((r.get("total_value") or 0) - total_value) < 0.01
            and (r.get("insider") or "") == insider):
            return r
    return None


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
        # Step 1: Look up existing record by natural key
        existing = await Neo4jClient.execute_query("""
            MATCH (c:Company {cik: $cik})-[:INSIDER_TRADE_OF]->(t:InsiderTransaction)
            WHERE t.accession_number = $accession
              AND t.insider_name = $insider_name
              AND t.shares = $shares
              AND t.price_per_share = $price
              AND t.transaction_date = $txn_date
              AND t.transaction_code = 'P'
            RETURN t.id AS existing_id
            LIMIT 1
        """, {
            "cik": issuer_cik,
            "accession": accession,
            "insider_name": insider_name,
            "shares": shares,
            "price": price,
            "txn_date": txn_date,
        })

        if existing:
            # Update existing record — only enrich with classification and footnotes
            existing_id = existing[0]["existing_id"]
            await Neo4jClient.execute_query("""
                MATCH (t:InsiderTransaction {id: $existing_id})
                SET t.footnotes = COALESCE($footnotes, t.footnotes),
                    t.primary_document = COALESCE($primary_document, t.primary_document),
                    t.classification = $classification,
                    t.classification_reason = $cls_reason,
                    t.classification_rule = $cls_rule,
                    t.classified_at = $now
            """, {
                "existing_id": existing_id,
                "footnotes": footnotes if footnotes else None,
                "primary_document": primary_document if primary_document else None,
                "classification": cls.get("classification", "GENUINE"),
                "cls_reason": cls.get("reason", "")[:500],
                "cls_rule": cls.get("rule_triggered", ""),
                "has_hostile_activist": cls.get("has_hostile_activist", False),
                "now": now,
            })
            return "updated"

        # Step 2: No existing record — create new with natural-key txn_id
        txn_id = f"{accession}_P_{txn_date}_{int(shares)}_{price}"
        params["txn_id"] = txn_id

        await Neo4jClient.execute_query("""
            MERGE (c:Company {cik: $cik})
            ON CREATE SET c.name = $company_name
            SET c.name = COALESCE(c.name, $company_name)

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
    total_txns = sum(len(f.get("p_transactions", [])) for f in parsed_data["parsed"])
    log(f"Total P transactions to process: {total_txns}")

    start = time.time()
    counts = {"inserted": 0, "updated": 0, "error": 0,
              "genuine_written": 0, "ambiguous_written": 0,
              "skipped_not_genuine": 0, "skipped_no_match": 0}
    # Classifications we write to Neo4j (skip NOT_GENUINE, PARSE_ERROR, API_ERROR)
    # AMBIGUOUS = LLM-uncertain or structured deals (rule_triggered distinguishes)
    # FILTERED = failed earnings proximity filter (pre-trade exclusion)
    WRITE_CLASSIFICATIONS = {"GENUINE", "AMBIGUOUS", "FILTERED"}

    for filing in parsed_data["parsed"]:
        insider_name = filing.get("insider", {}).get("name", "")
        for txn in filing.get("p_transactions", []):
            total_value = txn.get("total_value", 0)
            cls = match_classification(
                classified_results, filing["accession"], total_value, insider_name
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
  Orphan Persons cleaned: {orphans_deleted}
  Time: {elapsed}s
{'=' * 60}
""")
    log_file.close()
    await Neo4jClient.disconnect()


if __name__ == "__main__":
    asyncio.run(main())
