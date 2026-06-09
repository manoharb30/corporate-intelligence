"""Remove the immature LOGC strong_buy signal and confirm the cohort.

LOGC (ContextLogic Holdings, CIK 0002064307) is an Abrams-controlled permanent-
capital vehicle — a control-vehicle false positive, not an operating-midcap insider
cluster. CIK is blocklisted in code (insider_cluster_service.EXCLUDED_CIKS) so it
cannot re-form on next ingest.

This script ONLY removes the signal node(s). It does NOT touch the underlying
Form 4 transactions — Bobbili/Levy's buys are genuine open-market purchases and
stay classified GENUINE (deliberate divergence from invalidate_codi which relabels).

LOGC is immature, so the 173 MATURE strong_buy dashboard stats are unaffected.

Default = DRY-RUN (no writes). Pass --commit to delete.
"""
import argparse
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from app.db.neo4j_client import Neo4jClient

CIK = "0002064307"
SIGNAL_ID = "CLUSTER-0002064307-2026-06-03"


async def main(commit: bool):
    await Neo4jClient.connect()

    # 1. Show what we're about to remove
    sp = await Neo4jClient.execute_query("""
        MATCH (sp:SignalPerformance {signal_id: $sid})
        RETURN sp.ticker AS ticker, sp.company_name AS name, sp.signal_date AS sd,
               sp.conviction_tier AS tier, sp.is_mature AS mature,
               sp.num_insiders AS n, sp.total_value AS v, sp.market_cap AS mcap
    """, {"sid": SIGNAL_ID})
    if not sp:
        print(f"No SignalPerformance node {SIGNAL_ID} found — nothing to remove.")
        return
    s = sp[0]
    print(f"Target SignalPerformance: {SIGNAL_ID}")
    print(f"  {s['ticker']} ({s['name']})  signal_date={s['sd']}  tier={s['tier']}  "
          f"mature={s['mature']}  insiders={s['n']}  value=${s['v']:,.0f}  mcap=${s['mcap']:,.0f}")
    if s["mature"]:
        print("  ABORT: node is_mature=true — frozen cohort, refusing to delete.")
        sys.exit(1)

    ic = await Neo4jClient.execute_query("""
        MATCH (ic:InsiderCluster)
        WHERE ic.cluster_id = $sid OR ic.signal_id = $sid
        RETURN count(*) AS n
    """, {"sid": SIGNAL_ID})
    print(f"InsiderCluster nodes matching: {ic[0]['n']}")

    # Confirm underlying transactions remain GENUINE and untouched
    tx = await Neo4jClient.execute_query("""
        MATCH (c:Company {cik: $cik})-[:INSIDER_TRADE_OF]->(t:InsiderTransaction)
        WHERE substring(t.transaction_date,0,10) >= '2026-05-01'
        RETURN count(t) AS n, collect(DISTINCT t.classification) AS classes
    """, {"cik": CIK})
    print(f"Underlying LOGC transactions (>=2026-05-01): {tx[0]['n']} "
          f"classifications={tx[0]['classes']} — NOT modified by this script.")

    pre = await Neo4jClient.execute_query("""
        MATCH (sp:SignalPerformance) WHERE sp.conviction_tier='strong_buy'
        RETURN sum(CASE WHEN sp.is_mature THEN 1 ELSE 0 END) AS mature,
               sum(CASE WHEN NOT sp.is_mature THEN 1 ELSE 0 END) AS immature
    """)
    print(f"\nBEFORE strong_buy cohort: mature={pre[0]['mature']}  immature={pre[0]['immature']}")

    if not commit:
        print("\nDRY-RUN: no writes. Re-run with --commit to delete the SP + InsiderCluster nodes.")
        return

    # 2. Delete
    print("\n=== COMMIT ===")
    d1 = await Neo4jClient.execute_query("""
        MATCH (sp:SignalPerformance {signal_id: $sid}) DETACH DELETE sp RETURN count(*) AS d
    """, {"sid": SIGNAL_ID})
    print(f"  SignalPerformance deleted: {d1[0]['d']}")
    d2 = await Neo4jClient.execute_query("""
        MATCH (ic:InsiderCluster) WHERE ic.cluster_id=$sid OR ic.signal_id=$sid
        DETACH DELETE ic RETURN count(*) AS d
    """, {"sid": SIGNAL_ID})
    print(f"  InsiderCluster deleted: {d2[0]['d']}")

    post = await Neo4jClient.execute_query("""
        MATCH (sp:SignalPerformance) WHERE sp.conviction_tier='strong_buy'
        RETURN sum(CASE WHEN sp.is_mature THEN 1 ELSE 0 END) AS mature,
               sum(CASE WHEN NOT sp.is_mature THEN 1 ELSE 0 END) AS immature
    """)
    print(f"\nAFTER strong_buy cohort: mature={post[0]['mature']}  immature={post[0]['immature']}")
    if post[0]['mature'] != pre[0]['mature']:
        print("  WARNING: mature count changed — expected unchanged (LOGC was immature). Investigate.")
        sys.exit(1)
    if post[0]['immature'] != pre[0]['immature'] - 1:
        print("  WARNING: immature count did not drop by exactly 1. Investigate.")
        sys.exit(1)
    print("  OK: 173 mature unchanged; immature -1. LOGC removed.")
    print("\nNote: Signal List is served from an in-memory snapshot cache — it refreshes")
    print("on TTL expiry or backend restart. CIK is blocklisted in code (effective after redeploy).")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--commit", action="store_true", help="write deletes (default: dry-run)")
    asyncio.run(main(ap.parse_args().commit))
