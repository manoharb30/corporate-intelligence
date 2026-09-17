"""Record Signal Watch promises for the three open signals that have none.

DFH, LMB and MCFT all have an earnings call INSIDE their 90-day window, and no
Promise nodes. Sourced from each company's most recent earnings release on
EDGAR (not from transcripts, which are not available to us) — so every `quote`
below is verbatim 8-K/press-release text and every `target` is a number the
company itself published.

    DFH  signal 2026-09-14  call 2026-07-30 (Q2)     next print 2026-10-29  day-90 2026-12-13
    LMB  signal 2026-09-16  call 2026-08-04 (Q2)     next print 2026-11-04  day-90 2026-12-15
    MCFT signal 2026-09-16  call 2026-09-10 (FY26)   next print 2026-11-04  day-90 2026-12-15

signal_date is the cluster WINDOW END, not the first buy date — LMB's buys start
2026-09-11 but its signal_date is 2026-09-16.

Promises start verdict='pending'; score_promise() resolves them on print day.
MERGE is keyed on metric, so re-running updates evidence in place and never
stacks duplicates or overwrites a verdict already scored.

Additive only — touches no signal row.

Default = DRY-RUN. Pass --commit to write.
"""

import argparse
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from app.db.neo4j_client import Neo4jClient
from app.services.signal_watch_service import SignalWatchService

DFH_8K = "https://www.sec.gov/Archives/edgar/data/1825088/000162828026050841/dfh-q22026xer.htm"
LMB_8K = "https://www.sec.gov/Archives/edgar/data/1606163/000162828026052611/a20260630ex991pr.htm"
MCFT_8K = "https://www.sec.gov/Archives/edgar/data/1638290/000119312526387237/mcft-ex99_1.htm"

PLAN = [
    ("DFH", "2026-09-14", [
        {
            "metric": "FY26 home closings",
            "target": "~9,250 closings for full year 2026 (reiterated)",
            "quote": "We reiterate our 2026 full-year guidance of approximately 9,250 home closings.",
            "source_call_date": "2026-07-30",
            "source_url": DFH_8K,
            "break_condition": "Guidance cut below ~9,250, or withdrawn",
        },
        {
            "metric": "cost structure / affordability",
            "target": "Cost structure improves; ASP declines offset by closing volume",
            "quote": ("The home building market continues to be challenging, but our teams have worked "
                      "hard to identify opportunities to improve our cost structure with the goal of "
                      "delivering more affordable homes to our customers. We believe costs will need to "
                      "continue to trend down, perhaps significantly, to have a meaningful impact on "
                      "market-wide housing results."),
            "source_call_date": "2026-07-30",
            "source_url": DFH_8K,
            "break_condition": "Gross margin falls further from Q2's 14.2% without a cost offset",
        },
        {
            "metric": "inventory marks",
            "target": "No community inventory impairment (none taken through 2026-06-30)",
            "quote": ("No such impairment charges were recorded for the three and six months ended "
                      "June 30, 2026 and 2025. [10-Q, period 2026-06-30]"),
            "source_call_date": "2026-07-30",
            "source_url": DFH_8K,
            "break_condition": ("FIRST inventory impairment taken — breaks the tangible-book support "
                                "the thesis rests on. This is the single most important line to watch."),
        },
        {
            "metric": "liquidity / revolver",
            "target": "Total liquidity $605M; revolver drawn $999M as of 2026-06-30",
            "quote": ("Total liquidity of $605 million as of June 30, 2026, comprised of cash and cash "
                      "equivalents and availability under the revolving credit facility"),
            "source_call_date": "2026-07-30",
            "source_url": DFH_8K,
            "break_condition": "Liquidity falls below ~$450M or revolver draw exceeds ~$1.1B",
        },
    ]),
    ("LMB", "2026-09-16", [
        {
            "metric": "FY26 revenue guidance",
            "target": "$760M - $790M (raised from $730M - $760M at Q1)",
            "quote": ("Increases Full Year 2026 Revenue Guidance to $760 million to $790 million and "
                      "Revises Adjusted EBITDA Guidance to $78 million to $84 million"),
            "source_call_date": "2026-08-04",
            "source_url": LMB_8K,
            "break_condition": "Revenue guidance cut back below $760M",
        },
        {
            "metric": "FY26 adjusted EBITDA guidance",
            "target": "$78M - $84M (CUT from $90M - $94M at Q1, ~-12%)",
            "quote": ("Reaffirms Full Year 2026 Revenue Guidance of $730 million to $760 million and "
                      "Adjusted EBITDA of $90 million to $94 million [Q1, 2026-05-05] -> Revises "
                      "Adjusted EBITDA Guidance to $78 million to $84 million [Q2, 2026-08-04]"),
            "source_call_date": "2026-08-04",
            "source_url": LMB_8K,
            "break_condition": "SECOND consecutive EBITDA guidance cut — would make Q2 a trend, not an event",
        },
        {
            "metric": "Pioneer Power gross margin",
            "target": "Gross margins improve as 2026 progresses; to company average over 2-3 years",
            "quote": ("Pioneer Power continues to perform in line with the Company's integration "
                      "expectations and management expects gross margins to improve as 2026 progresses. "
                      "Operational and pricing improvement initiatives are underway to enhance "
                      "profitability at Pioneer Power with the goal of bringing gross margins in line "
                      "with the Company average over the next two to three years."),
            "source_call_date": "2026-08-04",
            "source_url": LMB_8K,
            "break_condition": ("Total gross margin falls below Q2's 21.5%. NOTE: the full fix is a "
                                "2-3 year project by management's own words — well outside this window. "
                                "Only DIRECTION is scoreable here, not arrival."),
        },
        {
            "metric": "bookings / book-to-bill",
            "target": "Bookings $182.0M at 1.1x book-to-bill; demand healthy",
            "quote": ("bookings remained strong at $182.0 million, producing a 1.1x book-to-bill ratio, "
                      "and reinforcing our confidence that customer demand remains healthy"),
            "source_call_date": "2026-08-04",
            "source_url": LMB_8K,
            "break_condition": ("Book-to-bill drops below 1.0x — would contradict management's claim "
                                "that the miss was timing/pricing rather than demand"),
        },
        {
            "metric": "organic revenue",
            "target": "ODR organic revenue was -3.4% in Q2; growth is acquisition-driven",
            "quote": ("Acquisition-related revenue increased 21.3%, or $23.2 million, partially offset "
                      "by a 3.4%, or $3.7 million decrease in organic revenue."),
            "source_call_date": "2026-08-04",
            "source_url": LMB_8K,
            "break_condition": "ODR organic revenue declines further — the core keeps shrinking under the M&A",
        },
    ]),
    ("MCFT", "2026-09-16", [
        {
            "metric": "Q1 transition net sales",
            "target": "~$147M for Jul-Sep 2026",
            "quote": ("For the first quarter of the Transition Period, consolidated net sales are "
                      "expected to be approximately $147 million, with Adjusted EBITDA of approximately "
                      "$16 million, and Adjusted Earnings per share of approximately $0.40."),
            "source_call_date": "2026-09-10",
            "source_url": MCFT_8K,
            "break_condition": "Net sales materially below ~$147M",
        },
        {
            "metric": "Q1 transition adjusted EBITDA",
            "target": "~$16M for Jul-Sep 2026",
            "quote": ("consolidated net sales are expected to be approximately $147 million, with "
                      "Adjusted EBITDA of approximately $16 million"),
            "source_call_date": "2026-09-10",
            "source_url": MCFT_8K,
            "break_condition": "Adjusted EBITDA below ~$16M — the first test of post-merger earnings power",
        },
        {
            "metric": "transition period guidance",
            "target": "Jul-Dec 2026: net sales $287-291M, Adj EBITDA $29-32M, Adj EPS $0.66-0.76, capex ~$9M",
            "quote": ("For the six-month Transition Period we expect consolidated net sales to be "
                      "between $287 million and $291 million, with Adjusted EBITDA between $29 million "
                      "and $32 million, and Adjusted Earnings per share between $0.66 and $0.76. We "
                      "expect capital expenditures to be approximately $9 million for the Transition period."),
            "source_call_date": "2026-09-10",
            "source_url": MCFT_8K,
            "break_condition": "Transition-period guidance cut at the Q1 print",
        },
        {
            "metric": "margin durability",
            "target": "Adjusted EBITDA margin 13.1% in FY26, up from 8.6%; claimed execution-driven",
            "quote": ("Adjusted EBITDA margin was 13.1% for fiscal 2026, up from 8.6% for the "
                      "prior-year period... What gives me confidence is that these results were earned, "
                      "not market-driven."),
            "source_call_date": "2026-09-10",
            "source_url": MCFT_8K,
            "break_condition": ("Adjusted EBITDA margin falls back toward single digits — would make "
                                "'earned, not market-driven' the wrong read"),
        },
        {
            "metric": "Chaparral/Robalo integration",
            "target": "Merger closed 2026-05-15; new Recreation and Sport Fishing segment performing",
            "quote": ("We grew net sales, expanded Adjusted EBITDA nearly 80%, and completed the "
                      "transformational combination with Chaparral and Robalo."),
            "source_call_date": "2026-09-10",
            "source_url": MCFT_8K,
            "break_condition": ("Integration charges, dealer-network conflict, or segment losses. 10-K "
                                "concedes 'limited prior operating experience' in sterndrive and "
                                "saltwater fishing, and excluded Marine Products from FY26 ICFR assessment."),
        },
    ]),
]


async def main(commit: bool):
    await Neo4jClient.connect()

    total = 0
    for ticker, signal_date, promises in PLAN:
        rows = await Neo4jClient.execute_query("""
            MATCH (sp:SignalPerformance)
            WHERE sp.ticker = $ticker AND substring(sp.signal_date, 0, 10) = $signal_date
            OPTIONAL MATCH (sp)-[:HAS_PROMISE]->(pr:Promise)
            RETURN sp.signal_id AS sid, sp.is_mature AS mature, count(pr) AS existing
        """, {"ticker": ticker, "signal_date": signal_date})
        if not rows:
            print(f"ABORT: no SignalPerformance for {ticker} {signal_date}")
            sys.exit(1)
        r = rows[0]
        print(f"\n{ticker} {signal_date}  sid={r['sid']}  mature={r['mature']}  "
              f"existing promises={r['existing']}  -> recording {len(promises)}")
        for p in promises:
            print(f"    - {p['metric']:<32} {str(p['target'])[:70]}")
        total += len(promises)

        if commit:
            n = await SignalWatchService.record_promises(ticker, signal_date, promises)
            print(f"    WROTE {n} Promise nodes")

    if not commit:
        print(f"\nDRY-RUN: nothing written. {total} promises would be recorded. Use --commit.")
        return

    check = await Neo4jClient.execute_query("""
        MATCH (sp:SignalPerformance)-[:HAS_PROMISE]->(pr:Promise)
        WHERE sp.is_mature = false
        RETURN sp.ticker AS tkr, count(pr) AS n, collect(DISTINCT pr.verdict) AS verdicts
        ORDER BY tkr
    """)
    print("\nOpen-signal promise ledger after write:")
    for row in check:
        print(f"  {row['tkr']:<6} {row['n']:>2} promises  verdicts={row['verdicts']}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--commit", action="store_true", help="write promises (default: dry-run)")
    asyncio.run(main(ap.parse_args().commit))
