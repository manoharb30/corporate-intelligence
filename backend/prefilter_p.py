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

sys.stdout.reconfigure(line_buffering=True)
sys.path.insert(0, ".")

from classify_p_with_prefilter import prefilter


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

    for filing in parsed_filings:
        for txn in filing.get("p_transactions", []):
            base = {
                "accession": filing["accession"],
                "issuer": filing.get("issuer_name", ""),
                "insider": filing.get("insider", {}).get("name", ""),
                "total_value": txn.get("total_value", 0),
                "transaction_date": txn.get("transaction_date", ""),
                "price_per_share": txn.get("price_per_share", 0),
                "primary_document": filing.get("primary_document", ""),
            }
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
