"""Phase C: Merge prefilter results + LLM queue → unified classified.json.

Reads:
  form4_index_YYYYMMDD_p_prefiltered.json  (prefilter NOT_GENUINE)
  form4_index_YYYYMMDD_p_llm_queue.json     (LLM classifications)
  form4_index_YYYYMMDD_p_parsed.json        (optional — for structured deal detector)

Writes:
  form4_index_YYYYMMDD_p_classified.json   (legacy format + optional extra fields)

After merging, runs a cross-filing structured deal detector:
  - Groups GENUINE transactions by (issuer, transaction_date, price_per_share)
  - If 3+ distinct insiders bought at the same exact price same day → SUSPECTED_STRUCTURED
  - Flag is preserved in Neo4j (ingest writes it), cluster queries still filter
    WHERE classification='GENUINE' so these don't pollute signals.

Halts if LLM queue has unclassified items (user must complete Phase B first).

Usage:
    python merge_classifications.py --date 2025-12-24
"""

import argparse
import json
import os
import sys
from collections import defaultdict

sys.stdout.reconfigure(line_buffering=True)


def enrich_from_parsed(merged_results: list, parsed_path: str) -> None:
    """Add transaction_date, price_per_share, and ticker to each merged result, in-place.

    Used when prefilter/queue files were created before we added those fields.
    Matches parsed transactions by (accession, insider_name, total_value).
    """
    if not os.path.exists(parsed_path):
        return

    with open(parsed_path) as f:
        parsed = json.load(f)

    # Build lookup: (accession, insider_name, total_value) -> (txn_date, price, ticker)
    lookup = {}
    for filing in parsed.get("parsed", []):
        acc = filing["accession"]
        insider = filing.get("insider", {}).get("name", "")
        # Extract ticker from issuer_name or txt_url accession
        ticker = filing.get("issuer_trading_symbol", "")
        for t in filing.get("p_transactions", []):
            key = (acc, insider, t.get("total_value", 0))
            lookup[key] = (t.get("transaction_date", ""),
                           t.get("price_per_share", 0),
                           ticker)

    # Fill in missing fields on merged results
    for r in merged_results:
        key = (r["accession"], r["insider"], r["total_value"])
        entry = lookup.get(key)
        if entry:
            txn_date, price, ticker = entry
            r.setdefault("transaction_date", txn_date)
            r.setdefault("price_per_share", price)
            if ticker:
                r.setdefault("ticker", ticker)


def detect_structured_clusters(merged_results: list) -> int:
    """Post-classification detector for suspected structured deals.

    Groups GENUINE transactions by (issuer, transaction_date, price_per_share).
    If group has ≥3 distinct insiders, reclassify all as AMBIGUOUS with
    rule_triggered=POST_CLUSTER_CHECK so they can be isolated from LLM-AMBIGUOUS
    cases when reviewed.

    Returns count of transactions reclassified.
    """
    groups = defaultdict(list)
    for r in merged_results:
        if r.get("classification") != "GENUINE":
            continue
        txn_date = r.get("transaction_date", "")
        price = r.get("price_per_share", 0)
        if not txn_date or not price:
            continue  # Can't group without these
        key = (r.get("issuer", ""), txn_date, price)
        groups[key].append(r)

    flagged = 0
    for key, group in groups.items():
        insiders = {r.get("insider", "") for r in group}
        if len(insiders) >= 3:
            issuer, txn_date, price = key
            reason = (
                f"Suspected structured allocation: {len(insiders)} insiders "
                f"bought {issuer} at exactly ${price} on {txn_date}"
            )
            for r in group:
                r["classification"] = "AMBIGUOUS"
                r["reason"] = reason
                r["rule_triggered"] = "POST_CLUSTER_CHECK"
            flagged += len(group)
            print(f"  🚩 {issuer[:40]:40} — {len(insiders)} insiders @ ${price} on {txn_date}")
    return flagged


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--date", required=True, help="YYYY-MM-DD")
    args = ap.parse_args()

    date_compact = args.date.replace("-", "")
    prefiltered_path = f"form4_index_{date_compact}_p_prefiltered.json"
    queue_path = f"form4_index_{date_compact}_p_llm_queue.json"
    parsed_path = f"form4_index_{date_compact}_p_parsed.json"
    classified_path = f"form4_index_{date_compact}_p_classified.json"

    if not os.path.exists(prefiltered_path):
        print(f"ERROR: {prefiltered_path} not found. Run prefilter_p.py first.")
        sys.exit(1)
    if not os.path.exists(queue_path):
        print(f"ERROR: {queue_path} not found. Run prefilter_p.py first.")
        sys.exit(1)

    with open(prefiltered_path) as f:
        pre = json.load(f)
    with open(queue_path) as f:
        queue = json.load(f)

    unclassified = [it for it in queue["items"]
                    if it.get("classification") is None]
    if unclassified:
        print(f"ERROR: {len(unclassified)} items in LLM queue still unclassified.")
        print("Run batch_llm_classify.py to complete them before merging.")
        for it in unclassified[:5]:
            print(f"  - {it['issuer'][:40]:40} / {it['insider'][:25]:25} ${it['total_value']:>10,.0f}")
        sys.exit(1)

    merged_results = []

    # Prefilter NOT_GENUINE (carry through transaction_date/price_per_share/primary_document if present)
    for r in pre["results"]:
        item = {
            "accession": r["accession"],
            "issuer": r["issuer"],
            "insider": r["insider"],
            "total_value": r["total_value"],
            "classification": r["classification"],
            "reason": r["reason"],
            "rule_triggered": r["rule_triggered"],
        }
        if "transaction_date" in r:
            item["transaction_date"] = r["transaction_date"]
        if "price_per_share" in r:
            item["price_per_share"] = r["price_per_share"]
        if "primary_document" in r:
            item["primary_document"] = r["primary_document"]
        merged_results.append(item)

    # LLM classifications
    for qi in queue["items"]:
        item = {
            "accession": qi["accession"],
            "issuer": qi["issuer"],
            "insider": qi["insider"],
            "total_value": qi["total_value"],
            "classification": qi["classification"],
            "reason": qi["reason"] or "",
            "rule_triggered": qi.get("rule_triggered") or "LLM",
        }
        if "transaction_date" in qi:
            item["transaction_date"] = qi["transaction_date"]
        if "price_per_share" in qi:
            item["price_per_share"] = qi["price_per_share"]
        elif "payload" in qi and qi["payload"]:
            item["price_per_share"] = qi["payload"].get("price_per_share", 0)
        if "primary_document" in qi:
            item["primary_document"] = qi["primary_document"]
        merged_results.append(item)

    # Backward compat: enrich from parsed.json if txn_date/price missing
    enrich_from_parsed(merged_results, parsed_path)

    # Run structured deal detector
    print(f"\n=== STRUCTURED DEAL DETECTOR ===")
    flagged = detect_structured_clusters(merged_results)
    if flagged > 0:
        print(f"Reclassified {flagged} transactions as AMBIGUOUS (structured)")
    else:
        print(f"No structured deals detected")

    # Run earnings proximity filter on GENUINE signals
    print(f"\n=== EARNINGS PROXIMITY FILTER ===")
    from app.services.signal_filter import SignalFilter

    # Build CIK→ticker mapping from parsed JSON (issuer_cik → issuer_trading_symbol)
    # For historical data without issuer_trading_symbol, fall back to Neo4j mapping
    cik_ticker_map = {}
    if os.path.exists(parsed_path):
        with open(parsed_path) as f:
            p_data = json.load(f)
        for filing in p_data.get("parsed", []):
            cik = filing.get("issuer_cik", "")
            sym = filing.get("issuer_trading_symbol", "")
            if cik and sym:
                cik_ticker_map[cik] = sym

    # If no tickers from parsed JSON, load from Neo4j (covers all historical data)
    if not cik_ticker_map:
        try:
            import asyncio
            from app.db.neo4j_client import Neo4jClient

            async def load_ticker_map():
                await Neo4jClient.connect()
                r = await Neo4jClient.execute_query("""
                    MATCH (c:Company)
                    WHERE c.tickers IS NOT NULL AND size(c.tickers) > 0
                    RETURN c.cik AS cik, c.tickers[0] AS ticker
                """)
                m = {row["cik"]: row["ticker"] for row in r}
                await Neo4jClient.disconnect()
                return m

            cik_ticker_map = asyncio.run(load_ticker_map())
            print(f"  Loaded {len(cik_ticker_map)} CIK→ticker mappings from Neo4j")
        except Exception as e:
            print(f"  Warning: could not load CIK→ticker map: {e}")

    # Also build accession→CIK mapping from parsed JSON
    acc_cik_map = {}
    if os.path.exists(parsed_path):
        with open(parsed_path) as f:
            p_data = json.load(f)
        for filing in p_data.get("parsed", []):
            acc_cik_map[filing["accession"]] = filing.get("issuer_cik", "")

    filtered_count = 0
    skipped_no_ticker = 0
    for r in merged_results:
        if r.get("classification") != "GENUINE":
            continue
        # Resolve ticker: direct field → CIK lookup → skip
        ticker = r.get("ticker") or ""
        if not ticker:
            cik = acc_cik_map.get(r.get("accession", ""), "")
            ticker = cik_ticker_map.get(cik, "")
        signal_date = r.get("transaction_date") or ""
        if not ticker or not signal_date:
            skipped_no_ticker += 1
            continue
        result = SignalFilter.apply_filter(ticker, signal_date)
        if not result.passed:
            r["classification"] = "FILTERED"
            r["reason"] = result.reason
            r["rule_triggered"] = "EARNINGS_FILTER"
            filtered_count += 1
    if filtered_count > 0:
        print(f"  Filtered {filtered_count} signals (earnings >60d)")
    else:
        print(f"  No signals filtered")
    if skipped_no_ticker > 0:
        print(f"  Skipped {skipped_no_ticker} signals (no ticker resolved)")

    # Run hostile activist flag on remaining GENUINE signals (informational only)
    print(f"\n=== HOSTILE ACTIVIST FLAG ===")
    hostile_count = 0
    for r in merged_results:
        if r.get("classification") != "GENUINE":
            continue
        cik = acc_cik_map.get(r.get("accession", ""), "")
        if not cik:
            r["has_hostile_activist"] = False
            r["hostile_keywords"] = []
            continue
        hostile_result = SignalFilter.check_hostile_activist(cik)
        r["has_hostile_activist"] = hostile_result.has_hostile
        r["hostile_keywords"] = hostile_result.keywords
        if hostile_result.has_hostile:
            hostile_count += 1
    print(f"  Flagged {hostile_count} signals with hostile activist text")

    # Classification counts (recount after detector)
    classification_counts = {}
    for r in merged_results:
        c = r["classification"]
        classification_counts[c] = classification_counts.get(c, 0) + 1

    output = {
        "date": pre["date"],
        "total_classified": len(merged_results),
        "prefilter_caught": pre["prefilter_caught"],
        "rule_breakdown": pre["rule_breakdown"],
        "llm_called": len(queue["items"]),
        "structured_flagged": flagged,
        "classification_counts": classification_counts,
        "results": merged_results,
    }

    with open(classified_path, "w") as f:
        json.dump(output, f, indent=2)

    print(f"\nMerged → {classified_path}")
    print(f"  Total classified:   {len(merged_results)}")
    print(f"  Prefilter caught:   {pre['prefilter_caught']}")
    print(f"  LLM classified:     {len(queue['items'])}")
    print(f"  Structured flagged: {flagged}")
    print(f"  Breakdown:          {classification_counts}")


if __name__ == "__main__":
    main()
