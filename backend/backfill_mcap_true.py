"""Backfill `mcap_at_signal_true` on mature strong_buy SignalPerformance nodes.

Replaces the price-ratio estimate (`Company.market_cap × (signal_price / current_price)`)
with a primary-source calculation:

    mcap_at_signal_true = avg_raw_Form4_price × shares_outstanding_from_nearest_prior_10Q_or_10K

Shares outstanding comes from SEC EDGAR XBRL company-facts API.
Raw Form 4 price comes from stored InsiderTransaction nodes (GENUINE P only).

Additive only — does NOT modify any existing property (respects v1.2 immutability invariant).

Usage:
    python backfill_mcap_true.py --dry-run             # preview targets
    python backfill_mcap_true.py --apply               # run backfill
    python backfill_mcap_true.py --apply --limit 10    # test with 10
    python backfill_mcap_true.py --apply --delay 1.5   # slower XBRL pacing
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

sys.path.insert(0, ".")
sys.stdout.reconfigure(line_buffering=True)

from app.db.neo4j_client import Neo4jClient
from ingestion.sec_edgar.xbrl_client import (
    SharesOutstandingEntry,
    XBRLClient,
)

CHECKPOINT_DIR = os.path.join(os.path.dirname(__file__), "backfill_checkpoints")
ERROR_LOG_DIR = os.path.join(os.path.dirname(__file__), "backfill_errors")
DEFAULT_DELAY = 1.0  # seconds between XBRL calls (SEC allows 10 req/sec; we stay well under)

os.makedirs(ERROR_LOG_DIR, exist_ok=True)
os.makedirs(CHECKPOINT_DIR, exist_ok=True)

logger = logging.getLogger("mcap_true")
logger.setLevel(logging.INFO)
console = logging.StreamHandler(stream=sys.stdout)
console.setFormatter(logging.Formatter("%(message)s"))
logger.addHandler(console)


def checkpoint_path() -> str:
    return os.path.join(CHECKPOINT_DIR, "checkpoint_mcap_true.json")


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
        json.dump(
            {
                "processed": sorted(processed),
                "count": len(processed),
                "last_updated": datetime.utcnow().isoformat(),
            },
            f,
        )
    os.replace(tmp, path)


async def get_target_signals() -> list[dict]:
    """Mature strong_buy signals missing mcap_at_signal_true."""
    result = await Neo4jClient.execute_query(
        """
        MATCH (sp:SignalPerformance)
        WHERE sp.direction = 'buy'
          AND sp.conviction_tier = 'strong_buy'
          AND sp.is_mature = true
          AND sp.mcap_at_signal_true IS NULL
        RETURN sp.signal_id AS id, sp.cik AS cik, sp.ticker AS ticker,
               sp.signal_date AS sd, sp.market_cap AS mcap_old
        ORDER BY sp.signal_date
        """
    )
    return [dict(r) for r in result]


async def fetch_raw_px_for_signal(cik: str, signal_date: str) -> Optional[dict]:
    """Value-weighted average raw Form 4 price on (or near) signal_date.

    Returns {avg_px, total_value, total_shares, txn_date_used} or None if no data found.
    Widens to 5 days before + including signal_date if exact-day match returns nothing.
    """
    sd10 = signal_date[:10]
    # First try exact day
    r = await Neo4jClient.execute_query(
        """
        MATCH (c:Company {cik: $cik})-[:INSIDER_TRADE_OF]->(t:InsiderTransaction)
        WHERE t.transaction_code = 'P'
          AND (t.classification = 'GENUINE' OR t.classification = 'FILTERED' OR t.classification IS NULL)
          AND substring(t.transaction_date, 0, 10) = $sd
          AND t.shares > 0 AND t.price_per_share > 0
        RETURN sum(t.total_value) AS total_value,
               sum(t.shares) AS total_shares,
               $sd AS txn_date
        """,
        {"cik": cik, "sd": sd10},
    )
    if r and r[0]["total_value"] and r[0]["total_shares"]:
        tv = float(r[0]["total_value"])
        ts = float(r[0]["total_shares"])
        return {
            "avg_px": round(tv / ts, 4),
            "total_value": tv,
            "total_shares": ts,
            "txn_date_used": sd10,
        }

    # Widen to 5 days before + including signal_date
    from datetime import datetime, timedelta

    try:
        sd_dt = datetime.strptime(sd10, "%Y-%m-%d")
    except ValueError:
        return None
    start = (sd_dt - timedelta(days=5)).strftime("%Y-%m-%d")

    r = await Neo4jClient.execute_query(
        """
        MATCH (c:Company {cik: $cik})-[:INSIDER_TRADE_OF]->(t:InsiderTransaction)
        WHERE t.transaction_code = 'P'
          AND (t.classification = 'GENUINE' OR t.classification = 'FILTERED' OR t.classification IS NULL)
          AND substring(t.transaction_date, 0, 10) >= $start
          AND substring(t.transaction_date, 0, 10) <= $sd
          AND t.shares > 0 AND t.price_per_share > 0
        WITH sum(t.total_value) AS total_value,
             sum(t.shares) AS total_shares,
             max(substring(t.transaction_date, 0, 10)) AS txn_date
        RETURN total_value, total_shares, txn_date
        """,
        {"cik": cik, "start": start, "sd": sd10},
    )
    if r and r[0]["total_value"] and r[0]["total_shares"]:
        tv = float(r[0]["total_value"])
        ts = float(r[0]["total_shares"])
        return {
            "avg_px": round(tv / ts, 4),
            "total_value": tv,
            "total_shares": ts,
            "txn_date_used": r[0]["txn_date"],
        }
    return None


async def store_mcap_true(
    signal_id: str,
    mcap: float,
    shares: int,
    end_date: str,
    avg_px: float,
    source: str = "xbrl",
) -> bool:
    """Persist the new mcap_at_signal_true + provenance sidecar properties.

    Additive only — does NOT touch any existing property.

    Args:
        source: provenance label. One of 'xbrl' (pre-signal entry, preferred)
                or 'xbrl_post_signal_approx' (first entry within 90d after signal;
                used for late-IPO issuers where pre-signal XBRL doesn't exist).
    """
    now = datetime.utcnow().isoformat()
    try:
        await Neo4jClient.execute_write(
            """
            MATCH (sp:SignalPerformance {signal_id: $id})
            SET sp.mcap_at_signal_true = $mcap,
                sp.mcap_at_signal_true_source = $source,
                sp.mcap_at_signal_true_shares = $shares,
                sp.mcap_at_signal_true_shares_end_date = $end_date,
                sp.mcap_at_signal_true_avg_raw_px = $avg_px,
                sp.mcap_at_signal_true_computed_at = $now
            """,
            {
                "id": signal_id,
                "mcap": mcap,
                "shares": shares,
                "end_date": end_date,
                "avg_px": avg_px,
                "source": source,
                "now": now,
            },
        )
        return True
    except Exception as e:
        logger.error(f"Failed to store for {signal_id}: {e}")
        return False


async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument(
        "--delay",
        type=float,
        default=DEFAULT_DELAY,
        help=f"Seconds between XBRL calls (default: {DEFAULT_DELAY})",
    )
    ap.add_argument(
        "--limit", type=int, default=0, help="Limit to N signals (0 = all)"
    )
    args = ap.parse_args()

    if not args.apply and not args.dry_run:
        logger.error("Specify --apply or --dry-run")
        return

    is_apply = args.apply

    # Stable progress log
    progress_log_path = "/tmp/backfill_mcap_true.log"
    progress_handler = logging.FileHandler(progress_log_path, mode="w")
    progress_handler.setLevel(logging.INFO)
    progress_handler.setFormatter(logging.Formatter("%(asctime)s %(message)s"))
    logger.addHandler(progress_handler)

    # Timestamped error log
    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    error_log_path = os.path.join(
        ERROR_LOG_DIR, f"errors_mcap_true_{timestamp}.log"
    )
    file_handler = logging.FileHandler(error_log_path)
    file_handler.setLevel(logging.WARNING)
    file_handler.setFormatter(
        logging.Formatter("%(asctime)s %(levelname)s %(message)s")
    )
    logger.addHandler(file_handler)

    logger.info(f"Mode: {'APPLY' if is_apply else 'DRY RUN'}")
    logger.info(f"XBRL call pacing: {args.delay}s")
    logger.info(f"Progress log: {progress_log_path}")
    logger.info(f"Error log:    {error_log_path}")

    await Neo4jClient.connect()
    targets = await get_target_signals()
    logger.info(f"\nMature strong_buy signals needing mcap_at_signal_true: {len(targets)}")

    if args.limit > 0:
        targets = targets[: args.limit]
        logger.info(f"Limited to first {args.limit}")

    processed = load_checkpoint()
    if processed:
        before = len(targets)
        targets = [t for t in targets if t["id"] not in processed]
        logger.info(
            f"Checkpoint: {len(processed):,} done, "
            f"{before - len(targets):,} skipped, {len(targets):,} remaining"
        )

    if not targets:
        logger.info("Nothing to do.")
        await Neo4jClient.disconnect()
        return

    if args.dry_run:
        logger.info(f"\nDRY RUN — would process {len(targets)} signals:")
        unique_ciks = {t["cik"] for t in targets}
        logger.info(f"  Unique CIKs to fetch from XBRL: {len(unique_ciks)}")
        for t in targets[:10]:
            logger.info(
                f"  {t['ticker']:8} {t['sd']} cik={t['cik']} "
                f"mcap_old=${(t['mcap_old'] or 0)/1e6:.0f}M"
            )
        if len(targets) > 10:
            logger.info(f"  ... and {len(targets) - 10} more")
        await Neo4jClient.disconnect()
        return

    # APPLY mode
    start = time.time()
    stored = 0
    unresolved = []  # list of (signal_id, reason)
    xbrl_cache: dict[str, list[SharesOutstandingEntry]] = {}
    deltas = []  # (signal_id, ticker, mcap_old, mcap_new, pct_delta)

    for i, tgt in enumerate(targets):
        sid = tgt["id"]
        cik = tgt["cik"]
        ticker = tgt["ticker"]
        sd = str(tgt["sd"])[:10]

        # Fetch XBRL for this CIK (cache per-run)
        if cik not in xbrl_cache:
            if i > 0 and cik not in xbrl_cache:
                time.sleep(args.delay)
            try:
                entries = await XBRLClient.get_shares_outstanding(cik)
            except Exception as e:
                logger.warning(f"XBRL fetch failed for {ticker} ({cik}): {e}")
                xbrl_cache[cik] = []  # cache empty so we don't retry within this run
                unresolved.append((sid, f"xbrl_fetch_error: {type(e).__name__}"))
                continue
            xbrl_cache[cik] = entries

        entries = xbrl_cache[cik]
        if not entries:
            unresolved.append((sid, "no_xbrl_shares_facts"))
            continue

        picked = XBRLClient.pick_shares_at_or_before(entries, sd)
        source_label = "xbrl"
        if not picked:
            # Fallback: use earliest XBRL entry AFTER signal, within 90 days.
            # For stable issuers, shares outstanding changes slowly — a quarter
            # post-signal is typically within a few % of point-in-time.
            # Labeled distinctly so audit consumers can flag it.
            picked = XBRLClient.pick_nearest_post_signal(entries, sd, max_days=90)
            if picked:
                source_label = "xbrl_post_signal_approx"
            else:
                unresolved.append((sid, f"no_shares_within_90d_of_{sd}"))
                continue

        # Get raw price from Form 4 transactions
        raw_px_info = await fetch_raw_px_for_signal(cik, sd)
        if not raw_px_info:
            unresolved.append((sid, "no_p_txns_for_signal_date_even_widened"))
            continue

        mcap = round(raw_px_info["avg_px"] * picked.shares)
        ok = await store_mcap_true(
            signal_id=sid,
            mcap=float(mcap),
            shares=picked.shares,
            end_date=picked.end_date,
            avg_px=raw_px_info["avg_px"],
            source=source_label,
        )
        if ok:
            stored += 1
            processed.add(sid)
            mcap_old = tgt["mcap_old"] or 0
            pct_delta = (
                abs(mcap - mcap_old) / mcap_old * 100 if mcap_old > 0 else 0.0
            )
            deltas.append((sid, ticker, mcap_old, mcap, pct_delta))

            if (i + 1) % 25 == 0:
                save_checkpoint(processed)

        if (i + 1) % 10 == 0 or (i + 1) == len(targets):
            elapsed = round(time.time() - start, 1)
            rate = (i + 1) / elapsed if elapsed > 0 else 0
            remaining = len(targets) - (i + 1)
            eta = remaining / rate if rate > 0 else 0
            logger.info(
                f"  {i+1:>4}/{len(targets)} ({(i+1)/len(targets)*100:.0f}%) — "
                f"stored:{stored} unresolved:{len(unresolved)} — "
                f"{elapsed:.0f}s, ~{eta:.0f}s left"
            )

    save_checkpoint(processed)
    total_time = round(time.time() - start, 1)

    logger.info(
        f"""
{'=' * 72}
  MCAP_AT_SIGNAL_TRUE BACKFILL COMPLETE
  Signals considered:     {len(targets):,}
  Stored (resolved):      {stored:,}
  Unresolved:             {len(unresolved):,}
  Unique CIKs fetched:    {len(xbrl_cache):,}
  Total time:             {total_time}s ({total_time / 60:.1f} min)
  Error log:              {error_log_path}
{'=' * 72}
"""
    )

    if unresolved:
        logger.info("\nUnresolved signals (check error log for details):")
        for sid, reason in unresolved:
            logger.info(f"  {sid}: {reason}")

    # Top 10 largest deltas (where true mcap differs most from the ratio estimate)
    if deltas:
        deltas_sorted = sorted(deltas, key=lambda x: x[4], reverse=True)[:10]
        logger.info("\nTop 10 largest |mcap_new − mcap_old| / mcap_old:")
        logger.info(f"  {'ticker':8} {'mcap_old':>14} {'mcap_new':>14} {'Δ%':>8}")
        for sid, ticker, mcap_old, mcap_new, pct in deltas_sorted:
            logger.info(
                f"  {(ticker or '—'):8} "
                f"${mcap_old/1e6:>12,.0f}M "
                f"${mcap_new/1e6:>12,.0f}M "
                f"{pct:>7.1f}%"
            )

    await Neo4jClient.disconnect()


if __name__ == "__main__":
    asyncio.run(main())
