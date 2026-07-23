"""Tests for signal_watch_service.py — TDD RED phase.

Signal Watch: promise-vs-delivery monitoring for open signals.
(:SignalPerformance)-[:HAS_PROMISE]->(:Promise)
(:SignalPerformance)-[:HAS_EVENT]->(:SignalEvent)
"""

import pytest
from unittest.mock import patch, AsyncMock


# === Pure computation tests (no DB) ===

class TestDayIndex:
    """day_index: which day of the 90-day window an event lands on."""

    def test_same_day_is_zero(self):
        from app.services.signal_watch_service import day_index
        assert day_index("2026-06-10", "2026-06-10") == 0

    def test_forty_days_in(self):
        from app.services.signal_watch_service import day_index
        assert day_index("2026-06-10", "2026-07-20") == 40

    def test_pre_window_is_negative(self):
        from app.services.signal_watch_service import day_index
        assert day_index("2026-06-10", "2026-06-04") == -6

    def test_tz_suffix_stripped(self):
        from app.services.signal_watch_service import day_index
        assert day_index("2026-06-10-05:00", "2026-07-20") == 40
        assert day_index("2026-06-10", "2026-07-20-05:00") == 40


class TestValidation:
    """Event types, directions, and verdicts are closed vocabularies."""

    def test_valid_event_types(self):
        from app.services.signal_watch_service import EVENT_TYPES
        for t in ("earnings_call", "guidance", "capital_action", "regulatory",
                  "insider_followon", "ma", "analyst", "index"):
            assert t in EVENT_TYPES

    def test_validate_event_rejects_unknown_type(self):
        from app.services.signal_watch_service import validate_event
        with pytest.raises(ValueError, match="event_type"):
            validate_event({"event_date": "2026-07-20", "event_type": "tweet",
                            "direction": "neutral", "headline": "x"})

    def test_validate_event_rejects_unknown_direction(self):
        from app.services.signal_watch_service import validate_event
        with pytest.raises(ValueError, match="direction"):
            validate_event({"event_date": "2026-07-20", "event_type": "guidance",
                            "direction": "sideways", "headline": "x"})

    def test_validate_event_requires_headline_and_date(self):
        from app.services.signal_watch_service import validate_event
        with pytest.raises(ValueError, match="headline"):
            validate_event({"event_date": "2026-07-20", "event_type": "guidance",
                            "direction": "neutral", "headline": ""})
        with pytest.raises(ValueError, match="event_date"):
            validate_event({"event_date": "", "event_type": "guidance",
                            "direction": "neutral", "headline": "x"})

    def test_validate_event_accepts_good_event(self):
        from app.services.signal_watch_service import validate_event
        validate_event({"event_date": "2026-07-20", "event_type": "earnings_call",
                        "direction": "confirming", "headline": "Q2 print 7/8"})

    def test_valid_verdicts(self):
        from app.services.signal_watch_service import VERDICTS
        assert VERDICTS == {"pass", "fail", "pending"}


# === DB write-path tests (mocked Neo4jClient) ===

class TestRecordPromises:
    @pytest.mark.asyncio
    async def test_merges_promises_keyed_on_metric(self):
        from app.services.signal_watch_service import SignalWatchService
        with patch("app.services.signal_watch_service.Neo4jClient") as mock:
            mock.execute_query = AsyncMock(return_value=[{"n": 2}])
            n = await SignalWatchService.record_promises(
                "SMBK", "2026-06-10",
                [
                    {"metric": "Q2 op EPS", "target": ">= 0.85",
                     "quote": "$4 run-rate by Q4", "source_call_date": "2026-04-20",
                     "break_condition": "walk-back"},
                    {"metric": "NIM", "target": "flat Q2, up H2",
                     "quote": "flat then up", "source_call_date": "2026-04-20",
                     "break_condition": None},
                ],
            )
            assert n == 2
            cypher = mock.execute_query.call_args[0][0]
            params = mock.execute_query.call_args[0][1]
            assert "MERGE" in cypher            # idempotent, re-runnable
            assert "HAS_PROMISE" in cypher
            assert "SignalPerformance" in cypher
            assert params["ticker"] == "SMBK"
            assert params["signal_date"] == "2026-06-10"
            # verdict defaults to pending on create
            assert "pending" in cypher

    @pytest.mark.asyncio
    async def test_source_url_stored_and_refreshable(self):
        """source_url is evidence — it must be written on create AND updated on
        re-run (so evidence can be added to existing promises), while verdict
        is never touched on match."""
        from app.services.signal_watch_service import SignalWatchService
        with patch("app.services.signal_watch_service.Neo4jClient") as mock:
            mock.execute_query = AsyncMock(return_value=[{"n": 1}])
            await SignalWatchService.record_promises(
                "SMBK", "2026-06-10",
                [{"metric": "NIM", "target": "flat",
                  "quote": "flat then up",
                  "source_call_date": "2026-04-20",
                  "source_url": "https://www.fool.com/smbk-q1-transcript"}],
            )
            cypher = mock.execute_query.call_args[0][0]
            params = mock.execute_query.call_args[0][1]
            assert params["promises"][0]["source_url"] == "https://www.fool.com/smbk-q1-transcript"
            assert "ON MATCH SET" in cypher
            # evidence fields refresh on match; verdict must not appear after ON MATCH SET
            on_match = cypher.split("ON MATCH SET")[1].split("RETURN")[0]
            assert "source_url" in on_match
            assert "verdict" not in on_match

    @pytest.mark.asyncio
    async def test_rejects_promise_without_metric(self):
        from app.services.signal_watch_service import SignalWatchService
        with pytest.raises(ValueError, match="metric"):
            await SignalWatchService.record_promises(
                "SMBK", "2026-06-10", [{"target": ">= 0.85"}])

    @pytest.mark.asyncio
    async def test_empty_list_writes_nothing(self):
        from app.services.signal_watch_service import SignalWatchService
        with patch("app.services.signal_watch_service.Neo4jClient") as mock:
            mock.execute_query = AsyncMock()
            n = await SignalWatchService.record_promises("SMBK", "2026-06-10", [])
            assert n == 0
            mock.execute_query.assert_not_called()


class TestRecordEvent:
    @pytest.mark.asyncio
    async def test_writes_event_with_day_index(self):
        from app.services.signal_watch_service import SignalWatchService
        with patch("app.services.signal_watch_service.Neo4jClient") as mock:
            mock.execute_query = AsyncMock(return_value=[{"created": 1}])
            await SignalWatchService.record_event(
                "SMBK", "2026-06-10",
                {"event_date": "2026-07-20", "event_type": "earnings_call",
                 "direction": "confirming", "headline": "Q2: 7/8 promises pass",
                 "detail": "Op EPS $0.96 vs >=0.85", "source_url": "https://sec.gov/x"},
            )
            params = mock.execute_query.call_args[0][1]
            assert params["event"]["day_index"] == 40
            cypher = mock.execute_query.call_args[0][0]
            assert "HAS_EVENT" in cypher
            assert "MERGE" in cypher            # same event re-recorded → no dupe

    @pytest.mark.asyncio
    async def test_invalid_event_never_reaches_db(self):
        from app.services.signal_watch_service import SignalWatchService
        with patch("app.services.signal_watch_service.Neo4jClient") as mock:
            mock.execute_query = AsyncMock()
            with pytest.raises(ValueError):
                await SignalWatchService.record_event(
                    "SMBK", "2026-06-10",
                    {"event_date": "2026-07-20", "event_type": "rumor",
                     "direction": "neutral", "headline": "x"})
            mock.execute_query.assert_not_called()


class TestScorePromise:
    @pytest.mark.asyncio
    async def test_sets_verdict_and_actual(self):
        from app.services.signal_watch_service import SignalWatchService
        with patch("app.services.signal_watch_service.Neo4jClient") as mock:
            mock.execute_query = AsyncMock(return_value=[{"updated": 1}])
            ok = await SignalWatchService.score_promise(
                "SMBK", "2026-06-10", "Q2 op EPS", "pass", "$0.96")
            assert ok is True
            params = mock.execute_query.call_args[0][1]
            assert params["verdict"] == "pass"
            assert params["actual"] == "$0.96"

    @pytest.mark.asyncio
    async def test_rejects_unknown_verdict(self):
        from app.services.signal_watch_service import SignalWatchService
        with pytest.raises(ValueError, match="verdict"):
            await SignalWatchService.score_promise(
                "SMBK", "2026-06-10", "Q2 op EPS", "maybe", "$0.96")

    @pytest.mark.asyncio
    async def test_returns_false_when_no_promise_matched(self):
        from app.services.signal_watch_service import SignalWatchService
        with patch("app.services.signal_watch_service.Neo4jClient") as mock:
            mock.execute_query = AsyncMock(return_value=[{"updated": 0}])
            ok = await SignalWatchService.score_promise(
                "SMBK", "2026-06-10", "nonexistent", "pass", "x")
            assert ok is False
