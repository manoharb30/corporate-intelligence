"""Backfill market_cap + price_series for cluster signal companies.

Targets companies that have GENUINE insider clusters (2+ buyers, ≥$100K total)
but are missing market_cap or price_series data. Both are needed for the
strong_buy conviction tier filter (midcap $300M-$10B + value + cluster).

One yfinance call per ticker fetches both market_cap (from Ticker.info) and
2-year daily close prices (from Ticker.history).

Usage:
    python backfill_signal_coverage.py --dry-run             # preview target list
    python backfill_signal_coverage.py --apply               # run backfill
    python backfill_signal_coverage.py --apply --limit 20    # test with 20
    python backfill_signal_coverage.py --apply --delay 2.0   # slower pacing
"""

import argparse
import asyncio
import json
import logging
import os
import sys
import time
from datetime import datetime, timedelta
from typing import Optional

import yfinance as yf

sys.path.insert(0, ".")
sys.stdout.reconfigure(line_buffering=True)
from app.db.neo4j_client import Neo4jClient

CHECKPOINT_DIR = os.path.join(os.path.dirname(__file__), "backfill_checkpoints")
ERROR_LOG_DIR = os.path.join(os.path.dirname(__file__), "backfill_errors")
DEFAULT_DELAY = 1.5
DEFAULT_PERIOD = "2y"

os.makedirs(ERROR_LOG_DIR, exist_ok=True)
os.makedirs(CHECKPOINT_DIR, exist_ok=True)

logger = logging.getLogger("signal_coverage")
logger.setLevel(logging.INFO)
console = logging.StreamHandler(stream=sys.stdout)
console.setFormatter(logging.Formatter("%(message)s"))
logger.addHandler(console)


def checkpoint_path() -> str:
    return os.path.join(CHECKPOINT_DIR, "checkpoint_signal_coverage.json")


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


def fetch_market_cap_and_prices(
    ticker: str, period: str = DEFAULT_PERIOD
) -> tuple[Optional[float], Optional[list[dict]]]:
    """Fetch both market_cap and price history in one yfinance session.

    Returns (market_cap, price_series). Either/both may be None on failure.
    """
    mcap = None
    series = None
    try:
        t = yf.Ticker(ticker)

        # Market cap (from info dict)
        try:
            info = t.info
            cap = info.get("marketCap")
            if cap and cap > 0:
                mcap = float(cap)
        except Exception as e:
            logger.warning(f"{ticker}: market_cap fetch failed: {type(e).__name__}: {str(e)[:60]}")

        # Price history (daily closes)
        try:
            df = t.history(period=period)
            if not df.empty:
                tmp = []
                for date, row in df.iterrows():
                    close = row.get("Close")
                    if close is None or close <= 0:
                        continue
                    tmp.append({
                        "d": date.strftime("%Y-%m-%d"),
                        "c": round(float(close), 2),
                    })
                series = tmp if tmp else None
        except Exception as e:
            logger.warning(f"{ticker}: price history fetch failed: {type(e).__name__}: {str(e)[:60]}")

    except Exception as e:
        logger.warning(f"{ticker}: yfinance Ticker init failed: {type(e).__name__}: {str(e)[:60]}")

    return mcap, series


async def get_target_companies(refresh_older_than_days: Optional[int] = None) -> list[dict]:
    """Cluster signal companies (2+ buyers, ≥$100K GENUINE P).

    Two modes:
    - Default (refresh_older_than_days=None): only companies MISSING market_cap or price_series.
      Original backfill behavior — safe / additive.
    - Refresh mode (refresh_older_than_days=N): also include companies whose
      `prices_updated_at` is older than N days (stale prices). Used to refresh
      freshness for immature signals.

    Matured SignalPerformance nodes are NEVER affected by this script —
    `compute_all` enforces v1.2 immutability on them regardless of what this
    script writes to the Company node.
    """
    missing_clause = "(c.market_cap IS NULL OR c.price_series IS NULL)"
    if refresh_older_than_days and refresh_older_than_days > 0:
        # Stale = prices_updated_at older than N days, using ISO lexical comparison.
        cutoff = (datetime.utcnow() - timedelta(days=refresh_older_than_days)).isoformat()
        where_clause = (
            f"({missing_clause} "
            f"OR c.prices_updated_at IS NULL "
            f"OR c.prices_updated_at < '{cutoff}')"
        )
    else:
        where_clause = missing_clause

    query = f"""
        MATCH (c:Company)-[:INSIDER_TRADE_OF]->(t:InsiderTransaction)<-[:TRADED_BY]-(p:Person)
        WHERE t.classification = 'GENUINE'
          AND t.transaction_code = 'P'
          AND t.transaction_date IS NOT NULL
        WITH c, count(DISTINCT p.name) AS buyers, sum(t.total_value) AS cluster_value
        WHERE buyers >= 2
          AND cluster_value >= 100000
          AND c.tickers IS NOT NULL AND size(c.tickers) > 0
          AND {where_clause}
        WITH DISTINCT c
        RETURN c.cik AS cik, c.tickers[0] AS ticker, c.name AS name,
               c.market_cap IS NULL AS needs_mcap,
               c.price_series IS NULL AS needs_prices,
               c.prices_updated_at AS prices_updated_at
        ORDER BY ticker
    """
    result = await Neo4jClient.execute_query(query)
    return [dict(r) for r in result]


async def store_data(
    cik: str, ticker: str, market_cap: Optional[float], series: Optional[list[dict]]
) -> tuple[bool, bool]:
    """Store market_cap and/or price_series on Company node.

    Returns (stored_mcap, stored_prices) flags.
    """
    now = datetime.utcnow().isoformat()
    set_clauses = []
    params = {"cik": cik, "now": now, "ticker": ticker}

    stored_mcap = False
    stored_prices = False

    if market_cap is not None:
        set_clauses.append("c.market_cap = $market_cap")
        set_clauses.append("c.market_cap_updated_at = $now")
        params["market_cap"] = market_cap
        stored_mcap = True

    if series is not None:
        series_json = json.dumps(series, separators=(",", ":"))
        set_clauses.append("c.price_series = $series_json")
        set_clauses.append("c.prices_updated_at = $now")
        set_clauses.append("c.price_count = $count")
        params["series_json"] = series_json
        params["count"] = len(series)
        stored_prices = True

    if not set_clauses:
        return False, False

    set_clauses.append("c.ticker = COALESCE(c.ticker, $ticker)")
    query = f"""
        MATCH (c:Company {{cik: $cik}})
        SET {', '.join(set_clauses)}
    """
    try:
        await Neo4jClient.execute_write(query, params)
        return stored_mcap, stored_prices
    except Exception as e:
        logger.error(f"Failed to store for {ticker} ({cik}): {e}")
        return False, False


async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--delay", type=float, default=DEFAULT_DELAY,
                    help=f"Seconds between yfinance calls (default: {DEFAULT_DELAY})")
    ap.add_argument("--period", type=str, default=DEFAULT_PERIOD,
                    help=f"yfinance price period (default: {DEFAULT_PERIOD})")
    ap.add_argument("--limit", type=int, default=0,
                    help="Limit to N tickers (0 = all)")
    ap.add_argument("--refresh-older-than", type=int, default=0,
                    help="Also refresh companies whose prices_updated_at is older than N days "
                         "(0 = disabled, backfill-only behavior). Use for freshness ops; does NOT "
                         "affect matured SignalPerformance rows (v1.2 invariant is enforced by compute_all).")
    args = ap.parse_args()

    if not args.apply and not args.dry_run:
        logger.error("Specify --apply or --dry-run")
        return

    is_apply = args.apply

    # Stable progress log — tail with: tail -f /tmp/backfill_signal_coverage.log
    progress_log_path = "/tmp/backfill_signal_coverage.log"
    progress_handler = logging.FileHandler(progress_log_path, mode='w')
    progress_handler.setLevel(logging.INFO)
    progress_handler.setFormatter(logging.Formatter("%(asctime)s %(message)s"))
    logger.addHandler(progress_handler)

    # Timestamped error log (warnings only, for audit)
    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    error_log_path = os.path.join(ERROR_LOG_DIR, f"errors_signal_coverage_{timestamp}.log")
    file_handler = logging.FileHandler(error_log_path)
    file_handler.setLevel(logging.WARNING)
    file_handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
    logger.addHandler(file_handler)

    logger.info(f"Mode: {'APPLY' if is_apply else 'DRY RUN'}")
    logger.info(f"Period: {args.period} | Delay: {args.delay}s")
    logger.info(f"Progress log: {progress_log_path}")
    logger.info(f"Error log:    {error_log_path}")

    await Neo4jClient.connect()
    refresh_older_than = args.refresh_older_than if args.refresh_older_than > 0 else None
    if refresh_older_than:
        logger.info(f"Refresh mode: include companies with prices older than {refresh_older_than} days")
    targets = await get_target_companies(refresh_older_than_days=refresh_older_than)

    mcap_needed = sum(1 for t in targets if t['needs_mcap'])
    price_needed = sum(1 for t in targets if t['needs_prices'])
    stale = [t for t in targets if not t['needs_mcap'] and not t['needs_prices']]
    logger.info(f"\nCluster signal companies to process: {len(targets)}")
    logger.info(f"  Missing market_cap:     {mcap_needed}")
    logger.info(f"  Missing price_series:   {price_needed}")
    logger.info(f"  Stale (refresh mode):   {len(stale)}")

    if args.limit > 0:
        targets = targets[: args.limit]
        logger.info(f"Limited to first {args.limit}")

    # Checkpoint is meaningful for "first-time fill" (backfill mode) only.
    # In refresh mode, a CIK being in the checkpoint just means it was filled ONCE;
    # it does NOT mean the data is still fresh. So skip the checkpoint in refresh mode.
    if refresh_older_than:
        processed = set()
        logger.info("Checkpoint disabled in refresh mode (each run targets freshness, not first-fill).")
    else:
        processed = load_checkpoint()
        if processed:
            before = len(targets)
            targets = [t for t in targets if t['cik'] not in processed]
            logger.info(f"Checkpoint: {len(processed):,} done, {before - len(targets):,} skipped, {len(targets):,} remaining")

    if not targets:
        logger.info("Nothing to do.")
        await Neo4jClient.disconnect()
        return

    if args.dry_run:
        logger.info(f"\nDRY RUN — would process {len(targets)} companies:")
        for t in targets[:20]:
            flags = []
            if t['needs_mcap']: flags.append("mcap")
            if t['needs_prices']: flags.append("prices")
            if not flags:
                flags.append("stale-refresh")
            updated = (t.get('prices_updated_at') or '')[:10] or 'never'
            logger.info(f"  {t['ticker']:8} {(t['name'] or '')[:40]:40} [{','.join(flags):18}] last_updated={updated}")
        if len(targets) > 20:
            logger.info(f"  ... and {len(targets) - 20} more")
        await Neo4jClient.disconnect()
        return

    # Apply mode
    start = time.time()
    stored_mcap = 0
    stored_prices = 0
    failed = 0

    for i, tgt in enumerate(targets):
        ticker = tgt['ticker']
        cik = tgt['cik']

        if i > 0:
            time.sleep(args.delay)

        mcap, series = fetch_market_cap_and_prices(ticker, period=args.period)
        if mcap is None and series is None:
            failed += 1
            logger.warning(f"No data for {ticker} ({cik})")
            continue

        stored_m, stored_p = await store_data(cik, ticker, mcap, series)
        if stored_m or stored_p:
            if stored_m:
                stored_mcap += 1
            if stored_p:
                stored_prices += 1
            processed.add(cik)
            if (i + 1) % 25 == 0:
                save_checkpoint(processed)
        else:
            failed += 1

        if (i + 1) % 25 == 0 or (i + 1) == len(targets):
            elapsed = round(time.time() - start, 1)
            remaining = len(targets) - (i + 1)
            rate = (i + 1) / elapsed if elapsed > 0 else 0
            eta = remaining / rate if rate > 0 else 0
            logger.info(
                f"  {i+1:>4}/{len(targets)} ({(i+1)/len(targets)*100:.0f}%) — "
                f"mcap:{stored_mcap} prices:{stored_prices} failed:{failed} — "
                f"{elapsed:.0f}s, ~{eta:.0f}s left"
            )

    save_checkpoint(processed)
    total_time = round(time.time() - start, 1)
    logger.info(f"""
{'=' * 60}
  SIGNAL COVERAGE BACKFILL COMPLETE
  Companies processed: {len(targets):,}
  Market cap stored:   {stored_mcap:,}
  Prices stored:       {stored_prices:,}
  Failed:              {failed:,}
  Total time:          {total_time}s ({total_time / 60:.1f} min)
  Error log:           {error_log_path}
{'=' * 60}
""")
    if failed > 0:
        logger.warning(f"  {failed} tickers failed — check error log")

    await Neo4jClient.disconnect()


if __name__ == "__main__":
    asyncio.run(main())
