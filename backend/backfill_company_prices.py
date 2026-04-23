"""Backfill 2 years of daily close prices for all companies with signals.

Stores prices as a JSON string property on Company nodes:
    Company.price_series = '[{"d":"2024-04-01","c":118.40}, ...]'
    Company.prices_updated_at = '2026-04-11T10:00:00'

Reads prices from yfinance, one ticker at a time with delays to avoid rate limits.
Checkpoints progress so we can resume if interrupted.

Usage:
    python backfill_company_prices.py --apply
    python backfill_company_prices.py --apply --workers 3
    python backfill_company_prices.py --dry-run
"""

import argparse
import asyncio
import json
import logging
import os
import sys
import time
from datetime import datetime
from typing import Optional

import yfinance as yf

sys.path.insert(0, ".")
from app.db.neo4j_client import Neo4jClient

CHECKPOINT_DIR = os.path.join(os.path.dirname(__file__), "backfill_checkpoints")
ERROR_LOG_DIR = os.path.join(os.path.dirname(__file__), "backfill_errors")
DEFAULT_DELAY = 1.5  # seconds between yfinance calls
DEFAULT_PERIOD = "2y"

os.makedirs(ERROR_LOG_DIR, exist_ok=True)
os.makedirs(CHECKPOINT_DIR, exist_ok=True)

logger = logging.getLogger("price_backfill")
logger.setLevel(logging.INFO)
console = logging.StreamHandler(stream=sys.stdout)
console.setFormatter(logging.Formatter("%(message)s"))
logger.addHandler(console)

# Force unbuffered stdout so tail -f shows progress immediately
sys.stdout.reconfigure(line_buffering=True)


def checkpoint_path() -> str:
    return os.path.join(CHECKPOINT_DIR, "checkpoint_company_prices.json")


def load_checkpoint() -> set:
    path = checkpoint_path()
    if os.path.exists(path):
        with open(path) as f:
            data = json.load(f)
        return set(data.get("processed", []))
    return set()


def save_checkpoint(processed: set):
    path = checkpoint_path()
    tmp = path + ".tmp"
    with open(tmp, "w") as f:
        json.dump({
            "processed": list(processed),
            "count": len(processed),
            "last_updated": datetime.utcnow().isoformat(),
        }, f)
    os.replace(tmp, path)


def fetch_price_series(ticker: str, period: str = DEFAULT_PERIOD) -> Optional[list[dict]]:
    """Fetch daily close prices for a ticker from yfinance.

    Returns list of {"d": "YYYY-MM-DD", "c": float} or None on failure.
    """
    try:
        df = yf.Ticker(ticker).history(period=period)
        if df.empty:
            return None
        series = []
        for date, row in df.iterrows():
            close = row.get("Close")
            if close is None or close <= 0:
                continue
            series.append({
                "d": date.strftime("%Y-%m-%d"),
                "c": round(float(close), 2),
            })
        return series if series else None
    except Exception as e:
        logger.warning(f"yfinance error for {ticker}: {type(e).__name__}: {str(e)[:100]}")
        return None


async def get_target_companies() -> list[dict]:
    """Get all companies that have at least one SignalPerformance node."""
    result = await Neo4jClient.execute_query("""
        MATCH (sp:SignalPerformance)
        WHERE sp.ticker IS NOT NULL AND sp.ticker <> ""
        WITH DISTINCT sp.ticker AS ticker, sp.cik AS cik
        RETURN ticker, cik
        ORDER BY ticker
    """)
    return [{"ticker": r["ticker"], "cik": r["cik"]} for r in result]


async def store_price_series(cik: str, ticker: str, series: list[dict]) -> bool:
    """Store the price series JSON on the Company node."""
    series_json = json.dumps(series, separators=(",", ":"))
    try:
        await Neo4jClient.execute_write("""
            MATCH (c:Company {cik: $cik})
            SET c.price_series = $series_json,
                c.prices_updated_at = $now,
                c.price_count = $count,
                c.ticker = COALESCE(c.ticker, $ticker)
        """, {
            "cik": cik,
            "series_json": series_json,
            "now": datetime.utcnow().isoformat(),
            "count": len(series),
            "ticker": ticker,
        })
        return True
    except Exception as e:
        logger.error(f"Failed to store prices for {ticker} ({cik}): {e}")
        return False


async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--delay", type=float, default=DEFAULT_DELAY, help="Seconds between yfinance calls")
    ap.add_argument("--period", type=str, default=DEFAULT_PERIOD, help="yfinance period (1y, 2y, 5y)")
    ap.add_argument("--limit", type=int, default=0, help="Limit to N tickers (0 = all)")
    args = ap.parse_args()

    if not args.apply and not args.dry_run:
        logger.error("Specify --apply or --dry-run")
        return

    is_apply = args.apply

    # Setup error log
    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    error_log_path = os.path.join(ERROR_LOG_DIR, f"errors_company_prices_{timestamp}.log")
    file_handler = logging.FileHandler(error_log_path)
    file_handler.setLevel(logging.WARNING)
    file_handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
    logger.addHandler(file_handler)

    logger.info(f"Mode: {'APPLY' if is_apply else 'DRY RUN'}")
    logger.info(f"Period: {args.period} | Delay: {args.delay}s")
    logger.info(f"Error log: {error_log_path}")

    await Neo4jClient.connect()
    companies = await get_target_companies()
    logger.info(f"Companies with signals: {len(companies):,}")

    if args.limit > 0:
        companies = companies[: args.limit]
        logger.info(f"Limited to first {args.limit}")

    # Load checkpoint
    processed = load_checkpoint()
    if processed:
        before = len(companies)
        companies = [c for c in companies if c["cik"] not in processed]
        logger.info(f"Checkpoint: {len(processed):,} already processed, {before - len(companies):,} skipped, {len(companies):,} remaining")

    if not companies:
        logger.info("Nothing to do.")
        await Neo4jClient.disconnect()
        return

    # Process each ticker
    start = time.time()
    stored = 0
    failed = 0
    skipped = 0

    for i, c in enumerate(companies):
        ticker = c["ticker"]
        cik = c["cik"]

        if i > 0:
            time.sleep(args.delay)

        series = fetch_price_series(ticker, period=args.period)
        if not series:
            failed += 1
            logger.warning(f"No price data for {ticker} ({cik})")
            continue

        if is_apply:
            ok = await store_price_series(cik, ticker, series)
            if ok:
                stored += 1
                processed.add(cik)
                # Save checkpoint every 25
                if stored % 25 == 0:
                    save_checkpoint(processed)
            else:
                failed += 1
        else:
            skipped += 1

        # Progress every 25
        if (i + 1) % 25 == 0:
            elapsed = round(time.time() - start, 1)
            done = i + 1
            remaining_count = len(companies) - done
            speed = done / elapsed if elapsed > 0 else 0
            remaining_time = remaining_count / speed if speed > 0 else 0
            logger.info(
                f"  {done:>5,}/{len(companies):,} ({done / len(companies) * 100:.0f}%) — "
                f"{stored} stored, {failed} failed — "
                f"{elapsed:.0f}s elapsed — ~{remaining_time:.0f}s remaining"
            )

    # Final checkpoint
    if is_apply:
        save_checkpoint(processed)

    total_time = round(time.time() - start, 1)
    logger.info(f"""
{'=' * 60}
  PRICE BACKFILL {'COMPLETE' if is_apply else 'DRY RUN'}
  Companies: {len(companies):,}
  Stored: {stored:,}
  Failed: {failed:,}
  Total time: {total_time}s ({total_time / 60:.1f} min)
  Error log: {error_log_path}
{'=' * 60}
""")

    if failed > 0:
        logger.warning(f"  {failed} tickers failed — check error log")

    await Neo4jClient.disconnect()


if __name__ == "__main__":
    asyncio.run(main())
