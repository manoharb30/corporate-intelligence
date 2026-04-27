"""Phase A: Lock the historic anchor.

Computes aggregates from the current 142 mature strong_buy SignalPerformance rows
and persists them to a (:HistoricAnchor {id:'v1.0-v1.6'}) node. Idempotent:
re-running prints existing values without overwriting.

These numbers become the frozen baseline for the incremental (historic anchor
+ running delta) dashboard model. Nothing in the codebase should ever
overwrite this node.
"""
import asyncio
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from app.db.neo4j_client import Neo4jClient


async def main():
    await Neo4jClient.connect()

    # Check if anchor already exists — if so, report and exit without mutation
    existing = await Neo4jClient.execute_query(
        "MATCH (a:HistoricAnchor {id: 'v1.0-v1.6'}) "
        "RETURN a.n AS n, a.wins AS wins, a.losses AS losses, "
        "a.return_sum AS return_sum, a.alpha_sum AS alpha_sum, "
        "a.beat_count AS beat_count, a.n_with_spy AS n_with_spy, "
        "a.hit_rate AS hit_rate, a.avg_return AS avg_return, "
        "a.avg_alpha AS avg_alpha, a.beat_spy_pct AS beat_spy_pct, "
        "a.locked_at AS locked_at"
    )
    if existing:
        a = existing[0]
        print("HistoricAnchor already exists — not overwriting.")
        print(f"  locked_at:   {a['locked_at']}")
        print(f"  n:           {a['n']}")
        print(f"  wins/losses: {a['wins']}/{a['losses']}")
        print(f"  return_sum:  {a['return_sum']:.2f}")
        print(f"  alpha_sum:   {a['alpha_sum']:.2f}")
        print(f"  beat_count:  {a['beat_count']} of {a['n_with_spy']}")
        print(f"  hit_rate:    {a['hit_rate']}%")
        print(f"  avg_return:  {a['avg_return']}%")
        print(f"  avg_alpha:   +{a['avg_alpha']}%")
        print(f"  beat_spy:    {a['beat_spy_pct']}%")
        return

    # Compute aggregates from current DB state
    rows = await Neo4jClient.execute_query("""
        MATCH (sp:SignalPerformance)
        WHERE sp.is_mature = true
          AND sp.conviction_tier = 'strong_buy'
          AND sp.direction = 'buy'
        RETURN sp.return_day0 AS ret, sp.spy_return_90d AS spy
    """)
    n = len(rows)
    if n == 0:
        print("ERROR: No matured strong_buy rows found — aborting.")
        sys.exit(1)

    wins = sum(1 for r in rows if (r["ret"] or 0) > 0)
    return_sum = sum((r["ret"] or 0) for r in rows)

    # Alpha + beat_spy are only meaningful where spy_return_90d is populated
    with_spy = [r for r in rows
                if r["spy"] is not None and r["ret"] is not None]
    alpha_sum = sum((r["ret"] - r["spy"]) for r in with_spy)
    beat_count = sum(1 for r in with_spy if (r["ret"] - r["spy"]) > 0)
    n_with_spy = len(with_spy)

    hit_rate = round(wins / n * 100, 1)
    avg_return = round(return_sum / n, 1)
    avg_alpha = round(alpha_sum / n_with_spy, 1) if n_with_spy else 0.0
    beat_spy_pct = round(beat_count / n_with_spy * 100, 1) if n_with_spy else 0.0

    now = datetime.utcnow().isoformat()

    await Neo4jClient.execute_query("""
        CREATE (a:HistoricAnchor {
            id: 'v1.0-v1.6',
            n: $n,
            wins: $wins,
            losses: $losses,
            return_sum: $return_sum,
            alpha_sum: $alpha_sum,
            beat_count: $beat_count,
            n_with_spy: $n_with_spy,
            hit_rate: $hit_rate,
            avg_return: $avg_return,
            avg_alpha: $avg_alpha,
            beat_spy_pct: $beat_spy_pct,
            locked_at: $now,
            note: 'Frozen aggregate of 142 mature strong_buy SignalPerformance rows as of 2026-04-24. Never overwritten. Source for incremental (anchor + running delta) dashboard model.'
        })
    """, {
        "n": n, "wins": wins, "losses": n - wins,
        "return_sum": return_sum, "alpha_sum": alpha_sum,
        "beat_count": beat_count, "n_with_spy": n_with_spy,
        "hit_rate": hit_rate, "avg_return": avg_return,
        "avg_alpha": avg_alpha, "beat_spy_pct": beat_spy_pct,
        "now": now,
    })

    print("HistoricAnchor LOCKED:")
    print(f"  n:           {n}")
    print(f"  wins/losses: {wins}/{n - wins}")
    print(f"  return_sum:  {return_sum:.2f}")
    print(f"  alpha_sum:   {alpha_sum:.2f}")
    print(f"  beat_count:  {beat_count} of {n_with_spy}")
    print(f"  hit_rate:    {hit_rate}%")
    print(f"  avg_return:  {avg_return}%")
    print(f"  avg_alpha:   +{avg_alpha}%")
    print(f"  beat_spy:    {beat_spy_pct}%")
    print(f"  locked_at:   {now}")


if __name__ == "__main__":
    asyncio.run(main())
