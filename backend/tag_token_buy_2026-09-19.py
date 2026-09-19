"""Tag the two existing token-buy notes with the new token_buy_cluster flag.

KRMN's note (2026-09-19) documented the pattern but carried no flag, because the
vocabulary had no entry for it. LUCK's note (2026-09-16) is the first instance
and predates the flag entirely. Tagging both makes the pattern queryable across
cases instead of living only in prose.

Amends risk_flags IN PLACE — record_note MERGEs on note_date, so the thesis,
verdict, catalysts, sources and mcap are re-sent unchanged and only the flag
list moves. Idempotent: re-running is a no-op once the flag is present.

Default = DRY-RUN. Pass --commit to write.
"""

import argparse
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from app.db.neo4j_client import Neo4jClient
from app.services.research_note_service import ResearchNoteService

FLAG = "token_buy_cluster"

# (cik, ticker, note_date) — both exhibit one real buy plus a gesture.
TARGETS = [
    ("0002040127", "KRMN", "2026-09-19"),  # $1,007,648 vs $18,720 and $10,117
    ("0001840572", "LUCK", "2026-09-16"),  # $175,800 vs $3,268
]


async def main(commit: bool):
    await Neo4jClient.connect()

    for cik, ticker, note_date in TARGETS:
        notes = await ResearchNoteService.get_notes(cik)
        match = [n for n in notes if n["note_date"] == note_date]
        if not match:
            print(f"{ticker}: no note dated {note_date} — SKIPPING (nothing to amend)")
            continue
        note = match[0]
        flags = list(note.get("risk_flags") or [])
        if FLAG in flags:
            print(f"{ticker}: already tagged — no-op")
            continue

        print(f"{ticker} {note_date}: risk_flags {flags} -> {flags + [FLAG]}  "
              f"(thesis {len(note['thesis']):,} chars unchanged)")
        if commit:
            payload = {
                "note_date": note["note_date"],
                "ticker": note["ticker"],
                "thesis": note["thesis"],
                "verdict": note["verdict"],
                "risk_flags": flags + [FLAG],
                "catalysts": note.get("catalysts") or [],
                "sources": note.get("sources") or [],
                "mcap_at_note": note.get("mcap_at_note"),
            }
            n = await ResearchNoteService.record_note(cik, payload)
            print(f"    WROTE {n}")

    if not commit:
        print("\nDRY-RUN: nothing written. Use --commit.")
        return

    print(f"\nAll notes carrying {FLAG}:")
    rows = await Neo4jClient.execute_query(
        """
        MATCH (c:Company)-[:HAS_RESEARCH_NOTE]->(rn:ResearchNote)
        WHERE $flag IN rn.risk_flags
        RETURN rn.ticker AS ticker, rn.note_date AS note_date,
               rn.verdict AS verdict, rn.risk_flags AS flags
        ORDER BY rn.note_date
        """,
        {"flag": FLAG},
    )
    for r in rows:
        print(f"  {r['ticker']:<6} {r['note_date']}  {r['verdict']:<20} {r['flags']}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--commit", action="store_true", help="write the flags (default: dry-run)")
    asyncio.run(main(ap.parse_args().commit))
