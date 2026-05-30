"""Phase A: Python prefilter only (no LLM).

Takes a parsed Form 4 JSON file, applies deterministic prefilter rules, writes 2 outputs:

  form4_index_YYYYMMDD_p_prefiltered.json
      - Definitive NOT_GENUINE results from prefilter rules
      - Contains rule_breakdown stats

  form4_index_YYYYMMDD_p_llm_queue.json
      - Subset that needs LLM review (classification = null)
      - Contains payload for each item (what LLM will see)
      - Mutable: Phase B (batch_llm_classify.py) updates this file in-place

Reuses prefilter() from classify_p_with_prefilter.py so any rule changes there
automatically apply here.

Usage:
    python prefilter_p.py --input form4_index_20251224_p_parsed.json
"""

import argparse
import json
import sys
from collections import defaultdict

sys.stdout.reconfigure(line_buffering=True)
sys.path.insert(0, ".")

from classify_p_with_prefilter import prefilter


def detect_dsp_allocations(parsed_filings: list[dict]) -> dict:
    """Detect IPO Directed Share Program allocations across the daily batch.

    DSP fingerprint (any non-IPO occurrence essentially impossible):
    - 2+ distinct insiders
    - Same issuer, same transaction date
    - Same exact whole-dollar price per share (e.g., $20.00)

    Returns: dict mapping (accession, insider_name, txn_index) -> reason string.
    Caller uses this to mark matching transactions NOT_GENUINE before LLM.
    """
    groups = defaultdict(list)  # (issuer_cik, date, price_cents) -> list of (acc, insider, txn_idx)
    for filing in parsed_filings:
        acc = filing.get("accession", "")
        insider_name = (filing.get("insider", {}) or {}).get("name", "")
        issuer_cik = filing.get("issuer_cik") or filing.get("issuer_name", "")
        for i, txn in enumerate(filing.get("p_transactions", [])):
            price = txn.get("price_per_share", 0) or 0
            # Whole-dollar check: within 1 cent of an integer, and positive
            if price <= 0 or abs(price - round(price)) > 0.01:
                continue
            date = (txn.get("transaction_date") or "")[:10]
            if not date:
                continue
            key = (issuer_cik, date, int(round(price * 100)))
            groups[key].append((acc, insider_name, i))

    flagged: dict = {}
    for (issuer_cik, date, price_cents), members in groups.items():
        unique_insiders = {m[1].upper() for m in members if m[1]}
        if len(unique_insiders) < 2:
            continue
        price = price_cents / 100
        reason = (
            f"IPO DSP allocation: {len(unique_insiders)} distinct insiders bought at "
            f"exactly ${price:.2f} on {date} (same issuer, same date, same whole-dollar price — "
            f"non-conviction offering allocation)"
        )
        for acc, insider, idx in members:
            flagged[(acc, insider, idx)] = reason
    return flagged


def build_payload_dict(filing: dict, txn: dict) -> dict:
    """Build LLM payload as dict (more readable than string in queue file)."""
    insider = filing.get("insider", {})
    return {
        "issuer": filing.get("issuer_name", ""),
        "insider_name": insider.get("name", ""),
        "insider_is_officer": insider.get("is_officer", False),
        "insider_is_director": insider.get("is_director", False),
        "insider_is_ten_percent_owner": insider.get("is_ten_percent_owner", False),
        "is_10b5_1": filing.get("is_10b5_1", False),
        "security_title": txn.get("security_title", ""),
        "shares": txn.get("shares", 0),
        "price_per_share": txn.get("price_per_share", 0),
        "total_value": txn.get("total_value", 0),
        "ownership_type": txn.get("ownership_type", ""),
        "ownership_nature": txn.get("ownership_nature", ""),
        "footnotes": (filing.get("footnotes", "") or "")[:1500],
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", required=True, help="Path to *_p_parsed.json")
    args = ap.parse_args()

    with open(args.input) as f:
        data = json.load(f)

    date = data["date"]
    parsed_filings = data["parsed"]

    prefilter_results = []
    llm_queue_items = []
    rule_counts = {}

    # Cross-filing DSP detection — looks across the whole batch for IPO
    # directed-share-program patterns the per-transaction prefilter can't see.
    dsp_flags = detect_dsp_allocations(parsed_filings)

    for filing in parsed_filings:
        for i, txn in enumerate(filing.get("p_transactions", [])):
            base = {
                "accession": filing["accession"],
                "issuer": filing.get("issuer_name", ""),
                "insider": filing.get("insider", {}).get("name", ""),
                "total_value": txn.get("total_value", 0),
                "transaction_date": txn.get("transaction_date", ""),
                "price_per_share": txn.get("price_per_share", 0),
                "primary_document": filing.get("primary_document", ""),
            }
            # Rule 22 — IPO DSP allocation (cross-filing detection)
            dsp_key = (filing["accession"], (filing.get("insider", {}) or {}).get("name", ""), i)
            if dsp_key in dsp_flags:
                rule_counts["Rule 22"] = rule_counts.get("Rule 22", 0) + 1
                prefilter_results.append({
                    **base,
                    "classification": "NOT_GENUINE",
                    "reason": dsp_flags[dsp_key],
                    "rule_triggered": "Rule 22",
                })
                continue
            pre = prefilter(filing, txn)
            if pre:
                reason, rule = pre
                rule_counts[rule] = rule_counts.get(rule, 0) + 1
                prefilter_results.append({
                    **base,
                    "classification": "NOT_GENUINE",
                    "reason": reason,
                    "rule_triggered": rule,
                })
            else:
                llm_queue_items.append({
                    **base,
                    "payload": build_payload_dict(filing, txn),
                    "classification": None,
                    "reason": None,
                    "rule_triggered": None,
                    "classified_at": None,
                })

    total_txns = len(prefilter_results) + len(llm_queue_items)

    print(f"Input: {args.input}")
    print(f"Date: {date}")
    print(f"Total P transactions: {total_txns}")
    print(f"\n=== STAGE 1: Python pre-filter ===")
    print(f"Pre-filter caught: {len(prefilter_results)} as NOT_GENUINE")
    for rule, cnt in sorted(rule_counts.items(),
                            key=lambda x: int(x[0].split()[-1]) if x[0].split()[-1].isdigit() else 999):
        print(f"  {rule}: {cnt}")
    print(f"To LLM: {len(llm_queue_items)}")

    prefiltered_path = args.input.replace("_p_parsed.json", "_p_prefiltered.json")
    with open(prefiltered_path, "w") as f:
        json.dump({
            "date": date,
            "total_transactions": total_txns,
            "prefilter_caught": len(prefilter_results),
            "rule_breakdown": rule_counts,
            "results": prefilter_results,
        }, f, indent=2)

    queue_path = args.input.replace("_p_parsed.json", "_p_llm_queue.json")
    with open(queue_path, "w") as f:
        json.dump({
            "date": date,
            "total_to_classify": len(llm_queue_items),
            "pending": len(llm_queue_items),
            "completed": 0,
            "items": llm_queue_items,
        }, f, indent=2)

    print(f"\nOutputs:")
    print(f"  Prefiltered: {prefiltered_path}")
    print(f"  LLM queue:   {queue_path}")


if __name__ == "__main__":
    main()
