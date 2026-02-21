"""Tests for the accuracy service — price outcome computation and verdict classification."""

import pytest
from app.services.accuracy_service import (
    compute_price_outcomes,
    classify_verdict,
    compute_level_stats,
    SignalOutcome,
)


class TestComputePriceOutcomes:
    """Tests for the pure function that computes price changes from a history array."""

    def test_basic_price_changes(self):
        """30d/60d/90d changes computed from known price array."""
        prices = [
            {"date": "2025-01-02", "close": 100.0},
            {"date": "2025-01-31", "close": 105.0},  # ~30d
            {"date": "2025-03-03", "close": 112.0},  # ~60d
            {"date": "2025-04-02", "close": 120.0},  # ~90d
        ]
        result = compute_price_outcomes(prices, "2025-01-02")

        assert result["price_at_signal"] == 100.0
        assert result["price_change_30d"] == 5.0
        assert result["price_change_60d"] == 12.0
        assert result["price_change_90d"] == 20.0

    def test_negative_returns(self):
        """Negative price changes are correctly negative."""
        prices = [
            {"date": "2025-01-02", "close": 100.0},
            {"date": "2025-02-01", "close": 90.0},
            {"date": "2025-03-03", "close": 85.0},
            {"date": "2025-04-02", "close": 80.0},
        ]
        result = compute_price_outcomes(prices, "2025-01-02")

        assert result["price_at_signal"] == 100.0
        assert result["price_change_30d"] == -10.0
        assert result["price_change_60d"] == -15.0
        assert result["price_change_90d"] == -20.0

    def test_empty_price_history(self):
        """Returns all None for empty history."""
        result = compute_price_outcomes([], "2025-01-02")

        assert result["price_at_signal"] is None
        assert result["price_change_30d"] is None
        assert result["price_change_60d"] is None
        assert result["price_change_90d"] is None

    def test_no_future_data(self):
        """If price history doesn't extend far enough, later windows are None."""
        prices = [
            {"date": "2025-01-02", "close": 100.0},
            {"date": "2025-01-31", "close": 110.0},
        ]
        result = compute_price_outcomes(prices, "2025-01-02")

        assert result["price_at_signal"] == 100.0
        assert result["price_change_30d"] == 10.0
        assert result["price_change_60d"] is None  # no data at ~60d
        assert result["price_change_90d"] is None

    def test_invalid_signal_date(self):
        """Invalid date returns all None."""
        prices = [{"date": "2025-01-02", "close": 100.0}]
        result = compute_price_outcomes(prices, "not-a-date")

        assert result["price_at_signal"] is None

    def test_signal_date_not_in_history(self):
        """Signal date far from any data point returns None (>7 day gap)."""
        prices = [
            {"date": "2025-06-01", "close": 100.0},
        ]
        result = compute_price_outcomes(prices, "2025-01-02")

        assert result["price_at_signal"] is None

    def test_closest_date_matching(self):
        """Uses closest available date within 7 days."""
        prices = [
            {"date": "2025-01-03", "close": 100.0},  # Friday (1 day after signal)
            {"date": "2025-02-03", "close": 108.0},
        ]
        result = compute_price_outcomes(prices, "2025-01-02")

        assert result["price_at_signal"] == 100.0
        assert result["price_change_30d"] == 8.0

    def test_zero_price_at_signal(self):
        """Zero price at signal returns None to avoid division by zero."""
        prices = [
            {"date": "2025-01-02", "close": 0.0},
            {"date": "2025-02-01", "close": 50.0},
        ]
        result = compute_price_outcomes(prices, "2025-01-02")

        assert result["price_at_signal"] is None


class TestClassifyVerdict:
    """Tests for verdict classification logic."""

    def test_pending_when_too_recent(self):
        assert classify_verdict(
            signal_age_days=15,
            price_change_90d=None,
            price_change_60d=None,
            price_change_30d=None,
            followed_by_8k=False,
            min_signal_age_days=30,
        ) == "pending"

    def test_hit_on_large_return(self):
        assert classify_verdict(
            signal_age_days=100,
            price_change_90d=15.0,
            price_change_60d=12.0,
            price_change_30d=5.0,
            followed_by_8k=False,
        ) == "hit"

    def test_hit_on_8k_follow(self):
        """8-K follow is an automatic hit regardless of return."""
        assert classify_verdict(
            signal_age_days=100,
            price_change_90d=-5.0,
            price_change_60d=None,
            price_change_30d=None,
            followed_by_8k=True,
        ) == "hit"

    def test_partial_hit(self):
        assert classify_verdict(
            signal_age_days=100,
            price_change_90d=7.0,
            price_change_60d=None,
            price_change_30d=None,
            followed_by_8k=False,
        ) == "partial_hit"

    def test_miss_on_negative(self):
        assert classify_verdict(
            signal_age_days=100,
            price_change_90d=-8.0,
            price_change_60d=-5.0,
            price_change_30d=-3.0,
            followed_by_8k=False,
        ) == "miss"

    def test_no_data_when_no_prices(self):
        assert classify_verdict(
            signal_age_days=100,
            price_change_90d=None,
            price_change_60d=None,
            price_change_30d=None,
            followed_by_8k=False,
        ) == "no_data"

    def test_uses_60d_when_90d_missing(self):
        """Falls back to 60d when 90d not available."""
        assert classify_verdict(
            signal_age_days=70,
            price_change_90d=None,
            price_change_60d=12.0,
            price_change_30d=5.0,
            followed_by_8k=False,
        ) == "hit"

    def test_uses_30d_when_60d_and_90d_missing(self):
        assert classify_verdict(
            signal_age_days=40,
            price_change_90d=None,
            price_change_60d=None,
            price_change_30d=-2.0,
            followed_by_8k=False,
        ) == "miss"

    def test_exactly_10_pct_is_hit(self):
        assert classify_verdict(
            signal_age_days=100,
            price_change_90d=10.0,
            price_change_60d=None,
            price_change_30d=None,
            followed_by_8k=False,
        ) == "hit"

    def test_exactly_0_pct_is_partial_hit(self):
        assert classify_verdict(
            signal_age_days=100,
            price_change_90d=0.0,
            price_change_60d=None,
            price_change_30d=None,
            followed_by_8k=False,
        ) == "partial_hit"


class TestComputeLevelStats:
    """Tests for aggregate level stats computation."""

    def _make_outcome(self, **kwargs) -> SignalOutcome:
        defaults = {
            "cik": "0001234",
            "company_name": "Test Corp",
            "ticker": "TEST",
            "signal_level": "high",
            "signal_date": "2025-01-01",
            "num_buyers": 3,
            "total_buy_value": 500000,
            "signal_age_days": 100,
            "verdict": "hit",
        }
        defaults.update(kwargs)
        return SignalOutcome(**defaults)

    def test_basic_stats(self):
        outcomes = [
            self._make_outcome(verdict="hit", price_change_90d=15.0),
            self._make_outcome(verdict="miss", price_change_90d=-5.0),
            self._make_outcome(verdict="partial_hit", price_change_90d=3.0),
        ]
        stats = compute_level_stats(outcomes, "high")

        assert stats.count == 3
        assert stats.scoreable == 3
        assert stats.hits == 1
        assert stats.partial_hits == 1
        assert stats.misses == 1
        assert stats.hit_rate == pytest.approx(33.3, abs=0.1)
        assert stats.avg_return_90d == pytest.approx(4.33, abs=0.01)

    def test_filters_by_level(self):
        outcomes = [
            self._make_outcome(signal_level="high", verdict="hit"),
            self._make_outcome(signal_level="medium", verdict="miss"),
        ]
        stats = compute_level_stats(outcomes, "high")

        assert stats.count == 1
        assert stats.hits == 1

    def test_pending_excluded_from_scoreable(self):
        outcomes = [
            self._make_outcome(verdict="hit"),
            self._make_outcome(verdict="pending"),
        ]
        stats = compute_level_stats(outcomes, "high")

        assert stats.count == 2
        assert stats.scoreable == 1

    def test_empty_outcomes(self):
        stats = compute_level_stats([], "high")

        assert stats.count == 0
        assert stats.scoreable == 0
        assert stats.hit_rate is None

    def test_8k_follow_rate(self):
        outcomes = [
            self._make_outcome(followed_by_8k=True, verdict="hit"),
            self._make_outcome(followed_by_8k=False, verdict="miss"),
            self._make_outcome(followed_by_8k=True, verdict="hit"),
        ]
        # Need to set the attribute directly
        outcomes[0].followed_by_8k = True
        outcomes[1].followed_by_8k = False
        outcomes[2].followed_by_8k = True

        stats = compute_level_stats(outcomes, "high")
        assert stats.eight_k_follow_rate == pytest.approx(66.7, abs=0.1)
