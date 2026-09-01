"""Tests for signal_filter.py — earnings filter + hostile activist flag.

Earnings rule: Exclude signals where next earnings is >60 days away.
Hostile flag: Informational tag when activist filing has hostile keywords (not a filter).
"""

import pytest
from unittest.mock import patch
from app.services.signal_filter import (
    SignalFilter, FilterResult, HostileCheckResult,
    FAIL_OPEN_OUTCOMES,
    OUTCOME_PASS_WITHIN, OUTCOME_REJECT_BEYOND, OUTCOME_PASS_NO_DATA,
    OUTCOME_PASS_NO_FUTURE, OUTCOME_PASS_FETCH_ERROR,
)


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
            SignalFilter._caches_loaded = True  # prevent loading from disk
            SignalFilter.apply_filter("AAPL", "2025-06-01")
            SignalFilter.apply_filter("AAPL", "2025-06-15")
            assert call_count == 1  # only fetched once


class TestHostileActivistFlag:
    """Tests for the hostile activist informational flag."""

    def setup_method(self):
        """Clear hostile cache between tests."""
        SignalFilter._hostile_cache.clear()

    def test_hostile_true_when_proxy_keyword(self):
        """Purpose text with 'proxy' → hostile = true."""
        with patch.object(SignalFilter, '_get_activist_purpose_texts', return_value=[
            "The reporting persons intend to solicit proxy votes for board changes."
        ]):
            result = SignalFilter.check_hostile_activist("0000123456")
            assert result.has_hostile is True
            assert "proxy" in result.keywords

    def test_hostile_true_when_remove_keyword(self):
        """Purpose text with 'remove' → hostile = true."""
        with patch.object(SignalFilter, '_get_activist_purpose_texts', return_value=[
            "We intend to remove the current CEO and replace with our nominee."
        ]):
            result = SignalFilter.check_hostile_activist("0000123456")
            assert result.has_hostile is True
            assert any(k in result.keywords for k in ["remove", "replace"])

    def test_hostile_false_when_supportive_text(self):
        """Purpose text without hostile keywords → hostile = false."""
        with patch.object(SignalFilter, '_get_activist_purpose_texts', return_value=[
            "The shares were acquired for investment purposes. The reporting person may engage in constructive dialogue with management."
        ]):
            result = SignalFilter.check_hostile_activist("0000123456")
            assert result.has_hostile is False
            assert result.keywords == []

    def test_hostile_false_when_no_activist(self):
        """No activist filings → hostile = false."""
        with patch.object(SignalFilter, '_get_activist_purpose_texts', return_value=[]):
            result = SignalFilter.check_hostile_activist("0000123456")
            assert result.has_hostile is False
            assert result.keywords == []

    def test_hostile_case_insensitive(self):
        """Keyword matching should be case insensitive."""
        with patch.object(SignalFilter, '_get_activist_purpose_texts', return_value=[
            "We plan to launch a PROXY contest to REPLACE the board."
        ]):
            result = SignalFilter.check_hostile_activist("0000123456")
            assert result.has_hostile is True

    def test_hostile_returns_all_matched_keywords(self):
        """Multiple hostile keywords → all returned."""
        with patch.object(SignalFilter, '_get_activist_purpose_texts', return_value=[
            "We oppose management, demand strategic alternatives, and will solicit proxy votes."
        ]):
            result = SignalFilter.check_hostile_activist("0000123456")
            assert result.has_hostile is True
            assert len(result.keywords) >= 2

    def test_hostile_result_structure(self):
        """HostileCheckResult has required fields."""
        with patch.object(SignalFilter, '_get_activist_purpose_texts', return_value=[]):
            result = SignalFilter.check_hostile_activist("0000123456")
            assert hasattr(result, 'has_hostile')
            assert hasattr(result, 'keywords')
            assert isinstance(result.has_hostile, bool)
            assert isinstance(result.keywords, list)


class TestEarningsOutcomeRecording:
    """Every decision records WHY — pass or fail.

    Before this, only rejections left a trace (classification_rule=EARNINGS_FILTER),
    so a pass could not be distinguished from a fail-open after the fact. Since
    yfinance's earnings coverage changes over time, the decision cannot be
    reconstructed retrospectively — it has to be recorded when it is made.
    """

    def test_real_pass_is_tagged(self):
        with patch.object(SignalFilter, '_get_earnings_dates', return_value=[
            "2025-01-15", "2025-04-15", "2025-07-15"
        ]):
            r = SignalFilter.apply_filter("AAPL", "2025-03-01")
            assert r.passed is True
            assert r.outcome == OUTCOME_PASS_WITHIN
            assert r.outcome not in FAIL_OPEN_OUTCOMES

    def test_real_reject_is_tagged(self):
        with patch.object(SignalFilter, '_get_earnings_dates', return_value=[
            "2025-01-15", "2025-07-15"
        ]):
            r = SignalFilter.apply_filter("AAPL", "2025-02-01")
            assert r.passed is False
            assert r.outcome == OUTCOME_REJECT_BEYOND

    def test_no_data_tagged_as_fail_open(self):
        """No earnings dates at all -> passes by default, tagged as fail-open."""
        with patch.object(SignalFilter, '_get_earnings_dates', return_value=[]):
            r = SignalFilter.apply_filter("NEWCO", "2025-03-01")
            assert r.passed is True
            assert r.outcome == OUTCOME_PASS_NO_DATA
            assert r.outcome in FAIL_OPEN_OUTCOMES
            assert r.no_history_before_signal is True

    def test_no_future_date_tagged_as_fail_open(self):
        """Dates exist but none on/after signal date -> fail-open."""
        with patch.object(SignalFilter, '_get_earnings_dates', return_value=[
            "2024-01-15", "2024-04-15"
        ]):
            r = SignalFilter.apply_filter("AAPL", "2025-03-01")
            assert r.passed is True
            assert r.outcome == OUTCOME_PASS_NO_FUTURE
            assert r.outcome in FAIL_OPEN_OUTCOMES

    def test_fetch_error_tagged_as_fail_open(self):
        with patch.object(SignalFilter, '_get_earnings_dates',
                          side_effect=RuntimeError("yfinance down")):
            r = SignalFilter.apply_filter("AAPL", "2025-03-01")
            assert r.passed is True
            assert r.outcome == OUTCOME_PASS_FETCH_ERROR
            assert r.outcome in FAIL_OPEN_OUTCOMES


class TestNoHistoryBeforeSignal:
    """`no_history_before_signal` = the company had never reported at the time of
    the buy. This is the new-listing detector (AIAI pattern) that the future
    fail-closed rule will key on. Recorded now, not yet acted on.
    """

    def test_new_listing_has_no_prior_history(self):
        """All known earnings dates are AFTER the signal -> never reported yet."""
        with patch.object(SignalFilter, '_get_earnings_dates', return_value=[
            "2025-08-15", "2025-11-15"
        ]):
            r = SignalFilter.apply_filter("AIAI", "2025-07-01")
            assert r.no_history_before_signal is True
            assert r.passed is True  # still passes — fail-closed not built yet

    def test_established_company_has_prior_history(self):
        with patch.object(SignalFilter, '_get_earnings_dates', return_value=[
            "2024-11-15", "2025-02-15", "2025-05-15"
        ]):
            r = SignalFilter.apply_filter("AAPL", "2025-04-01")
            assert r.no_history_before_signal is False

    def test_no_history_flag_does_not_change_pass_fail(self):
        """Recording only — a new listing beyond 60d still fails on the real rule."""
        with patch.object(SignalFilter, '_get_earnings_dates', return_value=[
            "2025-12-15"
        ]):
            r = SignalFilter.apply_filter("AIAI", "2025-07-01")
            assert r.no_history_before_signal is True
            assert r.passed is False
            assert r.outcome == OUTCOME_REJECT_BEYOND
