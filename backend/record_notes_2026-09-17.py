"""Research notes for LMB and MCFT, plus a correction to the DFH note.

LMB and MCFT signalled 2026-09-16 (surfaced by the 2026-09-16 backfill) and both
were KEPT on per-arrival review. Neither has LUCK's disqualifying shape — both
clusters have two meaningful buyers, no token buy.

The DFH entry re-MERGEs note_date 2026-09-16 to correct one material fact I had
wrong: Beckwitt is not a long-standing director. He JOINED THE BOARD in Q2 2026,
announced in the 2026-07-30 call, and bought ~$1.39M within weeks. MERGE is keyed
on note_date, so this updates that note in place rather than stacking a second one.

Default = DRY-RUN. Pass --commit to write.
"""

import argparse
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from app.db.neo4j_client import Neo4jClient
from app.services.research_note_service import ResearchNoteService, validate_note

LMB_THESIS = (
    "Signal 2026-09-16, 2 insiders, $159,949. KEPT on per-arrival review. "
    "\n\n"
    "INSIDER CASE. Two directors, both meaningful — no token buy. Gaboury $99,619 "
    "(09-14); Horowitz $49,590 (09-11) then ADDED $10,739 (09-15). Horowitz buying "
    "twice inside five days is the tell. Both bought after the 2026-09-09 8-K "
    "(items 1.01/1.02/2.03, credit agreement) and five weeks after the Q2 print that "
    "cut the stock in half."
    "\n\n"
    "WHAT BROKE. The 2026-08-04 Q2 release RAISED revenue guidance to $760-790M while "
    "CUTTING Adjusted EBITDA guidance to $78-84M, from $90-94M reaffirmed at Q1 on "
    "2026-05-05 — roughly -12%. Revenue up, profit down. The stock is -54% from its "
    "$114.95 high, at $52.56."
    "\n\n"
    "THE MARGIN PROBLEM IS STRUCTURAL, NOT A BLIP. Q2 revenue +21.9% to $173.5M, but "
    "ODR acquisition revenue contributed +$23.2M while ODR ORGANIC revenue fell 3.4% "
    "(-$3.7M). Total gross margin 21.5% vs 28.0% — down 650bp. ODR 24.0% vs 29.0%; "
    "GCR 14.5% vs 24.7%. Cause is the lower margin profile of the Pioneer Power "
    "acquisition, plus lower net project write-ups and skilled-labour competition in "
    "data-centre markets. Adjusted EBITDA -22.3% to $13.9M; net income -38.8% to $4.7M. "
    "Management's own timeline for fixing it: gross margins to company average 'over "
    "the next two to three years' — far outside this signal's 90-day window. "
    "All the growth is bought; the core is shrinking underneath it. Acquisition cadence "
    "is fast: Pioneer Power, then CYMCOR closed 2026-08-04, revolver raised $100M -> "
    "$125M in July, another credit agreement 8-K on 2026-09-09."
    "\n\n"
    "WHY IT STILL HOLDS UP. LMB is the CHEAPEST name in a high-quality peer group on "
    "EV/EBITDA at 11.3x, against FIX 27.1, IESC 22.9, APG 17.5, EME 16.2, MTZ 16.0, "
    "MYRG 14.5. Free cash flow is +$38.2M — a 6.0% yield on a $631M market cap — with "
    "operating cash flow $52.4M. Leverage is modest: debt $59.6M against $203.1M "
    "equity, D/E 29% versus MTZ 90% and APG 109%. ROE 16.2%. Bookings $182.0M at 1.1x "
    "book-to-bill. Equity has compounded $170.5M -> $203.1M over four quarters. Forward "
    "P/E 11.2 against trailing 20.1. Analyst target $77.20 on 5 estimates."
    "\n\n"
    "NET. A real cash-generating business that got re-rated from compounder to low-margin "
    "roll-up, with two directors buying the de-rating. The bet is that Pioneer Power "
    "margins normalise; management has scoped that at 2-3 years, so within 90 days only "
    "DIRECTION is testable, not arrival. Watch gross margin against Q2's 21.5%, "
    "book-to-bill against 1.1x, and whether ODR organic revenue stops shrinking. "
    "Next print 2026-11-04, inside the window; promises recorded."
    "\n\n"
    "DATA NOTE. Company.market_cap is stored at $1.109B vs ~$631M actual (-43%, implying "
    "a price near $93 from months ago) — still inside the $300M-$5B band, so no gate "
    "decision changed. Third instance of the stale-mcap issue. No RISK_FLAGS value fits "
    "'acquisition-driven margin dilution', so this note carries none."
)

MCFT_THESIS = (
    "Signal 2026-09-16, 2 insiders, $123,761. KEPT on per-arrival review. "
    "\n\n"
    "INSIDER CASE. Brad Nelson, CHIEF EXECUTIVE OFFICER, bought $46,800 + $1,945 "
    "(09-15); Roch Lambert, director, $75,016 (09-15). Both meaningful. They bought "
    "FOUR/FIVE DAYS AFTER the 2026-09-10 FY2026 release in which the company published "
    "explicit forward guidance — buying into their own numbers with the numbers public. "
    "Verified directly against EDGAR: all 10 Form 4s filed 2026-09-16 contain exactly 3 "
    "open-market P transactions from 2 buyers totalling $123,761. Pipeline capture is "
    "exact; nothing was missed."
    "\n\n"
    "THE SCREEN DATA IS WRONG ON THIS NAME — READ THIS BEFORE THE MULTIPLES. yfinance "
    "shows EV/EBITDA 18.7, the MOST expensive in the boat peer group (MBUU 8.2, THO 8.0, "
    "LCII 7.0, PATK 8.9). That is an artifact. On 2026-05-15 MCFT completed a merger with "
    "Marine Products Corporation — $284.2M, each MPX share converting to 0.232 MCFT "
    "shares plus $2.43 cash — acquiring the Chaparral and Robalo brands and creating a "
    "Recreation and Sport Fishing segment. TTM figures therefore contain only ~6 weeks of "
    "Marine Products. Management reported FY26 ADJUSTED EBITDA of $45.6M, up $21.2M "
    "(~+87%), margin 13.1% vs 8.6%. On that, EV/EBITDA is ~9.3x. Annualising the guided "
    "transition period (~$60M) puts it near ~6.8x — the CHEAP end of the peer set. "
    "A naive screen read rejects this name for the opposite of the true reason."
    "\n\n"
    "SHARE COUNT +50% IS MERGER CONSIDERATION, NOT A RAISE. 16.3M -> 24.4M shares and "
    "equity $189.1M -> $381.1M in one quarter, both from the MPX stock consideration. "
    "This is NOT the journal-L5 dilution pattern (offering/ATM/placement signalling "
    "weakness) and should not be flagged as such; it also predates the signal by four "
    "months. The -$7M quarterly net loss is transaction costs and inventory step-up."
    "\n\n"
    "THE DIFFERENTIATOR: ZERO TOTAL DEBT and $43.9M cash after a $284M acquisition, in a "
    "sector where peers carry D/E of BC 136%, PATK 146%, HZO 115% and ONEW 305%. Insiders "
    "hold 24.4%. P/B 1.23, forward P/E 9.3. Analyst target $26.80 on 5 estimates."
    "\n\n"
    "WHAT MANAGEMENT COMMITTED TO (2026-09-10). Fiscal year-end moves June 30 -> "
    "December 31, so a six-month transition report covers Jul-Dec 2026. Guidance: "
    "transition-period net sales $287-291M, Adjusted EBITDA $29-32M, Adjusted EPS "
    "$0.66-0.76, capex ~$9M; and for Q1 of that period (Jul-Sep) net sales ~$147M, "
    "Adjusted EBITDA ~$16M, Adjusted EPS ~$0.40. Nelson: 'these results were earned, not "
    "market-driven.' Three hard numbers with a date on them — the cleanest promise set in "
    "the ledger. Next print 2026-11-04, inside the window."
    "\n\n"
    "AGAINST IT. The marine sector is in a genuine downturn — peers are 25-53% off highs "
    "and most have declining revenue (HZO -7.0%, LCII -12.5%, WGO -9.9%, THO -3.9%). Free "
    "cash flow is -$19.5M. The 10-K concedes 'limited prior operating experience' in "
    "sterndrive and saltwater fishing, flags a coastal dealer network that 'overlaps in "
    "part' with the existing one, and excluded Marine Products from FY26 internal-control "
    "assessment under the SEC's one-year post-acquisition accommodation. Integration is "
    "the risk, and it is unproven — MCFT's post-merger earnings power has never printed a "
    "full quarter."
    "\n\n"
    "NET. Trough cycle plus an unproven integration, bought by a CEO days after he "
    "published the numbers he will be judged against, on a debt-free balance sheet in a "
    "levered sector. Mcap $466M sits just under the journal-L2 $500M-1B sweet spot."
)

DFH_AMENDMENT = (
    "CORRECTION recorded 2026-09-17 — Beckwitt's tenure. The 2026-07-30 Q2 release "
    "announcing DFH's results ALSO announced his appointment to the board: 'Rick's "
    "extensive public homebuilding experience is second to none in the industry, having "
    "served as Co-CEO of one of the largest homebuilders, by revenue, in the world.' "
    "He is therefore a NEWLY APPOINTED director who committed ~$1.39M of personal "
    "capital within weeks of joining — materially stronger than the original note's "
    "framing of him as an existing director. Steve Fischer (former public-banking "
    "CFO/CEO) joined at the same time. "
    "\n\n"
    "Also from that call, not in the original note: FY2026 guidance of ~9,250 home "
    "closings was REITERATED; controlled lot pipeline fell to 54,091 from 63,121 at "
    "2025-12-31 (-14%), corroborating the declining lot-deposit trend; return on "
    "participating equity 9.6% vs 25.0%; $15M of buybacks (1,012,621 Class A shares) in "
    "Q2; and backlog ASP ROSE to $497,716 from $465,237 at 2026-03-31. Zalupski: 'We "
    "believe costs will need to continue to trend down, perhaps significantly, to have a "
    "meaningful impact on market-wide housing results.'"
)

NOTES = [
    ("0001606163", {
        "note_date": "2026-09-17",
        "ticker": "LMB",
        "thesis": LMB_THESIS,
        "verdict": "watch",
        "risk_flags": [],
        "catalysts": [
            "Q3 2026 print 2026-11-04 — inside the window (day-90 2026-12-15); watch gross margin vs 21.5%, book-to-bill vs 1.1x, ODR organic revenue",
            "A SECOND consecutive Adjusted EBITDA guidance cut would turn Q2 from an event into a trend",
            "Pioneer Power margin recovery — management scoped it at 2-3 years, so direction only inside this window",
            "Further M&A: CYMCOR closed 2026-08-04, revolver already raised to $125M",
        ],
        "sources": [
            "8-K 2026-08-04 Q2 2026 results, accession 0001628280-26-052611 (EX-99.1 press release)",
            "8-K 2026-05-05 Q1 2026 results, accession 0001628280-26-030701 — source of the $90-94M prior guidance",
            "8-K 2026-09-09 items 1.01/1.02/2.03 credit agreement, accession 0001628280-26-061042",
            "yfinance 2026-09-16 — valuation and 9-name mechanical/building-systems peer comps",
            "LookInsight graph — 3 InsiderTransaction rows, 2026-09-11 to 2026-09-15",
        ],
        "mcap_at_note": 631_000_000.0,
    }),
    ("0001638290", {
        "note_date": "2026-09-17",
        "ticker": "MCFT",
        "thesis": MCFT_THESIS,
        "verdict": "watch",
        "risk_flags": [],
        "catalysts": [
            "Q1 transition print 2026-11-04 — inside the window (day-90 2026-12-15); guided ~$147M net sales, ~$16M Adj EBITDA, ~$0.40 Adj EPS",
            "First full post-merger quarter — MCFT's combined earnings power has never printed",
            "Chaparral/Robalo integration: dealer-network overlap, and Marine Products excluded from FY26 ICFR assessment",
            "Marine cycle turn — the whole peer group is 25-53% off highs",
        ],
        "sources": [
            "8-K 2026-09-10 FY2026 results + transition guidance, accession 0001193125-26-387237 (EX-99.1)",
            "10-K FY2026 filed 2026-09-10 (period 2026-06-30), accession 0001193125-26-387432 — Marine Products Transaction, ICFR exclusion, segment detail",
            "EDGAR direct read of all 10 Form 4s filed 2026-09-16 — 3 P transactions, 2 buyers, $123,761",
            "yfinance 2026-09-16 — valuation and 9-name recreational-boat peer comps",
        ],
        "mcap_at_note": 466_098_976.0,
    }),
]


async def main(commit: bool):
    for cik, note in NOTES:
        validate_note(note)
    print(f"Both notes validate. LMB {len(LMB_THESIS):,} chars, MCFT {len(MCFT_THESIS):,} chars.")

    await Neo4jClient.connect()

    for cik, note in NOTES:
        existing = await ResearchNoteService.get_notes(cik)
        print(f"\n{note['ticker']} (cik {cik}) — existing notes: {len(existing)} -> writing {note['note_date']} / {note['verdict']}")
        for c in note["catalysts"]:
            print(f"    catalyst: {c[:100]}")
        if commit:
            n = await ResearchNoteService.record_note(cik, note)
            print(f"    WROTE {n}")

    # DFH correction — same note_date, so this MERGEs in place.
    dfh = await ResearchNoteService.get_notes("0001825088")
    if not dfh:
        print("\nWARNING: no existing DFH note to amend — skipping correction.")
    else:
        cur = dfh[0]
        if "CORRECTION recorded 2026-09-17" in (cur["thesis"] or ""):
            print("\nDFH: correction already applied — skipping.")
        else:
            amended = dict(cur)
            amended["thesis"] = cur["thesis"] + "\n\n" + DFH_AMENDMENT
            print(f"\nDFH — amending note {cur['note_date']} in place: "
                  f"{len(cur['thesis']):,} -> {len(amended['thesis']):,} chars")
            if commit:
                n = await ResearchNoteService.record_note("0001825088", amended)
                print(f"    WROTE {n}")

    if not commit:
        print("\nDRY-RUN: nothing written. Use --commit.")
        return

    print("\nNotes on the three open signals now:")
    for cik, tkr in [("0001606163", "LMB"), ("0001638290", "MCFT"), ("0001825088", "DFH")]:
        rows = await ResearchNoteService.get_notes(cik)
        for r in rows:
            print(f"  {tkr:<5} {r['note_date']}  {r['verdict']:<8} {len(r['thesis']):>6,} chars  "
                  f"{len(r['catalysts'])} catalysts")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--commit", action="store_true", help="write the notes (default: dry-run)")
    asyncio.run(main(ap.parse_args().commit))
