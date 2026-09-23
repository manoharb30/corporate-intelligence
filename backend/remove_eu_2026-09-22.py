"""Record the EU research note, then remove the ineligible EU signal.

enCore Energy (EU, CIK 0001500881) signalled 2026-09-22 and should never have
formed. This is an ELIGIBILITY failure, not a per-arrival judgment call:
Company.market_cap was stale at $380.6M while true mcap is $235.1M (194.3M
shares x $1.21) — 22% BELOW the $300M floor. At the actual buy prices it was
$157M-$206M.

Same failure and remedy as REI (2026-06-18), which also passed the midcap gate
only on a stale yfinance figure.

Order matters: the note is written BEFORE the row is deleted, so the reasoning
does not disappear with it. That is the failure that left LUCK undocumented for
three days, and the removal step here refuses to run without a note present.

Default = DRY-RUN. Pass --commit to write and delete.
"""

import argparse
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from app.db.neo4j_client import Neo4jClient
from app.services.research_note_service import ResearchNoteService, validate_note

CIK = "0001500881"
SIGNAL_ID = "CLUSTER-0001500881-2026-09-22"

THESIS = (
    "Signal 2026-09-22, 2 insiders, $111,850. REMOVED on ELIGIBILITY — this signal should "
    "never have formed. Not a judgment call like LUCK, BWMX, KRMN or TH."
    "\n\n"
    "=== THE DISQUALIFIER: STALE MARKET CAP ==="
    "\n"
    "Company.market_cap was stored at $380.6M. True mcap is $235.1M — 194.3M shares "
    "outstanding x $1.21 — which is 22% BELOW the $300M midcap floor. At the prices the "
    "insiders actually paid it was further below still: $157M at $0.81, $169M at $0.87, "
    "$206M at $1.06. It was never close to eligible at any point in the cluster window. "
    "The midcap gate was applied to a number that was 62% too high."
    "\n"
    "IDENTICAL to REI (CIK 0001384195, removed 2026-06-18): 'true mcap ~$233-284M is below "
    "the $300M midcap floor; it only passed on a stale 2026-04-22 yfinance mcap.' Same "
    "mechanism, nearly the same numbers, same remedy. See feedback_mcap_boundary_recheck."
    "\n"
    "This is the FIFTH stale-mcap instance in September 2026 (LUCK stored $1.216B vs $749M "
    "actual; DFH $1.346B vs $1.122B; LMB $1.109B vs $631M; TH $1.837B vs $2.075B) and the "
    "FIRST where staleness manufactured a signal rather than merely looking wrong. The "
    "other four stayed inside the band either way."
    "\n\n"
    "=== EVERYTHING ELSE POINTED THE SAME WAY ==="
    "\n"
    "Had it been eligible it would still have failed review. Sub-$1 stock throughout the "
    "cluster ($0.81-$1.06), against a 52-week range of $0.77-$4.18 — roughly 71% off the "
    "high. EBITDA -$78.9M and free cash flow -$89.4M on $55.2M of revenue, a -112.8% net "
    "margin. Debt $113.7M against $74.0M cash, so at that burn a raise looks close to "
    "inevitable — journal-L5 territory. Insiders hold only 1.91%. And 47.2M shares traded "
    "on 2026-09-14 against a ~2-3M norm, price $1.10 -> $0.93, with NOTHING in EDGAR "
    "explaining it: no 8-K, no offering. Whatever moved it is not in the filings."
    "\n"
    "Portfolio note: EU is a uranium name and UUUU is already held. Even if eligible, that "
    "is a correlated second bet on one commodity."
    "\n\n"
    "=== BUYER STRUCTURE (recorded, moot given eligibility) ==="
    "\n"
    "Sheriff (Executive Chairman) contributed $101,250 of the $111,850 cluster — 90.5%, "
    "which trips the token_buy_cluster >=90% guideline — against Little (CEO) at $10,600. "
    "Little at 9.5% of the lead sits well above the 2% floor, so it is borderline rather "
    "than clear-cut, and it is not the reason for removal."
    "\n\n"
    "=== EARNINGS GATE SPLIT THE SAME BUYING PROGRAMME ==="
    "\n"
    "Sheriff's 2026-09-14 and 09-15 buys recorded reject_beyond_60d and were FILTERED; his "
    "09-18 buys recorded pass_within_60d and became the signal. One continuous programme "
    "split by the 60-day line — the MBC pattern again (research_mbc_2026-09-03). The "
    "cluster records $111,850 where the family of buys totals $262,100."
)

NOTE = {
    "note_date": "2026-09-22",
    "ticker": "EU",
    "thesis": THESIS,
    "verdict": "blocklist_candidate",
    "risk_flags": ["below_mcap_floor"],
    "catalysts": [
        "Acted on 2026-09-22: CIK 0001500881 added to EXCLUDED_CIKS and the signal row removed",
        "Root cause is Company.market_cap staleness, not this company — five instances in September, this the first to manufacture a signal",
        "Burn rate: EBITDA -$78.9M and FCF -$89.4M against $74.0M cash implies a capital raise",
    ],
    "sources": [
        "yfinance 2026-09-22 — 194.3M shares x $1.21 = $235.1M vs $380.6M stored; daily closes 2026-09-08..22",
        "LookInsight graph — 6 InsiderTransaction rows 2026-09-14..21, earnings_outcome split reject_beyond_60d / pass_within_60d",
        "EDGAR submissions CIK0001500881 — no 8-K or offering explaining the 2026-09-14 volume spike",
        "Precedent: REI (CIK 0001384195) removed 2026-06-18 on the same stale-mcap failure",
    ],
    "mcap_at_note": 235_100_000.0,
}


async def main(commit: bool):
    validate_note(NOTE)
    print(f"Note validates. {len(THESIS):,} chars, flags={NOTE['risk_flags']}")

    await Neo4jClient.connect()

    rows = await Neo4jClient.execute_query("""
        MATCH (sp:SignalPerformance {signal_id: $sid})
        RETURN sp.ticker AS ticker, sp.company_name AS name, sp.is_mature AS mature,
               sp.num_insiders AS n, sp.total_value AS v, sp.market_cap AS mcap
    """, {"sid": SIGNAL_ID})
    if not rows:
        print(f"No SignalPerformance {SIGNAL_ID} — nothing to remove.")
        return
    s = rows[0]
    print(f"\nTarget: {SIGNAL_ID}")
    print(f"  {s['ticker']} ({s['name']})  mature={s['mature']}  insiders={s['n']}  "
          f"value=${s['v']:,.0f}")
    print(f"  stored mcap ${s['mcap']:,.0f}  vs true ${NOTE['mcap_at_note']:,.0f}  "
          f"-> {'BELOW' if NOTE['mcap_at_note'] < 300e6 else 'within'} the $300M floor")
    if s["mature"]:
        print("  ABORT: is_mature=true — frozen cohort, refusing to delete.")
        sys.exit(1)

    pre = await Neo4jClient.execute_query("""
        MATCH (sp:SignalPerformance) WHERE sp.conviction_tier='strong_buy'
        RETURN sum(CASE WHEN sp.is_mature THEN 1 ELSE 0 END) AS mature,
               sum(CASE WHEN NOT sp.is_mature THEN 1 ELSE 0 END) AS immature
    """)
    print(f"\nBEFORE: mature={pre[0]['mature']}  immature={pre[0]['immature']}")

    if not commit:
        print("\nDRY-RUN: nothing written. Use --commit.")
        return

    n = await ResearchNoteService.record_note(CIK, NOTE)
    print(f"\nResearchNote WROTE {n}")

    # Guard: never delete a signal row unless its reasoning is already recorded.
    check = await Neo4jClient.execute_query("""
        MATCH (c:Company {cik: $cik})-[:HAS_RESEARCH_NOTE]->(rn:ResearchNote)
        RETURN count(rn) AS n
    """, {"cik": CIK})
    if not check or not check[0]["n"]:
        print("ABORT: note not readable back — refusing to delete the row.")
        sys.exit(1)

    d = await Neo4jClient.execute_query("""
        MATCH (sp:SignalPerformance {signal_id: $sid}) DETACH DELETE sp RETURN count(*) AS d
    """, {"sid": SIGNAL_ID})
    print(f"SignalPerformance deleted: {d[0]['d']}")

    post = await Neo4jClient.execute_query("""
        MATCH (sp:SignalPerformance) WHERE sp.conviction_tier='strong_buy'
        RETURN sum(CASE WHEN sp.is_mature THEN 1 ELSE 0 END) AS mature,
               sum(CASE WHEN NOT sp.is_mature THEN 1 ELSE 0 END) AS immature
    """)
    print(f"AFTER:  mature={post[0]['mature']}  immature={post[0]['immature']}")
    if post[0]["mature"] != pre[0]["mature"]:
        print("WARNING: mature count changed — expected unchanged. Investigate.")
        sys.exit(1)
    if post[0]["immature"] != pre[0]["immature"] - 1:
        print("WARNING: immature did not drop by exactly 1. Investigate.")
        sys.exit(1)

    remaining = await Neo4jClient.execute_query("""
        MATCH (sp:SignalPerformance)
        WHERE sp.conviction_tier='strong_buy' AND NOT sp.is_mature
        RETURN sp.ticker AS t ORDER BY t
    """)
    print(f"OK. Open book now: {[r['t'] for r in remaining]}")
    print("\nSignal List is served from a 15-min snapshot cache — restart the backend "
          "(which the blocklist deploy does anyway) to clear it immediately.")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--commit", action="store_true", help="write note + delete (default: dry-run)")
    asyncio.run(main(ap.parse_args().commit))
