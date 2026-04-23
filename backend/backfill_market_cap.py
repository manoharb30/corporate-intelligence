"""Backfill market cap for all companies with signals.

Fetches market cap from yfinance and stores on Company.market_cap in Neo4j.
Only processes companies that have SignalPerformance nodes (i.e., companies
where we've detected insider clusters).

Usage:
    python backfill_market_cap.py --dry-run
    python backfill_market_cap.py --apply
    python backfill_market_cap.py --apply --limit 50
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
os.makedirs(CHECKPOINT_DIR, exist_ok=True)

DEFAULT_DELAY = 1.5  # seconds between yfinance calls

logger = logging.getLogger("mcap_backfill")
logger.setLevel(logging.INFO)
console = logging.StreamHandler(stream=sys.stdout)
console.setFormatter(logging.Formatter("%(message)s"))
logger.addHandler(console)
sys.stdout.reconfigure(line_buffering=True)


def checkpoint_path() -> str:
    return os.path.join(CHECKPOINT_DIR, "checkpoint_market_cap.json")


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


def fetch_market_cap(ticker: str) -> Optional[float]:
    """Fetch market cap from yfinance for a ticker."""
    try:
        info = yf.Ticker(ticker).info
        mcap = info.get("marketCap")
        if mcap and mcap > 0:
            return float(mcap)
        return None
    except Exception as e:
        logger.warning(f"yfinance error for {ticker}: {type(e).__name__}: {str(e)[:80]}")
        return None


async def get_target_companies() -> list[dict]:
    """Get companies with strong_buy signals that need market cap."""
    result = await Neo4jClient.execute_query("""
        MATCH (sp:SignalPerformance)
        WHERE sp.ticker IS NOT NULL AND sp.ticker <> ""
          AND sp.conviction_tier = 'strong_buy'
        WITH DISTINCT sp.ticker AS ticker, sp.cik AS cik
        RETURN ticker, cik
        ORDER BY ticker
    """)
    return [{"ticker": r["ticker"], "cik": r["cik"]} for r in result]


async def store_market_cap(cik: str, ticker: str, market_cap: float) -> bool:
    """Store market cap on the Company node."""
    try:
        await Neo4jClient.execute_query("""
            MATCH (c:Company {cik: $cik})
            SET c.market_cap = $market_cap,
                c.market_cap_updated_at = $now
        """, {
            "cik": cik,
            "market_cap": market_cap,
            "now": datetime.utcnow().isoformat(),
        })
        return True
    except Exception as e:
        logger.error(f"Failed to store market cap for {ticker} ({cik}): {e}")
        return False


async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--delay", type=float, default=DEFAULT_DELAY)
    ap.add_argument("--limit", type=int, default=0, help="Limit to N tickers (0 = all)")
    ap.add_argument("--reset", action="store_true", help="Reset checkpoint and start fresh")
    args = ap.parse_args()

    if not args.apply and not args.dry_run:
        logger.error("Specify --apply or --dry-run")
        return

    is_apply = args.apply

    logger.info(f"Mode: {'APPLY' if is_apply else 'DRY RUN'}")
    logger.info(f"Delay: {args.delay}s")

    await Neo4jClient.connect()
    companies = await get_target_companies()
    logger.info(f"Companies with signals: {len(companies)}")

    if args.limit > 0:
        companies = companies[:args.limit]
        logger.info(f"Limited to first {args.limit}")

    # Load checkpoint
    processed = set() if args.reset else load_checkpoint()
    if processed:
        before = len(companies)
        companies = [c for c in companies if c["cik"] not in processed]
        logger.info(f"Checkpoint: {len(processed)} already done, {len(companies)} remaining")

    if not companies:
        logger.info("Nothing to do.")
        return

    start = time.time()
    stored = 0
    failed = 0
    skipped = 0

    for i, c in enumerate(companies):
        ticker = c["ticker"]
        cik = c["cik"]

        if i > 0:
            time.sleep(args.delay)

        mcap = fetch_market_cap(ticker)
        if not mcap:
            failed += 1
            logger.warning(f"No market cap for {ticker} ({cik})")
            # Still mark as processed so we don't retry failures every run
            processed.add(cik)
            continue

        if is_apply:
            ok = await store_market_cap(cik, ticker, mcap)
            if ok:
                stored += 1
                processed.add(cik)
                if stored % 25 == 0:
                    save_checkpoint(processed)
            else:
                failed += 1
        else:
            mcap_str = f"${mcap/1e9:.1f}B" if mcap >= 1e9 else f"${mcap/1e6:.0f}M"
            logger.info(f"  {ticker:8} {mcap_str}")
            skipped += 1
            processed.add(cik)

        if (i + 1) % 25 == 0:
            elapsed = round(time.time() - start, 1)
            done = i + 1
            remaining = len(companies) - done
            speed = done / elapsed if elapsed > 0 else 0
            eta = remaining / speed if speed > 0 else 0
            logger.info(
                f"  {done:>5}/{len(companies)} ({done / len(companies) * 100:.0f}%) — "
                f"{stored} stored, {failed} failed — "
                f"{elapsed:.0f}s elapsed, ~{eta:.0f}s remaining"
            )

    if is_apply:
        save_checkpoint(processed)

    total_time = round(time.time() - start, 1)
    logger.info(f"""
{'=' * 60}
  MARKET CAP BACKFILL {'COMPLETE' if is_apply else 'DRY RUN'}
  Companies: {len(companies)}
  Stored: {stored}
  Failed: {failed}
  Total time: {total_time}s ({total_time / 60:.1f} min)
{'=' * 60}
""")


if __name__ == "__main__":
    asyncio.run(main())
