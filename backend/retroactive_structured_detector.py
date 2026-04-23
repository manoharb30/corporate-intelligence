"""Retroactively apply structured deal detector to historical classified.json files.

Works on all form4_index_YYYYMMDD_p_classified.json files in the backend directory.
For each day:
  1. Reads classified.json + parsed.json (to enrich with price/date)
  2. Groups GENUINE transactions by (issuer, transaction_date, price_per_share)
  3. Any group with ≥3 distinct insiders → reclassify as AMBIGUOUS with
     rule_triggered=POST_CLUSTER_CHECK
  4. Writes updated classified.json
  5. Re-ingests that day via ingest_genuine_p_to_neo4j.py (delete + insert fresh)

Progress log: /tmp/retroactive_structured_detector.log (tail for live status)

Usage:
    python retroactive_structured_detector.py --apply
    python retroactive_structured_detector.py --dry-run
"""

import argparse
import glob
import json
import logging
import os
import subprocess
import sys
import time
from collections import defaultdict

sys.path.insert(0, ".")
sys.stdout.reconfigure(line_buffering=True)

logger = logging.getLogger("retroactive_detector")
logger.setLevel(logging.INFO)
console = logging.StreamHandler(stream=sys.stdout)
console.setFormatter(logging.Formatter("%(message)s"))
logger.addHandler(console)

PY = "venv/bin/python"


def enrich_from_parsed(results: list, parsed_path: str) -> None:
    """Populate transaction_date + price_per_share on each result from parsed.json."""
    if not os.path.exists(parsed_path):
        return
    with open(parsed_path) as f:
        parsed = json.load(f)
    lookup = {}
    for filing in parsed.get("parsed", []):
        acc = filing["accession"]
        insider = filing.get("insider", {}).get("name", "")
        for t in filing.get("p_transactions", []):
            key = (acc, insider, t.get("total_value", 0))
            lookup[key] = (t.get("transaction_date", ""),
                           t.get("price_per_share", 0))
    for r in results:
        key = (r["accession"], r["insider"], r["total_value"])
        txn_date, price = lookup.get(key, ("", 0))
        r.setdefault("transaction_date", txn_date)
        r.setdefault("price_per_share", price)


def detect_structured(results: list) -> int:
    """Reclassify 3+ same-price groups as AMBIGUOUS (rule_triggered=POST_CLUSTER_CHECK)."""
    groups = defaultdict(list)
    for r in results:
        if r.get("classification") != "GENUINE":
            continue
        txn_date = r.get("transaction_date", "")
        price = r.get("price_per_share", 0)
        if not txn_date or not price:
            continue
        key = (r.get("issuer", ""), txn_date, price)
        groups[key].append(r)

    flagged = 0
    for (issuer, txn_date, price), group in groups.items():
        insiders = {r.get("insider", "") for r in group}
        if len(insiders) >= 5:
            reason = (f"Suspected structured allocation: {len(insiders)} insiders "
                      f"bought {issuer} at exactly ${price} on {txn_date}")
            for r in group:
                r["classification"] = "AMBIGUOUS"
                r["reason"] = reason
                r["rule_triggered"] = "POST_CLUSTER_CHECK"
            flagged += len(group)
            logger.info(f"    🚩 {issuer[:40]:40} — {len(insiders)} insiders @ ${price} on {txn_date}")
    return flagged


def process_day(classified_path: str, is_apply: bool) -> dict:
    """Process one day's classified.json. Returns {date, flagged, ingested}."""
    filename = os.path.basename(classified_path)
    date_compact = filename.replace("form4_index_", "").replace("_p_classified.json", "")
    date_iso = f"{date_compact[:4]}-{date_compact[4:6]}-{date_compact[6:8]}"
    parsed_path = f"form4_index_{date_compact}_p_parsed.json"
    # Try /tmp fallback for parsed
    if not os.path.exists(parsed_path):
        parsed_path = f"/tmp/form4_index_{date_compact}_p_parsed.json"

    with open(classified_path) as f:
        data = json.load(f)

    # Enrich with price/date (for older files that lack these)
    enrich_from_parsed(data["results"], parsed_path)

    # Detect
    flagged = detect_structured(data["results"])

    if flagged > 0 and is_apply:
        # Recount classifications
        counts = {}
        for r in data["results"]:
            c = r["classification"]
            counts[c] = counts.get(c, 0) + 1
        data["classification_counts"] = counts
        data["structured_flagged"] = flagged

        # Write updated classified.json
        with open(classified_path, "w") as f:
            json.dump(data, f, indent=2)

        # Re-run ingest
        result = subprocess.run(
            [PY, "ingest_genuine_p_to_neo4j.py", "--date", date_iso],
            capture_output=True, text=True
        )
        return {
            "date": date_iso,
            "flagged": flagged,
            "ingested": result.returncode == 0,
            "error": result.stderr[:200] if result.returncode != 0 else None,
        }
    else:
        return {"date": date_iso, "flagged": flagged, "ingested": False, "skipped": flagged == 0}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    if not args.apply and not args.dry_run:
        logger.error("Specify --apply or --dry-run")
        return

    # Progress logfile (per project convention — tail this to monitor)
    progress_path = "/tmp/retroactive_structured_detector.log"
    handler = logging.FileHandler(progress_path, mode='w')
    handler.setLevel(logging.INFO)
    handler.setFormatter(logging.Formatter("%(asctime)s %(message)s"))
    logger.addHandler(handler)

    mode = "APPLY" if args.apply else "DRY RUN"
    logger.info(f"Mode: {mode}")
    logger.info(f"Progress log: {progress_path}")

    classified_files = sorted(glob.glob("form4_index_*_p_classified.json"))
    logger.info(f"\nFound {len(classified_files)} classified.json files to scan")

    start = time.time()
    total_flagged = 0
    days_with_flags = 0
    days_ingested = 0
    days_failed = 0

    for i, path in enumerate(classified_files, 1):
        logger.info(f"\n[{i}/{len(classified_files)}] {path}")
        try:
            result = process_day(path, args.apply)
            if result["flagged"] > 0:
                days_with_flags += 1
                total_flagged += result["flagged"]
                if args.apply:
                    if result["ingested"]:
                        days_ingested += 1
                        logger.info(f"   ✓ {result['flagged']} flagged, re-ingested")
                    else:
                        days_failed += 1
                        logger.info(f"   ✗ {result['flagged']} flagged, ingest failed: {result.get('error')}")
            # else: silent (most days have 0)
        except Exception as e:
            days_failed += 1
            logger.error(f"   ✗ Error processing {path}: {e}")

    elapsed = round(time.time() - start, 1)
    logger.info(f"\n{'=' * 60}")
    logger.info(f"  RETROACTIVE DETECTOR {mode} COMPLETE")
    logger.info(f"  Days scanned:        {len(classified_files)}")
    logger.info(f"  Days with flags:     {days_with_flags}")
    logger.info(f"  Total txns flagged:  {total_flagged}")
    if args.apply:
        logger.info(f"  Days re-ingested:    {days_ingested}")
        logger.info(f"  Days failed:         {days_failed}")
    logger.info(f"  Time:                {elapsed:.1f}s ({elapsed/60:.1f} min)")
    logger.info(f"{'=' * 60}")


if __name__ == "__main__":
    main()
