"""Phase C: Merge prefilter results + LLM queue → unified classified.json.

Reads:
  form4_index_YYYYMMDD_p_prefiltered.json  (prefilter NOT_GENUINE)
  form4_index_YYYYMMDD_p_llm_queue.json     (LLM classifications)
  form4_index_YYYYMMDD_p_parsed.json        (optional — for structured deal detector)

Writes:
  form4_index_YYYYMMDD_p_classified.json   (legacy format + optional extra fields)

After merging, runs a cross-filing structured deal detector:
  - Groups GENUINE transactions by (issuer, transaction_date)
  - If 3+ distinct insiders bought at effectively one price that day → SUSPECTED_STRUCTURED
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


# Relative width of the price band that counts as "one price". Deliberately
# tight — this is a fraud tell, not a price filter. Form 4 reports a per-filing
# weighted average, so insiders filled out of one allocation land a few hundredths
# of a percent apart rather than exactly equal (CODI 2023-01-03 spread 0.043%,
# CODI 2024-01-18 spread 0.042%). Measured against every ≥3-insider day in the
# graph, 0.1% flags exactly the same days as exact-price matching plus those two.
STRUCTURED_PRICE_TOLERANCE = 0.001


def _tight_price_bands(group: list) -> list:
    """Return sub-groups of ≥3 insiders whose whole day sits in one price band.

    The tell for an allocation is not merely that several insiders traded at a
    similar price — it is that each of them reports a single weighted-average
    price off one block. So an insider only qualifies if their *entire* day fits
    inside the band. That keeps out the common shape where one buyer works a
    large order across a wide range and small buyers happen to print inside it.

    Bands are anchored rather than chained: five buyers each 0.09% above the
    last span 0.36% overall and must not collapse into one group.
    """
    bands, seen = [], set()

    def add(rows):
        key = tuple(sorted(id(r) for r in rows))
        if key not in seen:
            seen.add(key)
            bands.append(sorted(rows, key=lambda r: r["price_per_share"]))

    # Arm 1 — exact price agreement between ≥3 insiders. A tell on its own, and
    # robust to a participant also holding an unrelated odd lot that day.
    by_price = defaultdict(list)
    for r in group:
        by_price[r["price_per_share"]].append(r)
    for rows in by_price.values():
        if len({r.get("insider", "") for r in rows}) >= 3:
            add(rows)

    # Arm 2 — near-agreement, for weighted-average reporting.
    by_insider = defaultdict(list)
    for r in group:
        by_insider[r.get("insider", "")].append(r)

    # An insider whose own day spans more than the band was working an order,
    # not reporting an allocation.
    days = []
    for insider, rows in by_insider.items():
        prices = [r["price_per_share"] for r in rows]
        lo, hi = min(prices), max(prices)
        if hi <= lo * (1 + STRUCTURED_PRICE_TOLERANCE):
            days.append((lo, hi, rows))
    days.sort(key=lambda d: d[0])

    for i, (anchor_lo, _, _) in enumerate(days):
        ceiling = anchor_lo * (1 + STRUCTURED_PRICE_TOLERANCE)
        members = [d for d in days[i:] if d[1] <= ceiling]
        if len(members) >= 3:
            add([r for _, _, rows in members for r in rows])
    return bands


def detect_structured_clusters(merged_results: list) -> int:
    """Post-classification detector for suspected structured deals.

    Groups GENUINE transactions by (issuer, transaction_date), then looks for
    ≥3 distinct insiders whose prices sit inside one tolerance band. Those are
    reclassified AMBIGUOUS with rule_triggered=POST_CLUSTER_CHECK so they can be
    isolated from LLM-AMBIGUOUS cases when reviewed.

    Keyed on a band rather than an exact price because Form 4 reports weighted
    averages: CODI's director allocations twice evaded exact-price matching on
    fourth-decimal differences, and the 2023 block reached a live strong_buy
    signal that had to be invalidated by hand.

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
        key = (r.get("issuer", ""), txn_date)
        groups[key].append(r)

    flagged = 0
    for (issuer, txn_date), group in groups.items():
        for band in _tight_price_bands(group):
            insiders = {r.get("insider", "") for r in band}
            lo = band[0]["price_per_share"]
            hi = band[-1]["price_per_share"]
            span = f"${lo}" if lo == hi else f"${lo}-${hi}"
            reason = (
                f"Suspected structured allocation: {len(insiders)} insiders "
                f"bought {issuer} at {span} on {txn_date}"
            )
            for r in band:
                if r["rule_triggered"] == "POST_CLUSTER_CHECK":
                    continue  # already caught by an overlapping band
                r["classification"] = "AMBIGUOUS"
                r["reason"] = reason
                r["rule_triggered"] = "POST_CLUSTER_CHECK"
                flagged += 1
            print(f"  🚩 {issuer[:40]:40} — {len(insiders)} insiders @ {span} on {txn_date}")
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
        # Record the gate's decision on EVERY row — pass or fail. Previously only
        # rejections left a trace, which made the gate un-auditable after the fact.
        r["earnings_outcome"] = result.outcome
        r["earnings_distance_days"] = result.earnings_distance
        r["earnings_no_history"] = result.no_history_before_signal
        if not result.passed:
            r["classification"] = "FILTERED"
            r["reason"] = result.reason
            r["rule_triggered"] = "EARNINGS_FILTER"
            filtered_count += 1
    if filtered_count > 0:
        print(f"  Filtered {filtered_count} signals (earnings >60d)")
    else:
        print(f"  No signals filtered")

    # Outcome breakdown — how many PASSED on the real rule vs by fail-open.
    from app.services.signal_filter import FAIL_OPEN_OUTCOMES
    oc = {}
    for r in merged_results:
        o = r.get("earnings_outcome")
        if o:
            oc[o] = oc.get(o, 0) + 1
    if oc:
        print("  Earnings-gate outcomes:")
        for k in sorted(oc):
            flag = "  <- FAIL-OPEN" if k in FAIL_OPEN_OUTCOMES else ""
            print(f"    {k:<22} {oc[k]:>5}{flag}")
        fo = sum(v for k, v in oc.items() if k in FAIL_OPEN_OUTCOMES)
        tot = sum(oc.values())
        print(f"    fail-open share: {fo}/{tot} = {fo/tot*100:.1f}%")
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
