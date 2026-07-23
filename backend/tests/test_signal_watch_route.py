"""Tests for /api/signal-watch route + watch_summary — TDD RED phase."""

import pytest
from unittest.mock import patch, AsyncMock
from fastapi.testclient import TestClient


SMBK_WATCH = {
    "ticker": "SMBK",
    "signal_date": "2026-06-10",
    "promises": [
        {"metric": "Q2 op EPS", "target": ">= ~$0.85", "quote": None,
         "source_call_date": "2026-04-20", "break_condition": None,
         "verdict": "pass", "actual": "$0.96"},
        {"metric": "NIM", "target": "flat Q2", "quote": None,
         "source_call_date": "2026-04-20", "break_condition": None,
         "verdict": "pending", "actual": None},
    ],
    "events": [
        {"event_date": "2026-07-20", "day_index": 40, "event_type": "earnings_call",
         "direction": "confirming", "headline": "Q2 print", "detail": None,
         "source_url": None},
    ],
}


class TestWatchSummary:
    """watch_summary: pure rollup of promise verdicts for the FE header line."""

    def test_counts_and_on_track(self):
        from app.services.signal_watch_service import watch_summary
        s = watch_summary(SMBK_WATCH["promises"])
        assert s == {"total": 2, "passed": 1, "failed": 0, "pending": 1, "on_track": True}

    def test_any_fail_means_not_on_track(self):
        from app.services.signal_watch_service import watch_summary
        s = watch_summary([
            {"verdict": "pass"}, {"verdict": "fail"}, {"verdict": "pending"},
        ])
        assert s["failed"] == 1
        assert s["on_track"] is False

    def test_empty_promises(self):
        from app.services.signal_watch_service import watch_summary
        s = watch_summary([])
        assert s == {"total": 0, "passed": 0, "failed": 0, "pending": 0, "on_track": True}


class TestSignalWatchRoute:
    def _client(self):
        from app.main import app
        return TestClient(app)

    def test_returns_watch_with_summary(self):
        with patch(
            "app.api.routes.signal_watch.SignalWatchService.get_watch",
            AsyncMock(return_value=SMBK_WATCH),
        ):
            resp = self._client().get("/api/signal-watch/SMBK?signal_date=2026-06-10")
            assert resp.status_code == 200
            body = resp.json()
            assert body["ticker"] == "SMBK"
            assert body["summary"]["total"] == 2
            assert body["summary"]["passed"] == 1
            assert body["summary"]["on_track"] is True
            assert len(body["promises"]) == 2
            assert len(body["events"]) == 1

    def test_404_when_no_watch_data(self):
        with patch(
            "app.api.routes.signal_watch.SignalWatchService.get_watch",
            AsyncMock(return_value={"ticker": "ZZZZ", "signal_date": "2026-01-01",
                                    "promises": [], "events": []}),
        ):
            resp = self._client().get("/api/signal-watch/ZZZZ?signal_date=2026-01-01")
            assert resp.status_code == 404

    def test_signal_date_required(self):
        resp = self._client().get("/api/signal-watch/SMBK")
        assert resp.status_code == 422
