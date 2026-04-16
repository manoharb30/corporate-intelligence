"""Tests for signal_filter.py — earnings-based pre-trade filter.

Rule: Exclude signals where next earnings is >60 days away.
Rationale: Mid-quarter buys (within 60d of earnings) have 68.5% HR vs 61.5% baseline.
Insiders buying within 60d of earnings have informational edge on current quarter.
"""

import pytest
from unittest.mock import patch
from app.services.signal_filter import SignalFilter, FilterResult


class TestSignalFilter:
    """Tests for the earnings proximity filter."""

    # --- Core rule: earnings within 60 days = PASS ---

    def test_passes_when_earnings_within_60_days(self):
        """Signal with earnings 45 days away should pass."""
        with patch.object(SignalFilter, '_get_earnings_dates', return_value=[
            "2025-03-15", "2025-06-14", "2025-09-13", "2025-12-13"
        ]):
            result = SignalFilter.apply_filter("AAPL", "2025-04-30")
            assert result.passed is True
            assert result.earnings_distance == 45  # Jun 14 - Apr 30

    def test_passes_when_earnings_30_days_away(self):
        """Signal 30 days before earnings — mid-quarter sweet spot."""
        with patch.object(SignalFilter, '_get_earnings_dates', return_value=[
            "2025-04-15", "2025-07-15", "2025-10-15"
        ]):
            result = SignalFilter.apply_filter("AAPL", "2025-06-15")
            assert result.passed is True
            assert result.earnings_distance == 30

    def test_passes_when_earnings_exactly_60_days(self):
        """Boundary: exactly 60 days should pass (<=60)."""
        with patch.object(SignalFilter, '_get_earnings_dates', return_value=[
            "2025-06-01"
        ]):
            result = SignalFilter.apply_filter("AAPL", "2025-04-02")
            assert result.passed is True
            assert result.earnings_distance == 60

    # --- Core rule: earnings beyond 60 days = FAIL ---

    def test_fails_when_earnings_beyond_60_days(self):
        """Signal with earnings 75 days away — post-earnings buy, no edge."""
        with patch.object(SignalFilter, '_get_earnings_dates', return_value=[
            "2025-04-15", "2025-07-15"
        ]):
            result = SignalFilter.apply_filter("AAPL", "2025-05-01")
            assert result.passed is False
            assert result.earnings_distance == 75  # Jul 15 - May 1
            assert "beyond 60" in result.reason.lower() or "60" in result.reason

    def test_fails_when_earnings_90_days_away(self):
        """Signal right after earnings — worst zone."""
        with patch.object(SignalFilter, '_get_earnings_dates', return_value=[
            "2025-01-15", "2025-04-15"
        ]):
            result = SignalFilter.apply_filter("AAPL", "2025-01-16")
            assert result.passed is False
            assert result.earnings_distance == 89  # Apr 15 - Jan 16

    def test_fails_when_earnings_61_days(self):
        """Boundary: 61 days should fail (>60)."""
        with patch.object(SignalFilter, '_get_earnings_dates', return_value=[
            "2025-06-02"
        ]):
            result = SignalFilter.apply_filter("AAPL", "2025-04-02")
            assert result.passed is False
            assert result.earnings_distance == 61

    # --- Edge cases: graceful degradation ---

    def test_passes_when_no_earnings_data(self):
        """No earnings dates available — pass with warning, don't block."""
        with patch.object(SignalFilter, '_get_earnings_dates', return_value=[]):
            result = SignalFilter.apply_filter("UNKNOWN", "2025-06-15")
            assert result.passed is True
            assert result.earnings_distance is None
            assert "no earnings data" in result.reason.lower()

    def test_passes_when_earnings_fetch_fails(self):
        """yfinance error — pass with warning, don't block."""
        with patch.object(SignalFilter, '_get_earnings_dates', side_effect=Exception("yfinance error")):
            result = SignalFilter.apply_filter("BAD_TICKER", "2025-06-15")
            assert result.passed is True
            assert result.earnings_distance is None
            assert "error" in result.reason.lower() or "warning" in result.reason.lower()

    def test_passes_when_no_future_earnings_from_signal_date(self):
        """All earnings dates are before signal date — pass with warning."""
        with patch.object(SignalFilter, '_get_earnings_dates', return_value=[
            "2024-01-15", "2024-04-15"
        ]):
            result = SignalFilter.apply_filter("AAPL", "2025-06-15")
            assert result.passed is True
            assert result.earnings_distance is None

    # --- FilterResult structure ---

    def test_result_has_required_fields(self):
        """FilterResult must have passed, earnings_distance, reason."""
        with patch.object(SignalFilter, '_get_earnings_dates', return_value=[
            "2025-07-15"
        ]):
            result = SignalFilter.apply_filter("AAPL", "2025-06-15")
            assert hasattr(result, 'passed')
            assert hasattr(result, 'earnings_distance')
            assert hasattr(result, 'reason')
            assert isinstance(result.passed, bool)
            assert isinstance(result.reason, str)

    def test_result_earnings_distance_is_int_when_available(self):
        """earnings_distance should be int (days) when data available."""
        with patch.object(SignalFilter, '_get_earnings_dates', return_value=[
            "2025-07-15"
        ]):
            result = SignalFilter.apply_filter("AAPL", "2025-06-15")
            assert isinstance(result.earnings_distance, int)

    # --- Caching ---

    def test_caches_earnings_dates(self):
        """Second call for same ticker should not re-fetch."""
        call_count = 0
        original_dates = ["2025-04-15", "2025-07-15"]

        def mock_fetch(ticker):
            nonlocal call_count
            call_count += 1
            return original_dates

        with patch.object(SignalFilter, '_fetch_earnings_dates', side_effect=mock_fetch):
            SignalFilter._earnings_cache.clear()
            SignalFilter.apply_filter("AAPL", "2025-06-01")
            SignalFilter.apply_filter("AAPL", "2025-06-15")
            assert call_count == 1  # only fetched once
