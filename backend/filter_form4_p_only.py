"""Read Form 4 index JSON, fetch each URL, keep only those with P (purchase) transactions.

8 parallel workers with 1-second pace each = 8 req/sec (under SEC's 10/sec limit).
Retries on HTTP 429 (rate limit) with 5-second backoff, up to 3 attempts.
Outputs subset JSON + live progress log.

Usage:
    python filter_form4_p_only.py --input /tmp/form4_index_20251001.json
"""

import argparse
import json
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime

import requests

sys.stdout.reconfigure(line_buffering=True)

HEADERS = {"User-Agent": "LookInsight research@lookinsight.ai"}
WORKERS = 9
PACE_SEC = 1.0  # per-worker delay between requests

# Per-worker last-request timestamp (threading)
_last_request = threading.local()


def check_has_p(filing: dict) -> dict:
    """Fetch filing, check for P transaction code. Returns dict with status."""
    # Pace: ensure 1 sec since this worker's last request
    now = time.time()
    last = getattr(_last_request, "t", 0)
    wait = PACE_SEC - (now - last)
    if wait > 0:
        time.sleep(wait)
    _last_request.t = time.time()

    max_retries = 3
    for attempt in range(max_retries):
        try:
            resp = requests.get(filing["txt_url"], headers=HEADERS, timeout=20)
        except requests.RequestException as e:
            return {"filing": filing, "status": "error", "error": str(e)[:80]}

        if resp.status_code == 429:
            if attempt < max_retries - 1:
                time.sleep(5 * (attempt + 1))  # 5s, 10s backoff
                _last_request.t = time.time()
                continue
            return {"filing": filing, "status": "rate_limited"}
        if resp.status_code == 404:
            return {"filing": filing, "status": "not_found"}
        if resp.status_code != 200:
            return {"filing": filing, "status": f"http_{resp.status_code}"}

        text = resp.text
        has_p = "<transactionCode>P</transactionCode>" in text
        return {"filing": filing, "status": "has_p" if has_p else "no_p", "text": text if has_p else None}

    return {"filing": filing, "status": "error", "error": "max retries exceeded"}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", required=True, help="Input JSON file with Form 4 index")
    args = ap.parse_args()

    with open(args.input) as f:
        data = json.load(f)

    date = data["date"]
    filings = data["filings"]
    total = len(filings)

    log_path = f"/tmp/filter_form4_p_{date.replace('-', '')}.log"
    log_file = open(log_path, "w", buffering=1)

    def log(msg):
        print(msg, flush=True)
        log_file.write(msg + "\n")
        log_file.flush()

    log(f"Input: {args.input}")
    log(f"Date: {date}")
    log(f"Total Form 4s to check: {total}")
    log(f"Workers: {WORKERS}, Pace: {PACE_SEC}s per worker")
    log(f"Log: {log_path}")
    log("")

    start = time.time()
    has_p_list = []
    no_p_count = 0
    rate_limited_count = 0
    not_found_count = 0
    error_count = 0
    processed = 0

    with ThreadPoolExecutor(max_workers=WORKERS) as executor:
        futures = {executor.submit(check_has_p, f): f for f in filings}
        for future in as_completed(futures):
            result = future.result()
            processed += 1
            status = result["status"]

            if status == "has_p":
                has_p_list.append(result["filing"])
            elif status == "no_p":
                no_p_count += 1
            elif status == "rate_limited":
                rate_limited_count += 1
            elif status == "not_found":
                not_found_count += 1
            else:
                error_count += 1

            # Progress every 100
            if processed % 100 == 0:
                elapsed = round(time.time() - start, 1)
                rate = processed / elapsed if elapsed > 0 else 0
                eta = (total - processed) / rate if rate > 0 else 0
                log(f"  [{processed:>4}/{total}] has_p={len(has_p_list)} no_p={no_p_count} "
                    f"rl={rate_limited_count} 404={not_found_count} err={error_count} "
                    f"({elapsed:.0f}s, ~{eta:.0f}s remaining)")

    # Save output
    out_path = args.input.replace(".json", "_p_only.json")
    with open(out_path, "w") as f:
        json.dump({
            "date": date,
            "total_checked": total,
            "with_p_count": len(has_p_list),
            "no_p_count": no_p_count,
            "rate_limited_count": rate_limited_count,
            "not_found_count": not_found_count,
            "error_count": error_count,
            "filings": has_p_list,
        }, f, indent=2)

    elapsed = round(time.time() - start, 1)
    log(f"""
{'=' * 60}
  FILTER COMPLETE (for {date})
  Total checked:        {total}
  Have P transactions:  {len(has_p_list)}
  No P:                 {no_p_count}
  Rate limited:         {rate_limited_count}
  Not found (404):      {not_found_count}
  Errors:               {error_count}
  Time: {elapsed}s ({elapsed/60:.1f} min)
  Output: {out_path}
{'=' * 60}
""")

    log_file.close()


if __name__ == "__main__":
    main()
