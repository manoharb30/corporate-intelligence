"""Research notes — durable qualitative findings on companies we investigated.

Anchored on Company (not SignalPerformance) so a note survives whether or not a
signal ever forms:

    (:Company)-[:HAS_RESEARCH_NOTE]->(:ResearchNote)

Most researched names never become signals — they fail a gate (mcap, solo buyer)
or the cluster never completes. Those findings used to evaporate. The payoff is
the read-back: when a cluster later forms on a CIK we already looked at,
get_notes_for_ciks() surfaces what we knew at review time.

Additive only: never mutates Company or any signal row. A note is an opinion
with a date on it, not a gate — nothing here filters a signal.
"""

import logging

from app.db.neo4j_client import Neo4jClient

logger = logging.getLogger(__name__)

VERDICTS = {"watch", "pass", "blocklist_candidate"}

RISK_FLAGS = {
    "hostile_activist",     # 13D/petition hostility — see signal_filter evidence
    "recent_dilution",      # offering/ATM/placement inside ~90d (journal L5)
    "below_mcap_floor",     # < $300M
    "above_mcap_ceiling",   # > $5B
    "solo_buyer",           # single insider, no cluster
    "post_run",             # already ran past insiders' prices
    "going_concern",        # auditor/liquidity doubt
    "reverse_split",        # split artifact in price history
    "shell_profile",        # minimal operations / shell-like structure
}


def _pad(cik: str) -> str:
    return (cik or "").strip().zfill(10)


def validate_note(note: dict) -> None:
    """Raise ValueError on missing required fields or closed-vocabulary misses."""
    if not note.get("note_date"):
        raise ValueError("note_date is required")
    if not note.get("thesis"):
        raise ValueError("thesis is required")
    if note.get("verdict") not in VERDICTS:
        raise ValueError(f"verdict must be one of {sorted(VERDICTS)}")
    for flag in note.get("risk_flags") or []:
        if flag not in RISK_FLAGS:
            raise ValueError(f"risk_flag {flag!r} must be one of {sorted(RISK_FLAGS)}")


class ResearchNoteService:
    @staticmethod
    async def record_note(cik: str, note: dict) -> int:
        """MERGE a ResearchNote onto a Company, keyed on note_date (idempotent).

        Note fields: {note_date, ticker, thesis, verdict, risk_flags, catalysts,
        sources, mcap_at_note}. Re-running the same date updates that note in
        place rather than stacking duplicates.
        """
        validate_note(note)
        params = {
            "cik": _pad(cik),
            "note_date": note["note_date"],
            "ticker": note.get("ticker"),
            "thesis": note["thesis"],
            "verdict": note["verdict"],
            "risk_flags": note.get("risk_flags") or [],
            "catalysts": note.get("catalysts") or [],
            "sources": note.get("sources") or [],
            "mcap_at_note": note.get("mcap_at_note"),
        }
        results = await Neo4jClient.execute_query(
            """
            MERGE (c:Company {cik: $cik})
            MERGE (c)-[:HAS_RESEARCH_NOTE]->(rn:ResearchNote {note_date: $note_date})
            ON CREATE SET rn.recorded_at = datetime()
            SET rn.ticker = $ticker,
                rn.thesis = $thesis,
                rn.verdict = $verdict,
                rn.risk_flags = $risk_flags,
                rn.catalysts = $catalysts,
                rn.sources = $sources,
                rn.mcap_at_note = $mcap_at_note,
                rn.updated_at = datetime()
            RETURN count(rn) AS n
            """,
            params,
        )
        return results[0]["n"] if results else 0

    @staticmethod
    async def get_notes(cik: str) -> list[dict]:
        """All notes for one company, newest first."""
        return await Neo4jClient.execute_query(
            """
            MATCH (c:Company {cik: $cik})-[:HAS_RESEARCH_NOTE]->(rn:ResearchNote)
            RETURN rn.note_date AS note_date, rn.ticker AS ticker,
                   rn.thesis AS thesis, rn.verdict AS verdict,
                   rn.risk_flags AS risk_flags, rn.catalysts AS catalysts,
                   rn.sources AS sources, rn.mcap_at_note AS mcap_at_note
            ORDER BY rn.note_date DESC
            """,
            {"cik": _pad(cik)},
        )

    @staticmethod
    async def get_notes_for_ciks(ciks: list[str]) -> dict[str, list[dict]]:
        """Batch read-back for cluster review: {cik: [notes newest first]}.

        Only CIKs with notes appear in the result.
        """
        if not ciks:
            return {}
        rows = await Neo4jClient.execute_query(
            """
            MATCH (c:Company)-[:HAS_RESEARCH_NOTE]->(rn:ResearchNote)
            WHERE c.cik IN $ciks
            RETURN c.cik AS cik, rn.note_date AS note_date, rn.ticker AS ticker,
                   rn.thesis AS thesis, rn.verdict AS verdict,
                   rn.risk_flags AS risk_flags, rn.catalysts AS catalysts,
                   rn.sources AS sources, rn.mcap_at_note AS mcap_at_note
            ORDER BY rn.note_date DESC
            """,
            {"ciks": [_pad(c) for c in ciks]},
        )
        by_cik: dict[str, list[dict]] = {}
        for r in rows:
            by_cik.setdefault(r["cik"], []).append(
                {k: v for k, v in r.items() if k != "cik"}
            )
        return by_cik
