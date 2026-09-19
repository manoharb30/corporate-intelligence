"""Research notes for KRMN and TH — the 2026-09-18 signals.

Both reviewed 2026-09-19. Verdict blocklist_candidate on both: RECOMMENDED for
removal, NOT yet acted on. The signal rows are still live and the CIKs are not
in EXCLUDED_CIKS at the time this is written.

Notes are anchored on Company, so they surface on the signal detail page and in
get_notes_for_ciks() if either name is ever evaluated again.

Default = DRY-RUN. Pass --commit to write.
"""

import argparse
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from app.db.neo4j_client import Neo4jClient
from app.services.research_note_service import ResearchNoteService, validate_note

KRMN_THESIS = (
    "Signal 2026-09-18, 3 insiders, $1,036,485. RECOMMENDED DROP. Two separate "
    "objections — one structural, one substantive. The substantive one is bigger and I "
    "found it second."
    "\n\n"
    "=== 1. THE CLUSTER IS A SOLO BUY IN A THREE-INSIDER COSTUME ==="
    "\n"
    "Stinnett David (director) $1,007,648 = 97.2% of the cluster. Petryszyn Mary D "
    "(director) $18,720 = 1.8%. Twitty Stephen (director) $10,117 = 1.0%. Remove the two "
    "token buys and ONE buyer remains, so the cluster fails MIN_CLUSTER_INSIDERS "
    "outright — it cleared the gate on $28,837 of tokens. Identical ratio to LUCK "
    "(2026-09-16), whose token was 1.8% of the lead buy. All three bought 2026-09-16, "
    "the SAME DAY the company furnished an investor presentation (8-K item 7.01, "
    "accession 0001193125-26-392480) — one information event, not three independent "
    "judgments."
    "\n"
    "VOCABULARY GAP: this is the TOKEN-BUY variant of dependent buying. The "
    "control_block_buyers flag added for BWMX covers shared identity (family, vehicle, "
    "sponsor), not size asymmetry, so this note carries NO flag despite being the second "
    "instance of the pattern in four days. A token_buy_cluster flag is warranted."
    "\n\n"
    "=== 2. THE -70% IS A PE SPONSOR EXITING INTO A LIVE SHELF ==="
    "\n"
    "This is the part that would make me cautious even if all three directors had bought "
    "$1M each. Karman IPO'd Feb 2025; there have been THREE distributions in 18 months: "
    "IPO (424B4 2025-02-13), secondary (S-1 + 424B7 2025-07-24), and a 14,000,000-share "
    "secondary on 2026-05-28 (424B7 0001193125-26-248889) plus a 2,100,000-share "
    "underwriters' option, priced off $63.52. The prospectus states plainly: 'We are not "
    "selling any shares of common stock under this prospectus supplement and will not "
    "receive any proceeds from the sale of shares by the selling stockholders.' It also "
    "describes 'senior principals of Trive Capital, OUR FORMER CONTROLLING STOCKHOLDER, "
    "and certain other original stockholders... whose shares represent in the aggregate "
    "approximately 11% of the Company's outstanding stock' as bound by a MODIFIED "
    "lock-up. An S-3ASR automatic shelf was filed the same day, so further supply can "
    "arrive with no new registration and no warning. "
    "Price path: $118.38 high -> $63.52 at the May secondary -> $35.75 now. It fell "
    "another 44% AFTER that deal. That is a supply overhang, and no amount of backlog "
    "fixes it inside a 90-day window."
    "\n\n"
    "=== 3. HALF THE GROWTH IS BOUGHT, AND DEBT-FUNDED ==="
    "\n"
    "Q2 revenue +58.2% headline but +24.4% ORGANIC — roughly 34 points are acquisitions "
    "(Walker Precision Engineering, ~$94M, agreed in Q2). Debt went $483.7M -> $587.3M -> "
    "$867.0M -> $875.3M across four quarters, +81%. D/E 208%, the second highest in the "
    "peer set after ATRO 178%. The 2026-08-28 8-K is a SIXTH AMENDMENT to a credit "
    "agreement dated only 2025-04-01 — six amendments in 17 months — adding 'Sixth "
    "Amendment Incremental Term Lenders'."
    "\n\n"
    "=== 4. EBITDA IS NOT CONVERTING TO CASH ==="
    "\n"
    "TTM EBITDA $153.9M but OPERATING cash flow only $5.9M, and FCF -$57.2M. Cash $51.7M "
    "against $875.3M of debt. A levered roll-up that does not convert is a different "
    "animal from the one the press release describes."
    "\n\n"
    "=== WHAT IS GENUINELY GOOD — this is the hardest drop so far ==="
    "\n"
    "Q2 2026 (released 2026-08-06) was records across the board: revenue $182M, net "
    "income $14.0M (+106.1%), adjusted EBITDA $54.6M (+54.7%), RECORD BACKLOG $1.3B UP "
    "65% vs FY2025 end, quarterly bookings ~$500M including a large multi-year space and "
    "launch contract. Guidance was RAISED to $730-745M revenue and $215-222.5M adjusted "
    "EBITDA. CEO Jon Rambeau: 'The demand environment continues to strengthen, with more "
    "than $90 billion in recent prime contractor awards for THAAD and PAC-3 interceptors "
    "and over $76 billion for new Columbia and Virginia class submarines.' On RAISED FY26 "
    "guidance EV/EBITDA is ~25x — in line with peers (CW 25.7, MOG-A 20.0, ATRO 21.3, DCO "
    "21.9, HEI 30.3, HWM 34.3), NOT the 36x the trailing figure implies. A director "
    "putting $1M in at a 70% discount is a real fact."
    "\n\n"
    "=== CHECKED AND CLEARED ==="
    "\n"
    "MCAP BOUNDARY RECHECK (near the $5B ceiling, so verified per feedback_mcap_boundary_"
    "recheck): 132.5M shares x $35.75 = $4.738B, matching the stored value. IN BAND with "
    "~5% headroom. Earnings gate: real pass_within_60d on all three transactions, not a "
    "fail-open; next earnings 2026-11-06, inside the window. Buys are genuinely "
    "open-market — Stinnett's footnote shows a weighted average over $36.99-$37.52. NOT a "
    "control block: no family link or shared vehicle in any footnote. NOT new-appointee "
    "qualifying buys: the only recent Form 3 (2026-09-15) is incoming CFO Chris Boynton, "
    "who started 2026-09-14 and did not buy."
    "\n\n"
    "=== OTHER FLAGS ==="
    "\n"
    "Still not cheap after -70%: P/B 11.25, EV/Rev 9.43, forward P/E 37.3. Short interest "
    "11.5% vs defense peers 1.4-5.9%. Institutions reported at 104.7% of shares, a float "
    "artifact typical of heavy recent distribution. Board's recent history is "
    "DISTRIBUTION not accumulation: five Form 144s (proposed sales) filed Nov 2025, and "
    "14 Form 4s on a single day in May 2026 around the secondary. Cluster value $1.04M "
    "sits just inside the journal-L1 $1-5M dead zone."
    "\n\n"
    "NET: the buyer structure is the RULE objection; the sponsor overhang plus "
    "debt-funded growth that does not convert to cash is the SUBSTANTIVE one. You would "
    "be buying against a shelf that can print stock any day."
)

TH_THESIS = (
    "Signal 2026-09-18, 2 insiders, $375,158. RECOMMENDED DROP — on entry price, not on "
    "buyer quality."
    "\n\n"
    "=== BUYERS ARE CLEAN ==="
    "\n"
    "Unlike KRMN and LUCK there is no independence problem here. Archer James Bradley "
    "(Director, CEO and President) $250,166 on 09-15 at $18.69; Schrenk Troy C. (Chief "
    "Commercial Officer) $124,992 on 09-18 at $21.16. Both meaningful, both operators, "
    "no token buy. Earnings gate: real pass_within_60d on both."
    "\n\n"
    "=== THE PROBLEM: IT ALREADY RAN, AND IT RAN INSIDE THE CLUSTER WINDOW ==="
    "\n"
    "Look at the two prices: $18.69 on 09-15 and $21.16 on 09-18 — the stock rose 13.2% "
    "in THREE DAYS between the CEO's buy and the CCO's. The second buy is chasing the "
    "first. Zoom out and it is worse: 52-week range $5.97 to $21.415, currently $21.19 — "
    "up ~255% in a year and sitting -1% off its 52-week HIGH. This is "
    "lesson_post_run_clusters in textbook form: if the stock has already run far above "
    "the insiders' prices when the cluster completes, risk/reward is bad. Here it ran "
    "WITHIN the window. Against a cohort where 62% of signals form in the bottom quintile "
    "of their 52-week range (research_52w_range_filter_rejected), this forms at the top."
    "\n\n"
    "=== VALUATION IS EXTREME, ON A LOSS-MAKING BUSINESS ==="
    "\n"
    "EV/EBITDA 48.3 against peers CVEO 6.4, WLFC 8.9, MYRG 14.7, ACA 15.0 — three to "
    "seven times the entire peer set. EV/Rev 6.2 vs peers 0.81-4.71. P/B 5.74. And the "
    "operating margin is NEGATIVE at -8.8%, where CVEO 2.8%, MYRG 6.2%, ACA 12.3% and "
    "WLFC 37.7% are all positive. ROE -9.8%. Cash $6.1M with a current ratio of 0.646. "
    "FCF -$44.1M despite operating cash flow of +$170.1M — capex is consuming everything."
    "\n\n"
    "=== THE CALL WAS GOOD, WHICH IS WHY IT RAN ==="
    "\n"
    "Q2 2026 (released 2026-08-10): revenue +39% to $85.5M; 'Since January 2026, secured "
    "over $1.4 billion of multi-year contract awards across diversified, high-growth "
    "strategic Workforce Hospitality Solutions end markets'; and it 'Raises Full-Year 2026 "
    "Revenue and Adjusted EBITDA Outlook by 11% and 13%, Respectively'. But the same "
    "release reports a NET LOSS of $9.0 million for the quarter, and management flags "
    "'certain transitional costs related to ongoing network optimization initiatives in "
    "the Government segment over the balance of 2026, which are expected to temporarily "
    "impact segment operating margins'. Next earnings would fall inside the window."
    "\n\n"
    "=== DATA NOTE ==="
    "\n"
    "Company.market_cap stored $1.837B vs ~$2.075B actual (97.9M shares x $21.19) — stale "
    "by ~13%, the FOURTH stale-mcap instance this week after LUCK -38%, DFH -20% and LMB "
    "-43%. Both values are inside the $300M-$5B band so no gate decision changed."
    "\n\n"
    "NET: good operators buying a good quarter, at 48x EV/EBITDA on negative operating "
    "margins, at the 52-week high, after a 255% run — with the second buyer chasing the "
    "first by 13% in three days. The insider signal is real; the entry price is not."
)

NOTES = [
    ("0002040127", {
        "note_date": "2026-09-19",
        "ticker": "KRMN",
        "thesis": KRMN_THESIS,
        "verdict": "blocklist_candidate",
        # No flag fits. control_block_buyers covers shared IDENTITY (family, vehicle,
        # sponsor); this is size ASYMMETRY — one real buyer plus tokens. Second
        # instance in four days after LUCK. A token_buy_cluster flag is warranted;
        # not inventing one inside a note-writing script.
        "risk_flags": [],
        "catalysts": [
            "S-3ASR automatic shelf filed 2026-05-28 — further sponsor supply can arrive with no new registration and no warning",
            "Q3 earnings 2026-11-06 — inside the window; watch organic vs acquired growth and whether operating cash flow converts",
            "Seventh credit agreement amendment / further incremental term debt",
            "Walker Precision Engineering (~$94M) integration",
        ],
        "sources": [
            "424B7 2026-05-28 accession 0001193125-26-248889 — 14,000,000-share selling-stockholder secondary, Trive 'former controlling stockholder', modified lock-up on ~11%",
            "S-3ASR 2026-05-28 accession 0001193125-26-245212 — automatic shelf",
            "8-K 2026-08-06 accession 0002040127-26-000018 — Q2 results, record backlog, raised guidance",
            "8-K 2026-08-28 accession 0001193125-26-374378 — Sixth Amendment to Credit Agreement, incremental term lenders",
            "8-K 2026-09-16 accession 0001193125-26-392480 — investor presentation, same day as all three buys",
            "8-K 2026-08-27 accession 0001193125-26-369561 — CFO change (Chris Boynton)",
            "EDGAR Form 4s 0001193125-26-395095/395097/395098 and Form 3 0001193125-26-392160",
            "yfinance 2026-09-19 — 10-name aerospace/defense peer comps and mcap recheck",
        ],
        "mcap_at_note": 4_738_080_256.0,
    }),
    ("0001712189", {
        "note_date": "2026-09-19",
        "ticker": "TH",
        "thesis": TH_THESIS,
        "verdict": "blocklist_candidate",
        "risk_flags": ["post_run"],
        "catalysts": [
            "Post-run entry: -1% off the 52w high after +255% in a year; the CCO bought 13.2% above the CEO three days earlier",
            "Q3 earnings — inside the window; watch whether the Government-segment transitional costs keep margins negative",
            "$1.4B of multi-year contract awards secured since January 2026 converting to profit, or not",
            "Liquidity: cash $6.1M, current ratio 0.646, FCF -$44.1M",
        ],
        "sources": [
            "8-K 2026-08-10 accession 0001104659-26-093011 — Q2 results, $1.4B awards, guidance raised 11%/13%, net loss $9.0M, Government transitional costs",
            "10-Q 2026-08-10 accession 0001104659-26-093264 (period 2026-06-30)",
            "LookInsight graph — 2 GENUINE P transactions, earnings_outcome pass_within_60d on both",
            "yfinance 2026-09-19 — workforce-housing peer comps (CVEO, WLFC, ACA, MYRG)",
        ],
        "mcap_at_note": 2_075_000_000.0,
    }),
]


async def main(commit: bool):
    for cik, note in NOTES:
        validate_note(note)
    print(f"Both validate. KRMN {len(KRMN_THESIS):,} chars, TH {len(TH_THESIS):,} chars.")

    await Neo4jClient.connect()
    for cik, note in NOTES:
        existing = await ResearchNoteService.get_notes(cik)
        sig = await Neo4jClient.execute_query(
            "MATCH (sp:SignalPerformance) WHERE sp.ticker = $t "
            "RETURN sp.signal_id AS sid, sp.is_mature AS mature",
            {"t": note["ticker"]})
        print(f"\n{note['ticker']} (cik {cik}) — existing notes {len(existing)}, "
              f"signal rows {len(sig)} (STILL LIVE — not removed by this script)")
        print(f"    verdict={note['verdict']} flags={note['risk_flags']} "
              f"catalysts={len(note['catalysts'])} sources={len(note['sources'])}")
        if commit:
            n = await ResearchNoteService.record_note(cik, note)
            print(f"    WROTE {n}")

    if not commit:
        print("\nDRY-RUN: nothing written. Use --commit.")
        return

    print("\nRead-back:")
    for cik, note in NOTES:
        for r in await ResearchNoteService.get_notes(cik):
            print(f"  {note['ticker']:<5} {r['note_date']}  {r['verdict']:<20} "
                  f"{len(r['thesis']):>6,} chars  flags={r['risk_flags']}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--commit", action="store_true", help="write the notes (default: dry-run)")
    asyncio.run(main(ap.parse_args().commit))
