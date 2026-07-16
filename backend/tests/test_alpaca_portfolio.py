"""Tests for alpaca_portfolio_service pure helpers."""

from app.services.alpaca_portfolio_service import (
    compute_allocation,
    compute_shortfall,
    day90_exit,
    normalize_spy_curve,
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


class TestNormalizeSpyCurve:
    SPY = [
        {"d": "2026-07-14", "c": 750.0},
        {"d": "2026-07-15", "c": 757.5},
        {"d": "2026-07-16", "c": 742.5},
    ]

    def test_anchored_to_base_on_first_date(self):
        out = normalize_spy_curve(self.SPY, ["2026-07-14", "2026-07-15", "2026-07-16"], base=100_000)
        assert out[0] == {"date": "2026-07-14", "equity": 100_000.0}
        assert out[1]["equity"] == 101_000.0  # +1%
        assert out[2]["equity"] == 99_000.0   # -1%

    def test_missing_spy_date_skipped_not_interpolated(self):
        out = normalize_spy_curve(self.SPY, ["2026-07-14", "2026-07-17"], base=100_000)
        assert [p["date"] for p in out] == ["2026-07-14"]

    def test_no_anchor_returns_empty(self):
        out = normalize_spy_curve(self.SPY, ["2026-07-10"], base=100_000)
        assert out == []

    def test_empty_inputs(self):
        assert normalize_spy_curve([], ["2026-07-14"]) == []
        assert normalize_spy_curve(self.SPY, []) == []


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
