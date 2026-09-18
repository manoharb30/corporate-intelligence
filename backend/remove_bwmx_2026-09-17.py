"""Remove the immature BWMX strong_buy signal and confirm the cohort.

BWMX (Betterware de Mexico, S.A.P.I. de C.V., CIK 0001788257) signalled
2026-09-17 with the largest cluster value in the open book ($2,293,811, 3
insiders). Dropped on per-arrival review — the FIRST exclusion for control-block
buyer concentration.

The three "independent" insiders are one family buying on the same two days:
Luis Campos (director AND 10% owner, holding voting and investment power over
Campalier S.A. de C.V. per his own Form 4 footnote), plus his sons Andres Campos
Chevallier (CEO) and Santiago Campos Chevallier (MD Betterware Mexico). Insiders
already held 63.2%. MIN_CLUSTER_INSIDERS counts heads, not decisions.

Compounding: $2.29M sits in the journal-L1 $1-5M dead zone; D/E 339% (6x the
worst direct-selling peer); FCF ~-$89M despite positive operating cash flow;
current ratio 1.11; and entry is only -19% off the 52w high, where 62% of our
signals form in the bottom quintile.

Explicitly NOT a data-quality exclusion. Unlike AXIA3, the Form 4 values are
genuinely USD — $16.2588 and $16.4416 weighted averages with footnote ranges
$15.7689-$16.4694, verified against the EDGAR XML — and the earnings gate
recorded pass_within_60d on all five transactions, a real pass rather than a
fail-open. The underlying business is the best in its peer group on both growth
(+16.8%) and operating margin (16.4%).

CIK is blocklisted in insider_cluster_service.EXCLUDED_CIKS so no future cluster
can re-form on it.

This script ONLY removes the signal node(s). The underlying Form 4 transactions
keep their GENUINE classification.

BWMX is immature, so the MATURE cohort and dashboard stats are unaffected. Per
feedback_matured_signals_frozen.md this ABORTS if the node has somehow matured.

Default = DRY-RUN (no writes). Pass --commit to delete.
"""
import argparse
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from app.db.neo4j_client import Neo4jClient

CIK = "0001788257"
SIGNAL_ID = "CLUSTER-0001788257-2026-09-17"


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
        WHERE substring(t.transaction_date,0,10) >= '2026-04-01'
        RETURN count(t) AS n, collect(DISTINCT t.classification) AS classes
    """, {"cik": CIK})
    print(f"Underlying BWMX transactions (>=2026-08-01): {tx[0]['n']} "
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
        print("  WARNING: mature count changed — expected unchanged (BWMX was immature). Investigate.")
        sys.exit(1)
    if post[0]['immature'] != pre[0]['immature'] - 1:
        print("  WARNING: immature count did not drop by exactly 1. Investigate.")
        sys.exit(1)
    print(f"  OK: {post[0]['mature']} mature unchanged; immature -1. BWMX removed.")
    print("\nNote: Signal List is served from an in-memory snapshot cache — it refreshes")
    print("on TTL expiry or backend restart. CIK is blocklisted in code (effective after redeploy).")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--commit", action="store_true", help="write deletes (default: dry-run)")
    asyncio.run(main(ap.parse_args().commit))
