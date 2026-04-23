"""Audit the 142 mature strong_buy signals against fresh yfinance + SEC XBRL.

For each mature strong_buy row:
  - Re-fetch prices from yfinance TODAY (auto_adjust=True — split/div adjusted)
  - Recompute fresh return_day0 from filing_date -> filing_date+90d
  - Recompute fresh SPY 90d return over the same window
  - Fetch XBRL shares-outstanding at signal date for true mcap

Emit diffs: where stored return != fresh return, where true mcap differs from
the price-ratio estimate used for the midcap filter.

Usage:
    cd backend && venv/bin/python audit_142_mature_2026-04-22.py
"""

import asyncio
import json
import logging
import sys
import time
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import yfinance as yf

from app.db.neo4j_client import Neo4jClient
from app.services.signal_performance_service import find_price
from ingestion.sec_edgar.xbrl_client import XBRLClient

logger = logging.getLogger("audit")
logger.setLevel(logging.INFO)
_h = logging.StreamHandler(sys.stdout)
_h.setFormatter(logging.Formatter("%(message)s"))
logger.addHandler(_h)
sys.stdout.reconfigure(line_buffering=True)

HORIZON_DAYS = 90
RATE_LIMIT_SEC = 1.5  # between distinct ticker fetches
XBRL_PACING_SEC = 1.0  # between distinct CIK XBRL fetches

MIDCAP_LO = 300_000_000
MIDCAP_HI = 5_000_000_000


async def fetch_mature_rows() -> list[dict]:
    rows = await Neo4jClient.execute_query(
        """
        MATCH (sp:SignalPerformance)
        WHERE sp.is_mature = true
          AND sp.direction = 'buy'
          AND sp.conviction_tier = 'strong_buy'
        RETURN sp.signal_id AS signal_id,
               sp.ticker AS ticker,
               sp.cik AS cik,
               sp.company_name AS company_name,
               sp.signal_date AS signal_date,
               sp.actionable_date AS actionable_date,
               sp.price_day0 AS stored_p0,
               sp.price_day90 AS stored_p90,
               sp.return_day0 AS stored_return,
               sp.spy_return_90d AS stored_spy,
               sp.market_cap AS stored_mcap_ratio,
               sp.mcap_at_signal_true AS stored_mcap_true,
               sp.mcap_at_signal_true_source AS stored_mcap_true_source,
               sp.total_value AS total_value,
               sp.num_insiders AS num_insiders
        ORDER BY sp.signal_date
        """
    )
    return [dict(r) for r in rows]


def fetch_series(ticker: str, period: str = "3y") -> list[dict] | None:
    try:
        df = yf.Ticker(ticker).history(period=period, auto_adjust=True)
        if df.empty:
            return None
        series = []
        for d, row in df.iterrows():
            c = row.get("Close")
            if c is None or c <= 0:
                continue
            series.append({"d": d.strftime("%Y-%m-%d"), "c": float(c)})
        return series if series else None
    except Exception as e:
        logger.warning(f"  yfinance fail {ticker}: {type(e).__name__}: {str(e)[:80]}")
        return None


def summarize(rows: list[dict], ret_field: str, spy_field: str) -> dict | None:
    valid = [r for r in rows if r.get(ret_field) is not None]
    if not valid:
        return None
    n = len(valid)
    wins = sum(1 for r in valid if r[ret_field] > 0)
    avg_ret = sum(r[ret_field] for r in valid) / n
    with_spy = [r for r in valid if r.get(spy_field) is not None]
    avg_alpha = (
        sum(r[ret_field] - r[spy_field] for r in with_spy) / len(with_spy)
        if with_spy
        else None
    )
    return {
        "n": n,
        "hr": round(wins / n * 100, 1),
        "avg_ret": round(avg_ret, 2),
        "avg_alpha": round(avg_alpha, 2) if avg_alpha is not None else None,
    }


async def main():
    await Neo4jClient.connect()

    rows = await fetch_mature_rows()
    logger.info(f"Loaded {len(rows)} mature strong_buy rows\n")
    if not rows:
        await Neo4jClient.disconnect()
        return

    logger.info("Fetching SPY fresh (3y)...")
    spy = fetch_series("SPY", period="3y")
    logger.info(f"  SPY points: {len(spy) if spy else 0}\n")

    # Group by ticker — one yfinance fetch per unique ticker covers all its signals
    signals_by_ticker: dict[str, list[dict]] = defaultdict(list)
    for r in rows:
        signals_by_ticker[r["ticker"]].append(r)

    logger.info(
        f"Unique tickers: {len(signals_by_ticker)} | "
        f"Estimated fetch time: ~{len(signals_by_ticker) * RATE_LIMIT_SEC:.0f}s\n"
    )

    audited: list[dict] = []
    start_time = time.time()

    for i, (ticker, sigs) in enumerate(signals_by_ticker.items()):
        if i > 0:
            time.sleep(RATE_LIMIT_SEC)

        series = fetch_series(ticker, period="3y")
        for sig in sigs:
            actionable = (sig["actionable_date"] or sig["signal_date"])[:10]
            sig["actionable_date_used"] = actionable

            if not series:
                sig["fresh_p0"] = None
                sig["fresh_p90"] = None
                sig["fresh_return"] = None
                sig["fresh_spy_p0"] = None
                sig["fresh_spy_p90"] = None
                sig["fresh_spy_return"] = None
                sig["fresh_alpha"] = None
                sig["fresh_error"] = "no_yf_series"
                audited.append(sig)
                continue

            fresh_p0 = find_price(series, actionable)
            try:
                exit_dt = datetime.strptime(actionable, "%Y-%m-%d") + timedelta(
                    days=HORIZON_DAYS
                )
            except ValueError:
                exit_dt = None
            exit_date = exit_dt.strftime("%Y-%m-%d") if exit_dt else None
            fresh_p90 = find_price(series, exit_date) if exit_date else None

            fresh_return = None
            if fresh_p0 and fresh_p0 > 0 and fresh_p90 is not None:
                fresh_return = round((fresh_p90 - fresh_p0) / fresh_p0 * 100, 2)

            # SPY over same window
            fresh_spy_p0 = find_price(spy, actionable) if spy else None
            fresh_spy_p90 = (
                find_price(spy, exit_date) if spy and exit_date else None
            )
            fresh_spy_return = None
            if (
                fresh_spy_p0
                and fresh_spy_p0 > 0
                and fresh_spy_p90 is not None
            ):
                fresh_spy_return = round(
                    (fresh_spy_p90 - fresh_spy_p0) / fresh_spy_p0 * 100, 2
                )

            fresh_alpha = (
                round(fresh_return - fresh_spy_return, 2)
                if fresh_return is not None and fresh_spy_return is not None
                else None
            )

            sig["fresh_p0"] = round(fresh_p0, 2) if fresh_p0 else None
            sig["fresh_p90"] = round(fresh_p90, 2) if fresh_p90 else None
            sig["fresh_return"] = fresh_return
            sig["fresh_spy_p0"] = round(fresh_spy_p0, 2) if fresh_spy_p0 else None
            sig["fresh_spy_p90"] = round(fresh_spy_p90, 2) if fresh_spy_p90 else None
            sig["fresh_spy_return"] = fresh_spy_return
            sig["fresh_alpha"] = fresh_alpha
            audited.append(sig)

        if (i + 1) % 20 == 0 or (i + 1) == len(signals_by_ticker):
            elapsed = round(time.time() - start_time, 1)
            logger.info(
                f"  yfin: {i + 1}/{len(signals_by_ticker)} tickers ({elapsed:.0f}s)"
            )

    # XBRL pass — one fetch per unique CIK
    unique_ciks = sorted({r["cik"] for r in rows if r["cik"]})
    logger.info(
        f"\nFetching XBRL for {len(unique_ciks)} CIKs "
        f"(~{len(unique_ciks) * XBRL_PACING_SEC:.0f}s)..."
    )
    xbrl_cache: dict[str, list] = {}
    xbrl_start = time.time()
    for i, cik in enumerate(unique_ciks):
        if i > 0:
            await asyncio.sleep(XBRL_PACING_SEC)
        try:
            xbrl_cache[cik] = await XBRLClient.get_shares_outstanding(cik)
        except Exception as e:
            logger.warning(f"  XBRL fail {cik}: {type(e).__name__}: {str(e)[:80]}")
            xbrl_cache[cik] = []
        if (i + 1) % 20 == 0 or (i + 1) == len(unique_ciks):
            elapsed = round(time.time() - xbrl_start, 1)
            logger.info(f"  xbrl: {i + 1}/{len(unique_ciks)} CIKs ({elapsed:.0f}s)")

    # Apply XBRL to each signal
    for sig in audited:
        entries = xbrl_cache.get(sig["cik"], [])
        fresh_px = sig.get("fresh_p0")
        sig["fresh_mcap_true"] = None
        sig["fresh_mcap_true_source"] = None
        sig["fresh_mcap_true_shares"] = None
        if not entries or not fresh_px:
            continue
        picked = XBRLClient.pick_shares_at_or_before(entries, sig["signal_date"])
        source = "xbrl"
        if not picked:
            picked = XBRLClient.pick_nearest_post_signal(
                entries, sig["signal_date"], max_days=90
            )
            source = "xbrl_post_signal_approx" if picked else None
        if picked:
            sig["fresh_mcap_true"] = int(round(fresh_px * picked.shares))
            sig["fresh_mcap_true_source"] = source
            sig["fresh_mcap_true_shares"] = picked.shares

    # ============= REPORT =============
    logger.info("\n" + "=" * 72)
    logger.info("RETURN / ALPHA AUDIT — stored vs fresh yfinance")
    logger.info("=" * 72)

    def diff(a, b):
        if a is None or b is None:
            return None
        return round(a - b, 2)

    def within(a, b, tol):
        if a is None or b is None:
            return False
        return abs(a - b) <= tol

    ret_match_tight = [
        a for a in audited if within(a.get("fresh_return"), a["stored_return"], 0.5)
    ]
    ret_match_loose = [
        a
        for a in audited
        if within(a.get("fresh_return"), a["stored_return"], 2.0)
        and not within(a.get("fresh_return"), a["stored_return"], 0.5)
    ]
    ret_drift = [
        a
        for a in audited
        if a.get("fresh_return") is not None
        and a["stored_return"] is not None
        and abs(a["fresh_return"] - a["stored_return"]) > 2.0
    ]
    ret_missing = [
        a
        for a in audited
        if a.get("fresh_return") is None or a["stored_return"] is None
    ]

    logger.info(f"Rows audited: {len(audited)}")
    logger.info(
        f"  Return match within ±0.5pp:  {len(ret_match_tight)} "
        f"({len(ret_match_tight) / len(audited) * 100:.1f}%)"
    )
    logger.info(f"  Return match within ±2.0pp:  {len(ret_match_loose)}")
    logger.info(f"  Return drift > ±2.0pp:       {len(ret_drift)}")
    logger.info(f"  Missing (unresolvable):      {len(ret_missing)}")

    if ret_drift:
        logger.info("\n  DRIFT > 2.0pp (sorted by magnitude, top 25):")
        logger.info(
            f"  {'ticker':<8}{'signal':<12}"
            f"{'stored_r':>10}{'fresh_r':>10}{'diff':>8}   "
            f"{'stored_p0':>10}{'fresh_p0':>10}  "
            f"{'stored_p90':>11}{'fresh_p90':>11}"
        )
        for d in sorted(
            ret_drift,
            key=lambda x: abs(x["fresh_return"] - x["stored_return"]),
            reverse=True,
        )[:25]:
            logger.info(
                f"  {d['ticker']:<8}{d['signal_date'][:10]:<12}"
                f"{d['stored_return']:>10.2f}"
                f"{d['fresh_return']:>10.2f}"
                f"{diff(d['fresh_return'], d['stored_return']):>+8.2f}   "
                f"{(d['stored_p0'] or 0):>10.2f}"
                f"{(d['fresh_p0'] or 0):>10.2f}  "
                f"{(d['stored_p90'] or 0):>11.2f}"
                f"{(d['fresh_p90'] or 0):>11.2f}"
            )

    if ret_missing:
        logger.info(f"\n  UNRESOLVABLE (fresh fetch failed or stored missing):")
        for d in ret_missing[:20]:
            err = d.get("fresh_error", "?")
            logger.info(
                f"    {d['ticker']:<8}{d['signal_date'][:10]:<12}"
                f" stored_r={d['stored_return']}  err={err}"
            )

    # SPY chain health
    spy_match = [
        a for a in audited if within(a.get("fresh_spy_return"), a["stored_spy"], 0.5)
    ]
    spy_drift = [
        a
        for a in audited
        if a.get("fresh_spy_return") is not None
        and a["stored_spy"] is not None
        and abs(a["fresh_spy_return"] - a["stored_spy"]) > 2.0
    ]
    logger.info("\n" + "-" * 72)
    logger.info("SPY CHAIN AUDIT")
    logger.info("-" * 72)
    logger.info(f"  Match within ±0.5pp:  {len(spy_match)}/{len(audited)}")
    logger.info(f"  Drift > ±2.0pp:       {len(spy_drift)}")

    # Cohort comparison
    logger.info("\n" + "=" * 72)
    logger.info("COHORT COMPARISON — stored vs fresh")
    logger.info("=" * 72)
    stored_summary = summarize(audited, "stored_return", "stored_spy")
    fresh_summary = summarize(audited, "fresh_return", "fresh_spy_return")

    def fmt(v):
        return "—" if v is None else str(v)

    logger.info(
        f"  {'metric':<20}{'stored':>14}{'fresh yfinance':>18}"
    )
    for k, label in [
        ("n", "signals"),
        ("hr", "hit rate %"),
        ("avg_ret", "avg return %"),
        ("avg_alpha", "avg alpha pp"),
    ]:
        s_val = stored_summary.get(k) if stored_summary else None
        f_val = fresh_summary.get(k) if fresh_summary else None
        logger.info(f"  {label:<20}{fmt(s_val):>14}{fmt(f_val):>18}")

    # XBRL true mcap
    logger.info("\n" + "=" * 72)
    logger.info("TRUE MCAP AUDIT — XBRL vs ratio estimate")
    logger.info("=" * 72)
    resolved = [a for a in audited if a.get("fresh_mcap_true")]
    logger.info(f"  XBRL resolved: {len(resolved)}/{len(audited)}")
    by_source: dict[str, int] = defaultdict(int)
    for a in resolved:
        by_source[a.get("fresh_mcap_true_source") or "unknown"] += 1
    for src, n in by_source.items():
        logger.info(f"    {src}: {n}")

    true_in_band = [
        a
        for a in resolved
        if MIDCAP_LO <= a["fresh_mcap_true"] <= MIDCAP_HI
    ]
    true_below = [a for a in resolved if a["fresh_mcap_true"] < MIDCAP_LO]
    true_above = [a for a in resolved if a["fresh_mcap_true"] > MIDCAP_HI]
    logger.info(f"\n  Distribution under TRUE mcap band (${MIDCAP_LO:,} – ${MIDCAP_HI:,}):")
    logger.info(f"    In band:     {len(true_in_band)}")
    logger.info(f"    Below $300M: {len(true_below)}")
    logger.info(f"    Above $5B:   {len(true_above)}")

    # HR/alpha if tightened to true mcap
    in_band_sum = summarize(true_in_band, "stored_return", "stored_spy")
    below_sum = summarize(true_below, "stored_return", "stored_spy")
    above_sum = summarize(true_above, "stored_return", "stored_spy")
    logger.info("\n  Cohort if filter retightened to TRUE midcap:")
    if in_band_sum:
        logger.info(
            f"    Kept ({in_band_sum['n']} signals): "
            f"HR {in_band_sum['hr']}%, avg_ret {in_band_sum['avg_ret']}%, "
            f"alpha {in_band_sum['avg_alpha']}pp"
        )
    if below_sum:
        logger.info(
            f"    Dropped <$300M ({below_sum['n']}): "
            f"HR {below_sum['hr']}%, avg_ret {below_sum['avg_ret']}%, "
            f"alpha {below_sum['avg_alpha']}pp"
        )
    if above_sum:
        logger.info(
            f"    Dropped >$5B   ({above_sum['n']}): "
            f"HR {above_sum['hr']}%, avg_ret {above_sum['avg_ret']}%, "
            f"alpha {above_sum['avg_alpha']}pp"
        )

    # Ratio-vs-true mcap spread
    ratio_vs_true = []
    for a in resolved:
        if a.get("stored_mcap_ratio") and a["fresh_mcap_true"]:
            pct_err = (
                (a["stored_mcap_ratio"] - a["fresh_mcap_true"])
                / a["fresh_mcap_true"]
                * 100
            )
            ratio_vs_true.append((abs(pct_err), pct_err, a))
    if ratio_vs_true:
        ratio_vs_true.sort(reverse=True)
        top = ratio_vs_true[:15]
        logger.info(
            f"\n  Top ratio-estimate errors (|pct_err|) — ratio vs true mcap:"
        )
        logger.info(
            f"  {'ticker':<8}{'signal':<12}"
            f"{'ratio_mcap':>14}{'true_mcap':>14}{'pct_err':>10}"
        )
        for _, perr, a in top:
            logger.info(
                f"  {a['ticker']:<8}{a['signal_date'][:10]:<12}"
                f"{(a['stored_mcap_ratio'] or 0):>14,.0f}"
                f"{a['fresh_mcap_true']:>14,.0f}"
                f"{perr:>+9.1f}%"
            )

    # Dump raw JSON
    out_path = Path(__file__).parent / "audit_142_mature_2026-04-22.json"
    # Convert any non-JSON-serializable objects
    clean = []
    for a in audited:
        c = {k: v for k, v in a.items()}
        for k in list(c.keys()):
            if isinstance(c[k], (datetime,)):
                c[k] = c[k].isoformat()
        clean.append(c)
    with open(out_path, "w") as f:
        json.dump(clean, f, indent=2, default=str)
    logger.info(f"\nRaw audit data: {out_path}")

    await Neo4jClient.disconnect()


if __name__ == "__main__":
    asyncio.run(main())
