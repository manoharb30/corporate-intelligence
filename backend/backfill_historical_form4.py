"""Backfill historical Form 4 filings from SEC EDGAR daily index files.

Standalone script — does not touch the daily scanner or any existing services.
Uses parallel fetching (5 workers) for speed.

Usage:
    python backfill_historical_form4.py --start 2024-10-01 --end 2024-12-31 --dry-run
    python backfill_historical_form4.py --start 2024-10-01 --end 2024-12-31 --apply
"""

import argparse
import asyncio
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Optional

import requests

sys.path.insert(0, ".")
from app.db.neo4j_client import Neo4jClient
from ingestion.sec_edgar.parsers.form4_parser import Form4Parser

EDGAR_HEADERS = {"User-Agent": "LookInsight research@lookinsight.ai"}
WORKERS = 5

# Retry config
MAX_RETRIES_429 = 3
RATE_LIMIT_BACKOFF_SEC = 60
MAX_RETRIES_5XX = 2
SERVER_ERROR_BACKOFF_SEC = 30

# Sanity thresholds for per-day validation
MIN_FORM4_WEEKDAY = 50   # typical days have 500-2000 Form 4s; <50 is suspicious

parser = Form4Parser()


# === Error types ===
class FetchError(Exception):
    """Base fetch error."""
    def __init__(self, message, url="", status=None):
        self.url = url
        self.status = status
        super().__init__(message)

class RateLimitError(FetchError):
    """HTTP 429 — SEC throttling us."""
    pass

class NotFoundError(FetchError):
    """HTTP 404 — resource genuinely doesn't exist (holiday, bad URL)."""
    pass

class ServerError(FetchError):
    """HTTP 5xx — SEC side transient failure."""
    pass


# === Day-level result ===
@dataclass
class DayResult:
    date: str
    status: str  # "ok" | "no_index_404" | "rate_limited" | "server_error" | "genuinely_empty" | "error"
    filings_in_index: int = 0
    already_in_db: int = 0
    fetched: int = 0
    with_ps: int = 0
    ps_trades: int = 0
    stored: int = 0
    fetch_errors: int = 0
    rate_limited_count: int = 0
    server_error_count: int = 0
    retries_used: int = 0
    elapsed_sec: float = 0
    warning: str = ""


def get_trading_days(start_date: str, end_date: str) -> list[str]:
    start = datetime.strptime(start_date, "%Y-%m-%d")
    end = datetime.strptime(end_date, "%Y-%m-%d")
    days = []
    current = start
    while current <= end:
        if current.weekday() < 5:
            days.append(current.strftime("%Y-%m-%d"))
        current += timedelta(days=1)
    return days


def _get_with_retry(url: str, timeout: int = 15, max_retries_429: int = MAX_RETRIES_429,
                    max_retries_5xx: int = MAX_RETRIES_5XX) -> tuple[str, int]:
    """Fetch URL with differentiated error handling and retry.

    Returns: (text, retries_used)
    Raises: RateLimitError, NotFoundError, ServerError, FetchError
    """
    retries_429 = 0
    retries_5xx = 0
    total_retries = 0

    while True:
        try:
            resp = requests.get(url, headers=EDGAR_HEADERS, timeout=timeout)
        except requests.RequestException as e:
            raise FetchError(f"Network error: {e}", url=url)

        if resp.status_code == 200:
            return resp.text, total_retries

        if resp.status_code == 404:
            raise NotFoundError("Not found (404)", url=url, status=404)

        if resp.status_code == 429:
            if retries_429 >= max_retries_429:
                raise RateLimitError(f"Rate limited after {retries_429} retries", url=url, status=429)
            retries_429 += 1
            total_retries += 1
            time.sleep(RATE_LIMIT_BACKOFF_SEC)
            continue

        if 500 <= resp.status_code < 600:
            if retries_5xx >= max_retries_5xx:
                raise ServerError(f"Server error {resp.status_code} after {retries_5xx} retries",
                                  url=url, status=resp.status_code)
            retries_5xx += 1
            total_retries += 1
            time.sleep(SERVER_ERROR_BACKOFF_SEC)
            continue

        # Other 4xx — don't retry
        raise FetchError(f"HTTP {resp.status_code}", url=url, status=resp.status_code)


def fetch_daily_index(date_str: str) -> tuple[list[dict], str, int]:
    """Fetch the EDGAR daily index for one date.

    Returns: (filings, status, retries_used)
      status: "ok" | "no_index_404" | "rate_limited" | "server_error" | "error"
    """
    dt = datetime.strptime(date_str, "%Y-%m-%d")
    year = dt.year
    qtr = (dt.month - 1) // 3 + 1
    url = f"https://www.sec.gov/Archives/edgar/daily-index/{year}/QTR{qtr}/master.{dt.strftime('%Y%m%d')}.idx"

    try:
        text, retries = _get_with_retry(url)
    except NotFoundError:
        return [], "no_index_404", 0
    except RateLimitError:
        return [], "rate_limited", MAX_RETRIES_429
    except ServerError:
        return [], "server_error", MAX_RETRIES_5XX
    except FetchError as e:
        return [], "error", 0

    filings = []
    for line in text.split("\n"):
        if "|" not in line:
            continue
        parts = line.strip().split("|")
        if len(parts) < 5 or parts[2].strip() != "4":
            continue
        accession = parts[4].strip().split("/")[-1].replace(".txt", "")
        filings.append({
            "cik": parts[0].strip(),
            "company_name": parts[1].strip(),
            "date_filed": parts[3].strip(),
            "accession": accession,
            "txt_url": f"https://www.sec.gov/Archives/{parts[4].strip()}",
        })
    return filings, "ok", retries


def fetch_and_parse(filing: dict) -> dict:
    """Fetch one filing, extract XML, parse. Returns result dict.

    status:
      "ok"            — P/S found, parsed successfully
      "skip_no_ps"    — no P or S transactions in filing
      "skip_invalid"  — missing ownershipDocument or parse failed
      "rate_limited"  — HTTP 429 after retries
      "server_error"  — HTTP 5xx after retries
      "error"         — other error
    """
    try:
        text, retries = _get_with_retry(filing["txt_url"])
    except RateLimitError:
        return {"filing": filing, "status": "rate_limited", "retries": MAX_RETRIES_429}
    except ServerError:
        return {"filing": filing, "status": "server_error", "retries": MAX_RETRIES_5XX}
    except NotFoundError:
        return {"filing": filing, "status": "skip_invalid", "retries": 0}
    except FetchError as e:
        return {"filing": filing, "status": "error", "retries": 0, "error": str(e)}

    try:
        if "<ownershipDocument>" not in text:
            return {"filing": filing, "status": "skip_invalid", "retries": retries}

        # Early P/S check — skip expensive XML parse if no P or S codes present
        if ("<transactionCode>P</transactionCode>" not in text
            and "<transactionCode>S</transactionCode>" not in text):
            return {"filing": filing, "status": "skip_no_ps", "retries": retries}

        s = text.index("<ownershipDocument>")
        e = text.index("</ownershipDocument>") + len("</ownershipDocument>")
        xml = '<?xml version="1.0"?>\n' + text[s:e]

        # Extract raw footnotes block if present (store as-is, do not parse)
        footnotes_text = ""
        if "<footnotes>" in xml and "</footnotes>" in xml:
            fs = xml.index("<footnotes>")
            fe = xml.index("</footnotes>") + len("</footnotes>")
            footnotes_text = xml[fs:fe]

        result = parser.parse_form4(xml, filing["accession"], filing["date_filed"])
        if not result:
            return {"filing": filing, "status": "skip_invalid", "retries": retries}
        ps_trades = [t for t in result.transactions if t.transaction_code in ("P", "S")]
        if not ps_trades:
            return {"filing": filing, "status": "skip_no_ps", "retries": retries}
        return {"filing": filing, "result": result, "footnotes": footnotes_text,
                "status": "ok", "retries": retries}
    except Exception as e:
        return {"filing": filing, "status": "error", "retries": retries, "error": str(e)}


async def store_results(parsed_results: list[dict]) -> int:
    """Store all parsed P/S trades in Neo4j. Returns count stored."""
    stored = 0
    for item in parsed_results:
        if item["status"] != "ok" or not item.get("result"):
            continue
        result = item["result"]
        filing = item["filing"]
        footnotes_text = item.get("footnotes", "")
        issuer_cik = result.issuer_cik.zfill(10) if result.issuer_cik else filing["cik"].zfill(10)
        issuer_name = result.issuer_name or filing["company_name"]

        for idx, txn in enumerate(result.transactions):
            if txn.transaction_code not in ("P", "S"):
                continue

            # Price fix
            price_source = "filing"
            if txn.price_per_share == 0 and txn.shares > 0:
                try:
                    from app.services.stock_price_service import StockPriceService
                    ticker_result = await Neo4jClient.execute_query("""
                        MATCH (c:Company {cik: $cik})
                        WHERE c.tickers IS NOT NULL AND size(c.tickers) > 0
                        RETURN c.tickers[0] AS ticker
                    """, {"cik": issuer_cik})
                    if ticker_result and ticker_result[0].get("ticker"):
                        price_data = StockPriceService.get_price_at_date(
                            ticker_result[0]["ticker"], txn.transaction_date
                        )
                        if price_data and price_data.get("price_at_date"):
                            txn.price_per_share = price_data["price_at_date"]
                            txn.total_value = txn.shares * txn.price_per_share
                            price_source = "market_close"
                except Exception:
                    pass

            txn_id = f"{result.accession_number}_{idx}"
            pct = None
            try:
                if txn.transaction_code == "S" and (txn.shares_after_transaction + txn.shares) > 0:
                    pct = round(txn.shares / (txn.shares_after_transaction + txn.shares) * 100, 1)
                elif txn.transaction_code == "P" and txn.shares_after_transaction > 0:
                    pct = round(txn.shares / txn.shares_after_transaction * 100, 1)
            except Exception:
                pass

            try:
                await Neo4jClient.execute_query("""
                    MERGE (c:Company {cik: $cik})
                    ON CREATE SET c.name = $company_name
                    SET c.name = COALESCE(c.name, $company_name)
                    MERGE (t:InsiderTransaction {id: $txn_id})
                    SET t.accession_number = $accession, t.filing_date = $filing_date,
                        t.transaction_date = $txn_date, t.transaction_code = $code,
                        t.transaction_type = $type, t.security_title = $security,
                        t.shares = $shares, t.price_per_share = $price,
                        t.total_value = $total, t.shares_after_transaction = $after,
                        t.ownership_type = $own_type, t.is_derivative = $deriv,
                        t.insider_name = $name, t.insider_title = $title,
                        t.insider_cik = $insider_cik, t.is_10b5_1 = $is_plan,
                        t.is_officer = $is_officer, t.is_director = $is_director,
                        t.is_ten_percent_owner = $is_ten_percent_owner,
                        t.price_source = $price_source, t.pct_of_position_traded = $pct,
                        t.footnotes = $footnotes
                    MERGE (c)-[:INSIDER_TRADE_OF]->(t)
                    WITH t
                    MERGE (p:Person {normalized_name: toLower($name)})
                    ON CREATE SET p.name = $name, p.id = randomUUID()
                    MERGE (p)-[:TRADED_BY]->(t)
                """, {
                    "cik": issuer_cik, "company_name": issuer_name,
                    "txn_id": txn_id, "accession": result.accession_number,
                    "filing_date": filing["date_filed"], "txn_date": txn.transaction_date,
                    "code": txn.transaction_code, "type": txn.transaction_type,
                    "security": txn.security_title, "shares": txn.shares,
                    "price": txn.price_per_share, "total": txn.total_value,
                    "after": txn.shares_after_transaction, "own_type": txn.ownership_type,
                    "deriv": txn.is_derivative, "name": result.insider.name,
                    "title": result.insider.title, "insider_cik": result.insider.cik,
                    "is_plan": result.is_10b5_1, "price_source": price_source, "pct": pct,
                    "is_officer": result.insider.is_officer,
                    "is_director": result.insider.is_director,
                    "is_ten_percent_owner": result.insider.is_ten_percent_owner,
                    "footnotes": footnotes_text,
                })
                stored += 1
            except Exception:
                pass

    return stored


async def process_day(day: str, is_apply: bool, log) -> DayResult:
    """Process one trading day end-to-end. Returns DayResult."""
    day_start = time.time()
    dr = DayResult(date=day, status="ok")

    # 1. Fetch index
    filings, idx_status, idx_retries = fetch_daily_index(day)
    dr.retries_used += idx_retries

    if idx_status != "ok":
        dr.status = idx_status
        dr.elapsed_sec = round(time.time() - day_start, 1)
        return dr

    if not filings:
        dr.status = "genuinely_empty"
        dr.elapsed_sec = round(time.time() - day_start, 1)
        return dr

    dr.filings_in_index = len(filings)

    # Sanity check: weekday with very few Form 4s is suspicious
    if len(filings) < MIN_FORM4_WEEKDAY:
        dr.warning = f"Only {len(filings)} Form 4s in index — unusually low"

    # 2. Dedup
    if is_apply:
        accessions = [f["accession"] for f in filings]
        existing = await Neo4jClient.execute_query("""
            MATCH (t:InsiderTransaction)
            WHERE t.accession_number IN $accs
            RETURN DISTINCT t.accession_number AS acc
        """, {"accs": accessions})
        existing_set = {r["acc"] for r in existing}
        if existing_set:
            before = len(filings)
            filings = [f for f in filings if f["accession"] not in existing_set]
            dr.already_in_db = before - len(filings)

    dr.fetched = len(filings)

    # 3. Parallel fetch + parse
    parsed = []
    if filings:
        with ThreadPoolExecutor(max_workers=WORKERS) as executor:
            futures = {executor.submit(fetch_and_parse, f): f for f in filings}
            for future in as_completed(futures):
                parsed.append(future.result())

    # 4. Classify results
    ok = [p for p in parsed if p["status"] == "ok"]
    dr.with_ps = len(ok)
    dr.ps_trades = sum(
        sum(1 for t in p["result"].transactions if t.transaction_code in ("P", "S"))
        for p in ok
    )
    dr.rate_limited_count = sum(1 for p in parsed if p["status"] == "rate_limited")
    dr.server_error_count = sum(1 for p in parsed if p["status"] == "server_error")
    dr.fetch_errors = sum(1 for p in parsed if p["status"] == "error")
    dr.retries_used += sum(p.get("retries", 0) for p in parsed)

    # If we got rate-limited on many filings, mark day as rate_limited
    if dr.rate_limited_count > 0 and dr.rate_limited_count >= len(filings) * 0.1:
        dr.warning = (dr.warning + " | " if dr.warning else "") + f"{dr.rate_limited_count} filings rate-limited"
        if dr.with_ps == 0:
            dr.status = "rate_limited"

    # 5. Store if applying
    if is_apply and ok:
        dr.stored = await store_results(ok)

    dr.elapsed_sec = round(time.time() - day_start, 1)
    return dr


def format_day_log(dr: DayResult) -> str:
    base = (
        f"  {dr.date}: [{dr.status}] idx={dr.filings_in_index} dedup={dr.already_in_db} "
        f"fetched={dr.fetched} with_ps={dr.with_ps} trades={dr.ps_trades} stored={dr.stored} "
        f"rl={dr.rate_limited_count} 5xx={dr.server_error_count} err={dr.fetch_errors} "
        f"retries={dr.retries_used} ({dr.elapsed_sec}s)"
    )
    if dr.warning:
        base += f" WARN: {dr.warning}"
    return base


async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--start", required=True)
    ap.add_argument("--end", required=True)
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    is_apply = args.apply
    if not is_apply and not args.dry_run:
        print("Specify --apply or --dry-run")
        sys.exit(2)

    mode = "APPLY" if is_apply else "DRY RUN"
    print(f"Mode: {mode}")
    print(f"Range: {args.start} to {args.end}")

    if is_apply:
        await Neo4jClient.connect()

    trading_days = get_trading_days(args.start, args.end)
    print(f"Trading days: {len(trading_days)}\n")

    start_time = time.time()
    log_path = f"/tmp/backfill_form4_{args.start}_{args.end}.log"
    log = open(log_path, "w")

    all_results: list[DayResult] = []
    for day in trading_days:
        dr = await process_day(day, is_apply, log)
        all_results.append(dr)
        msg = format_day_log(dr)
        print(msg)
        log.write(msg + "\n")
        log.flush()

    # Classify days
    status_counts = {}
    for dr in all_results:
        status_counts[dr.status] = status_counts.get(dr.status, 0) + 1

    total_filings = sum(r.filings_in_index for r in all_results)
    total_stored = sum(r.stored for r in all_results)
    total_ps = sum(r.ps_trades for r in all_results)
    total_errors = sum(r.fetch_errors + r.rate_limited_count + r.server_error_count for r in all_results)
    warnings = [r for r in all_results if r.warning]

    elapsed = round(time.time() - start_time, 1)

    summary = f"""
{'=' * 70}
  BACKFILL COMPLETE ({mode})
  Range: {args.start} to {args.end} | {len(trading_days)} trading days
{'-' * 70}
  Day status breakdown:
"""
    for status, cnt in sorted(status_counts.items()):
        summary += f"    {status:20}: {cnt}\n"

    summary += f"""{'-' * 70}
  Total Form 4 filings in indexes: {total_filings:,}
  P/S trades {'stored' if is_apply else 'found'}: {total_stored if is_apply else total_ps:,}
  Total errors (rate-limit + 5xx + other): {total_errors:,}
  Days with warnings: {len(warnings)}
  Time: {elapsed}s ({elapsed/60:.1f} min)
  Log: {log_path}
{'=' * 70}
"""

    if warnings:
        summary += "\nDAYS WITH WARNINGS:\n"
        for r in warnings:
            summary += f"  {r.date}: {r.warning}\n"

    # Exit code: 0 only if all days are clean (ok or genuinely_empty)
    problem_statuses = {"rate_limited", "server_error", "error"}
    bad_days = [r for r in all_results if r.status in problem_statuses]
    if bad_days:
        summary += f"\nDAYS NEEDING RETRY ({len(bad_days)}):\n"
        for r in bad_days:
            summary += f"  {r.date}: {r.status}\n"
        exit_code = 1
    else:
        exit_code = 0

    print(summary)
    log.write(summary)
    log.close()

    if is_apply:
        await Neo4jClient.disconnect()

    sys.exit(exit_code)


if __name__ == "__main__":
    asyncio.run(main())
