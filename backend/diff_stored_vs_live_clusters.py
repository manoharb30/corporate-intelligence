"""Diff: stored immature strong_buy SignalPerformance rows vs live-detected clusters.

Stored side: SignalPerformance nodes with is_mature=false AND conviction_tier='strong_buy'
Live side:   InsiderClusterService.detect_clusters() results filtered to strong_buy

Read-only.
"""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from app.db.neo4j_client import Neo4jClient
from app.services.insider_cluster_service import InsiderClusterService


async def main():
    await Neo4jClient.connect()

    # 1. Stored set
    stored = await Neo4jClient.execute_query("""
        MATCH (sp:SignalPerformance)
        WHERE sp.is_mature = false
          AND sp.conviction_tier = 'strong_buy'
          AND sp.direction = 'buy'
        RETURN sp.signal_id AS sid, sp.ticker AS ticker,
               sp.signal_date AS sig_date, sp.num_insiders AS n,
               sp.total_value AS val
        ORDER BY sp.signal_date DESC
    """)
    stored_ids = {r["sid"] for r in stored}
    print(f"Stored immature strong_buy SignalPerformance rows: {len(stored_ids)}")

    # 2. Live detection
    clusters = await InsiderClusterService.detect_clusters(
        days=90, window_days=30, min_level="medium", direction="buy"
    )
    live = [c for c in clusters if c.conviction_tier == "strong_buy"]
    live_ids = {c.accession_number for c in live}
    print(f"Live strong_buy clusters (days=90, window_days=30): {len(live_ids)}")

    # 3. Diff
    only_stored = stored_ids - live_ids
    only_live = live_ids - stored_ids
    print(f"\nIn stored but NOT live ({len(only_stored)}):")
    for sid in sorted(only_stored):
        row = next((r for r in stored if r["sid"] == sid), {})
        print(f"  {sid}  {row.get('ticker')}  {row.get('sig_date')}  "
              f"n={row.get('n')}  ${row.get('val') or 0:,.0f}")

    print(f"\nIn live but NOT stored ({len(only_live)}):")
    for sid in sorted(only_live):
        c = next((c for c in live if c.accession_number == sid), None)
        if c:
            print(f"  {sid}  {c.ticker}  {c.window_end}  n={c.num_buyers}  "
                  f"${c.total_buy_value:,.0f}")


if __name__ == "__main__":
    asyncio.run(main())
