"""Operator CLI: record and read ResearchNote nodes on companies.

Write a note (idempotent — MERGEs on note_date, re-run to correct it):
    python record_research_note.py record CIK note.json

Read notes back:
    python record_research_note.py show CIK
    python record_research_note.py show CIK1 CIK2 CIK3        # batch
    python record_research_note.py flagged hostile_activist   # by risk flag

note.json:
    {"note_date": "YYYY-MM-DD", "ticker": "PRQR",
     "thesis": "...", "verdict": "watch|pass|blocklist_candidate",
     "risk_flags": ["hostile_activist", ...],
     "catalysts": ["2026-12-31 AX-0811 data", ...],
     "sources": ["https://...", ...],
     "mcap_at_note": 241317724}

Notes are opinions with a date on them — never a gate. Nothing here filters a
signal; the payoff is surfacing prior work when a name comes back.
"""
import argparse
import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from app.db.neo4j_client import Neo4jClient
from app.services.research_note_service import RISK_FLAGS, ResearchNoteService


def _print_note(n: dict, prefix: str = "") -> None:
    flags = ", ".join(n.get("risk_flags") or []) or "none"
    mcap = n.get("mcap_at_note")
    mcap_s = f"${mcap/1e6:,.0f}M" if mcap else "n/a"
    print(f"{prefix}{n['note_date']}  {n.get('ticker') or '?':<6} "
          f"[{n['verdict']}]  mcap={mcap_s}")
    print(f"{prefix}  flags: {flags}")
    print(f"{prefix}  {n['thesis']}")
    for c in n.get("catalysts") or []:
        print(f"{prefix}  catalyst: {c}")
    for s in n.get("sources") or []:
        print(f"{prefix}  source: {s}")


async def main() -> None:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)

    p_rec = sub.add_parser("record", help="write/update a note for one CIK")
    p_rec.add_argument("cik")
    p_rec.add_argument("note_file")

    p_show = sub.add_parser("show", help="read notes for one or more CIKs")
    p_show.add_argument("ciks", nargs="+")

    p_flag = sub.add_parser("flagged", help="list notes carrying a risk flag")
    p_flag.add_argument("flag", choices=sorted(RISK_FLAGS))

    args = ap.parse_args()
    await Neo4jClient.connect()
    try:
        if args.cmd == "record":
            note = json.loads(Path(args.note_file).read_text())
            n = await ResearchNoteService.record_note(args.cik, note)
            print(f"Recorded {n} note ({note['note_date']}) for CIK {args.cik} "
                  f"[{note.get('ticker')}]")

        elif args.cmd == "show":
            by_cik = await ResearchNoteService.get_notes_for_ciks(args.ciks)
            if not by_cik:
                print("No research notes found.")
                return
            for cik, notes in by_cik.items():
                print(f"\nCIK {cik} — {len(notes)} note(s)")
                for n in notes:
                    _print_note(n, prefix="  ")

        elif args.cmd == "flagged":
            rows = await Neo4jClient.execute_query(
                """
                MATCH (c:Company)-[:HAS_RESEARCH_NOTE]->(rn:ResearchNote)
                WHERE $flag IN rn.risk_flags
                RETURN c.cik AS cik, rn.note_date AS note_date, rn.ticker AS ticker,
                       rn.thesis AS thesis, rn.verdict AS verdict,
                       rn.risk_flags AS risk_flags, rn.catalysts AS catalysts,
                       rn.sources AS sources, rn.mcap_at_note AS mcap_at_note
                ORDER BY rn.note_date DESC
                """,
                {"flag": args.flag},
            )
            print(f"{len(rows)} note(s) flagged {args.flag}")
            for r in rows:
                print(f"\nCIK {r['cik']}")
                _print_note(r, prefix="  ")
    finally:
        await Neo4jClient.disconnect()


if __name__ == "__main__":
    asyncio.run(main())
