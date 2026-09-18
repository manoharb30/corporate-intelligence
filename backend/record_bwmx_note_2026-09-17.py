"""Record the BWMX research note — first use of the control_block_buyers flag.

BWMX signalled 2026-09-17 and was DROPPED on per-arrival review. The note is the
durable record of why, and the reusable pattern: the 2+ insider gate counts
HEADS, not independent decisions, so one family / fund / control block can
present as a multi-insider cluster.

Note is anchored on Company, so if a BWMX cluster is ever evaluated again this
surfaces via get_notes_for_ciks() during review — which is the point.

Verdict 'blocklist_candidate' (acted on: CIK is in EXCLUDED_CIKS and the signal
row was removed by remove_bwmx_2026-09-17.py).

Default = DRY-RUN. Pass --commit to write.
"""

import argparse
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from app.db.neo4j_client import Neo4jClient
from app.services.research_note_service import ResearchNoteService, validate_note

CIK = "0001788257"

THESIS = (
    "Signal 2026-09-17, 3 insiders, $2,293,811 — the largest cluster value in the open "
    "book. DROPPED on per-arrival review. First exclusion for CONTROL-BLOCK BUYER "
    "CONCENTRATION."
    "\n\n"
    "THE PATTERN THIS NAME ESTABLISHES — read this part first. The 2+ insider gate "
    "counts HEADS, not DECISIONS. It exists to capture several insiders INDEPENDENTLY "
    "concluding the stock is cheap. It cannot see that the buyers are one family, one "
    "fund, or one control block acting together, so a single decision presents as a "
    "multi-insider cluster and clears the gate cleanly. Here the three buyers are: "
    "Luis Campos (director AND 10% owner, $731,646 on 09-15 + $575,456 on 09-16), and "
    "his sons Andres Campos Chevallier (CEO, $492,291 + $247,494) and Santiago Campos "
    "Chevallier (MD Betterware Mexico, $246,924). Same two days. Insiders already held "
    "63.2%. Luis Campos's own Form 4 footnote discloses he 'possesses the voting and "
    "investment power over the ordinary shares held directly by Campalier S.A. de C.V.' "
    "HOW TO SPOT IT NEXT TIME: shared surname or disclosed family relationship; a common "
    "holding vehicle named in the Form 4 footnotes; the same fund/sponsor or "
    "holder-appointed seats; insider ownership already very high. Tagged "
    "control_block_buyers — informational, never automatic. Concentrated family buying "
    "CAN still be a genuine signal; the flag is a prompt to check independence, not a gate."
    "\n\n"
    "WHAT IS NOT WRONG WITH IT — this was not a data-quality exclusion. Unlike AXIA3, "
    "the Form 4 values are genuinely USD: $16.2588 and $16.4416 weighted averages with "
    "footnote ranges $15.7689-$16.4694, verified directly against the EDGAR XML against "
    "a $15.97 market price. Our pipeline captured them exactly. The earnings gate "
    "recorded pass_within_60d on all five transactions — a real pass, not an AIAI-style "
    "fail-open — with next earnings 2026-10-23, inside the window."
    "\n\n"
    "THE BUSINESS IS GOOD, WHICH IS WHY THIS WAS CLOSE. Against 6 direct-selling peers "
    "BWMX is the ONLY one growing (+16.8% vs NUS -17.1%, MED -27.6%, LFVN -23.1%) and "
    "has the best operating margin (16.4% vs peers 3.9-9.8%), on 66.1% gross margin, "
    "with a ~8% dividend yield at 48.7% payout. The family has bought ~$3.3M across 2026 "
    "including earnings-filtered purchases in April and July."
    "\n\n"
    "WHAT DECIDED IT AGAINST. (1) Buyer independence, above. (2) Journal L1 — $2.29M "
    "sits squarely in the $1-5M cluster dead zone. (3) Leverage and cash: D/E 339%, six "
    "times the worst peer (NUS 53%, LFVN 29%, NATR 13%); FCF ~-$89M despite positive "
    "operating cash flow; current ratio 1.11; equity only ~$74M against a ~$620M market "
    "cap. (4) Entry is just -19% off the 52-week high — the LEAST beaten down of any "
    "peer (NUS -69%, USNA -54%, NATR -53%) — where 62% of our signals form in the bottom "
    "quintile of their range."
    "\n\n"
    "CURRENCY TRAP — DO NOT QUOTE SCREEN RATIOS ON THIS NAME. BWMX reports in Mexican "
    "pesos (275 XBRL facts in MXN vs 22 in USD) while price and market cap are USD. Any "
    "ratio mixing the two is unreliable: the 'P/E 6.2' shown on screens is really ~11x "
    "once FY2025 net income of 1,061M MXN is converted to ~$57M. Revenue 14,243M MXN is "
    "~$770M, EBITDA 2,660M MXN is ~$144M. Ratios of two MXN figures — margins, D/E, "
    "growth — are currency-neutral and safe. Mexican foreign private issuer: 20-F and "
    "6-K only, no 10-Q, so disclosure is half-yearly and harder to track inside a 90-day "
    "window."
    "\n\n"
    "CATEGORY NOTE. Distinct from the LOGC / RHLD / PWRL control-VEHICLE exclusions, "
    "which were entities that are not operating midcaps at all (a permanent-capital "
    "holdco, an externally-managed fee vehicle, a 1940-Act closed-end fund). BWMX is a "
    "real operating midcap that is perfectly in universe. The objection is about WHO "
    "BOUGHT, not what the company is."
)

NOTE = {
    "note_date": "2026-09-17",
    "ticker": "BWMX",
    "thesis": THESIS,
    "verdict": "blocklist_candidate",
    "risk_flags": ["control_block_buyers"],
    "catalysts": [
        "Pattern to reuse: shared surname, a common holding vehicle in Form 4 footnotes, same fund/sponsor, or already-high insider ownership — check buyer independence before trusting an insider count",
        "Q3 earnings 2026-10-23 — would have been inside the window; tracked only if this is ever revisited",
        "Leverage: D/E 339% with negative FCF — a refinancing or equity raise would change the picture",
    ],
    "sources": [
        "EDGAR Form 4 XML, accession 0001213900-26-101014 (Luis Campos) — USD weighted averages and the Campalier voting-power footnote",
        "SEC XBRL companyfacts CIK0001788257 — 275 MXN facts vs 22 USD, establishing reporting currency",
        "EDGAR submissions CIK0001788257 — 20-F/6-K filer, stateOfIncorporation O5 (Mexico)",
        "LookInsight graph — 8 InsiderTransaction rows 2026-04-28 to 2026-09-16; earnings_outcome pass_within_60d on all 5 GENUINE",
        "yfinance 2026-09-17 — 7-name direct-selling peer comps",
    ],
    "mcap_at_note": 620_483_712.0,
}


async def main(commit: bool):
    validate_note(NOTE)
    print(f"Note validates. thesis {len(THESIS):,} chars, "
          f"risk_flags={NOTE['risk_flags']}, verdict={NOTE['verdict']}")

    await Neo4jClient.connect()
    existing = await ResearchNoteService.get_notes(CIK)
    print(f"Existing notes on {CIK}: {len(existing)}")

    sig = await Neo4jClient.execute_query("""
        MATCH (sp:SignalPerformance) WHERE sp.ticker = 'BWMX'
        RETURN sp.signal_id AS sid, sp.is_mature AS mature
    """)
    print(f"BWMX signal rows present: {len(sig)}  (expected 0 after removal)")
    for s in sig:
        print(f"  {s['sid']}  mature={s['mature']}")

    if not commit:
        print("\nDRY-RUN: nothing written. Use --commit.")
        return

    n = await ResearchNoteService.record_note(CIK, NOTE)
    print(f"\nWROTE {n}")
    after = await ResearchNoteService.get_notes(CIK)
    m = [x for x in after if x["note_date"] == NOTE["note_date"]]
    if not m:
        print("WARNING: note not readable back. Investigate.")
        sys.exit(1)
    print(f"Read-back OK: {m[0]['note_date']} / {m[0]['verdict']} / "
          f"{len(m[0]['thesis']):,} chars / flags={m[0]['risk_flags']}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--commit", action="store_true", help="write the note (default: dry-run)")
    asyncio.run(main(ap.parse_args().commit))
