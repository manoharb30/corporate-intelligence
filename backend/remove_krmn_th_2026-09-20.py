"""Remove the immature KRMN and TH strong_buy signals and confirm the cohort.

Both signalled 2026-09-18 and were dropped on per-arrival review 2026-09-19.
ResearchNotes were written first (record_notes_krmn_th_2026-09-19.py) so the
reasoning outlives the rows; both CIKs are in EXCLUDED_CIKS so no future cluster
can re-form.

KRMN (Karman Holdings, CIK 0002040127) — token_buy_cluster plus a sponsor
overhang. Stinnett $1,007,648 is 97.2% of the cluster next to $18,720 and
$10,117, so removing the tokens leaves one buyer. Separately and more
importantly, the -70% drawdown is Trive Capital distributing: three offerings in
18 months, a 14,000,000-share secondary on 2026-05-28 from which the company
received nothing, ~11% under a modified lock-up, and a live S-3ASR shelf.

TH (Target Hospitality, CIK 0001712189) — post_run. Buyers are clean (CEO
$250,166, CCO $124,992) but the stock rose 13.2% in the three days between the
two buys and sits -1% off its 52-week high after +255% in a year, at 48.3x
EV/EBITDA on a -8.8% operating margin.

This script ONLY removes the signal nodes. Underlying Form 4 transactions keep
their GENUINE classification.

Both are immature, so the MATURE cohort and dashboard stats are unaffected. Per
feedback_matured_signals_frozen.md this ABORTS on any row that has matured, and
processes rows in order — a failure on the first leaves the second untouched.

Default = DRY-RUN (no writes). Pass --commit to delete.
"""

import argparse
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from app.db.neo4j_client import Neo4jClient

TARGETS = [
    ("KRMN", "0002040127", "CLUSTER-0002040127-2026-09-18"),
    ("TH",   "0001712189", "CLUSTER-0001712189-2026-09-18"),
]


async def main(commit: bool):
    await Neo4jClient.connect()

    pre = await Neo4jClient.execute_query("""
        MATCH (sp:SignalPerformance) WHERE sp.conviction_tier='strong_buy'
        RETURN sum(CASE WHEN sp.is_mature THEN 1 ELSE 0 END) AS mature,
               sum(CASE WHEN NOT sp.is_mature THEN 1 ELSE 0 END) AS immature
    """)
    print(f"BEFORE strong_buy cohort: mature={pre[0]['mature']}  immature={pre[0]['immature']}")

    targets = []
    for ticker, cik, sid in TARGETS:
        rows = await Neo4jClient.execute_query("""
            MATCH (sp:SignalPerformance {signal_id: $sid})
            RETURN sp.ticker AS ticker, sp.company_name AS name, sp.is_mature AS mature,
                   sp.num_insiders AS n, sp.total_value AS v, sp.market_cap AS mcap
        """, {"sid": sid})
        if not rows:
            print(f"\n{ticker}: no SignalPerformance {sid} — nothing to remove.")
            continue
        s = rows[0]
        print(f"\n{ticker} ({s['name']})  {sid}")
        print(f"  mature={s['mature']}  insiders={s['n']}  value=${s['v']:,.0f}  "
              f"mcap=${s['mcap']:,.0f}")
        if s["mature"]:
            print("  ABORT: is_mature=true — frozen cohort, refusing to delete.")
            sys.exit(1)

        note = await Neo4jClient.execute_query("""
            MATCH (c:Company {cik: $cik})-[:HAS_RESEARCH_NOTE]->(rn:ResearchNote)
            RETURN rn.note_date AS d, rn.verdict AS v, rn.risk_flags AS f
        """, {"cik": cik})
        if not note:
            print("  ABORT: no ResearchNote on this company — write the note BEFORE "
                  "removing the row, or the reasoning is lost with it.")
            sys.exit(1)
        print(f"  ResearchNote present: {note[0]['d']} / {note[0]['v']} / flags={note[0]['f']}")

        tx = await Neo4jClient.execute_query("""
            MATCH (c:Company {cik: $cik})-[:INSIDER_TRADE_OF]->(t:InsiderTransaction)
            WHERE substring(t.transaction_date,0,10) >= '2026-08-01'
            RETURN count(t) AS n, collect(DISTINCT t.classification) AS classes
        """, {"cik": cik})
        print(f"  Underlying transactions (>=2026-08-01): {tx[0]['n']} "
              f"{tx[0]['classes']} — NOT modified.")
        targets.append((ticker, sid))

    if not commit:
        print(f"\nDRY-RUN: no writes. {len(targets)} row(s) would be deleted. "
              f"Re-run with --commit.")
        return

    print("\n=== COMMIT ===")
    deleted = 0
    for ticker, sid in targets:
        d = await Neo4jClient.execute_query("""
            MATCH (sp:SignalPerformance {signal_id: $sid}) DETACH DELETE sp
            RETURN count(*) AS d
        """, {"sid": sid})
        print(f"  {ticker}: SignalPerformance deleted: {d[0]['d']}")
        deleted += d[0]["d"]

    post = await Neo4jClient.execute_query("""
        MATCH (sp:SignalPerformance) WHERE sp.conviction_tier='strong_buy'
        RETURN sum(CASE WHEN sp.is_mature THEN 1 ELSE 0 END) AS mature,
               sum(CASE WHEN NOT sp.is_mature THEN 1 ELSE 0 END) AS immature
    """)
    print(f"\nAFTER strong_buy cohort: mature={post[0]['mature']}  immature={post[0]['immature']}")
    if post[0]["mature"] != pre[0]["mature"]:
        print("  WARNING: mature count changed — expected unchanged. Investigate.")
        sys.exit(1)
    if post[0]["immature"] != pre[0]["immature"] - deleted:
        print(f"  WARNING: immature did not drop by exactly {deleted}. Investigate.")
        sys.exit(1)
    print(f"  OK: {post[0]['mature']} mature unchanged; immature -{deleted}.")

    remaining = await Neo4jClient.execute_query("""
        MATCH (sp:SignalPerformance)
        WHERE sp.conviction_tier='strong_buy' AND NOT sp.is_mature
        RETURN sp.ticker AS t ORDER BY t
    """)
    print(f"  Open book now: {[r['t'] for r in remaining]}")
    print("\nNote: Signal List is served from an in-memory snapshot cache — it refreshes")
    print("on TTL expiry or backend restart. Both CIKs are blocklisted in code.")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--commit", action="store_true", help="write deletes (default: dry-run)")
    asyncio.run(main(ap.parse_args().commit))
