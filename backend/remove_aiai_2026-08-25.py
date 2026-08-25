"""Remove the AIAI strong_buy created 2026-08-24.

CIK 0002096362 was blocklisted 2026-08-25 (see the research note): insiders sold
~$2.03M at $12.00-$15.62 then bought ~$140K at $5.25-$7.13, balance sheet is 91%
goodwill/intangibles at 0.47x book, and the signal only passed the earnings gate
because a May-2026 direct listing has no earnings history (filter fails open).

The row is is_mature=False, so nothing in the frozen 193-signal cohort moves.
Underlying InsiderTransaction rows are left as-is — they are genuine purchases;
the blocklist is what keeps them out of future clusters.

Mirrors remove_logc_2026-06-09.py: inspect, then DETACH DELETE.
"""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from app.db.neo4j_client import Neo4jClient

SIGNAL_ID = "CLUSTER-0002096362-2026-08-24"
CIK = "0002096362"


async def main() -> None:
    await Neo4jClient.connect()

    print("=== BEFORE ===")
    rows = await Neo4jClient.execute_query(
        "MATCH (sp:SignalPerformance {signal_id:$sid}) RETURN properties(sp) AS p",
        {"sid": SIGNAL_ID})
    if not rows:
        print("  no SignalPerformance node — nothing to do")
        await Neo4jClient.disconnect()
        return
    for k, v in sorted(rows[0]["p"].items()):
        print(f"    {k:<24} {v}")

    rels = await Neo4jClient.execute_query("""
        MATCH (sp:SignalPerformance {signal_id:$sid})-[r]-(n)
        RETURN type(r) AS rel, labels(n) AS labels, count(*) AS n
    """, {"sid": SIGNAL_ID})
    print("  attached:", [dict(r) for r in rels] or "none")

    clusters = await Neo4jClient.execute_query("""
        MATCH (ic:InsiderCluster)
        WHERE ic.cluster_id = $sid OR ic.signal_id = $sid
        RETURN count(*) AS n
    """, {"sid": SIGNAL_ID})
    print("  InsiderCluster nodes:", clusters[0]["n"] if clusters else 0)

    before = await Neo4jClient.execute_query("""
        MATCH (sp:SignalPerformance) WHERE sp.conviction_tier = 'strong_buy'
        RETURN count(*) AS total,
               sum(CASE WHEN sp.is_mature THEN 1 ELSE 0 END) AS mature,
               sum(CASE WHEN sp.is_mature THEN 0 ELSE 1 END) AS immature
    """)
    print("  strong_buy counts:", dict(before[0]))

    print("\n=== DELETING ===")
    d1 = await Neo4jClient.execute_query(
        "MATCH (sp:SignalPerformance {signal_id:$sid}) DETACH DELETE sp "
        "RETURN count(*) AS d", {"sid": SIGNAL_ID})
    print("  SignalPerformance deleted:", d1[0]["d"] if d1 else 0)

    d2 = await Neo4jClient.execute_query("""
        MATCH (ic:InsiderCluster)
        WHERE ic.cluster_id = $sid OR ic.signal_id = $sid
        DETACH DELETE ic RETURN count(*) AS d
    """, {"sid": SIGNAL_ID})
    print("  InsiderCluster deleted:", d2[0]["d"] if d2 else 0)

    print("\n=== AFTER ===")
    after = await Neo4jClient.execute_query("""
        MATCH (sp:SignalPerformance) WHERE sp.conviction_tier = 'strong_buy'
        RETURN count(*) AS total,
               sum(CASE WHEN sp.is_mature THEN 1 ELSE 0 END) AS mature,
               sum(CASE WHEN sp.is_mature THEN 0 ELSE 1 END) AS immature
    """)
    print("  strong_buy counts:", dict(after[0]))

    left = await Neo4jClient.execute_query(
        "MATCH (sp:SignalPerformance {signal_id:$sid}) RETURN count(*) AS n",
        {"sid": SIGNAL_ID})
    print("  rows still matching signal_id:", left[0]["n"])

    txns = await Neo4jClient.execute_query("""
        MATCH (c:Company {cik:$cik})-[:INSIDER_TRADE_OF]->(t:InsiderTransaction)
        RETURN count(*) AS n
    """, {"cik": CIK})
    print("  AIAI InsiderTransaction rows left intact:", txns[0]["n"])

    await Neo4jClient.disconnect()


asyncio.run(main())
