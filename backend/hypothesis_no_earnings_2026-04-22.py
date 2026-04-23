"""Hypothesis: what if we drop the earnings-proximity rule and keep only
midcap + $100K + 2+ buyers as the cohort definition?

Approach: analyze the existing 142 mature strong_buy cohort — which the bug
has been producing as an approximation of "drop earnings rule" all along —
and split it by whether the underlying transactions actually pass or fail
the earnings-60d check (via `classification = GENUINE` vs `FILTERED`).

Then compare cohort numbers under three filter scenarios:
  A. Current cohort (142 — midcap-ratio + $100K + 2+ buyers, no earnings gate)
  B. Apply earnings gate properly (only all-GENUINE underlying)
  C. Apply TRUE mcap band ($300M-$5B from XBRL) on top of A
  D. Apply BOTH — all-GENUINE + true-midcap (strictest)

No DB mutations. Read-only.
"""

import asyncio
import sys
from collections import Counter
from pathlib import Path
from statistics import mean, stdev

sys.path.insert(0, str(Path(__file__).parent))

from app.db.neo4j_client import Neo4jClient

MIDCAP_LO = 300_000_000
MIDCAP_HI = 5_000_000_000


async def fetch_cohort():
    """142 mature strong_buys + for each, their underlying txn classifications
    at the signal date."""
    rows = await Neo4jClient.execute_query(
        """
        MATCH (sp:SignalPerformance)
        WHERE sp.is_mature = true AND sp.conviction_tier = 'strong_buy'
          AND sp.direction = 'buy'
        WITH sp
        MATCH (c:Company {cik: sp.cik})-[:INSIDER_TRADE_OF]->(t:InsiderTransaction)
        WHERE t.transaction_code = 'P'
          AND substring(toString(t.transaction_date), 0, 10) =
              substring(toString(sp.signal_date), 0, 10)
        WITH sp, collect(DISTINCT t.classification) AS classifications,
             sum(CASE WHEN t.classification = 'GENUINE' THEN 1 ELSE 0 END) AS genuine_cnt,
             count(t) AS total_cnt
        RETURN sp.ticker AS ticker, sp.signal_id AS signal_id,
               substring(toString(sp.signal_date), 0, 10) AS signal_date,
               sp.num_insiders AS n_ins, sp.total_value AS total_value,
               sp.market_cap AS mcap_ratio,
               sp.mcap_at_signal_true AS mcap_true,
               sp.return_day0 AS ret, sp.spy_return_90d AS spy,
               classifications, genuine_cnt, total_cnt
        ORDER BY sp.signal_date
        """
    )
    return [dict(r) for r in rows]


def summarize(rows, label):
    if not rows:
        return f"  {label:<30s} n=0"
    n = len(rows)
    with_ret = [r for r in rows if r.get("ret") is not None]
    if not with_ret:
        return f"  {label:<30s} n={n} (no return data)"
    wins = sum(1 for r in with_ret if r["ret"] > 0)
    avg_ret = mean(r["ret"] for r in with_ret)
    with_spy = [r for r in with_ret if r.get("spy") is not None]
    if with_spy:
        alphas = [r["ret"] - r["spy"] for r in with_spy]
        avg_alpha = mean(alphas)
        alpha_std = stdev(alphas) if len(alphas) > 1 else 0.0
        alpha_se = alpha_std / (len(alphas) ** 0.5) if len(alphas) > 1 else 0.0
    else:
        avg_alpha = None
        alpha_se = None
    hr = wins / len(with_ret) * 100
    return (
        f"  {label:<30s} n={n:<3d}  HR={hr:5.1f}%  "
        f"avg_ret={avg_ret:+6.2f}%  "
        f"alpha={avg_alpha:+6.2f}pp"
        + (f" (SE={alpha_se:.2f})" if alpha_se else "")
    )


async def main():
    await Neo4jClient.connect()
    cohort = await fetch_cohort()
    await Neo4jClient.disconnect()
    print(f"Loaded {len(cohort)} mature strong_buy rows\n")

    # Classify each signal by whether underlying txns are all-GENUINE,
    # contain FILTERED (earnings-fail), or otherwise.
    all_genuine = []
    has_filtered = []
    has_other = []
    for r in cohort:
        classifications = set(r["classifications"])
        if classifications == {"GENUINE"}:
            all_genuine.append(r)
        elif "FILTERED" in classifications:
            has_filtered.append(r)
        else:
            has_other.append(r)

    # Classify by TRUE mcap band
    true_midcap = [r for r in cohort if r["mcap_true"]
                   and MIDCAP_LO <= r["mcap_true"] <= MIDCAP_HI]
    true_below = [r for r in cohort if r["mcap_true"]
                  and r["mcap_true"] < MIDCAP_LO]
    true_above = [r for r in cohort if r["mcap_true"]
                  and r["mcap_true"] > MIDCAP_HI]
    true_unknown = [r for r in cohort if not r["mcap_true"]]

    print("=" * 78)
    print("DECOMPOSITION BY UNDERLYING-TXN CLASSIFICATION")
    print("=" * 78)
    print(f"  All-GENUINE underlying (passes earnings gate): {len(all_genuine)}")
    print(f"  Has FILTERED underlying  (fails earnings gate): {len(has_filtered)}")
    print(f"  Has other (AMBIGUOUS/NULL/mixed):               {len(has_other)}")

    print("\n=== underlying classification mix ===")
    mix_counter = Counter()
    for r in cohort:
        mix_counter[tuple(sorted(r["classifications"]))] += 1
    for combo, cnt in mix_counter.most_common():
        print(f"  {str(list(combo)):45s} {cnt}")

    print("\n" + "=" * 78)
    print("DECOMPOSITION BY TRUE MCAP BAND")
    print("=" * 78)
    print(f"  In TRUE midcap band ($300M-$5B): {len(true_midcap)}")
    print(f"  TRUE microcap (<$300M):          {len(true_below)}")
    print(f"  TRUE largecap (>$5B):            {len(true_above)}")
    print(f"  TRUE unknown (no XBRL):          {len(true_unknown)}")

    # =================== SCENARIOS ===================
    print("\n" + "=" * 78)
    print("SCENARIO COMPARISON — effect of different filter combinations")
    print("=" * 78)

    # Scenario A: current (loose mcap, no earnings gate) — what we ship today
    print("\n[A] Current cohort — ratio-mcap + $100K + 2+ buyers, no earnings gate")
    print(summarize(cohort, "Full 142"))

    # Scenario B: apply earnings gate properly (the v1.1 stated methodology)
    print("\n[B] Add earnings-gate (keep only all-GENUINE underlying)")
    print(summarize(all_genuine, "All-GENUINE only"))
    print(summarize(has_filtered, "  ...dropped (has FILTERED)"))
    print(summarize(has_other, "  ...dropped (other/NULL)"))

    # Scenario C: apply TRUE mcap band on top of A (yesterday's audit)
    print("\n[C] Replace ratio-mcap with TRUE midcap (XBRL), no earnings gate")
    print(summarize(true_midcap, "TRUE midcap"))
    print(summarize(true_below, "  ...dropped (<$300M)"))
    print(summarize(true_above, "  ...dropped (>$5B)"))

    # Scenario D: strictest — all-GENUINE AND TRUE midcap
    clean = [r for r in all_genuine
             if r["mcap_true"]
             and MIDCAP_LO <= r["mcap_true"] <= MIDCAP_HI]
    dropped_earnings = [r for r in cohort
                        if r not in all_genuine
                        and r["mcap_true"]
                        and MIDCAP_LO <= r["mcap_true"] <= MIDCAP_HI]
    dropped_mcap_only = [r for r in all_genuine
                         if not (r["mcap_true"]
                                 and MIDCAP_LO <= r["mcap_true"] <= MIDCAP_HI)]
    print("\n[D] STRICTEST — all-GENUINE + TRUE midcap")
    print(summarize(clean, "Clean cohort"))
    print(summarize(dropped_earnings, "  (dropped: fails earnings only)"))
    print(summarize(dropped_mcap_only,
                    "  (dropped: earnings OK but mcap off)"))

    # Direct comparison table to answer "what if we drop earnings rule"
    print("\n" + "=" * 78)
    print("ANSWER: what if we DROP earnings-proximity rule?")
    print("=" * 78)
    print(
        "Under different mcap definitions, here's what cohort you get "
        "WITHOUT the earnings gate:\n"
    )
    print(f"  {'definition':<35s} {'n':<5s}{'HR':<10s}{'avg_ret':<12s}{'alpha':<12s}")
    print("  " + "-" * 74)

    rows_for_table = [
        ("Ratio-mcap (loose, today)",   cohort),
        ("TRUE-mcap only",              true_midcap),
        ("Drop earnings + ratio-mcap",  cohort),  # same as row 1 — no earnings gate
        ("Drop earnings + TRUE-mcap",   true_midcap),  # same as row 2
    ]
    # Cleaner: just report the 2 unique rows
    # Keep earnings gate versions too
    print(summarize(cohort, "Loose mcap, NO earnings"))
    print(summarize(all_genuine, "Loose mcap,  earnings gate"))
    print(summarize(true_midcap, "TRUE  mcap, NO earnings"))
    print(summarize(clean, "TRUE  mcap,  earnings gate"))

    print("\nKey question: does dropping earnings help or hurt?")
    fails_earnings = has_filtered
    print(summarize(fails_earnings, "Just the 'fails-earnings' set"))
    print("  (these are the rows you ADD when dropping the earnings rule)")


if __name__ == "__main__":
    asyncio.run(main())
