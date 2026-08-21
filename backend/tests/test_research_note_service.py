"""Tests for research_note_service.py — TDD RED phase.

Research notes: durable per-company qualitative findings for names we looked at
but did NOT signal on (failed gates, or no cluster yet). Anchored on Company so
they survive whether or not a SignalPerformance row ever exists.

(:Company)-[:HAS_RESEARCH_NOTE]->(:ResearchNote)

The payoff is the read-back: when a cluster later forms on a CIK we already
researched, surface the prior note at review time.
"""

import pytest
from unittest.mock import patch, AsyncMock


# === Vocabularies + validation (pure, no DB) ===

class TestVocabularies:
    def test_verdicts_are_closed(self):
        from app.services.research_note_service import VERDICTS
        assert VERDICTS == {"watch", "pass", "blocklist_candidate"}

    def test_risk_flags_include_known_patterns(self):
        from app.services.research_note_service import RISK_FLAGS
        for f in ("hostile_activist", "recent_dilution", "below_mcap_floor",
                  "above_mcap_ceiling", "solo_buyer", "post_run", "going_concern",
                  "reverse_split", "shell_profile"):
            assert f in RISK_FLAGS


class TestValidation:
    def _good(self):
        return {
            "note_date": "2026-08-04",
            "ticker": "PRQR",
            "thesis": "Positive Ph1, funded into 2028, but activist petition pending.",
            "verdict": "watch",
            "risk_flags": ["hostile_activist", "recent_dilution"],
        }

    def test_accepts_good_note(self):
        from app.services.research_note_service import validate_note
        validate_note(self._good())

    def test_requires_note_date(self):
        from app.services.research_note_service import validate_note
        n = self._good() | {"note_date": ""}
        with pytest.raises(ValueError, match="note_date"):
            validate_note(n)

    def test_requires_thesis(self):
        from app.services.research_note_service import validate_note
        n = self._good() | {"thesis": ""}
        with pytest.raises(ValueError, match="thesis"):
            validate_note(n)

    def test_rejects_unknown_verdict(self):
        from app.services.research_note_service import validate_note
        n = self._good() | {"verdict": "buy"}
        with pytest.raises(ValueError, match="verdict"):
            validate_note(n)

    def test_rejects_unknown_risk_flag(self):
        from app.services.research_note_service import validate_note
        n = self._good() | {"risk_flags": ["vibes_are_off"]}
        with pytest.raises(ValueError, match="risk_flag"):
            validate_note(n)

    def test_allows_empty_risk_flags(self):
        from app.services.research_note_service import validate_note
        validate_note(self._good() | {"risk_flags": []})


# === Write path (mocked Neo4jClient) ===

class TestRecordNote:
    @pytest.mark.asyncio
    async def test_merges_note_onto_company_keyed_on_date(self):
        from app.services.research_note_service import ResearchNoteService
        with patch("app.services.research_note_service.Neo4jClient") as mock:
            mock.execute_query = AsyncMock(return_value=[{"n": 1}])
            n = await ResearchNoteService.record_note(
                "0001612940",
                {
                    "note_date": "2026-08-04",
                    "ticker": "PRQR",
                    "thesis": "Ph1 clean; activist petition Jul 27.",
                    "verdict": "watch",
                    "risk_flags": ["hostile_activist"],
                    "sources": ["https://example.com/a"],
                },
            )
            assert n == 1
            cypher = mock.execute_query.call_args[0][0]
            params = mock.execute_query.call_args[0][1]
            assert "MERGE" in cypher                 # idempotent re-run
            assert "HAS_RESEARCH_NOTE" in cypher
            assert "ResearchNote" in cypher
            assert "Company" in cypher
            assert params["cik"] == "0001612940"
            assert params["note_date"] == "2026-08-04"

    @pytest.mark.asyncio
    async def test_zero_pads_cik(self):
        from app.services.research_note_service import ResearchNoteService
        with patch("app.services.research_note_service.Neo4jClient") as mock:
            mock.execute_query = AsyncMock(return_value=[{"n": 1}])
            await ResearchNoteService.record_note(
                "1612940",
                {"note_date": "2026-08-04", "ticker": "PRQR",
                 "thesis": "x", "verdict": "watch"},
            )
            assert mock.execute_query.call_args[0][1]["cik"] == "0001612940"

    @pytest.mark.asyncio
    async def test_invalid_note_raises_before_db_call(self):
        from app.services.research_note_service import ResearchNoteService
        with patch("app.services.research_note_service.Neo4jClient") as mock:
            mock.execute_query = AsyncMock()
            with pytest.raises(ValueError):
                await ResearchNoteService.record_note(
                    "0001612940",
                    {"note_date": "2026-08-04", "ticker": "PRQR",
                     "thesis": "x", "verdict": "nonsense"},
                )
            mock.execute_query.assert_not_called()


# === Read-back (the reason this exists) ===

class TestGetNotes:
    @pytest.mark.asyncio
    async def test_returns_notes_for_cik_newest_first(self):
        from app.services.research_note_service import ResearchNoteService
        with patch("app.services.research_note_service.Neo4jClient") as mock:
            mock.execute_query = AsyncMock(return_value=[
                {"note_date": "2026-08-04", "ticker": "PRQR", "thesis": "b",
                 "verdict": "watch", "risk_flags": ["hostile_activist"], "sources": []},
            ])
            notes = await ResearchNoteService.get_notes("1612940")
            assert len(notes) == 1
            assert notes[0]["ticker"] == "PRQR"
            cypher = mock.execute_query.call_args[0][0]
            assert "ORDER BY" in cypher and "DESC" in cypher
            assert mock.execute_query.call_args[0][1]["cik"] == "0001612940"

    @pytest.mark.asyncio
    async def test_batch_lookup_groups_notes_by_cik(self):
        """Cluster-formation surfacing: one query for many CIKs."""
        from app.services.research_note_service import ResearchNoteService
        with patch("app.services.research_note_service.Neo4jClient") as mock:
            mock.execute_query = AsyncMock(return_value=[
                {"cik": "0001612940", "note_date": "2026-08-04", "ticker": "PRQR",
                 "thesis": "a", "verdict": "watch", "risk_flags": [], "sources": []},
                {"cik": "0001612940", "note_date": "2026-06-01", "ticker": "PRQR",
                 "thesis": "older", "verdict": "watch", "risk_flags": [], "sources": []},
                {"cik": "0000715446", "note_date": "2026-08-04", "ticker": "ANIX",
                 "thesis": "b", "verdict": "pass", "risk_flags": [], "sources": []},
            ])
            by_cik = await ResearchNoteService.get_notes_for_ciks(["1612940", "715446"])
            assert set(by_cik) == {"0001612940", "0000715446"}
            assert len(by_cik["0001612940"]) == 2
            assert by_cik["0000715446"][0]["ticker"] == "ANIX"

    @pytest.mark.asyncio
    async def test_batch_lookup_with_no_ciks_skips_db(self):
        from app.services.research_note_service import ResearchNoteService
        with patch("app.services.research_note_service.Neo4jClient") as mock:
            mock.execute_query = AsyncMock()
            assert await ResearchNoteService.get_notes_for_ciks([]) == {}
            mock.execute_query.assert_not_called()
