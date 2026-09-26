"""Per-arrival review of the two 2026-09-24 signals: NYAX dropped, HHH kept.

Both reviewed together, opposite outcomes, so both notes are written by one
script — the contrast is the useful record.

NYAX — removed and blocklisted. HHH — KEPT, not blocklisted, stays in the open
list. Writing a note for a KEPT signal matters as much as for a dropped one:
without it the reasoning for keeping is invisible, and six months from now
nobody can tell whether HHH was examined or merely not noticed.

Notes are written BEFORE the NYAX row is deleted, and the deletion refuses to
run unless the note reads back.

Default = DRY-RUN. Pass --commit to write and delete.
"""

import argparse
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from app.db.neo4j_client import Neo4jClient
from app.services.research_note_service import ResearchNoteService, validate_note

NYAX_CIK = "0001901279"
NYAX_SIGNAL = "CLUSTER-0001901279-2026-09-24"
HHH_CIK = "0001981792"

NYAX_THESIS = (
    "Signal 2026-09-24, 2 insiders, $4,709,187 — the LARGEST cluster the book has "
    "produced. DROPPED on per-arrival review."
    "\n\n"
    "=== BUYER STRUCTURE — a flag, not the disqualifier ==="
    "\n"
    "Nechmad (CEO, Co-Founder AND Chairman) bought $4,607,723 in a single day on 09-24 — "
    "97.8% of the cluster. Ben-Avi (CTO, Co-Founder) contributed $101,465. That trips the "
    "token_buy_cluster >=90% guideline, BUT Ben-Avi bought across four separate days "
    "(09-17, 09-22, 09-23, 09-24), which reads as deliberate accumulation rather than a "
    "one-off gesture like LUCK's $3,268 or KRMN's two tokens. So the flag is recorded and "
    "it is NOT the reason for the drop."
    "\n"
    "Related: insiders already hold 58.9%, so this is a founder adding to majority "
    "control — the BWMX shape, though without the family dimension."
    "\n\n"
    "=== THE DISQUALIFIER: MARGINS COLLAPSING WHILE THE MULTIPLE STAYS HIGH ==="
    "\n"
    "Operating income by quarter: +$10M, +$8M, +$12M, +$4M, **-$7M**. Net income went "
    "+$12M to -$10M year over year. Revenue GREW 28.2% into that — so it is growing and "
    "losing money at the same time, and the trend is one-directional."
    "\n"
    "Against 6 payments peers it is the ONLY negative-operating-margin name (-5.4% vs PAY "
    "9.0%, EVTC 19.4%, TOST 7.4%, WEX 26.9%, GPN 16.1%) and simultaneously the MOST "
    "expensive on EV/EBITDA by a wide margin (51.0 vs TOST 32.9, PAY 32.6, EVTC 10.3, GPN "
    "9.3, WEX 6.1). Free cash flow -$37.0M on operating cash flow of +$28.4M. D/E 146%. "
    "Trailing P/E 203."
    "\n"
    "$4.71M also sits in the journal-L1 $1-5M cluster dead zone."
    "\n\n"
    "=== CHECKED AND CLEARED — this is judgment, not eligibility ==="
    "\n"
    "Market cap rechecked: 37.4M shares x $44.75 = $1.673B, comfortably in the $300M-$5B "
    "band. Earnings gate recorded a real pass_within_60d (next earnings 2026-11-19, inside "
    "the window), not a fail-open. And although Nayax is an ISRAELI FOREIGN PRIVATE ISSUER "
    "filing 20-F and 6-K, its XBRL carries 150 USD facts against 1 EUR — it reports in USD, "
    "so there is no BWMX/AXIA3 currency trap and the $42-44 Form 4 prices are genuine."
    "\n"
    "The earnings gate split the buying programme again: Ben-Avi's 09-17 buy recorded "
    "reject_beyond_60d while everything from 09-22 passed — the MBC pattern."
    "\n\n"
    "NET: a founder committing $4.6M of his own money after a 42% drawdown (52-week range "
    "$39.17-$76.86) is a real fact. A negative-margin business at 51x EV/EBITDA with "
    "operating income deteriorating every quarter is not what this cohort is built on."
)

HHH_THESIS = (
    "Signal 2026-09-24, 2 insiders, $1,667,428. **KEPT** — reviewed alongside NYAX on "
    "2026-09-26 and deliberately NOT dropped. Recording why a signal was kept, because "
    "otherwise there is no way to tell later whether it was examined or merely unnoticed."
    "\n\n"
    "=== THE INSIDER FACT IS THE STRONGEST SINCE BECKWITT ==="
    "\n"
    "Marc Grandisson — former CEO of Arch Capital, now Executive Chairman of Vantage, the "
    "insurance business HHH acquired (8-K 2026-06-05, items 1.01/2.01/3.02/3.03) — bought "
    "$1,602,938 on 09-23. Andrew Davis (COO) added $64,490. A newly installed senior "
    "operator putting $1.6M of personal capital into the vehicle he has just joined is a "
    "high-quality signal."
    "\n\n"
    "=== WHY THE USUAL OBJECTIONS DO NOT LAND HERE ==="
    "\n"
    "Buyer concentration: Grandisson is 96.1% of the cluster, which trips the "
    "token_buy_cluster >=90% guideline — but Davis at 4.0% of the lead buy is DOUBLE the "
    "~2% floor, so this is borderline rather than the clear-cut case LUCK (1.8%) or KRMN "
    "(1.0%) presented. Flagged for visibility, not treated as disqualifying."
    "\n"
    "Eligibility is clean throughout: mcap rechecked at $3.857B (59.7M shares x $64.58), "
    "in band; earnings gate a real pass_within_60d with next earnings 2026-11-10, inside "
    "the window; Delaware domestic filer on 10-K/10-Q, so no foreign-issuer or currency "
    "complications."
    "\n"
    "Valuation is the cheapest in its peer set: EV/EBITDA 8.25 against JOE 19.6, TRC 88.0, "
    "FPH 671; P/B 0.96, BELOW book; operating margin 28.4%."
    "\n\n"
    "=== THE REAL CONCERN, STATED HONESTLY ==="
    "\n"
    "This is a COMPARABILITY problem, not evidence the business is bad. Ackman is "
    "converting HHH into a diversified holding company, and the financials are "
    "mid-transformation: revenue '+330%' is the Vantage acquisition consolidating rather "
    "than growth, quarterly revenue swings $236M -> $1,122M, and trailing P/E 12.6 sits "
    "against forward P/E 63.3 — the market expects earnings to fall roughly four-fifths. "
    "FCF -$1,134M, debt $5.46B, D/E 135%, short interest 11.3%. Cluster value $1.67M is in "
    "the journal-L1 $1-5M dead zone."
    "\n"
    "The 202-signal cohort was built on midcap OPERATING businesses where insiders know "
    "their own book is cheap. A restructuring vehicle is a different animal, and the "
    "standard tools evaluate it poorly."
    "\n\n"
    "DECISION (Manohar, 2026-09-26): keep. The objection amounts to low confidence in the "
    "analysis rather than a disqualifier — unlike LUCK (negative book equity), BWMX "
    "(controlling family), EU (below the mcap floor) or NYAX (negative margins at 51x "
    "EV/EBITDA). CIK is deliberately NOT added to EXCLUDED_CIKS."
    "\n"
    "Watch: Q3 earnings 2026-11-10, inside the window — whether Vantage earnings are "
    "recognisable and whether the forward multiple compresses toward the trailing one. "
    "Note the stock rose 5.96% on 09-25, the day after the buys, so any later judgement of "
    "this decision should account for the entry level moving away quickly."
)

NOTES = [
    (NYAX_CIK, {
        "note_date": "2026-09-26", "ticker": "NYAX", "thesis": NYAX_THESIS,
        "verdict": "blocklist_candidate",
        "risk_flags": ["token_buy_cluster"],
        "catalysts": [
            "Acted on 2026-09-26: CIK 0001901279 added to EXCLUDED_CIKS and the signal row removed",
            "Operating income trend +$10M/+$8M/+$12M/+$4M/-$7M — the deterioration is the thesis",
            "Q3 earnings 2026-11-19 would have been inside the window",
        ],
        "sources": [
            "LookInsight graph — 5 InsiderTransaction rows 2026-09-17..24; earnings_outcome split reject_beyond_60d / pass_within_60d",
            "SEC XBRL companyfacts CIK0001901279 — 150 USD facts vs 1 EUR, establishing USD reporting despite 20-F filer status",
            "EDGAR submissions CIK0001901279 — 20-F/6-K foreign private issuer, incorporated Israel",
            "yfinance 2026-09-25 — valuation and 6-name payments peer comps; mcap recheck 37.4M sh x $44.75",
        ],
        "mcap_at_note": 1_673_000_000.0,
    }),
    (HHH_CIK, {
        "note_date": "2026-09-26", "ticker": "HHH", "thesis": HHH_THESIS,
        "verdict": "watch",
        "risk_flags": ["token_buy_cluster"],
        "catalysts": [
            "Q3 earnings 2026-11-10 — inside the window; watch whether Vantage earnings are recognisable and the forward multiple compresses toward trailing",
            "Vantage insurance integration (acquired per 8-K 2026-06-05) — the source of the +330% revenue optic",
            "Ackman-led conversion into a diversified holding company — changes what the name even is",
            "Stock +5.96% on 2026-09-25, the day after the buys — the entry level moved away quickly",
        ],
        "sources": [
            "LookInsight graph — 2 GENUINE P transactions 2026-09-23, earnings_outcome pass_within_60d on both",
            "EDGAR submissions CIK0001981792 — Delaware domestic filer, 10-K/10-Q; 8-K 2026-06-05 items 1.01/2.01/3.02/3.03 (Vantage)",
            "yfinance 2026-09-25 — valuation and 6-name developer peer comps; mcap recheck 59.7M sh x $64.58",
        ],
        "mcap_at_note": 3_857_000_000.0,
    }),
]


async def main(commit: bool):
    for _, n in NOTES:
        validate_note(n)
    print(f"Both notes validate. NYAX {len(NYAX_THESIS):,} chars (drop), "
          f"HHH {len(HHH_THESIS):,} chars (KEEP).")

    await Neo4jClient.connect()

    pre = await Neo4jClient.execute_query("""
        MATCH (sp:SignalPerformance) WHERE sp.conviction_tier='strong_buy'
        RETURN sum(CASE WHEN sp.is_mature THEN 1 ELSE 0 END) AS mature,
               sum(CASE WHEN NOT sp.is_mature THEN 1 ELSE 0 END) AS immature
    """)
    print(f"\nBEFORE: mature={pre[0]['mature']}  immature={pre[0]['immature']}")

    row = await Neo4jClient.execute_query("""
        MATCH (sp:SignalPerformance {signal_id: $sid})
        RETURN sp.ticker AS t, sp.is_mature AS mature, sp.total_value AS v
    """, {"sid": NYAX_SIGNAL})
    if not row:
        print(f"NYAX: no row {NYAX_SIGNAL} — nothing to remove.")
    else:
        print(f"NYAX target: {NYAX_SIGNAL}  mature={row[0]['mature']}  "
              f"value=${row[0]['v']:,.0f}")
        if row[0]["mature"]:
            print("  ABORT: is_mature=true — frozen cohort, refusing to delete.")
            sys.exit(1)

    if not commit:
        print("\nDRY-RUN: nothing written. HHH would be noted and KEPT; "
              "NYAX noted then removed. Use --commit.")
        return

    for cik, n in NOTES:
        w = await ResearchNoteService.record_note(cik, n)
        print(f"  note WROTE {w} for {n['ticker']} ({n['verdict']})")

    check = await Neo4jClient.execute_query(
        "MATCH (c:Company {cik:$cik})-[:HAS_RESEARCH_NOTE]->(rn:ResearchNote) RETURN count(rn) AS n",
        {"cik": NYAX_CIK})
    if not check or not check[0]["n"]:
        print("ABORT: NYAX note not readable back — refusing to delete the row.")
        sys.exit(1)

    if row:
        d = await Neo4jClient.execute_query("""
            MATCH (sp:SignalPerformance {signal_id: $sid}) DETACH DELETE sp RETURN count(*) AS d
        """, {"sid": NYAX_SIGNAL})
        print(f"  NYAX SignalPerformance deleted: {d[0]['d']}")

    post = await Neo4jClient.execute_query("""
        MATCH (sp:SignalPerformance) WHERE sp.conviction_tier='strong_buy'
        RETURN sum(CASE WHEN sp.is_mature THEN 1 ELSE 0 END) AS mature,
               sum(CASE WHEN NOT sp.is_mature THEN 1 ELSE 0 END) AS immature
    """)
    print(f"\nAFTER: mature={post[0]['mature']}  immature={post[0]['immature']}")
    if post[0]["mature"] != pre[0]["mature"]:
        print("WARNING: mature count changed — expected unchanged. Investigate.")
        sys.exit(1)

    remaining = await Neo4jClient.execute_query("""
        MATCH (sp:SignalPerformance)
        WHERE sp.conviction_tier='strong_buy' AND NOT sp.is_mature
        RETURN sp.ticker AS t ORDER BY t
    """)
    tickers = [r["t"] for r in remaining]
    print(f"Open book now: {tickers}")
    if "HHH" not in tickers:
        print("WARNING: HHH should still be in the open list. Investigate.")
        sys.exit(1)
    print("HHH confirmed still in the open list, as intended.")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--commit", action="store_true", help="write notes + remove NYAX (default: dry-run)")
    asyncio.run(main(ap.parse_args().commit))
