"""Mature GSHD + RLI strong_buy SignalPerformance rows.

Both signalled 2026-06-01 with actionable_date 2026-06-01, so day-90 = 2026-08-30
(a Sunday). Fully passed as of 2026-09-01 (age 92) per the maturation-timing rule:
never on day-90 itself. The Sunday day-90 resolves forward to the next close
(Mon 2026-08-31) via close_on_or_after — the same convention find_price uses in
signal_performance_service.

Cloned from mature_tbn_2026-07-14.py. Per feedback_matured_signals_frozen.md:
once is_mature=true this row becomes IMMUTABLE. Update IN PLACE — no DELETE/
CREATE — frozen rows untouched. Aborts hard on any anomaly before flipping.

Day-90 prices come from yfinance directly, NOT from Company.price_series (which
is only current through 2026-08-28), so series staleness does not affect this.

Safety:
- ABORT if not exactly 2 rows load
- ABORT if any required price_day{0,1,2,3,5,7} missing
- ABORT if yfinance returns no day-90 / SPY data
- ABORT if computed return_day0 deviates from the row's current return by more
  than tol = max(20pp, 0.30*|return_current|)  (catches garbage yfinance data
  while allowing normal few-day drift between price_current and price_day90)
- If EITHER name aborts, NOTHING downstream runs and the dashboard is NOT
  refreshed — but note a successful first row is already committed.
"""
import asyncio
import sys
from datetime import datetime, timedelta
from pathlib import Path

import yfinance as yf

sys.path.insert(0, str(Path(__file__).parent))
from app.db.neo4j_client import Neo4jClient
from app.services.signal_performance_service import SignalPerformanceService

TARGET_TICKERS = ["GSHD", "RLI"]
EXPECTED_ROWS = 2

# --dry-run: compute and report everything, write NOTHING (no row flips, no
# DashboardStats). Also previews the projected dashboard numbers by simulating
# the two flips in memory over the already-stored return_day0/spy_return_90d
# of every other row — no per-signal recomputation anywhere.
DRY_RUN = "--dry-run" in sys.argv


def close_on_or_after(ticker, target_date):
    try:
        end = target_date + timedelta(days=10)
        h = yf.Ticker(ticker).history(start=target_date.strftime("%Y-%m-%d"), end=end.strftime("%Y-%m-%d"))
        if h.empty:
            return None, None
        return float(h.iloc[0]["Close"]), h.index[0].strftime("%Y-%m-%d")
    except Exception as e:
        print(f"  yfinance error for {ticker}: {e}")
        return None, None


def close_on_or_before(ticker, target_date):
    try:
        start = target_date - timedelta(days=10)
        h = yf.Ticker(ticker).history(start=start.strftime("%Y-%m-%d"),
                                      end=(target_date + timedelta(days=1)).strftime("%Y-%m-%d"))
        if h.empty:
            return None, None
        return float(h.iloc[-1]["Close"]), h.index[-1].strftime("%Y-%m-%d")
    except Exception as e:
        print(f"  yfinance error for {ticker}: {e}")
        return None, None


async def mature_one(r):
    ticker = r["ticker"]
    sid = r["sid"]
    actionable_date = r["actionable_date"] or r["signal_date"]
    print(f"\n--- Maturing {ticker} (sid={sid}) ---")
    print(f"  actionable_date: {actionable_date}")

    try:
        actionable_dt = datetime.strptime(actionable_date[:10], "%Y-%m-%d")
    except (ValueError, TypeError):
        print(f"  ABORT: bad actionable_date '{actionable_date}'")
        return False

    # v1.7-incremental rows carry price_day0 only — the delay entry prices were
    # never stored. Reuse whatever IS stored (never overwrite it) and fetch the
    # rest so the matured row keeps the full day-0/1/2/3/5/7 shape of the v1.1
    # cohort. close_on_or_after gives the trading-day cushion for weekends.
    delay_prices = {}
    fetched = []
    for d in [0, 1, 2, 3, 5, 7]:
        stored = r.get(f"price_day{d}")
        if stored is not None:
            delay_prices[d] = float(stored)
            continue
        px, used = close_on_or_after(ticker, actionable_dt + timedelta(days=d))
        if px is None:
            print(f"  ABORT: no yfinance entry price for {ticker} at day{d}")
            return False
        delay_prices[d] = round(float(px), 2)
        fetched.append(d)
    if not delay_prices.get(0):
        print(f"  ABORT: price_day0 missing/zero")
        return False
    print(f"  entry prices:    " + ", ".join(
        f"d{d}=${delay_prices[d]:.2f}{'*' if d in fetched else ''}" for d in [0, 1, 2, 3, 5, 7]))
    if fetched:
        print(f"                   (* = fetched now; {len(fetched)} of 6 were not stored)")

    target_d90 = actionable_dt + timedelta(days=90)
    print(f"  target +90d:     {target_d90.strftime('%Y-%m-%d')}")

    price_day90, p90_used = close_on_or_after(ticker, target_d90)
    if price_day90 is None:
        print(f"  ABORT: no yfinance price for {ticker} near {target_d90}")
        return False
    price_day90 = round(price_day90, 2)
    print(f"  price_day90:     ${price_day90:.2f} (used {p90_used})")

    spy_d0, spy_d0_used = close_on_or_before("SPY", actionable_dt)
    spy_d90, spy_d90_used = close_on_or_after("SPY", target_d90)
    if spy_d0 is None or spy_d90 is None:
        print(f"  ABORT: SPY data missing (d0={spy_d0}, d90={spy_d90})")
        return False
    spy_return_90d = round((spy_d90 - spy_d0) / spy_d0 * 100, 2)
    print(f"  SPY d0/d90:      ${spy_d0:.2f} ({spy_d0_used}) / ${spy_d90:.2f} ({spy_d90_used}) -> {spy_return_90d:+.2f}%")

    returns = {}
    for d, p_d in delay_prices.items():
        if p_d and p_d > 0:
            returns[d] = round((price_day90 - p_d) / p_d * 100, 2)
        else:
            print(f"  ABORT: price_day{d} = {p_d}")
            return False

    alpha = round(returns[0] - spy_return_90d, 2)
    print(f"  return_day0:     {returns[0]:+.2f}% (headline)   alpha {alpha:+.2f}pp")

    # sanity vs current return
    cur = r["return_current"]
    if cur is not None:
        tol = max(20.0, 0.30 * abs(cur))
        diff = abs(returns[0] - cur)
        if diff > tol:
            print(f"  ABORT: return_day0 {returns[0]:+.2f}% deviates from return_current {cur:+.2f}% by {diff:.2f}pp (tol {tol:.1f}pp)")
            return False
        print(f"  sanity:          within {tol:.1f}pp of return_current ({cur:+.2f}%) -> OK")

    if DRY_RUN:
        print(f"  DRY RUN: would SET price_day90=${price_day90:.2f}, "
              f"spy_return_90d={spy_return_90d:+.2f}%, is_mature=true on {sid}")
        print(f"           returns: " + ", ".join(
            f"d{d}={returns[d]:+.2f}%" for d in [0, 1, 2, 3, 5, 7]))
        print(f"           entry px: " + ", ".join(
            f"d{d}=${delay_prices[d]:.2f}" for d in [0, 1, 2, 3, 5, 7]))
        r["_computed"] = {"return_day0": returns[0], "spy_return_90d": spy_return_90d}
        return True

    await Neo4jClient.execute_query("""
        MATCH (sp:SignalPerformance {signal_id: $sid})
        SET sp.price_day90 = $price_day90,
            sp.price_day0 = $p0, sp.price_day1 = $p1, sp.price_day2 = $p2,
            sp.price_day3 = $p3, sp.price_day5 = $p5, sp.price_day7 = $p7,
            sp.return_day0 = $r0, sp.return_day1 = $r1, sp.return_day2 = $r2,
            sp.return_day3 = $r3, sp.return_day5 = $r5, sp.return_day7 = $r7,
            sp.spy_return_90d = $spy_return_90d,
            sp.is_mature = true, sp.matured_at = $computed_at
    """, {"sid": sid, "price_day90": price_day90, "spy_return_90d": spy_return_90d,
          "computed_at": datetime.now().isoformat(),
          **{f"r{d}": returns[d] for d in [0, 1, 2, 3, 5, 7]},
          **{f"p{d}": delay_prices[d] for d in [0, 1, 2, 3, 5, 7]}})
    print(f"  WRITE: is_mature=true SET on {sid}")
    return True


async def main():
    if DRY_RUN:
        print("=" * 60)
        print("  DRY RUN — no writes. Remove --dry-run to commit.")
        print("=" * 60)
    await Neo4jClient.connect()
    pre = await Neo4jClient.execute_query("""
        MATCH (sp:SignalPerformance)
        WHERE sp.direction='buy' AND sp.conviction_tier='strong_buy'
        RETURN sum(CASE WHEN sp.is_mature THEN 1 ELSE 0 END) AS mature,
               sum(CASE WHEN sp.is_mature = false THEN 1 ELSE 0 END) AS immature
    """)
    print(f"Pre counts: mature={pre[0]['mature']}, immature={pre[0]['immature']}")

    rows = await Neo4jClient.execute_query("""
        MATCH (sp:SignalPerformance)
        WHERE sp.is_mature = false AND sp.conviction_tier='strong_buy'
          AND sp.ticker IN $tickers
        RETURN sp.signal_id AS sid, sp.ticker AS ticker, sp.signal_date AS signal_date,
               sp.actionable_date AS actionable_date, sp.return_current AS return_current,
               sp.price_day0 AS price_day0, sp.price_day1 AS price_day1, sp.price_day2 AS price_day2,
               sp.price_day3 AS price_day3, sp.price_day5 AS price_day5, sp.price_day7 AS price_day7
    """, {"tickers": TARGET_TICKERS})
    print(f"Loaded {len(rows)} rows: {sorted(r['ticker'] for r in rows)}")
    if len(rows) != EXPECTED_ROWS:
        print(f"ABORT: expected exactly {EXPECTED_ROWS} rows ({TARGET_TICKERS}). Got {len(rows)}.")
        sys.exit(1)

    matured = 0
    for r in rows:
        if not await mature_one(r):
            print(f"\nABORT: maturation failed for {r['ticker']}. Stopping. Dashboard NOT refreshed.")
            sys.exit(1)
        matured += 1

    post = await Neo4jClient.execute_query("""
        MATCH (sp:SignalPerformance)
        WHERE sp.direction='buy' AND sp.conviction_tier='strong_buy'
        RETURN sum(CASE WHEN sp.is_mature THEN 1 ELSE 0 END) AS mature,
               sum(CASE WHEN sp.is_mature = false THEN 1 ELSE 0 END) AS immature
    """)
    print(f"\nPost counts: mature={post[0]['mature']}, immature={post[0]['immature']}")
    print(f"Net delta: mature +{post[0]['mature'] - pre[0]['mature']}")
    if post[0]['mature'] != pre[0]['mature'] + matured:
        print("WARNING: mature delta != matured runs. Investigate before trusting dashboard.")

    print("\n--- DashboardStats ---")
    before = await SignalPerformanceService.get_dashboard_stats()
    print("Current (before):")
    for k, v in (before or {}).items():
        print(f"  {k:<20} = {v}")

    all_rows = await SignalPerformanceService._fetch_all_for_dashboard()

    if DRY_RUN:
        # Simulate the two flips in memory. Every other row keeps its stored
        # return_day0 / spy_return_90d verbatim — nothing is recomputed.
        computed = {r["ticker"]: r.get("_computed") for r in rows if r.get("_computed")}
        patched = 0
        n_before = sum(1 for r in all_rows if r["direction"] == "buy"
                       and r["conviction_tier"] == "strong_buy" and r["is_mature"])
        pool = [r for r in all_rows if r["direction"] == "buy"
                and r["conviction_tier"] == "strong_buy" and r["is_mature"]]
        for tk, c in computed.items():
            pool.append({"return_day0": c["return_day0"],
                         "spy_return_90d": c["spy_return_90d"]})
            patched += 1
        n = len(pool)
        wins = sum(1 for p in pool if (p.get("return_day0") or 0) > 0)
        with_spy = [p for p in pool if p.get("spy_return_90d") is not None]
        alphas = [(p.get("return_day0") or 0) - (p.get("spy_return_90d") or 0)
                  for p in with_spy]
        print(f"\nPROJECTED (dry run, {n_before} -> {n}, +{patched} simulated):")
        print(f"  total_signals        = {n}")
        print(f"  wins                 = {wins}")
        print(f"  losses               = {n - wins}")
        print(f"  hit_rate             = {round(wins / n * 100, 1)}")
        print(f"  avg_return           = {round(sum(p.get('return_day0') or 0 for p in pool) / n, 1)}")
        print(f"  avg_alpha            = {round(sum(alphas) / len(alphas), 1) if alphas else 0}")
        print(f"  beat_spy_pct         = {round(sum(1 for a in alphas if a > 0) / len(with_spy) * 100, 1) if with_spy else 0}")
        print(f"\nDRY RUN COMPLETE — nothing written. {matured} rows would mature.")
        return

    await SignalPerformanceService._save_dashboard_stats(all_rows)
    ds = await SignalPerformanceService.get_dashboard_stats()
    print("New DashboardStats:")
    for k, v in (ds or {}).items():
        print(f"  {k:<20} = {v}")
    print(f"\nDone. {matured} rows matured.")


if __name__ == "__main__":
    asyncio.run(main())
