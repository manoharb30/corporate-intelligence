"""Record the DFH research note from the 2026-09-16 per-arrival review.

DFH (Dream Finders Homes, CIK 0001825088) signalled 2026-09-14 — one of the two
names that ended the 64-day drought. LUCK, the other, was dropped and
blocklisted the same day. DFH is KEPT; this note is the durable record of why,
and of the specific risks that came out of reading the Q2 2026 10-Q and the
FY2025 10-K.

Verdict 'watch' = signal kept, thesis carries named risks with a dated
resolution point (Q3 earnings 2026-10-29, inside the 90-day window which ends
2026-12-13).

Additive only — record_note MERGEs a ResearchNote onto the Company and touches
nothing else. Per research_note_service: "A note is an opinion with a date on
it, not a gate — nothing here filters a signal."

Idempotent: MERGE is keyed on note_date, so re-running updates in place.

Default = DRY-RUN (validates, prints, writes nothing). Pass --commit to write.
"""
import argparse
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from app.db.neo4j_client import Neo4jClient
from app.services.research_note_service import ResearchNoteService, validate_note

CIK = "0001825088"

THESIS = (
    "Signal 2026-09-14, 2 insiders, $140,905 recorded. KEPT on per-arrival review. "
    "\n\n"
    "INSIDER CASE (the reason to keep). Richard Beckwitt, director and former "
    "co-CEO/president of Lennar, has bought ~$1.39M across four purchases since "
    "2026-08-11, averaging DOWN from $13.95 to $12.07: $976,500 (08-11), $110,640 "
    "(08-12), $177,600 (08-13), $120,700 (09-10). Only the last is in the signal — "
    "the three August buys were rejected by the earnings filter, so the recorded "
    "$140,905 understates real insider commitment by ~10x. Len Sturm added $20,205 "
    "(09-03) plus $22,110 filtered in August. Beckwitt's biggest buy came 08-11, "
    "twelve days AFTER the Q2 10-Q (filed 07-30) made the margin compression public "
    "— he bought knowing the numbers."
    "\n\n"
    "OPERATIONS — demand is growing, price is being cut (Q2'26 vs Q2'25). Net sales "
    "(orders) 2,232 vs 1,938, +15%. Cancellation rate 11.1% vs 14.0%, improving. "
    "Active communities 353 vs 271, +30%. Closings 2,290 vs 2,232, +3%. But ASP "
    "$438,171 vs $481,027, -9%; homebuilding gross margin 14.2% vs 16.5%, -2.3pp. "
    "H1 is the same shape harder: orders +17%, cancels 9.3% vs 12.8%, ASP -10%, "
    "gross margin 14.3% vs 17.8% (-3.5pp). Backlog 2,319 units vs 2,513 (-8%), "
    "value $1,154M vs $1,201M (-4%). Read: a deliberate downturn share-grab — cut "
    "price ~10%, expand communities 30%, take share — the Lennar playbook Beckwitt "
    "ran himself. Falling revenue is ASP, not demand."
    "\n\n"
    "HOW IT IS FUNDED — liquidity draining. Total liquidity $605M (06-30) vs $899M "
    "(12-31), -33% in six months. Revolver drawn $999M vs $798M (+$201M); "
    "availability $401M vs $665M. Cash $203M. Operating cash flow -$151.1M in H1'26 "
    "(vs -$113.2M H1'25), with -$299.9M into inventory. Net homebuilding debt to net "
    "capitalization 46.5% vs 41.8% at year-end. Debt $1,817M: revolver $999M, 8.25% "
    "notes due Aug 2028 $297M, 6.875% notes due Sep 2030 $295M, warehouse $187M. NO "
    "near-term maturity wall; company states covenant compliance and expects to "
    "remain compliant 12 months. ~2 years of runway at current burn. Also $148.5M "
    "redeemable preferred in mezzanine ahead of common, taking $13.5M/yr."
    "\n\n"
    "VALUATION — cheaper on headline than in fact. P/E 8.7, P/B 0.78, EV/Rev 0.71. "
    "But goodwill is $377M of $1,432M equity (26%), so tangible book is ~$1,055M and "
    "the stock trades at ~1.06x TANGIBLE book, not 0.78x. In line with peers, not "
    "cheap. Against 12 homebuilders DFH is the extreme on every risk axis: lowest "
    "operating margin (2.4% vs GRBK 19.5%, DHI 13.0%, LEN 5.3%), highest debt/equity "
    "(112.7 vs LGIH 74.3, KBH 52.6, rest under 40), highest short interest (45.9% of "
    "float vs LGIH 21.3, KBH 20.6), most beaten down (-59% off 52w high vs LEN -43%)."
    "\n\n"
    "THE BEAR CASE IS SPECIFIC: ZERO write-downs taken. 10-Q states verbatim 'No such "
    "impairment charges were recorded for the three and six months ended June 30, "
    "2026 and 2025' on community inventory, while real estate inventory grew to "
    "$2,328M (from $1,853M at 25-03, +26% in 15 months) and gross margin fell 3.5pp. "
    "Only $3.0M of lot-deposit/abandonment charges in H1 (SG&A, not COGS). Book value "
    "has absorbed no cycle marks at all — that is what the 45.9% short float is "
    "betting on. Goodwill last tested 2025-10-01, fair value exceeded carrying value "
    "at every reporting unit, no impairment 2023/24/25; next test 2026-10-01 but it "
    "surfaces in the FY26 10-K (Feb 2027), OUTSIDE this signal's 90-day window."
    "\n\n"
    "KEY-MAN / GOVERNANCE FLAG (new, from the 10-K). Patrick Zalupski is described as "
    "'heavily involved in the origination, underwriting and structuring of all land "
    "investment activities' — he IS the land underwriting function — and controls the "
    "company via Class B (57.7M shares vs 37.4M Class A); the 10-K states any "
    "acquisition 'would have to' be approved by him. Same document: 'In September "
    "2025, Mr. Zalupski further expanded his leadership in professional sports by "
    "becoming the Majority Owner, Managing Partner, and Co-Chair of the Tampa Bay "
    "Rays... as well as the Principal Owner of the Tampa Bay Rowdies.' The 10-K frames "
    "this as marketing upside. Read the other way: the controlling founder who "
    "personally underwrites every land deal took on an MLB franchise twelve months "
    "before margins compressed 3.5pp and liquidity fell a third. Not causation — but "
    "it belongs on the record. Geographic concentration in Florida and Texas is "
    "explicit, with hurricane/climate risk named as a specific adverse factor."
    "\n\n"
    "NET: a leveraged bet on a cycle turn, made by a director who knows this cycle "
    "professionally. Not the clean compounder 8.7x P/E implies, nor the collapsing "
    "business a 46% short float implies. Resolution point is Q3 earnings 2026-10-29, "
    "inside the window — watch ASP, gross margin, and whether the revolver draw keeps "
    "climbing."
    "\n\n"
    "DATA LIMITATIONS. Graph holds only 8 DFH transactions, all code P, all since "
    "2026-08-11 — no prior insider history, and the pipeline carries only P "
    "transactions, so we CANNOT say whether insiders are selling. Company.market_cap "
    "is stored at $1.346B vs ~$1.122B actual (yfinance, 2026-09-16); still inside the "
    "$300M-$5B band so no gate decision changed. No RISK_FLAGS value fits leverage or "
    "liquidity drain — the closed vocabulary has no entry for either, which is why "
    "this note carries none despite the balance-sheet concerns above."
)

NOTE = {
    "note_date": "2026-09-16",
    "ticker": "DFH",
    "thesis": THESIS,
    "verdict": "watch",
    # None of the nine closed-vocabulary flags apply: not hostile_activist, not
    # recent_dilution (share count is SHRINKING — treasury doubled to 4.2M), in
    # the mcap band, two real buyers so not solo_buyer, near 52w low so not
    # post_run, no auditor/going-concern language (covenant compliant), no
    # reverse split, not a shell. Leverage/liquidity has no flag in the vocab.
    "risk_flags": [],
    "catalysts": [
        "Q3 2026 earnings 2026-10-29 — inside the 90-day window (ends 2026-12-13); watch ASP, gross margin, revolver draw",
        "First inventory impairment, if taken, breaks the tangible-book support",
        "Goodwill retest 2026-10-01 — result not public until FY26 10-K (Feb 2027), outside the window",
        "Rate cuts — the cycle turn the share-grab is underwriting",
    ],
    "sources": [
        "10-Q Q2 2026 filed 2026-07-30 (period 2026-06-30), accession 0001628280-26-050969",
        "10-K FY2025 filed 2026-02-24 (period 2025-12-31), accession 0001628280-26-010837",
        "SEC XBRL companyfacts CIK0001825088 — inventory, impairment, goodwill, equity series",
        "yfinance 2026-09-16 — valuation, 12-name homebuilder peer comps",
        "LookInsight graph — 8 InsiderTransaction rows, 2026-08-11 to 2026-09-10",
    ],
    "mcap_at_note": 1_121_700_000.0,
}


async def main(commit: bool):
    validate_note(NOTE)
    print("Note validates against research_note_service schema.")
    print(f"  cik        {CIK}")
    print(f"  note_date  {NOTE['note_date']}")
    print(f"  ticker     {NOTE['ticker']}")
    print(f"  verdict    {NOTE['verdict']}")
    print(f"  risk_flags {NOTE['risk_flags']}")
    print(f"  catalysts  {len(NOTE['catalysts'])}")
    print(f"  sources    {len(NOTE['sources'])}")
    print(f"  mcap       ${NOTE['mcap_at_note']:,.0f}")
    print(f"  thesis     {len(NOTE['thesis']):,} chars")

    await Neo4jClient.connect()

    existing = await ResearchNoteService.get_notes(CIK)
    print(f"\nExisting notes on {CIK}: {len(existing)}")
    for n in existing:
        print(f"  {n['note_date']}  {n['verdict']}  {(n['thesis'] or '')[:70]}...")

    sig = await Neo4jClient.execute_query("""
        MATCH (sp:SignalPerformance) WHERE sp.ticker = 'DFH'
        RETURN sp.signal_id AS sid, substring(toString(sp.signal_date),0,10) AS sd,
               sp.conviction_tier AS tier, sp.is_mature AS mature
    """)
    print(f"\nDFH signal rows (kept, NOT modified by this script): {len(sig)}")
    for s in sig:
        print(f"  {s['sid']}  {s['sd']}  {s['tier']}  mature={s['mature']}")

    if not commit:
        print("\nDRY-RUN: nothing written. Re-run with --commit to record the note.")
        return

    print("\n=== COMMIT ===")
    n = await ResearchNoteService.record_note(CIK, NOTE)
    print(f"  ResearchNote MERGEd: {n}")

    after = await ResearchNoteService.get_notes(CIK)
    print(f"  Notes on {CIK} now: {len(after)}")
    match = [x for x in after if x["note_date"] == NOTE["note_date"]]
    if not match:
        print("  WARNING: note not readable back. Investigate.")
        sys.exit(1)
    print(f"  Read-back OK: {match[0]['note_date']} / {match[0]['verdict']} / "
          f"{len(match[0]['thesis']):,} chars / {len(match[0]['catalysts'])} catalysts")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--commit", action="store_true", help="write the note (default: dry-run)")
    asyncio.run(main(ap.parse_args().commit))
