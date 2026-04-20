"""Tests for signal_performance_service.py — TDD RED phase.

Tests written FIRST. Service doesn't exist yet.
All tests should FAIL until Task 3 implements the service.
"""

import pytest
from unittest.mock import patch, AsyncMock


# === Pure computation function tests (no DB) ===

class TestFindPrice:
    """find_price: look up closing price from price_series by date."""

    def test_exact_date_match(self):
        from app.services.signal_performance_service import find_price
        series = [
            {"d": "2024-06-03", "c": 45.23},
            {"d": "2024-06-04", "c": 46.10},
            {"d": "2024-06-05", "c": 45.80},
        ]
        assert find_price(series, "2024-06-04") == 46.10

    def test_weekend_scans_forward(self):
        """Saturday should find Monday's price."""
        from app.services.signal_performance_service import find_price
        series = [
            {"d": "2024-06-07", "c": 45.00},  # Friday
            {"d": "2024-06-10", "c": 46.00},  # Monday
        ]
        assert find_price(series, "2024-06-08") == 46.00  # Saturday → Monday

    def test_returns_none_beyond_max_skip(self):
        from app.services.signal_performance_service import find_price
        series = [
            {"d": "2024-06-03", "c": 45.00},
            {"d": "2024-06-20", "c": 50.00},  # too far
        ]
        assert find_price(series, "2024-06-10") is None  # default max_skip=5

    def test_empty_series(self):
        from app.services.signal_performance_service import find_price
        assert find_price([], "2024-06-03") is None

    def test_none_series(self):
        from app.services.signal_performance_service import find_price
        assert find_price(None, "2024-06-03") is None

    def test_custom_max_skip(self):
        from app.services.signal_performance_service import find_price
        series = [
            {"d": "2024-06-03", "c": 45.00},
            {"d": "2024-06-06", "c": 46.00},  # 3 days later
        ]
        assert find_price(series, "2024-06-03", max_skip=0) == 45.00
        assert find_price(series, "2024-06-04", max_skip=1) is None
        assert find_price(series, "2024-06-04", max_skip=2) == 46.00


class TestEstimateHistoricalMcap:
    """estimate_historical_mcap: current_mcap × (signal_price / current_price)."""

    def test_normal_case(self):
        from app.services.signal_performance_service import estimate_historical_mcap
        # Company doubled in price → historical mcap was half
        result = estimate_historical_mcap(
            current_mcap=10_000_000_000,  # $10B now
            current_price=100.0,
            signal_price=50.0,
        )
        assert result == 5_000_000_000  # $5B then

    def test_price_tripled(self):
        from app.services.signal_performance_service import estimate_historical_mcap
        result = estimate_historical_mcap(
            current_mcap=9_000_000_000,
            current_price=90.0,
            signal_price=30.0,
        )
        assert result == 3_000_000_000

    def test_current_price_zero(self):
        from app.services.signal_performance_service import estimate_historical_mcap
        result = estimate_historical_mcap(
            current_mcap=10_000_000_000,
            current_price=0,
            signal_price=50.0,
        )
        assert result is None

    def test_current_mcap_none(self):
        from app.services.signal_performance_service import estimate_historical_mcap
        result = estimate_historical_mcap(
            current_mcap=None,
            current_price=100.0,
            signal_price=50.0,
        )
        assert result is None

    def test_signal_price_none(self):
        from app.services.signal_performance_service import estimate_historical_mcap
        result = estimate_historical_mcap(
            current_mcap=10_000_000_000,
            current_price=100.0,
            signal_price=None,
        )
        assert result is None


class TestComputeReturns:
    """compute_returns: (exit_price - entry_price) / entry_price × 100."""

    def test_positive_return(self):
        from app.services.signal_performance_service import compute_returns
        entry_prices = {0: 50.0, 1: 51.0}
        result = compute_returns(entry_prices, exit_price=60.0)
        assert result[0] == 20.0  # (60-50)/50 * 100
        assert result[1] == pytest.approx(17.65, abs=0.01)  # (60-51)/51 * 100

    def test_negative_return(self):
        from app.services.signal_performance_service import compute_returns
        result = compute_returns({0: 100.0}, exit_price=80.0)
        assert result[0] == -20.0

    def test_zero_entry_price(self):
        from app.services.signal_performance_service import compute_returns
        result = compute_returns({0: 0.0, 1: 50.0}, exit_price=60.0)
        assert 0 not in result  # skip zero entry
        assert result[1] == 20.0

    def test_none_exit_price(self):
        from app.services.signal_performance_service import compute_returns
        result = compute_returns({0: 50.0}, exit_price=None)
        assert result == {}


class TestComputeConvictionTier:
    """conviction_tier based on historical market cap + cluster criteria."""

    def test_strong_buy_midcap(self):
        from app.services.signal_performance_service import compute_conviction_tier
        # Midcap ($300M-$5B) + $100K+ + 2+ buyers
        result = compute_conviction_tier(
            historical_mcap=2_000_000_000,  # $2B
            total_value=150_000,
            num_buyers=3,
        )
        assert result == "strong_buy"

    def test_buy_only_value(self):
        from app.services.signal_performance_service import compute_conviction_tier
        # $100K+ value but not midcap
        result = compute_conviction_tier(
            historical_mcap=200_000_000,  # $200M — below midcap
            total_value=150_000,
            num_buyers=3,
        )
        assert result == "buy"

    def test_buy_only_midcap(self):
        from app.services.signal_performance_service import compute_conviction_tier
        # Midcap but value < $100K
        result = compute_conviction_tier(
            historical_mcap=2_000_000_000,
            total_value=50_000,
            num_buyers=3,
        )
        assert result == "buy"

    def test_watch_below_both(self):
        from app.services.signal_performance_service import compute_conviction_tier
        result = compute_conviction_tier(
            historical_mcap=100_000_000,  # $100M
            total_value=30_000,
            num_buyers=2,
        )
        assert result == "watch"

    def test_none_mcap_uses_value_only(self):
        from app.services.signal_performance_service import compute_conviction_tier
        result = compute_conviction_tier(
            historical_mcap=None,
            total_value=150_000,
            num_buyers=3,
        )
        # Without mcap, can't confirm midcap → buy (not strong_buy)
        assert result == "buy"

    def test_large_cap_excluded(self):
        from app.services.signal_performance_service import compute_conviction_tier
        # $50B — too large for midcap ($300M-$5B)
        result = compute_conviction_tier(
            historical_mcap=50_000_000_000,
            total_value=500_000,
            num_buyers=5,
        )
        assert result == "buy"  # has value but not midcap

    def test_upper_midcap_excluded(self):
        from app.services.signal_performance_service import compute_conviction_tier
        # $7B — above $5B cap (was midcap under old $10B cap, now excluded)
        result = compute_conviction_tier(
            historical_mcap=7_000_000_000,
            total_value=500_000,
            num_buyers=5,
        )
        assert result == "buy"  # above $5B, not strong_buy

    def test_single_buyer_watch(self):
        from app.services.signal_performance_service import compute_conviction_tier
        result = compute_conviction_tier(
            historical_mcap=2_000_000_000,
            total_value=500_000,
            num_buyers=1,
        )
        assert result == "watch"  # need 2+ buyers


class TestComputeAlpha:
    """compute_alpha: signal_return - spy_return."""

    def test_positive_alpha(self):
        from app.services.signal_performance_service import compute_alpha
        assert compute_alpha(signal_return=15.0, spy_return=5.0) == 10.0

    def test_negative_alpha(self):
        from app.services.signal_performance_service import compute_alpha
        assert compute_alpha(signal_return=-5.0, spy_return=5.0) == -10.0

    def test_none_spy_return(self):
        from app.services.signal_performance_service import compute_alpha
        assert compute_alpha(signal_return=15.0, spy_return=None) is None

    def test_none_signal_return(self):
        from app.services.signal_performance_service import compute_alpha
        assert compute_alpha(signal_return=None, spy_return=5.0) is None


class TestPctOfMcap:
    """pct_of_mcap: total_value / historical_mcap × 100."""

    def test_normal(self):
        from app.services.signal_performance_service import compute_pct_of_mcap
        result = compute_pct_of_mcap(total_value=500_000, historical_mcap=1_000_000_000)
        assert result == pytest.approx(0.05, abs=0.001)  # 0.05%

    def test_none_mcap(self):
        from app.services.signal_performance_service import compute_pct_of_mcap
        assert compute_pct_of_mcap(total_value=500_000, historical_mcap=None) is None

    def test_zero_mcap(self):
        from app.services.signal_performance_service import compute_pct_of_mcap
        assert compute_pct_of_mcap(total_value=500_000, historical_mcap=0) is None


class TestMaturity:
    """is_mature: signal age >= 97 days AND price_day90 exists."""

    def test_mature_signal(self):
        from app.services.signal_performance_service import check_maturity
        result = check_maturity(age_days=100, price_day90=55.0)
        assert result is True

    def test_immature_too_young(self):
        from app.services.signal_performance_service import check_maturity
        result = check_maturity(age_days=50, price_day90=55.0)
        assert result is False

    def test_immature_no_price(self):
        from app.services.signal_performance_service import check_maturity
        result = check_maturity(age_days=100, price_day90=None)
        assert result is False

    def test_boundary_97_days(self):
        from app.services.signal_performance_service import check_maturity
        assert check_maturity(age_days=97, price_day90=55.0) is True
        assert check_maturity(age_days=96, price_day90=55.0) is False


# === compute_all matured-preservation invariant (v1.2 Phase 7) ===

class TestComputeAllPreservesMatured:
    """compute_all MUST NOT touch SignalPerformance nodes where is_mature = true.

    Invariant introduced in v1.2 Phase 7: a matured signal is a frozen historical
    record. Only immature signals and newly-detected clusters are (re)computed.
    """

    def _make_cluster(
        self,
        accession_number: str = "CLUSTER-TEST-2024-06-01",
        ticker: str = "TEST",
        cik: str = "0001234567",
        window_end: str = "2024-06-01",
        total_buy_value: float = 500_000,
        num_buyers: int = 3,
        signal_level: str = "high",
        company_name: str = "Test Co",
    ):
        """Build a minimal cluster object for _compute_one inputs."""
        from types import SimpleNamespace
        return SimpleNamespace(
            accession_number=accession_number,
            ticker=ticker,
            cik=cik,
            window_end=window_end,
            total_buy_value=total_buy_value,
            num_buyers=num_buyers,
            signal_level=signal_level,
            company_name=company_name,
        )

    def _make_company_data(self, cik: str = "0001234567"):
        """Build company_data dict with enough price history for maturity."""
        # ~1 year of daily prices covering 2024-05-15 → 2024-09-15 (mature window)
        from datetime import datetime, timedelta
        series = []
        start = datetime(2024, 5, 15)
        for i in range(150):
            d = start + timedelta(days=i)
            # Skip weekends to mimic real price_series
            if d.weekday() < 5:
                series.append({"d": d.strftime("%Y-%m-%d"), "c": 40.0 + i * 0.1})
        return {cik: {"market_cap": 1_000_000_000, "series": series}}

    def test_compute_one_short_circuits_when_signal_id_in_mature_ids(self):
        """AC-1: matured signals are skipped — _compute_one returns None."""
        from datetime import datetime
        from app.services.signal_performance_service import SignalPerformanceService

        cluster = self._make_cluster(accession_number="CLUSTER-MATURE-X")
        mature_ids = {"CLUSTER-MATURE-X"}

        result = SignalPerformanceService._compute_one(
            cluster,
            direction="buy",
            company_data=self._make_company_data(cluster.cik),
            spy_series=[],
            industry_map={},
            filing_date_map={},
            now=datetime(2024, 10, 1),
            mature_ids=mature_ids,
        )

        assert result is None, "Matured signal_id must be short-circuited, not recomputed"

    def test_compute_one_proceeds_for_new_cluster_not_in_mature_ids(self):
        """AC-2: new clusters ARE computed (not in mature_ids set)."""
        from datetime import datetime
        from app.services.signal_performance_service import SignalPerformanceService

        cluster = self._make_cluster(accession_number="CLUSTER-NEW-Y")
        mature_ids = {"CLUSTER-MATURE-X"}  # Y not in set

        result = SignalPerformanceService._compute_one(
            cluster,
            direction="buy",
            company_data=self._make_company_data(cluster.cik),
            spy_series=[],
            industry_map={},
            filing_date_map={},
            now=datetime(2024, 10, 1),
            mature_ids=mature_ids,
        )

        assert result is not None, "New cluster must be computed"
        assert result["signal_id"] == "CLUSTER-NEW-Y"

    def test_compute_one_proceeds_when_mature_ids_is_none(self):
        """Default/backward-compat: mature_ids=None means no short-circuit (pre-v1.2 behavior)."""
        from datetime import datetime
        from app.services.signal_performance_service import SignalPerformanceService

        cluster = self._make_cluster(accession_number="CLUSTER-Z")

        result = SignalPerformanceService._compute_one(
            cluster,
            direction="buy",
            company_data=self._make_company_data(cluster.cik),
            spy_series=[],
            industry_map={},
            filing_date_map={},
            now=datetime(2024, 10, 1),
            mature_ids=None,
        )

        assert result is not None, "With mature_ids=None, every cluster is computed"

    def test_compute_one_proceeds_for_immature_signal_even_if_prior_immature_existed(self):
        """AC-3: immature signals are not in mature_ids, so they get (re)computed.

        Only matured rows are preserved. Immature rows are deleted and recomputed
        each run — that's how late prices flow in. mature_ids only contains
        is_mature=true signal_ids, so immature signals by definition pass through.
        """
        from datetime import datetime
        from app.services.signal_performance_service import SignalPerformanceService

        cluster = self._make_cluster(accession_number="CLUSTER-IMMATURE-W")
        # Even if some OTHER signal is mature, this immature one must proceed
        mature_ids = {"CLUSTER-MATURE-X", "CLUSTER-MATURE-Y"}

        # Build company_data so this signal would be immature (age < 97 from now)
        from datetime import datetime as dt, timedelta
        now = dt(2024, 7, 1)  # signal_date 2024-06-01 → age ~30 days, immature
        series = []
        start = dt(2024, 5, 15)
        for i in range(60):  # ~60 days of prices, no day-90 price available yet
            d = start + timedelta(days=i)
            if d.weekday() < 5:
                series.append({"d": d.strftime("%Y-%m-%d"), "c": 40.0 + i * 0.1})
        company_data = {cluster.cik: {"market_cap": 1_000_000_000, "series": series}}

        result = SignalPerformanceService._compute_one(
            cluster,
            direction="buy",
            company_data=company_data,
            spy_series=[],
            industry_map={},
            filing_date_map={},
            now=now,
            mature_ids=mature_ids,
        )

        assert result is not None, "Immature signal (not in mature_ids) must be computed"
        assert result["signal_id"] == "CLUSTER-IMMATURE-W"
        assert result["is_mature"] is False, "Should be flagged immature given no day-90 price"
