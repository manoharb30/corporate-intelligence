"""Per-signal audit CSV for v1.4 signal quality audit.

Produces `signal_audit_v1_4.csv` + `.parquet` — one row per mature strong_buy
signal with ~30 deterministic columns. Zero human interpretation;
zero yfinance calls. Pure extraction from stored data.

Columns: identity / timing / cluster composition / both mcaps +
delta / classification under true mcap / returns + alpha / pre-cluster
+ post-signal insider activity / 30d volatility.

Run from backend/:
    venv/bin/python -m exports.audit_v1_4
    venv/bin/python -m exports.audit_v1_4 --out exports/out/signal_audit_v1_4.csv

See exports/AUDIT_V1_4_DATA_DICTIONARY.md for the column spec.
"""

import argparse
import asyncio
import csv
import json
import logging
import math
import os
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Optional

import pyarrow as pa
import pyarrow.parquet as pq

from app.db.neo4j_client import Neo4jClient

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")


# Column order locked here for determinism. Any change needs a plan bump.
COLUMNS: list[tuple[str, Any]] = [
    # Identity (5)
    ("signal_id", pa.string()),
    ("ticker", pa.string()),
    ("cik", pa.string()),
    ("company_name", pa.string()),
    ("industry", pa.string()),
    # Timing (4)
    ("signal_date", pa.string()),
    ("actionable_date", pa.string()),
    ("days_from_last_earnings_at_signal", pa.int32()),
    ("days_to_next_earnings_at_signal", pa.int32()),
    # Cluster composition (4)
    ("num_insiders", pa.int32()),
    ("total_cluster_value_usd", pa.float64()),
    ("avg_raw_execution_price_usd", pa.float64()),
    ("has_hostile_activist", pa.bool_()),
    # Market cap (5)
    ("market_cap_ratio_estimate_usd", pa.float64()),
    ("mcap_at_signal_true_usd", pa.float64()),
    ("mcap_at_signal_true_source", pa.string()),
    ("mcap_at_signal_true_shares_end_date", pa.string()),
    ("mcap_delta_pct", pa.float64()),
    # Classification under true mcap (2)
    ("is_midcap_by_true_mcap", pa.bool_()),
    ("would_remain_strong_buy", pa.bool_()),
    # Returns (6)
    ("price_day0", pa.float64()),
    ("price_day90", pa.float64()),
    ("return_90d_pct", pa.float64()),
    ("spy_return_90d_pct", pa.float64()),
    ("alpha_90d_pct", pa.float64()),
    ("hit_90d", pa.bool_()),
    # Pre-cluster insider activity (4) — 180d before actionable_date, officers/directors/10%
    ("pre_cluster_sells_count_180d", pa.int32()),
    ("pre_cluster_sellers_count_180d", pa.int32()),
    ("pre_cluster_sells_value_usd_180d", pa.float64()),
    ("pre_cluster_sells_latest_date_180d", pa.string()),
    # Post-signal insider activity (2) — 0-90d after actionable_date
    ("post_signal_sells_count_90d", pa.int32()),
    ("post_signal_sells_value_usd_90d", pa.float64()),
    # Volatility (1)
    ("stock_volatility_30d_pct", pa.float64()),
    # Methodology version (1) — v1.4 Phase 12
    ("methodology_version", pa.string()),
]

EARNINGS_CACHE_PATH = "/tmp/lookinsight_earnings_cache.json"


async def fetch_signals() -> list[dict]:
    """Fetch the 142 mature strong_buy SignalPerformance rows with all needed fields."""
    rows = await Neo4jClient.execute_query(
        """
        MATCH (sp:SignalPerformance)
        WHERE sp.direction = 'buy'
          AND sp.conviction_tier = 'strong_buy'
          AND sp.is_mature = true
        RETURN sp.signal_id AS signal_id,
               sp.ticker AS ticker,
               sp.cik AS cik,
               sp.company_name AS company_name,
               sp.industry AS industry,
               sp.signal_date AS signal_date,
               sp.actionable_date AS actionable_date,
               sp.num_insiders AS num_insiders,
               sp.total_value AS total_value,
               sp.market_cap AS market_cap_old,
               sp.mcap_at_signal_true AS mcap_at_signal_true,
               sp.mcap_at_signal_true_source AS mcap_at_signal_true_source,
               sp.mcap_at_signal_true_shares_end_date AS mcap_at_signal_true_shares_end_date,
               sp.mcap_at_signal_true_avg_raw_px AS avg_raw_px,
               sp.price_day0 AS price_day0,
               sp.price_day90 AS price_day90,
               sp.spy_return_90d AS spy_return_90d,
               sp.methodology_version AS methodology_version
        ORDER BY sp.signal_date
        """
    )
    return [dict(r) for r in rows]


async def fetch_hostile_flags(ciks: list[str]) -> dict[str, bool]:
    """Return {cik: has_hostile_activist}. Queries ActivistFiling nodes with hostile keywords."""
    if not ciks:
        return {}
    HOSTILE_KEYWORDS = [
        "proxy", "remove", "replace", "strategic alternative", "inadequate",
        "underperform", "oppose", "withhold", "hostile", "unsolicited",
    ]
    r = await Neo4jClient.execute_query(
        """
        UNWIND $ciks AS cik
        OPTIONAL MATCH (af:ActivistFiling)
        WHERE af.target_cik = cik
          AND af.purpose_text IS NOT NULL
        WITH cik, collect(toLower(af.purpose_text)) AS texts
        RETURN cik, texts
        """,
        {"ciks": ciks},
    )
    out = {}
    for row in r:
        hostile = any(kw in " ".join(row["texts"]) for kw in HOSTILE_KEYWORDS)
        out[row["cik"]] = hostile
    return out


async def fetch_insider_activity(
    ciks: list[str], actionable_dates_by_cik: dict[str, list[str]]
) -> dict[str, list[dict]]:
    """Fetch S (sell) transactions by officers/directors/10% owners for each CIK.

    Returns: {cik: list of dicts with transaction_date, insider_name, total_value}
    Only S transactions by senior insiders (officer/director/10% owner).
    """
    if not ciks:
        return {}
    rows = await Neo4jClient.execute_query(
        """
        MATCH (c:Company)-[:INSIDER_TRADE_OF]->(t:InsiderTransaction)
        WHERE c.cik IN $ciks
          AND t.transaction_code = 'S'
          AND (t.is_officer = true OR t.is_director = true OR t.is_ten_percent_owner = true)
          AND t.transaction_date IS NOT NULL
          AND t.total_value IS NOT NULL AND t.total_value > 0
        RETURN c.cik AS cik,
               substring(t.transaction_date, 0, 10) AS txn_date,
               t.insider_name AS insider_name,
               t.total_value AS total_value
        """,
        {"ciks": ciks},
    )
    by_cik: dict[str, list[dict]] = {c: [] for c in ciks}
    for r in rows:
        by_cik.setdefault(r["cik"], []).append(
            {
                "txn_date": r["txn_date"],
                "insider_name": r["insider_name"],
                "total_value": float(r["total_value"]),
            }
        )
    return by_cik


async def fetch_price_series(ciks: list[str]) -> dict[str, list[dict]]:
    """Fetch Company.price_series JSON-parsed for each CIK. Returns {cik: [{d, c}, ...]}."""
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


def load_earnings_cache() -> dict[str, list[str]]:
    """Load the yfinance earnings cache if present. {ticker: [date strings sorted]}."""
    if not os.path.exists(EARNINGS_CACHE_PATH):
        return {}
    try:
        with open(EARNINGS_CACHE_PATH) as f:
            return json.load(f)
    except (ValueError, OSError):
        return {}


def compute_earnings_deltas(
    earnings_cache: dict[str, list[str]], ticker: str, actionable_date: str
) -> tuple[Optional[int], Optional[int]]:
    """Return (days_from_last, days_to_next) relative to actionable_date. None if unknown."""
    dates = earnings_cache.get(ticker) or earnings_cache.get((ticker or "").upper())
    if not dates:
        return None, None
    try:
        ad = datetime.strptime(actionable_date[:10], "%Y-%m-%d")
    except (ValueError, TypeError):
        return None, None
    last = None
    next_ = None
    for d in dates:
        try:
            dt = datetime.strptime(d[:10], "%Y-%m-%d")
        except (ValueError, TypeError):
            continue
        if dt <= ad:
            last = dt
        elif next_ is None:
            next_ = dt
            break
    return (
        (ad - last).days if last else None,
        (next_ - ad).days if next_ else None,
    )


def compute_insider_window_stats(
    sells: list[dict], window_start: str, window_end: str, include_end: bool = False
) -> dict:
    """Aggregate sells whose txn_date falls in [window_start, window_end) or (...end] based on include_end."""
    in_window = []
    for s in sells:
        d = s["txn_date"]
        if include_end:
            if window_start < d <= window_end:
                in_window.append(s)
        else:
            if window_start <= d < window_end:
                in_window.append(s)
    if not in_window:
        return {
            "count": 0,
            "sellers_count": 0,
            "value": 0.0,
            "latest_date": None,
        }
    return {
        "count": len(in_window),
        "sellers_count": len({s["insider_name"] for s in in_window}),
        "value": sum(s["total_value"] for s in in_window),
        "latest_date": max(s["txn_date"] for s in in_window),
    }


def compute_volatility_30d_pct(price_series: list[dict], actionable_date: str) -> Optional[float]:
    """Annualized stdev of daily %-returns in 30 calendar days before actionable_date.

    Returns None if <15 trading-day close prices exist in window.
    """
    try:
        ad = datetime.strptime(actionable_date[:10], "%Y-%m-%d")
    except (ValueError, TypeError):
        return None
    start = (ad - timedelta(days=30)).strftime("%Y-%m-%d")
    end = actionable_date[:10]
    prices_in_window = [p["c"] for p in price_series if start <= p["d"] < end and p.get("c")]
    if len(prices_in_window) < 15:
        return None
    # Daily returns
    returns = []
    for i in range(1, len(prices_in_window)):
        prev = prices_in_window[i - 1]
        cur = prices_in_window[i]
        if prev and prev > 0:
            returns.append((cur - prev) / prev)
    if len(returns) < 10:
        return None
    mean = sum(returns) / len(returns)
    var = sum((r - mean) ** 2 for r in returns) / (len(returns) - 1)
    std = math.sqrt(var)
    # Annualize (252 trading days)
    return round(std * math.sqrt(252) * 100, 4)


def build_row(
    sp: dict,
    hostile_flags: dict[str, bool],
    insider_sells_by_cik: dict[str, list[dict]],
    price_series_by_cik: dict[str, list[dict]],
    earnings_cache: dict[str, list[str]],
) -> dict:
    """Assemble one row of the audit CSV."""
    ticker = sp["ticker"]
    cik = sp["cik"]
    ad = (sp["actionable_date"] or "")[:10]

    # Returns
    p0 = sp["price_day0"]
    p90 = sp["price_day90"]
    return_90d = None
    if p0 and p0 > 0 and p90 is not None:
        return_90d = round((p90 - p0) / p0 * 100, 4)
    spy_90d = sp.get("spy_return_90d")
    alpha_90d = None
    if return_90d is not None and spy_90d is not None:
        alpha_90d = round(return_90d - spy_90d, 4)
    hit_90d = return_90d is not None and return_90d > 0

    # mcap
    mcap_old = sp.get("market_cap_old")
    mcap_true = sp.get("mcap_at_signal_true")
    mcap_delta_pct = None
    if mcap_true and mcap_old and mcap_old > 0:
        mcap_delta_pct = round((mcap_true - mcap_old) / mcap_old * 100, 4)

    # Classification
    is_midcap = (
        mcap_true is not None
        and 300_000_000 <= mcap_true <= 5_000_000_000
    )
    would_remain_strong_buy = (
        is_midcap
        and (sp.get("total_value") or 0) >= 100_000
        and (sp.get("num_insiders") or 0) >= 2
    )

    # Earnings deltas
    days_from_last, days_to_next = compute_earnings_deltas(
        earnings_cache, ticker, ad
    )

    # Insider activity windows
    sells = insider_sells_by_cik.get(cik, [])
    # Pre-window: [ad - 180, ad)
    try:
        ad_dt = datetime.strptime(ad, "%Y-%m-%d")
        pre_start = (ad_dt - timedelta(days=180)).strftime("%Y-%m-%d")
        post_end = (ad_dt + timedelta(days=90)).strftime("%Y-%m-%d")
    except (ValueError, TypeError):
        pre_start = ad
        post_end = ad
    pre = compute_insider_window_stats(sells, pre_start, ad, include_end=False)
    post = compute_insider_window_stats(sells, ad, post_end, include_end=True)

    # Volatility
    vol = compute_volatility_30d_pct(price_series_by_cik.get(cik, []), ad)

    return {
        "signal_id": sp["signal_id"],
        "ticker": ticker,
        "cik": cik,
        "company_name": sp["company_name"],
        "industry": sp.get("industry"),
        "signal_date": (sp["signal_date"] or "")[:10],
        "actionable_date": ad,
        "days_from_last_earnings_at_signal": days_from_last,
        "days_to_next_earnings_at_signal": days_to_next,
        "num_insiders": int(sp["num_insiders"]) if sp.get("num_insiders") is not None else None,
        "total_cluster_value_usd": float(sp["total_value"]) if sp.get("total_value") is not None else None,
        "avg_raw_execution_price_usd": sp.get("avg_raw_px"),
        "has_hostile_activist": bool(hostile_flags.get(cik, False)),
        "market_cap_ratio_estimate_usd": mcap_old,
        "mcap_at_signal_true_usd": mcap_true,
        "mcap_at_signal_true_source": sp.get("mcap_at_signal_true_source"),
        "mcap_at_signal_true_shares_end_date": sp.get("mcap_at_signal_true_shares_end_date"),
        "mcap_delta_pct": mcap_delta_pct,
        "is_midcap_by_true_mcap": is_midcap,
        "would_remain_strong_buy": would_remain_strong_buy,
        "price_day0": p0,
        "price_day90": p90,
        "return_90d_pct": return_90d,
        "spy_return_90d_pct": spy_90d,
        "alpha_90d_pct": alpha_90d,
        "hit_90d": hit_90d,
        "pre_cluster_sells_count_180d": pre["count"],
        "pre_cluster_sellers_count_180d": pre["sellers_count"],
        "pre_cluster_sells_value_usd_180d": pre["value"],
        "pre_cluster_sells_latest_date_180d": pre["latest_date"],
        "post_signal_sells_count_90d": post["count"],
        "post_signal_sells_value_usd_90d": post["value"],
        "stock_volatility_30d_pct": vol,
        "methodology_version": sp.get("methodology_version") or "v1.1",
    }


def write_csv(rows: list[dict], path: Path) -> None:
    """Write rows to CSV in locked column order (deterministic)."""
    col_names = [c[0] for c in COLUMNS]
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=col_names, extrasaction="ignore")
        w.writeheader()
        for row in rows:
            # Normalize booleans and None for deterministic output
            out = {}
            for name in col_names:
                v = row.get(name)
                if isinstance(v, bool):
                    out[name] = "true" if v else "false"
                elif v is None:
                    out[name] = ""
                else:
                    out[name] = v
            w.writerow(out)


def write_parquet(rows: list[dict], path: Path) -> None:
    """Write rows to Parquet with the locked schema."""
    col_names = [c[0] for c in COLUMNS]
    schema = pa.schema([(name, dtype) for name, dtype in COLUMNS])
    columns: dict[str, list] = {name: [] for name in col_names}
    for row in rows:
        for name in col_names:
            columns[name].append(row.get(name))
    arrays = [pa.array(columns[name], type=dtype) for name, dtype in COLUMNS]
    table = pa.Table.from_arrays(arrays, schema=schema)
    path.parent.mkdir(parents=True, exist_ok=True)
    pq.write_table(table, path)


async def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--out",
        type=str,
        default="exports/out/signal_audit_v1_4.csv",
        help="Output CSV path (Parquet written alongside with same basename).",
    )
    args = ap.parse_args()

    out_csv = Path(args.out)
    out_parquet = out_csv.with_suffix(".parquet")

    await Neo4jClient.connect()

    logger.info("Fetching SignalPerformance rows...")
    sps = await fetch_signals()
    logger.info(f"  {len(sps)} mature strong_buy signals")

    ciks = sorted({sp["cik"] for sp in sps if sp["cik"]})
    logger.info(f"Fetching insider activity for {len(ciks)} companies...")
    insider_sells = await fetch_insider_activity(
        ciks, {}  # not used; kept for signature
    )
    logger.info(f"Fetching price series for {len(ciks)} companies...")
    price_series = await fetch_price_series(ciks)
    logger.info("Fetching hostile-activist flags...")
    hostile_flags = await fetch_hostile_flags(ciks)
    logger.info("Loading earnings cache...")
    earnings_cache = load_earnings_cache()
    logger.info(f"  {len(earnings_cache)} tickers in cache")

    await Neo4jClient.disconnect()

    logger.info("Assembling rows...")
    rows = [
        build_row(sp, hostile_flags, insider_sells, price_series, earnings_cache)
        for sp in sps
    ]
    # Deterministic order: by signal_date ASC, then signal_id ASC
    rows.sort(key=lambda r: (r["signal_date"] or "", r["signal_id"] or ""))

    logger.info(f"Writing CSV: {out_csv}")
    write_csv(rows, out_csv)
    logger.info(f"Writing Parquet: {out_parquet}")
    write_parquet(rows, out_parquet)

    # Summary
    print(f"\n{'=' * 60}")
    print(f"  AUDIT CSV COMPLETE")
    print(f"  Rows:    {len(rows)}")
    print(f"  Cols:    {len(COLUMNS)}")
    print(f"  CSV:     {out_csv}")
    print(f"  Parquet: {out_parquet}")
    print(f"{'=' * 60}")


if __name__ == "__main__":
    asyncio.run(main())
