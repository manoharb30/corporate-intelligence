"""Remove the immature LUCK strong_buy signal and confirm the cohort.

LUCK (Lucky Strike Entertainment Corp, CIK 0001840572) signalled 2026-09-11 —
one of the two names that ended the 64-day drought. Dropped on per-arrival
fundamental review, the documented practice for this project (no automated
quality gate; review qualitatively per arrival). Two reasons:

1. Two-insider in name only. Shannon (founder/CEO) bought $175,800 on 09-09;
   Bass (director) bought $3,268 on 09-10 — 1.8% of Shannon's size. The
   MIN_CLUSTER_INSIDERS gate cleared on a token buy, so this is functionally a
   one-insider signal.
2. Balance sheet. EV $4.11B against a $749M market cap; total debt $3.27B on
   $274M EBITDA (~11.9x); book equity NEGATIVE (P/B -1.88); revenue flat at
   +0.9%; TTM net margin -2.9%; FCF ~-$1.1M; cash $39M on a 0.50 current ratio.
   Share count is shrinking, so this is a leverage left tail, not a dilution one.

CIK is blocklisted in insider_cluster_service.EXCLUDED_CIKS so no future cluster
can re-form on it.

This script ONLY removes the signal node(s). It does NOT touch the underlying
Form 4 transactions — the Shannon/Bass buys stay classified GENUINE, and LUCK
stays visible on the Research Queue's data if it ever qualifies there.

LUCK is immature, so the MATURE cohort and its dashboard stats are unaffected.
Per feedback_matured_signals_frozen.md this script ABORTS if the node has
somehow matured.

Default = DRY-RUN (no writes). Pass --commit to delete.
"""
import argparse
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from app.db.neo4j_client import Neo4jClient

CIK = "0001840572"
SIGNAL_ID = "CLUSTER-0001840572-2026-09-11"


async def main(commit: bool):
    await Neo4jClient.connect()

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

    tx = await Neo4jClient.execute_query("""
        MATCH (c:Company {cik: $cik})-[:INSIDER_TRADE_OF]->(t:InsiderTransaction)
        WHERE substring(t.transaction_date,0,10) >= '2026-08-01'
        RETURN count(t) AS n, collect(DISTINCT t.classification) AS classes
    """, {"cik": CIK})
    print(f"Underlying LUCK transactions (>=2026-08-01): {tx[0]['n']} "
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
        print("  WARNING: mature count changed — expected unchanged (LUCK was immature). Investigate.")
        sys.exit(1)
    if post[0]['immature'] != pre[0]['immature'] - 1:
        print("  WARNING: immature count did not drop by exactly 1. Investigate.")
        sys.exit(1)
    print(f"  OK: {post[0]['mature']} mature unchanged; immature -1. LUCK removed.")
    print("\nNote: Signal List is served from an in-memory snapshot cache — it refreshes")
    print("on TTL expiry or backend restart. CIK is blocklisted in code (effective after redeploy).")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--commit", action="store_true", help="write deletes (default: dry-run)")
    asyncio.run(main(ap.parse_args().commit))
