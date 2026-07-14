"""Tests for alpaca_portfolio_service pure helpers."""

from app.services.alpaca_portfolio_service import (
    compute_allocation,
    compute_shortfall,
    day90_exit,
)


class TestComputeShortfall:
    def test_paid_up_vs_day0(self):
        # bought at 13.42 vs day-0 13.05 → +2.84%
        assert compute_shortfall(13.05, 13.42) == 2.84

    def test_filled_below_day0(self):
        assert compute_shortfall(10.0, 9.5) == -5.0

    def test_exact_fill(self):
        assert compute_shortfall(10.0, 10.0) == 0.0

    def test_missing_day0(self):
        assert compute_shortfall(None, 13.42) is None

    def test_missing_fill(self):
        assert compute_shortfall(13.05, None) is None

    def test_zero_day0(self):
        assert compute_shortfall(0.0, 13.42) is None


class TestComputeAllocation:
    def test_typical_split(self):
        alloc = compute_allocation(5223.57, 94122.40, 999.60)
        assert alloc["positions_pct"] == 5.2
        assert alloc["sweep_pct"] == 93.8
        assert alloc["cash_pct"] == 1.0

    def test_all_cash(self):
        alloc = compute_allocation(0, 0, 100000)
        assert alloc == {"positions_pct": 0.0, "sweep_pct": 0.0, "cash_pct": 100.0}

    def test_empty_account(self):
        alloc = compute_allocation(0, 0, 0)
        assert alloc == {"positions_pct": 0.0, "sweep_pct": 0.0, "cash_pct": 0.0}


class TestDay90Exit:
    def test_exit_date(self):
        exit_date, _ = day90_exit("2026-07-09")
        assert exit_date == "2026-10-07"

    def test_tz_suffix_truncated(self):
        exit_date, _ = day90_exit("2026-07-09T00:00:00-05:00")
        assert exit_date == "2026-10-07"

    def test_none_input(self):
        assert day90_exit(None) == (None, None)

    def test_bad_date(self):
        assert day90_exit("not-a-date") == (None, None)

    def test_days_left_never_negative(self):
        _, days_left = day90_exit("2020-01-01")
        assert days_left == 0
