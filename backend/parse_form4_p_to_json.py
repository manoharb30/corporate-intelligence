"""Read P-only Form 4 index JSON, fetch XML, parse with Form4Parser, output JSON.

For each Form 4 filing:
  - Fetch the .txt file
  - Extract <ownershipDocument> XML
  - Extract <footnotes> raw text block
  - Parse using Form4Parser
  - Keep only P transactions
  - Output to JSON (no Neo4j writes)

8 parallel workers, 1-second pace per worker = 8 req/sec (under SEC's 10/sec limit).

Usage:
    python parse_form4_p_to_json.py --input /tmp/form4_index_20251001_p_only.json
"""

import argparse
import json
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict

import requests

sys.stdout.reconfigure(line_buffering=True)

sys.path.insert(0, ".")
from ingestion.sec_edgar.parsers.form4_parser import Form4Parser

HEADERS = {"User-Agent": "LookInsight research@lookinsight.ai"}
WORKERS = 8
PACE_SEC = 1.0

_last_request = threading.local()
parser = Form4Parser()


def fetch_xml_and_footnotes(filing: dict) -> dict:
    """Fetch .txt file, extract XML + footnotes. Returns structured parsed data."""
    # Per-worker pacing
    now = time.time()
    last = getattr(_last_request, "t", 0)
    wait = PACE_SEC - (now - last)
    if wait > 0:
        time.sleep(wait)
    _last_request.t = time.time()

    try:
        resp = requests.get(filing["txt_url"], headers=HEADERS, timeout=20)
    except requests.RequestException as e:
        return {"filing": filing, "status": "error", "error": str(e)[:80]}

    if resp.status_code == 429:
        return {"filing": filing, "status": "rate_limited"}
    if resp.status_code == 404:
        return {"filing": filing, "status": "not_found"}
    if resp.status_code != 200:
        return {"filing": filing, "status": f"http_{resp.status_code}"}

    text = resp.text
    if "<ownershipDocument>" not in text:
        return {"filing": filing, "status": "no_ownership_doc"}

    try:
        s = text.index("<ownershipDocument>")
        e = text.index("</ownershipDocument>") + len("</ownershipDocument>")
        xml = '<?xml version="1.0"?>\n' + text[s:e]
    except ValueError:
        return {"filing": filing, "status": "xml_extraction_failed"}

    # Extract primary_document filename from <FILENAME> header in .txt
    # (used to build direct Form 4 URL for users to click through to SEC EDGAR)
    primary_document = ""
    if "<FILENAME>" in text:
        fn_start = text.index("<FILENAME>") + len("<FILENAME>")
        fn_end = text.index("\n", fn_start)
        primary_document = text[fn_start:fn_end].strip()

    # Extract raw footnotes block (not parsed)
    footnotes_text = ""
    if "<footnotes>" in xml and "</footnotes>" in xml:
        fs = xml.index("<footnotes>")
        fe = xml.index("</footnotes>") + len("</footnotes>")
        footnotes_text = xml[fs:fe]

    # Parse using Form4Parser
    result = parser.parse_form4(xml, filing["accession"], filing["date_filed"])
    if not result:
        return {"filing": filing, "status": "parse_failed"}

    # Keep only P transactions
    p_txns = [t for t in result.transactions if t.transaction_code == "P"]
    if not p_txns:
        return {"filing": filing, "status": "no_p_after_parse"}

    # Extract issuer trading symbol from XML
    issuer_trading_symbol = ""
    if "<issuerTradingSymbol>" in xml:
        try:
            ts_start = xml.index("<issuerTradingSymbol>") + len("<issuerTradingSymbol>")
            ts_end = xml.index("</issuerTradingSymbol>")
            issuer_trading_symbol = xml[ts_start:ts_end].strip()
        except ValueError:
            pass

    # Build output
    output = {
        "accession": result.accession_number,
        "filing_date": result.filing_date,
        "issuer_cik": result.issuer_cik,
        "issuer_name": result.issuer_name,
        "issuer_trading_symbol": issuer_trading_symbol,
        "is_10b5_1": result.is_10b5_1,
        "primary_document": primary_document,
        "insider": {
            "name": result.insider.name,
            "cik": result.insider.cik,
            "title": result.insider.title,
            "is_officer": result.insider.is_officer,
            "is_director": result.insider.is_director,
            "is_ten_percent_owner": result.insider.is_ten_percent_owner,
        },
        "footnotes": footnotes_text,
        "p_transactions": [
            {
                "security_title": t.security_title,
                "transaction_date": t.transaction_date,
                "transaction_code": t.transaction_code,
                "transaction_type": t.transaction_type,
                "shares": t.shares,
                "price_per_share": t.price_per_share,
                "total_value": t.total_value,
                "shares_after_transaction": t.shares_after_transaction,
                "ownership_type": t.ownership_type,
                "ownership_nature": t.ownership_nature,
                "is_derivative": t.is_derivative,
            }
            for t in p_txns
        ],
        "filer_cik": filing["cik"],
        "filer_name": filing["company_name"],
        "txt_url": filing["txt_url"],
    }
    return {"filing": filing, "status": "ok", "parsed": output}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", required=True, help="P-only index JSON file")
    args = ap.parse_args()

    with open(args.input) as f:
        data = json.load(f)

    date = data["date"]
    filings = data["filings"]
    total = len(filings)

    log_path = f"/tmp/parse_form4_p_{date.replace('-', '')}.log"
    log_file = open(log_path, "w", buffering=1)

    def log(msg):
        print(msg, flush=True)
        log_file.write(msg + "\n")
        log_file.flush()

    log(f"Input: {args.input}")
    log(f"Date: {date}")
    log(f"Filings to parse: {total}")
    log(f"Workers: {WORKERS}, Pace: {PACE_SEC}s per worker")
    log(f"Log: {log_path}\n")

    start = time.time()
    parsed_list = []
    status_counts = {}
    processed = 0

    with ThreadPoolExecutor(max_workers=WORKERS) as executor:
        futures = {executor.submit(fetch_xml_and_footnotes, f): f for f in filings}
        for future in as_completed(futures):
            result = future.result()
            processed += 1
            status = result["status"]
            status_counts[status] = status_counts.get(status, 0) + 1

            if status == "ok":
                parsed_list.append(result["parsed"])

            if processed % 20 == 0 or processed == total:
                elapsed = round(time.time() - start, 1)
                rate = processed / elapsed if elapsed > 0 else 0
                eta = (total - processed) / rate if rate > 0 else 0
                log(f"  [{processed:>3}/{total}] parsed={len(parsed_list)} "
                    f"statuses={dict(status_counts)} "
                    f"({elapsed:.0f}s, ~{eta:.0f}s remaining)")

    # Sort by total P value DESC for easier inspection
    for p in parsed_list:
        p["_total_p_value"] = sum(t["total_value"] for t in p["p_transactions"])
    parsed_list.sort(key=lambda x: x["_total_p_value"], reverse=True)
    for p in parsed_list:
        del p["_total_p_value"]

    out_path = args.input.replace("_p_only.json", "_p_parsed.json")
    with open(out_path, "w") as f:
        json.dump({
            "date": date,
            "total_input": total,
            "successfully_parsed": len(parsed_list),
            "status_counts": status_counts,
            "parsed": parsed_list,
        }, f, indent=2)

    elapsed = round(time.time() - start, 1)
    log(f"""
{'=' * 60}
  PARSE COMPLETE (for {date})
  Filings parsed successfully: {len(parsed_list)} / {total}
  Status breakdown: {dict(status_counts)}
  Time: {elapsed}s ({elapsed/60:.1f} min)
  Output: {out_path}
{'=' * 60}
""")
    log_file.close()


if __name__ == "__main__":
    main()
