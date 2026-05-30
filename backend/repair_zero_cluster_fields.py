"""Repair SignalPerformance rows where num_insiders=0 / total_value=0.

These records exist because an incremental cluster update on 4/27-4/28
encountered TZ-suffixed transaction_date values; _cluster_state_for_window
returned zeros which the update path then wrote.

Bug fix is in insider_cluster_service._cluster_state_for_window (uses
substring before date()). This script repopulates the existing bad rows
by re-running the same windowed query — now safe — for each affected
signal_id.

Scope: only rows where num_insiders=0 OR total_value=0. Writes only
num_insiders, total_value, signal_level (if it should bump to 'high'),
and computed_at. Touches nothing else.

Read-only on InsiderTransaction. Idempotent — safe to re-run.
"""
import asyncio
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from app.db.neo4j_client import Neo4jClient


async def main():
    await Neo4jClient.connect()

    # Find SP rows with zeroed cluster fields
    bad = await Neo4jClient.execute_query("""
        MATCH (sp:SignalPerformance)
        WHERE sp.direction = 'buy'
          AND sp.conviction_tier = 'strong_buy'
          AND (sp.num_insiders = 0 OR sp.total_value = 0 OR sp.total_value IS NULL)
          AND sp.signal_date IS NOT NULL
          AND sp.cik IS NOT NULL
        RETURN sp.signal_id AS sid, sp.cik AS cik, sp.ticker AS ticker,
               substring(sp.signal_date, 0, 10) AS signal_date,
               sp.num_insiders AS old_n, sp.total_value AS old_v,
               sp.signal_level AS old_level
        ORDER BY sp.signal_date DESC
    """)
    print(f"Bad SignalPerformance rows: {len(bad)}")
    if not bad:
        print("Nothing to repair.")
        return

    now_iso = datetime.now(timezone.utc).isoformat()
    repaired = 0
    skipped = 0

    for r in bad:
        # Recompute count + value from InsiderTransaction in the 30d window
        # ending on signal_date. Uses the same filter as the (now fixed)
        # _cluster_state_for_window in insider_cluster_service.
        state = await Neo4jClient.execute_query("""
            MATCH (c:Company {cik: $cik})-[:INSIDER_TRADE_OF]->(t:InsiderTransaction)
            WHERE t.classification = 'GENUINE'
              AND t.transaction_code = 'P'
              AND (t.is_derivative IS NULL OR t.is_derivative = false)
              AND (t.is_10b5_1 IS NULL OR t.is_10b5_1 = false)
              AND date($sd) - duration({days: 30})
                  <= date(substring(t.transaction_date, 0, 10))
              AND date(substring(t.transaction_date, 0, 10)) <= date($sd)
            RETURN count(DISTINCT t.insider_name) AS n,
                   sum(t.total_value) AS v
        """, {"cik": r["cik"], "sd": r["signal_date"]})

        n = (state[0]["n"] if state else 0) or 0
        v = float((state[0]["v"] if state else 0.0) or 0.0)

        if n < 2:
            print(f"  skip {r['ticker']:<6} {r['signal_date']}  recomputed n={n} (< 2, would not qualify) — leaving as-is")
            skipped += 1
            continue

        new_level = 'high' if n >= 3 else r["old_level"]

        await Neo4jClient.execute_query("""
            MATCH (sp:SignalPerformance {signal_id: $sid})
            SET sp.num_insiders = $n,
                sp.total_value = $v,
                sp.signal_level = $level,
                sp.computed_at = $now
        """, {"sid": r["sid"], "n": n, "v": v, "level": new_level, "now": now_iso})

        print(f"  {r['ticker']:<6} {r['signal_date']}  "
              f"n: {r['old_n']} → {n}   v: ${(r['old_v'] or 0)/1000:.0f}K → ${v/1000:.0f}K   "
              f"level: {r['old_level']} → {new_level}")
        repaired += 1

    print(f"\nDone. repaired={repaired}, skipped={skipped}")


if __name__ == "__main__":
    asyncio.run(main())
