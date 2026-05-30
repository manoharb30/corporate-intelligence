"""Refresh price fields used by the live product.

Two refresh steps, in order:
1. SignalPerformance.price_current / return_current — for immature strong_buy
   rows. Source for Signal Detail decision cards.
2. Company.price_series + SPY — for the live Signal List page (which computes
   returns + alpha from price_series[-1] for clusters in the last 90 days).
   Delegates to scanner.form4_scanner.update_signal_prices(days_lookback=90)
   so the scope matches what users actually see; >20h staleness skip avoids
   pointless re-fetches.

No maturity flips, no signal recompute.
"""
import asyncio
import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import yfinance as yf

sys.path.insert(0, str(Path(__file__).parent))
from app.db.neo4j_client import Neo4jClient
from scanner.form4_scanner import update_signal_prices


def latest_close(ticker: str) -> tuple[float | None, str | None]:
    """Return (close, date_str) for the most recent trading day, or (None, None)."""
    try:
        h = yf.Ticker(ticker).history(period="5d")
        if h.empty:
            return None, None
        last_close = float(h.iloc[-1]["Close"])
        last_date = h.index[-1].strftime("%Y-%m-%d")
        return last_close, last_date
    except Exception:
        return None, None


EXCLUDE_TICKERS: list[str] = []


async def main():
    await Neo4jClient.connect()
    rows = await Neo4jClient.execute_query("""
        MATCH (sp:SignalPerformance)
        WHERE sp.is_mature = false
          AND sp.conviction_tier = 'strong_buy'
          AND sp.direction = 'buy'
          AND sp.ticker IS NOT NULL
          AND sp.price_day0 IS NOT NULL
          AND sp.price_day0 > 0
          AND NOT sp.ticker IN $exclude
        RETURN sp.signal_id AS sid, sp.ticker AS t, sp.signal_date AS sd,
               sp.price_day0 AS p0
        ORDER BY sp.signal_date DESC
    """, {"exclude": EXCLUDE_TICKERS})
    print(f"Immature strong_buy SP rows to refresh: {len(rows)}")

    updated = 0
    skipped = 0
    for r in rows:
        close, used_date = latest_close(r["t"])
        if close is None:
            skipped += 1
            print(f"  skip {r['t']:<8} (yfinance no data)")
            continue
        return_current = round((close - r["p0"]) / r["p0"] * 100, 2)
        await Neo4jClient.execute_query("""
            MATCH (sp:SignalPerformance {signal_id: $sid})
            SET sp.price_current = $price,
                sp.price_current_date = $date,
                sp.return_current = $ret
        """, {"sid": r["sid"], "price": close, "date": used_date, "ret": return_current})
        updated += 1
        print(f"  {r['t']:<8} {r['sd']}: p0=${r['p0']:.2f} → price_current=${close:.2f} "
              f"({used_date}) return_current={return_current:+.2f}%")

    print(f"\nSignalPerformance refresh done. updated={updated}, skipped={skipped}")

    print("\nRefreshing Company.price_series for last-90d signal tickers + SPY...")
    n = await update_signal_prices(days_lookback=90)
    print(f"Company.price_series refresh done. companies updated={n}")


if __name__ == "__main__":
    asyncio.run(main())
