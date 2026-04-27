"""Phase C smoke test — run process_incremental against every CIK with an
existing immature strong_buy SP row.

Expected outcomes per CIK:
  - "none"    → state unchanged since creation (normal)
  - "updated" → new GENUINE trades joined the cluster since formation; SP row
                was stale; update synced num_insiders / total_value
  - "created" → UNEXPECTED (a duplicate active cluster shouldn't form here)
  - "error"   → exception; investigate

Does NOT touch InsiderTransaction data. Only reads them; may write to
SignalPerformance if a cluster's state has drifted.
"""
import asyncio
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from app.db.neo4j_client import Neo4jClient
from app.services.insider_cluster_service import InsiderClusterService


async def main():
    await Neo4jClient.connect()
    today = date.today().isoformat()

    rows = await Neo4jClient.execute_query(
        """
        MATCH (sp:SignalPerformance)
        WHERE sp.is_mature = false
          AND sp.conviction_tier = 'strong_buy'
          AND sp.direction = 'buy'
        RETURN DISTINCT sp.cik AS cik, sp.ticker AS ticker,
               sp.signal_date AS sd, sp.num_insiders AS n,
               sp.total_value AS v
        ORDER BY sp.signal_date DESC
        """
    )
    print(f"Found {len(rows)} immature strong_buy CIKs. Date: {today}\n")

    created = updated = noop = errored = 0
    for r in rows:
        cik = r["cik"]
        ticker = r["ticker"] or "-"
        sd = r["sd"]
        try:
            result = await InsiderClusterService.process_incremental(cik, today)
        except Exception as e:
            errored += 1
            print(f"  ERROR  {ticker:<8} {cik}  sd={sd}  {type(e).__name__}: {str(e)[:80]}")
            continue
        action = result.get("action", "none")
        if action == "created":
            created += 1
            print(f"  CREATED  {ticker:<8} {cik}  {result['signal_id']}")
        elif action == "updated":
            updated += 1
            print(f"  UPDATED  {ticker:<8} {cik}  sd={sd}  was n={r['n']} v={r['v']:,.0f}")
        else:
            noop += 1

    print(f"\nSummary: created={created}, updated={updated}, no-op={noop}, errors={errored}")


if __name__ == "__main__":
    asyncio.run(main())
