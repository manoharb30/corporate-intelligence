"""Backfill the missing LUCK research note.

LUCK was dropped and blocklisted on 2026-09-16 — the FIRST token-buy case — but
no ResearchNote was ever written. Its reasoning lived only in the EXCLUDED_CIKS
comment in insider_cluster_service, which means the originating instance of the
token_buy_cluster pattern was invisible to get_notes_for_ciks(), absent from the
signal detail page, and unfindable by querying the flag. Found by
tag_token_buy_2026-09-19.py, which printed the skip rather than swallowing it.

Dated 2026-09-16 to match when the review actually happened, not today — the
note records a decision taken that day. Content is drawn from the analysis
already committed in the blocklist comment (cd5cd18), so nothing here is new
reasoning applied with hindsight.

verdict 'blocklist_candidate' and acted on: CIK 0001840572 is in EXCLUDED_CIKS
and the signal row was removed by remove_luck_2026-09-16.py.

Default = DRY-RUN. Pass --commit to write.
"""

import argparse
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from app.db.neo4j_client import Neo4jClient
from app.services.research_note_service import ResearchNoteService, validate_note

CIK = "0001840572"

THESIS = (
    "Signal 2026-09-11, 2 insiders, $179,068. DROPPED and blocklisted 2026-09-16. "
    "FIRST instance of the token-buy pattern; note written 2026-09-19 to fill a gap — "
    "the decision and its reasoning date from 2026-09-16 and are unchanged."
    "\n\n"
    "=== TOKEN BUY — the originating case ==="
    "\n"
    "Thomas Shannon, founder and CEO, bought $175,800 on 09-09 at $5.86. Robert Bass, "
    "director, bought $3,268 on 09-10 at $5.45 — 1.8% of Shannon's size, and 0.0004% of "
    "market cap. Remove Bass and ONE buyer remains: the cluster fails "
    "MIN_CLUSTER_INSIDERS outright. It existed only because a second name appeared on "
    "the list, not because two people independently concluded the stock was cheap. "
    "The founder/CEO buying near a 52-week low is a real fact; the CLUSTER is not. "
    "Tagged token_buy_cluster (flag added 2026-09-19, after KRMN repeated the pattern)."
    "\n\n"
    "=== BALANCE SHEET — leverage, not dilution ==="
    "\n"
    "Enterprise value $4.11B against a $749M market cap, so equity is 18% of the capital "
    "structure. Total debt $3.27B on $274M EBITDA, ~11.9x. Book equity is NEGATIVE "
    "(P/B -1.88). Revenue essentially flat at +0.9% ($1.245B TTM). TTM net margin -2.9%. "
    "Free cash flow ~-$1.1M — operating cash flow of $104M entirely consumed by capex. "
    "Cash $39.4M against a 0.50 current ratio. Short interest 20.2% of float. Price "
    "$5.49 vs a 52-week range of $5.30-$10.82, so -49% off the high. "
    "Share count FELL 140.2M -> 136.3M over four quarters, so this is NOT the journal-L5 "
    "dilution left tail — it is a leverage one, the same family of risk wearing a "
    "different hat."
    "\n\n"
    "=== PROCESS NOTE ==="
    "\n"
    "I initially argued AGAINST dropping this, on selection-effect and track-record "
    "integrity grounds. That was wrong and should not be repeated: per-arrival "
    "qualitative review IS the documented process here (project_quality_gate_design), "
    "and the CIK blocklist is explicitly a per-name judgment call "
    "(project_cik_blocklist_prophylactic). The frozen-cohort rule protects MATURED rows; "
    "live signals are reviewable. See also the vocabulary gap this case exposed: no "
    "RISK_FLAGS value covered leverage or liquidity, which was the deciding factor here "
    "and remains unaddressed."
    "\n\n"
    "NET: a one-insider signal on a negative-equity, ~12x-levered balance sheet with flat "
    "revenue and no free cash flow. Blocklisted so no future cluster can re-form; the "
    "underlying Shannon and Bass transactions keep their GENUINE classification."
)

NOTE = {
    "note_date": "2026-09-16",
    "ticker": "LUCK",
    "thesis": THESIS,
    "verdict": "blocklist_candidate",
    "risk_flags": ["token_buy_cluster"],
    "catalysts": [
        "Acted on 2026-09-16: CIK 0001840572 added to EXCLUDED_CIKS (commit cd5cd18) and the signal row removed by remove_luck_2026-09-16.py",
        "Pattern origin: first token-buy cluster; KRMN 2026-09-18 repeated it and prompted the token_buy_cluster flag",
        "Open vocabulary gap: no RISK_FLAGS entry covers leverage or liquidity, the deciding factor on this name",
    ],
    "sources": [
        "LookInsight graph — 6 InsiderTransaction rows for CIK 0001840572, GENUINE and FILTERED, 2026-08-28 to 2026-09-10",
        "yfinance 2026-09-16 — valuation, leverage and leisure-sector context",
        "insider_cluster_service.EXCLUDED_CIKS comment, commit cd5cd18 — original rationale as committed",
    ],
    "mcap_at_note": 748_800_000.0,
}


async def main(commit: bool):
    validate_note(NOTE)
    print(f"Note validates. thesis {len(THESIS):,} chars, flags={NOTE['risk_flags']}")

    await Neo4jClient.connect()

    existing = await ResearchNoteService.get_notes(CIK)
    print(f"Existing notes on {CIK}: {len(existing)}")

    sig = await Neo4jClient.execute_query(
        "MATCH (sp:SignalPerformance) WHERE sp.ticker = 'LUCK' RETURN count(*) AS n")
    print(f"LUCK signal rows: {sig[0]['n']} (expected 0 — removed 2026-09-16)")

    tx = await Neo4jClient.execute_query(
        "MATCH (c:Company {cik: $cik})-[:INSIDER_TRADE_OF]->(t:InsiderTransaction) "
        "RETURN count(t) AS n, collect(DISTINCT t.classification) AS classes", {"cik": CIK})
    print(f"Underlying transactions: {tx[0]['n']} {tx[0]['classes']} — untouched")

    if not commit:
        print("\nDRY-RUN: nothing written. Use --commit.")
        return

    n = await ResearchNoteService.record_note(CIK, NOTE)
    print(f"\nWROTE {n}")
    back = [x for x in await ResearchNoteService.get_notes(CIK)
            if x["note_date"] == NOTE["note_date"]]
    if not back:
        print("WARNING: note not readable back. Investigate.")
        sys.exit(1)
    print(f"Read-back OK: {back[0]['note_date']} / {back[0]['verdict']} / "
          f"{len(back[0]['thesis']):,} chars / flags={back[0]['risk_flags']}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--commit", action="store_true", help="write the note (default: dry-run)")
    asyncio.run(main(ap.parse_args().commit))
