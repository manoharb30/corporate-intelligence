"""v1.5 Phase 13: per-candidate-cluster table for tier extension analysis.

Reads cluster detection output + XBRL ground-truth mcap + Form 4 raw prices,
attaches existing SignalPerformance linkage (if any), and writes a CSV for
Phase 14 per-tier analysis.

NO SignalPerformance mutations. Read-only against Neo4j (except for the
XBRL fetch, which is HTTP-only against data.sec.gov).

Run from backend/:
    venv/bin/python -m exports.tier_candidates_backfill
    venv/bin/python -m exports.tier_candidates_backfill --out exports/out/tier_candidates_v1_5.csv
"""

import argparse
import asyncio
import csv
import json
import logging
import os
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

from app.db.neo4j_client import Neo4jClient
from app.services.insider_cluster_service import InsiderClusterService
from ingestion.sec_edgar.xbrl_client import (
    SharesOutstandingEntry,
    XBRLClient,
)

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")

HORIZON_DAYS = 90
MATURITY_AGE_DAYS = 97


def size_tier(mcap: Optional[float]) -> str:
    if mcap is None:
        return "null"
    if mcap < 100_000_000:
        return "micro"
    if mcap < 300_000_000:
        return "small"
    if mcap <= 5_000_000_000:
        return "midcap"
    return "large"


async def fetch_existing_sp_map() -> dict[str, dict]:
    """Map existing SignalPerformance rows by signal_id → core fields."""
    rows = await Neo4jClient.execute_query(
        """
        MATCH (sp:SignalPerformance)
        RETURN sp.signal_id AS id, sp.conviction_tier AS tier, sp.is_mature AS mature,
               sp.price_day0 AS p0, sp.price_day90 AS p90, sp.spy_return_90d AS spy,
               sp.mcap_at_signal_true AS mcap_true,
               sp.mcap_at_signal_true_source AS mcap_src,
               sp.mcap_at_signal_true_shares AS mcap_shares,
               sp.mcap_at_signal_true_shares_end_date AS mcap_end_date,
               sp.mcap_at_signal_true_avg_raw_px AS avg_raw_px
        """
    )
    return {r["id"]: dict(r) for r in rows}


async def fetch_raw_px_for_signal(cik: str, signal_date: str) -> Optional[dict]:
    """Value-weighted avg raw Form 4 P-txn price on (or near) signal_date."""
    sd10 = signal_date[:10]
    r = await Neo4jClient.execute_query(
        """
        MATCH (c:Company {cik: $cik})-[:INSIDER_TRADE_OF]->(t:InsiderTransaction)
        WHERE t.transaction_code = 'P'
          AND (t.classification = 'GENUINE' OR t.classification = 'FILTERED' OR t.classification IS NULL)
          AND substring(t.transaction_date, 0, 10) = $sd
          AND t.shares > 0 AND t.price_per_share > 0
        RETURN sum(t.total_value) AS total_value,
               sum(t.shares) AS total_shares
        """,
        {"cik": cik, "sd": sd10},
    )
    if r and r[0]["total_value"] and r[0]["total_shares"]:
        tv = float(r[0]["total_value"])
        ts = float(r[0]["total_shares"])
        return {"avg_px": round(tv / ts, 4), "total_value": tv, "total_shares": ts}
    # Widen ±5 days
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
        RETURN sum(t.total_value) AS total_value,
               sum(t.shares) AS total_shares
        """,
        {"cik": cik, "start": start, "sd": sd10},
    )
    if r and r[0]["total_value"] and r[0]["total_shares"]:
        tv = float(r[0]["total_value"])
        ts = float(r[0]["total_shares"])
        return {"avg_px": round(tv / ts, 4), "total_value": tv, "total_shares": ts}
    return None


async def fetch_price_series_map(ciks: list[str]) -> dict[str, list[dict]]:
    if not ciks:
        return {}
    rows = await Neo4jClient.execute_query(
        """
        UNWIND $ciks AS cik
        OPTIONAL MATCH (c:Company {cik: cik})
        RETURN cik, c.price_series AS series
        """,
        {"ciks": ciks},
    )
    out: dict[str, list[dict]] = {}
    for r in rows:
        series = []
        if r.get("series"):
            try:
                series = json.loads(r["series"])
            except (ValueError, TypeError):
                pass
        out[r["cik"]] = series
    return out


async def fetch_spy_series() -> list[dict]:
    r = await Neo4jClient.execute_query(
        "MATCH (c:Company {ticker: 'SPY'}) RETURN c.price_series AS s"
    )
    if r and r[0].get("s"):
        try:
            return json.loads(r[0]["s"])
        except (ValueError, TypeError):
            pass
    return []


def find_price(series: list[dict], target_date: str, max_skip: int = 5) -> Optional[float]:
    if not series or not target_date:
        return None
    try:
        target = datetime.strptime(target_date[:10], "%Y-%m-%d")
    except (ValueError, TypeError):
        return None
    by_date = {e["d"]: float(e["c"]) for e in series if "d" in e and "c" in e}
    for skip in range(max_skip + 1):
        check = (target + timedelta(days=skip)).strftime("%Y-%m-%d")
        if check in by_date:
            return by_date[check]
    return None


async def fetch_filing_date_map(ciks: list[str]) -> dict[str, dict[str, str]]:
    """{cik: {transaction_date: latest_filing_date}}."""
    if not ciks:
        return {}
    rows = await Neo4jClient.execute_query(
        """
        MATCH (c:Company)-[:INSIDER_TRADE_OF]->(t:InsiderTransaction)
        WHERE c.cik IN $ciks AND t.transaction_code = 'P'
          AND (t.classification = 'GENUINE' OR t.classification = 'FILTERED' OR t.classification IS NULL)
          AND t.filing_date IS NOT NULL
        RETURN c.cik AS cik,
               substring(t.transaction_date, 0, 10) AS txn_date,
               max(t.filing_date) AS latest_filing_date
        """,
        {"ciks": ciks},
    )
    out: dict[str, dict[str, str]] = {}
    for r in rows:
        cik = r["cik"]
        out.setdefault(cik, {})[r["txn_date"]] = (r["latest_filing_date"] or "")[:10]
    return out


COLUMNS = [
    "accession_number",
    "cik",
    "ticker",
    "company_name",
    "signal_date",
    "actionable_date",
    "num_buyers",
    "total_value_usd",
    "avg_raw_px_usd",
    "mcap_at_signal_true_usd",
    "mcap_at_signal_true_source",
    "mcap_at_signal_true_shares",
    "mcap_at_signal_true_shares_end_date",
    "size_tier",
    "existing_signal_id",
    "existing_conviction_tier",
    "existing_is_mature",
    "price_day0",
    "price_day90",
    "return_90d_pct",
    "spy_return_90d_pct",
    "alpha_90d_pct",
    "hit_90d",
    "is_mature_by_age",
    "age_days_at_export",
]


async def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=str, default="exports/out/tier_candidates_v1_5.csv")
    ap.add_argument("--delay", type=float, default=1.0, help="XBRL call pacing (s)")
    args = ap.parse_args()

    await Neo4jClient.connect()

    logger.info("Running cluster detection (760 days, direction=buy, min_level=medium)...")
    clusters = await InsiderClusterService.detect_clusters(
        days=760, min_level="medium", direction="buy"
    )
    qualified = [c for c in clusters if c.num_buyers >= 2 and c.total_buy_value >= 100_000]
    logger.info(f"  Total clusters: {len(clusters)}; qualified (2+, >=$100K): {len(qualified)}")

    # Fetch existing SignalPerformance rows by accession_number (= signal_id)
    sp_map = await fetch_existing_sp_map()
    logger.info(f"  Existing SignalPerformance: {len(sp_map)} rows")

    # Gather CIKs for batch price_series + filing_date fetch
    ciks = sorted({c.cik for c in qualified if c.cik})
    logger.info(f"Fetching Company.price_series for {len(ciks)} CIKs...")
    price_series_map = await fetch_price_series_map(ciks)
    spy_series = await fetch_spy_series()
    logger.info(f"  SPY series: {len(spy_series)} entries")
    logger.info("Fetching filing-date map...")
    filing_date_map = await fetch_filing_date_map(ciks)

    now = datetime.now()
    xbrl_cache: dict[str, list[SharesOutstandingEntry]] = {}

    rows_out = []
    xbrl_hits = 0
    xbrl_misses = 0

    for i, c in enumerate(qualified):
        accession = c.accession_number
        cik = c.cik
        ticker = c.ticker or ""
        signal_date = (c.window_end or "")[:10]
        existing = sp_map.get(accession)

        # If already in SP and has mcap_at_signal_true, reuse everything
        if existing and existing.get("mcap_true"):
            mcap_true = existing.get("mcap_true")
            mcap_src = existing.get("mcap_src") or "xbrl"
            mcap_shares = existing.get("mcap_shares")
            mcap_end_date = existing.get("mcap_end_date")
            avg_px = existing.get("avg_raw_px")
            xbrl_hits += 1
        else:
            # Fetch XBRL (pacing 1s per unique CIK)
            if cik not in xbrl_cache:
                if i > 0:
                    time.sleep(args.delay)
                try:
                    xbrl_cache[cik] = await XBRLClient.get_shares_outstanding(cik)
                except Exception as e:
                    logger.warning(f"XBRL fail for {ticker} ({cik}): {e}")
                    xbrl_cache[cik] = []
            entries = xbrl_cache[cik]
            picked = XBRLClient.pick_shares_at_or_before(entries, signal_date) if entries else None
            mcap_src = None
            if not picked and entries:
                picked = XBRLClient.pick_nearest_post_signal(entries, signal_date, max_days=90)
                if picked:
                    mcap_src = "xbrl_post_signal_approx"
            elif picked:
                mcap_src = "xbrl"

            # Raw price
            raw = await fetch_raw_px_for_signal(cik, signal_date)
            avg_px = raw["avg_px"] if raw else None

            if picked and avg_px:
                mcap_true = float(round(avg_px * picked.shares))
                mcap_shares = picked.shares
                mcap_end_date = picked.end_date
                xbrl_hits += 1
            else:
                mcap_true = None
                mcap_shares = None
                mcap_end_date = None
                xbrl_misses += 1

        # Actionable date = latest filing_date for signal_date's txns
        actionable_date = (filing_date_map.get(cik, {}).get(signal_date) or signal_date)[:10]

        # Returns / maturity
        try:
            ad_dt = datetime.strptime(actionable_date, "%Y-%m-%d")
            age_days = (now - ad_dt).days
        except (ValueError, TypeError):
            ad_dt = None
            age_days = None
        exit_date = (ad_dt + timedelta(days=HORIZON_DAYS)).strftime("%Y-%m-%d") if ad_dt else None

        # Prefer existing SP's price fields if available
        if existing and existing.get("p0") is not None and existing.get("p90") is not None:
            p0 = existing["p0"]
            p90 = existing["p90"]
            spy_ret = existing.get("spy")
        else:
            series = price_series_map.get(cik, [])
            p0 = find_price(series, actionable_date) if ad_dt else None
            p90 = find_price(series, exit_date) if ad_dt else None
            if p0 is not None:
                p0 = float(round(p0, 2))
            if p90 is not None:
                p90 = float(round(p90, 2))
            spy_at_p0 = find_price(spy_series, actionable_date) if ad_dt else None
            spy_at_p90 = find_price(spy_series, exit_date) if ad_dt else None
            spy_ret = None
            if spy_at_p0 and spy_at_p90 and spy_at_p0 > 0:
                spy_ret = round((spy_at_p90 - spy_at_p0) / spy_at_p0 * 100, 4)

        is_mature_by_age = age_days is not None and age_days >= MATURITY_AGE_DAYS and p90 is not None
        ret_90d = None
        if p0 and p0 > 0 and p90 is not None:
            ret_90d = round((p90 - p0) / p0 * 100, 4)
        alpha_90d = None
        if ret_90d is not None and spy_ret is not None:
            alpha_90d = round(ret_90d - spy_ret, 4)
        hit_90d = ret_90d is not None and ret_90d > 0

        rows_out.append({
            "accession_number": accession,
            "cik": cik,
            "ticker": ticker,
            "company_name": c.company_name or "",
            "signal_date": signal_date,
            "actionable_date": actionable_date,
            "num_buyers": int(c.num_buyers),
            "total_value_usd": float(c.total_buy_value),
            "avg_raw_px_usd": avg_px,
            "mcap_at_signal_true_usd": mcap_true,
            "mcap_at_signal_true_source": mcap_src,
            "mcap_at_signal_true_shares": mcap_shares,
            "mcap_at_signal_true_shares_end_date": mcap_end_date,
            "size_tier": size_tier(mcap_true),
            "existing_signal_id": accession if existing else None,
            "existing_conviction_tier": (existing or {}).get("tier"),
            "existing_is_mature": (existing or {}).get("mature"),
            "price_day0": p0,
            "price_day90": p90,
            "return_90d_pct": ret_90d,
            "spy_return_90d_pct": spy_ret,
            "alpha_90d_pct": alpha_90d,
            "hit_90d": hit_90d if ret_90d is not None else None,
            "is_mature_by_age": is_mature_by_age,
            "age_days_at_export": age_days,
        })

        if (i + 1) % 25 == 0 or (i + 1) == len(qualified):
            logger.info(
                f"  {i+1}/{len(qualified)} — XBRL hits:{xbrl_hits} miss:{xbrl_misses} "
                f"(unique CIKs fetched: {len(xbrl_cache)})"
            )

    await Neo4jClient.disconnect()

    # Sort by signal_date then accession for determinism
    rows_out.sort(key=lambda r: (r["signal_date"] or "", r["accession_number"] or ""))

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=COLUMNS, extrasaction="ignore")
        w.writeheader()
        for row in rows_out:
            norm = {}
            for k in COLUMNS:
                v = row.get(k)
                if isinstance(v, bool):
                    norm[k] = "true" if v else "false"
                elif v is None:
                    norm[k] = ""
                else:
                    norm[k] = v
            w.writerow(norm)

    print(f"\n{'=' * 60}")
    print(f"  TIER CANDIDATES BACKFILL COMPLETE")
    print(f"  Rows:                {len(rows_out)}")
    print(f"  With ground-truth mcap: {sum(1 for r in rows_out if r['mcap_at_signal_true_usd'] is not None)}")
    print(f"  Existing SP linked:  {sum(1 for r in rows_out if r['existing_signal_id'])}")
    print(f"  Output:              {out}")
    print(f"{'=' * 60}\n")

    # Tier breakdown
    tier_counts: dict[str, int] = {}
    for r in rows_out:
        tier_counts[r["size_tier"]] = tier_counts.get(r["size_tier"], 0) + 1
    print("Size-tier distribution (by ground-truth mcap):")
    for t in ["micro", "small", "midcap", "large", "null"]:
        print(f"  {t:8}: {tier_counts.get(t, 0)}")


if __name__ == "__main__":
    asyncio.run(main())
