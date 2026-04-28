"""Refresh price_current + return_current for immature SignalPerformance rows.

Scope (intentionally narrow):
- Only rows where is_mature = false AND conviction_tier = 'strong_buy'
- Updates: sp.price_current, sp.price_current_date, sp.return_current
- Touches NOTHING else — no Company.price_series, no other SP fields,
  no maturity flips, no num_insiders/total_value changes.

Read-only on Company. Writes only to immature SP rows.
"""
import asyncio
import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import yfinance as yf

sys.path.insert(0, str(Path(__file__).parent))
from app.db.neo4j_client import Neo4jClient


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
        RETURN sp.signal_id AS sid, sp.ticker AS t, sp.signal_date AS sd,
               sp.price_day0 AS p0
        ORDER BY sp.signal_date DESC
    """)
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

    print(f"\nDone. updated={updated}, skipped={skipped}")


if __name__ == "__main__":
    asyncio.run(main())
