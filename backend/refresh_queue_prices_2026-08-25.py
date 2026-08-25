"""Refresh Company.price_series for research-queue names only.

Scoped deliberately to an explicit CIK list — NOT backfill_company_prices.py,
which has no ticker filter and would redo all ~200 signal companies for 2 years
(the mistake made on 2026-08-21). These are earnings-filtered near misses, so
most have either no series at all or a series that ends before their own cluster
window, which is why /research-queue cannot show a return for them.

Tickers come from the /api/near-miss payload, not Company.ticker, because several
of these Company nodes have a null ticker.

NaN guard is explicit: backfill_company_prices.fetch_price_series only rejects
`close <= 0`, and NaN <= 0 is False, so NaN closes pass straight through. NaN in
price_series is what produced the feed 500s fixed in a697352.

Usage:
    python refresh_queue_prices_2026-08-25.py --dry-run
    python refresh_queue_prices_2026-08-25.py --apply
"""
import argparse
import asyncio
import json
import math
import sys
import time
from datetime import datetime
from pathlib import Path

import yfinance as yf

sys.path.insert(0, str(Path(__file__).parent))
from app.db.neo4j_client import Neo4jClient

PERIOD = "1y"
DELAY = 1.5

QUEUE: list[tuple[str, str]] = [
    ("0002079999", "CDNL"), ("0001881487", "ACDC"), ("0001865200", "ANGX"),
    ("0001130713", "BBBY"), ("0001703057", "ABCL"), ("0001791145", "GBFH"),
    ("0001825088", "DFH"), ("0001872789", "EMBC"), ("0001631569", "CHCT"),
    ("0001730984", "BCML"), ("0000097134", "TNC"), ("0001005229", "CMCO"),
    ("0000063296", "MATW"), ("0002104052", "NVRI"), ("0001740332", "REZI"),
    ("0001854368", "DGXX"), ("0001127371", "CWBC"), ("0000860748", "KMPR"),
    ("0001899123", "BTDR"), ("0001884082", "PSNY"), ("0001725255", "AHCO"),
    ("0001227500", "EQBK"), ("0001812477", "KEEL"), ("0001627223", "CC"),
    ("0001964333", "BHRB"), ("0001630805", "BW"),
]


def fetch_series(ticker: str) -> tuple[list[dict] | None, int]:
    """Return (series, n_bad) where series is [{"d","c"}...] with NaN/<=0 dropped."""
    try:
        df = yf.Ticker(ticker).history(period=PERIOD)
    except Exception as e:
        print(f"    yfinance error: {type(e).__name__}: {str(e)[:90]}")
        return None, 0
    if df.empty:
        return None, 0
    series, bad = [], 0
    for dt, row in df.iterrows():
        close = row.get("Close")
        if close is None:
            bad += 1
            continue
        try:
            c = float(close)
        except (TypeError, ValueError):
            bad += 1
            continue
        if math.isnan(c) or math.isinf(c) or c <= 0:
            bad += 1
            continue
        series.append({"d": dt.strftime("%Y-%m-%d"), "c": round(c, 2)})
    return (series or None), bad


async def store(cik: str, ticker: str, series: list[dict]) -> None:
    await Neo4jClient.execute_write("""
        MATCH (c:Company {cik: $cik})
        SET c.price_series = $series_json,
            c.prices_updated_at = $now,
            c.price_count = $count,
            c.ticker = COALESCE(c.ticker, $ticker)
    """, {
        "cik": cik,
        "series_json": json.dumps(series, separators=(",", ":")),
        "now": datetime.utcnow().isoformat(),
        "count": len(series),
        "ticker": ticker,
    })


async def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    if not (args.apply or args.dry_run):
        print("Pass --apply or --dry-run")
        sys.exit(1)

    mode = "APPLY" if args.apply else "DRY RUN"
    print(f"{mode} — {len(QUEUE)} research-queue companies, period={PERIOD}\n")

    await Neo4jClient.connect()
    ok = failed = 0
    total_bad = 0
    try:
        for i, (cik, ticker) in enumerate(QUEUE, 1):
            print(f"[{i}/{len(QUEUE)}] {ticker} ({cik})")
            series, bad = fetch_series(ticker)
            total_bad += bad
            if not series:
                print("    no usable data — SKIPPED")
                failed += 1
            else:
                first, last = series[0]["d"], series[-1]["d"]
                print(f"    {len(series)} bars  {first} -> {last}  "
                      f"last close ${series[-1]['c']}"
                      + (f"  ({bad} bad bars dropped)" if bad else ""))
                if args.apply:
                    await store(cik, ticker, series)
                    print("    written")
                ok += 1
            if i < len(QUEUE):
                time.sleep(DELAY)
    finally:
        await Neo4jClient.disconnect()

    print(f"\n{mode} complete — ok={ok}, failed={failed}, "
          f"bad bars dropped={total_bad}")


asyncio.run(main())
