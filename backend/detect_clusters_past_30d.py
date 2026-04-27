"""One-off: detect clusters for the past 30-day window.

Uses production defaults: days=90 (enough lookback so 30-day windows aren't
truncated), window_days=30, min_level='medium', direction='buy'.

Read-only — no DB writes.
"""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from app.db.neo4j_client import Neo4jClient
from app.services.insider_cluster_service import InsiderClusterService


async def main():
    await Neo4jClient.connect()
    clusters = await InsiderClusterService.detect_clusters(
        days=90, window_days=30, min_level="medium", direction="buy"
    )
    print(f"{'window_end':<12} {'ticker':<8} {'level':<7} {'conviction':<11} "
          f"{'n':>3}  {'value':>14}  company")
    print("-" * 100)
    for c in clusters:
        print(f"{c.window_end:<12} {(c.ticker or '-'):<8} {c.signal_level:<7} "
              f"{c.conviction_tier:<11} {c.num_buyers:>3}  "
              f"${c.total_buy_value:>12,.0f}  {c.company_name[:40]}")
    print(f"\nTotal: {len(clusters)} clusters")


if __name__ == "__main__":
    asyncio.run(main())
