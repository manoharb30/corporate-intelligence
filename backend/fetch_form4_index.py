"""Fetch EDGAR daily index for a date, filter to Form 4 only, save as JSON.

One-off standalone script. No Neo4j. Just index → filtered subset → JSON file.

Usage:
    python fetch_form4_index.py --date 2025-10-01
"""

import argparse
import json
import sys
from datetime import datetime

import requests

sys.stdout.reconfigure(line_buffering=True)

HEADERS = {"User-Agent": "LookInsight research@lookinsight.ai"}


def fetch_and_filter(date_str: str) -> list[dict]:
    dt = datetime.strptime(date_str, "%Y-%m-%d")
    year = dt.year
    qtr = (dt.month - 1) // 3 + 1
    url = f"https://www.sec.gov/Archives/edgar/daily-index/{year}/QTR{qtr}/master.{dt.strftime('%Y%m%d')}.idx"

    print(f"Fetching: {url}")
    resp = requests.get(url, headers=HEADERS, timeout=30)

    if resp.status_code != 200:
        print(f"HTTP {resp.status_code} — aborting")
        sys.exit(1)

    total_lines = 0
    form4_rows = []  # all Form 4 rows (with duplicates)
    seen_accessions = set()
    form4_filings = []  # deduped by accession

    for line in resp.text.split("\n"):
        if "|" not in line:
            continue
        parts = line.strip().split("|")
        if len(parts) < 5:
            continue
        total_lines += 1
        if parts[2].strip() != "4":
            continue
        accession = parts[4].strip().split("/")[-1].replace(".txt", "")
        row = {
            "cik": parts[0].strip(),
            "company_name": parts[1].strip(),
            "form_type": parts[2].strip(),
            "date_filed": parts[3].strip(),
            "accession": accession,
            "txt_url": f"https://www.sec.gov/Archives/{parts[4].strip()}",
        }
        form4_rows.append(row)
        # Dedup by accession — keep only first occurrence
        if accession not in seen_accessions:
            seen_accessions.add(accession)
            form4_filings.append(row)

    duplicates_dropped = len(form4_rows) - len(form4_filings)
    print(f"Total index lines: {total_lines}")
    print(f"Form 4 rows (raw): {len(form4_rows)}")
    print(f"Form 4 unique accessions: {len(form4_filings)}")
    print(f"Duplicates removed: {duplicates_dropped}")
    return form4_filings


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--date", required=True, help="Date in YYYY-MM-DD format")
    args = ap.parse_args()

    form4_filings = fetch_and_filter(args.date)

    out_path = f"/tmp/form4_index_{args.date.replace('-', '')}.json"
    with open(out_path, "w") as f:
        json.dump({
            "date": args.date,
            "count": len(form4_filings),
            "filings": form4_filings,
        }, f, indent=2)

    print(f"Saved to: {out_path}")
    print(f"File size: {len(json.dumps(form4_filings))} bytes (indented version slightly larger)")


if __name__ == "__main__":
    main()
