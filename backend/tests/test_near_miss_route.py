"""Tests for /api/near-miss — the Research Queue endpoint.

Framing is load-bearing: this endpoint must never present itself as a signal
list, so the caveat is asserted here, not left to the frontend.
"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import patch, AsyncMock
from fastapi.testclient import TestClient


CDNL = {
    "cik": "0001973266",
    "ticker": "CDNL",
    "company_name": "Cardinal Infrastructure",
    "window_start": "2026-08-04",
    "window_end": "2026-08-05",
    "insider_count": 6,
    "total_value": 8_250_000.0,
    "market_cap": 800_000_000.0,
    "pct_of_mcap": 1.0313,
    "buyers": [],
    "research_notes": [{"note_date": "2026-08-19", "verdict": "watch"}],
    "verdict": "watch",
    "filter_reason": "Earnings in 98d",
}


def _client():
    from app.main import app
    return TestClient(app)


class TestNearMissRoute:
    def test_returns_ranked_queue_with_caveat(self):
        with patch(
            "app.api.routes.near_miss.NearMissService.get_near_misses",
            AsyncMock(return_value=[CDNL]),
        ):
            resp = _client().get("/api/near-miss")

        assert resp.status_code == 200
        body = resp.json()
        assert body["count"] == 1
        assert body["near_misses"][0]["ticker"] == "CDNL"
        assert body["near_misses"][0]["verdict"] == "watch"

    def test_caveat_states_this_is_not_a_signal_list(self):
        from app.services.near_miss_service import CAVEAT

        with patch(
            "app.api.routes.near_miss.NearMissService.get_near_misses",
            AsyncMock(return_value=[]),
        ):
            body = _client().get("/api/near-miss").json()

        assert body["caveat"] == CAVEAT
        assert "not a signal list" in body["caveat"].lower()

    def test_empty_queue_is_200_not_404(self):
        with patch(
            "app.api.routes.near_miss.NearMissService.get_near_misses",
            AsyncMock(return_value=[]),
        ):
            resp = _client().get("/api/near-miss")

        assert resp.status_code == 200
        assert resp.json()["count"] == 0
        assert resp.json()["near_misses"] == []

    def test_default_lookback_is_60_days(self):
        mock = AsyncMock(return_value=[])
        with patch("app.api.routes.near_miss.NearMissService.get_near_misses", mock):
            body = _client().get("/api/near-miss").json()

        expected = (datetime.now() - timedelta(days=60)).strftime("%Y-%m-%d")
        assert mock.await_args.kwargs["since_date"] == expected
        assert body["since_date"] == expected
        assert body["days"] == 60

    def test_days_param_controls_lookback(self):
        mock = AsyncMock(return_value=[])
        with patch("app.api.routes.near_miss.NearMissService.get_near_misses", mock):
            body = _client().get("/api/near-miss?days=30").json()

        expected = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")
        assert mock.await_args.kwargs["since_date"] == expected
        assert body["days"] == 30

    def test_rejects_out_of_range_days(self):
        assert _client().get("/api/near-miss?days=0").status_code == 422
        assert _client().get("/api/near-miss?days=400").status_code == 422
