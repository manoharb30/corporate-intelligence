"""One-off backfill: Signal Watch promises for the 10 open signals.

Source: docs/earnings-call-briefs-2026-07.md (compiled 2026-07-16 from the
last pre-cluster call of each name) + the SMBK Q2 2026 print scored 2026-07-21.

Writes:
- Promise nodes for all 10 open signals (verdict=pending)
- SMBK: 2 SignalEvents (Jun 12 CCO sale, Jul 20 Q2 print) + 7 promises scored
- HNRG: 2 insider follow-on SignalEvents (documented in the briefs)

Idempotent (MERGE throughout) — safe to re-run.
"""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from app.db.neo4j_client import Neo4jClient
from app.services.signal_watch_service import SignalWatchService

PROMISES = {
    # (ticker, signal_date): [promises from last pre-cluster call]
    ("SMBK", "2026-06-10"): [
        {"metric": "Q2 op EPS", "target": ">= ~$0.85", "source_call_date": "2026-04-20",
         "quote": "four-by-four: $4 EPS run-rate ($1/qtr) by Q4 2026",
         "break_condition": "Q2 EPS below ~$0.85 makes the ramp implausible"},
        {"metric": "four-by-four reaffirm", "target": "no walk-back on Jul 21 call",
         "source_call_date": "2026-04-20",
         "quote": "CEO publicly staked the $4 target", "break_condition": "walk-back = thesis break"},
        {"metric": "NIM", "target": "flat Q2 (~3.48%), up slightly H2",
         "source_call_date": "2026-04-20", "quote": "flat Q2, up slightly in back half",
         "break_condition": None},
        {"metric": "deposit costs", "target": "creep limited to a few bps",
         "source_call_date": "2026-04-20",
         "quote": "competition 'a little bit crazier'; new-deposit cost +22bp to 2.82%",
         "break_condition": None},
        {"metric": "loan growth", "target": "~10% annualized", "source_call_date": "2026-04-20",
         "quote": "guided ~10% after 14% annualized Q1", "break_condition": None},
        {"metric": "loan/deposit ratio", "target": "< 90%", "source_call_date": "2026-04-20",
         "quote": None, "break_condition": "drift to 90%+ = funding strain"},
        {"metric": "credit quality", "target": "NPAs ~0.25%, clean",
         "source_call_date": "2026-04-20", "quote": None, "break_condition": None},
        {"metric": "ACL coverage", "target": "97-98bp band", "source_call_date": "2026-04-20",
         "quote": None, "break_condition": None},
    ],
    ("NEWT", "2026-06-15"): [
        {"metric": "FY2026 EPS guide", "target": "$2.35 mid reaffirmed",
         "source_call_date": "2026-04-30", "quote": "reaffirmed 2026 $2.35 mid",
         "break_condition": "trim citing SBA rules = thesis break"},
        {"metric": "FY2027 EPS guide", "target": "$2.60 mid held",
         "source_call_date": "2026-04-30", "quote": "NEW 2027 $2.60 mid, above Street $2.43",
         "break_condition": None},
        {"metric": "SBA 7(a) volume", "target": "Q2 momentum holds (April was +10%)",
         "source_call_date": "2026-04-30", "quote": "Q1 originations +40% YoY, April +10%",
         "break_condition": None},
        {"metric": "gain-on-sale premium", "target": "vs $1.105 baseline",
         "source_call_date": "2026-04-30", "quote": None, "break_condition": None},
        {"metric": "SBA-book credit", "target": "4th consecutive improving quarter",
         "source_call_date": "2026-04-30", "quote": "credit improving 3-4 consecutive quarters",
         "break_condition": None},
        {"metric": "TBV trajectory", "target": "~$13.50 by YE", "source_call_date": "2026-04-30",
         "quote": None, "break_condition": None},
    ],
    ("GSHD", "2026-06-01"): [
        {"metric": "FY organic growth guide", "target": "10-19% reiterated",
         "source_call_date": "2026-04-22", "quote": "FY guide reiterated after +23% rev quarter",
         "break_condition": "guidance trim = thesis break"},
        {"metric": "client retention", "target": "progress 85% -> 86%",
         "source_call_date": "2026-04-22", "quote": None, "break_condition": None},
        {"metric": "Digital Agent rollout", "target": "next state + 2 auto carriers by ~late June",
         "source_call_date": "2026-04-22", "quote": "carriers paying 'outsized compensation'",
         "break_condition": None},
        {"metric": "AI/renewal-book defense", "target": "rebuttal WITH numbers on Jul 23 call",
         "source_call_date": "2026-04-22",
         "quote": "AI question engaged but not quantified in April",
         "break_condition": "vague answer keeps the overhang through our exit"},
    ],
    ("RLI", "2026-06-01"): [
        {"metric": "combined ratio", "target": "< 90 with favorable development",
         "source_call_date": "2026-04-23", "quote": "CR 86 in Q1, favorable PYD $35.5M",
         "break_condition": "adverse casualty development = thesis break"},
        {"metric": "casualty growth", "target": "umbrella/transportation >= ~15%",
         "source_call_date": "2026-04-23", "quote": "umbrella +23%, transportation +27% in Q1",
         "break_condition": None},
        {"metric": "property drag", "target": "E&S shrink deliberate, hurricane commentary benign",
         "source_call_date": "2026-04-23", "quote": "property deliberately shrinking (E&S -16%)",
         "break_condition": None},
        {"metric": "buyback execution", "target": "first buys under the new $250M authorization",
         "source_call_date": "2026-04-23", "quote": "May 14: $2.00 special div + 12.5% hike + $250M buyback",
         "break_condition": None},
    ],
    ("XRAY", "2026-06-15"): [
        {"metric": "FY guide at quarter two", "target": "$3.5-3.6B / $1.40-1.50 affirmed or raised",
         "source_call_date": "2026-05-05",
         "quote": "CEO: 'I like to see at least two [quarters]' before moving it",
         "break_condition": "guidance cut = thesis break"},
        {"metric": "tariff drag", "target": "easing Q2-Q3 as guided", "source_call_date": "2026-05-05",
         "quote": None, "break_condition": None},
        {"metric": "drop-ship inventory burn", "target": "~$30M across Q2-Q4 as pre-announced",
         "source_call_date": "2026-05-05", "quote": None, "break_condition": None},
        {"metric": "cost program", "target": "$120M savings run-rate on track",
         "source_call_date": "2026-05-05", "quote": None, "break_condition": None},
        {"metric": "leverage", "target": "net debt/EBITDA <= 3.3x, permanent CFO progress",
         "source_call_date": "2026-05-05", "quote": None, "break_condition": None},
        {"metric": "implants", "target": "stabilization from -13.5% cc; distributor-driven orders",
         "source_call_date": "2026-05-05", "quote": "called execution, not product",
         "break_condition": None},
    ],
    ("CXT", "2026-06-16"): [
        {"metric": "FY EPS guide", "target": "$4.10-4.40 held", "source_call_date": "2026-05-07",
         "quote": "sales guide RAISED to 15-17% (Antares), EPS held",
         "break_condition": "guide-down on H2 comps = thesis break"},
        {"metric": "backlog coverage", "target": "'90%+ of 2026 sales in backlog' restated",
         "source_call_date": "2026-05-07", "quote": None, "break_condition": None},
        {"metric": "Antares first full quarter", "target": "$60-70M DTT revenue, dilution contained",
         "source_call_date": "2026-05-07", "quote": None, "break_condition": None},
        {"metric": "SAT margin", "target": "~25% by YE", "source_call_date": "2026-05-07",
         "quote": "SAT +51% on currency strength", "break_condition": None},
        {"metric": "deleveraging", "target": "2.9x -> ~2.3x by YE", "source_call_date": "2026-05-07",
         "quote": None, "break_condition": None},
        {"metric": "$10 banknote announcement", "target": "'expected this year'",
         "source_call_date": "2026-05-07", "quote": "revenue uplift materially 2027",
         "break_condition": None},
    ],
    ("MBC", "2026-06-12"): [
        {"metric": "combined-co FY guide", "target": "first guide as combined company (Aug 5)",
         "source_call_date": "2026-05-05", "quote": "AMWD merger closed May 28",
         "break_condition": None},
        {"metric": "synergy capture", "target": "credible year-1 rate toward $90M yr-3",
         "source_call_date": "2026-05-05", "quote": None,
         "break_condition": "upside before Sep depends on synergy narrative, not end markets"},
        {"metric": "tariff offset", "target": "tracking to '100% offset exiting 2026'",
         "source_call_date": "2026-05-05", "quote": "tariffs ~5-6% of sales unmitigated",
         "break_condition": None},
        {"metric": "recovery timing", "target": "'no recovery until 2027' unchanged or earlier",
         "source_call_date": "2026-05-05", "quote": "CEO explicit: no recovery expected until 2027",
         "break_condition": "pushed later + weak H2 decrementals"},
        {"metric": "pro-forma balance sheet", "target": "leverage + share count (dilution math) laid out",
         "source_call_date": "2026-05-05", "quote": None, "break_condition": None},
    ],
    ("INR", "2026-06-12"): [
        {"metric": "FY production growth", "target": "+70% guide held", "source_call_date": "2026-05-13",
         "quote": "Q1 explicitly the LOW quarter, sequential builds to Q4 peak",
         "break_condition": None},
        {"metric": "Q2 sequential build", "target": "delivered; oil pad 'full rate in July' confirmed",
         "source_call_date": "2026-05-13", "quote": "wells pulled into June",
         "break_condition": None},
        {"metric": "leverage", "target": "net debt vs $477M declining from 1.3x",
         "source_call_date": "2026-05-13", "quote": None, "break_condition": None},
        {"metric": "Antero integration", "target": "proof points (3rd-party midstream volumes)",
         "source_call_date": "2026-05-13", "quote": "$1.2B asset deal closed",
         "break_condition": None},
        {"metric": "H2 hedging posture", "target": "stance articulated (oil largely unhedged by design)",
         "source_call_date": "2026-05-13", "quote": None, "break_condition": None},
    ],
    ("HNRG", "2026-06-25"): [
        {"metric": "IURC approval", "target": "petition docketed, hearing date, still '2026'",
         "source_call_date": "2026-05-06",
         "quote": "12-yr >$1B capacity agreement; approval 'anticipated H2 2026'",
         "break_condition": "slip past 2026 guts the swing catalyst"},
        {"metric": "ERAS/FID", "target": "MISO ERAS result ~Sept -> gas turbine FID",
         "source_call_date": "2026-05-06", "quote": "515 MW gas turbine second leg",
         "break_condition": None},
        {"metric": "Merom availability", "target": "clean summer run after planned outage",
         "source_call_date": "2026-05-06", "quote": "Q1 weak by design (planned outage)",
         "break_condition": "second availability miss is the crack"},
        {"metric": "contracted book", "target": "second capacity deal or counterparty reveal; >$2.1B grows",
         "source_call_date": "2026-05-06", "quote": "deal is 'one of several'",
         "break_condition": None},
    ],
    ("UUUU", "2026-07-09"): [
        {"metric": "guidance through shutdown", "target": "held despite planned mill shutdown",
         "source_call_date": "2026-05-07",
         "quote": "planned shutdown late Q2/early Q3 pre-flagged — Aug 7 print may look soft by design",
         "break_condition": None},
        {"metric": "Pinyon Plain ramp", "target": "grades rising H2, costs -> ~$30/lb",
         "source_call_date": "2026-05-07", "quote": None, "break_condition": None},
        {"metric": "VAC deal path", "target": "ASM completion confirmed; antitrust/FIRB on track; OSC loan firming",
         "source_call_date": "2026-05-07", "quote": "$1.9B VAC deal announced Jun 23 (post-call)",
         "break_condition": None},
        {"metric": "dilution containment", "target": "$20.93 preferred trigger addressed; no extra equity raise",
         "source_call_date": "2026-05-07", "quote": None,
         "break_condition": "any hint of an extra equity raise = the crack"},
    ],
}

EVENTS = [
    ("SMBK", "2026-06-10", {
        "event_date": "2026-06-12", "event_type": "insider_followon", "direction": "neutral",
        "headline": "CCO sale, de minimis",
        "detail": "Two days after signal; noted and dismissed in the Jul 16 brief."}),
    ("SMBK", "2026-06-10", {
        "event_date": "2026-07-20", "event_type": "earnings_call", "direction": "confirming",
        "headline": "Q2 print: 7 of 8 promises pass (op EPS $0.96)",
        "detail": ("Op EPS $0.96 vs >=~$0.85 needed (street $0.90, Q1 $0.81). NIM 3.52% (+4bp vs "
                   "'flat' guide). IB deposit costs +2bp. Loan growth 15% ann. ($165M organic). "
                   "L/D 86.9% flat. NPLs 0.25%, ACL 0.97%. TBV +13% ann.; crossed $6B assets. "
                   "Four-by-four reaffirm pending Jul 21 call transcript."),
        "source_url": "https://www.sec.gov/Archives/edgar/data/1038773/000110465926085102/smbk-20260720xex99d1.htm"}),
    ("HNRG", "2026-06-25", {
        "event_date": "2026-07-09", "event_type": "insider_followon", "direction": "confirming",
        "headline": "Director Hudson kept adding: ~$340K across Jun 24 - Jul 9",
        "detail": "Follow-on buying into the retrace below our entry."}),
    ("HNRG", "2026-06-25", {
        "event_date": "2026-07-14", "event_type": "insider_followon", "direction": "confirming",
        "headline": "Barbara Sugg (former Southwest Power Pool CEO) bought $86K",
        "detail": ("A former RTO chief buying ahead of regulatory/interconnection decisions. "
                   "Heavy call-option buying reported same day.")}),
]

# SMBK Q2 scoring (2026-07-21, from the Jul 20 8-K Ex-99.1)
SMBK_SCORES = [
    ("Q2 op EPS", "pass", "$0.96 (street $0.90, Q1 $0.81)"),
    ("four-by-four reaffirm", "pending", "call 2026-07-21 10am ET; transcript pending"),
    ("NIM", "pass", "3.52% vs 3.48% (+4bp, beat 'flat' guide)"),
    ("deposit costs", "pass", "IB deposits 2.62% (+2bp), total 2.15% (+3bp)"),
    ("loan growth", "pass", "15% annualized ($165M organic)"),
    ("loan/deposit ratio", "pass", "86.9%, flat vs 87.0% Q1"),
    ("credit quality", "pass", "NPLs 0.25% (from 0.27%), NPAs/assets 0.23%"),
    ("ACL coverage", "pass", "0.97% flat; NCOs $553K; provision down QoQ"),
]


async def main() -> None:
    await Neo4jClient.connect()
    try:
        for (ticker, signal_date), promises in PROMISES.items():
            n = await SignalWatchService.record_promises(ticker, signal_date, promises)
            print(f"{ticker} {signal_date}: {n} promises")
            if n != len(promises):
                print(f"  WARNING: expected {len(promises)} — check signal match")

        for ticker, signal_date, event in EVENTS:
            r = await SignalWatchService.record_event(ticker, signal_date, event)
            flag = "" if r["stored"] else "  WARNING: signal not matched"
            print(f"{ticker} event day {r['day_index']}: {r['headline']}{flag}")

        for metric, verdict, actual in SMBK_SCORES:
            ok = await SignalWatchService.score_promise("SMBK", "2026-06-10", metric, verdict, actual)
            print(f"SMBK score '{metric}' = {verdict}: {'ok' if ok else 'NO MATCH'}")

        watch = await SignalWatchService.get_watch("SMBK", "2026-06-10")
        print(f"\nVERIFY SMBK: {len(watch['promises'])} promises, {len(watch['events'])} events")
        for p in watch["promises"]:
            print(f"  [{p['verdict']:^7}] {p['metric']}: {p['actual'] or '-'}")
    finally:
        await Neo4jClient.disconnect()


if __name__ == "__main__":
    asyncio.run(main())
