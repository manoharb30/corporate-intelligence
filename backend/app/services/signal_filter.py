"""Signal filter — earnings-based pre-trade exclusion rule.

Rule: Exclude strong_buy signals where the next earnings report is >60 days away.

Rationale: Insiders buying within 60 days of earnings have informational edge
on current quarter performance (68.5% HR vs 61.5% baseline, +10.6% alpha).
Insiders buying right after earnings (60-90d from next) are trading on public
information with no edge.

Backed by research: p=0.003 statistical significance (earnings-sector-patterns.md).
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Optional

import yfinance as yf


EARNINGS_THRESHOLD_DAYS = 60  # Max days to next earnings for signal to pass


@dataclass
class FilterResult:
    """Result of applying the signal filter."""
    passed: bool
    earnings_distance: Optional[int]  # days to next earnings, None if unavailable
    reason: str


class SignalFilter:
    """Earnings proximity filter for strong_buy signals."""

    _earnings_cache: dict[str, list[str]] = {}

    @staticmethod
    def apply_filter(ticker: str, signal_date: str) -> FilterResult:
        """Apply earnings proximity rule to a signal.

        Args:
            ticker: Stock ticker symbol
            signal_date: Signal date in YYYY-MM-DD format

        Returns:
            FilterResult with pass/fail, distance, and reason
        """
        try:
            earnings_dates = SignalFilter._get_earnings_dates(ticker)
        except Exception:
            return FilterResult(
                passed=True,
                earnings_distance=None,
                reason="Warning: error fetching earnings data — signal passed by default"
            )

        if not earnings_dates:
            return FilterResult(
                passed=True,
                earnings_distance=None,
                reason="Warning: no earnings data available — signal passed by default"
            )

        sig_dt = datetime.strptime(signal_date, "%Y-%m-%d")
        next_earnings_dist = None

        for d in earnings_dates:
            try:
                e_dt = datetime.strptime(d, "%Y-%m-%d")
                if e_dt >= sig_dt:
                    next_earnings_dist = (e_dt - sig_dt).days
                    break
            except (ValueError, TypeError):
                continue

        if next_earnings_dist is None:
            return FilterResult(
                passed=True,
                earnings_distance=None,
                reason="Warning: no future earnings date found from signal date — signal passed by default"
            )

        if next_earnings_dist <= EARNINGS_THRESHOLD_DAYS:
            return FilterResult(
                passed=True,
                earnings_distance=next_earnings_dist,
                reason=f"Earnings in {next_earnings_dist}d — within {EARNINGS_THRESHOLD_DAYS}d window (mid-quarter conviction)"
            )
        else:
            return FilterResult(
                passed=False,
                earnings_distance=next_earnings_dist,
                reason=f"Earnings in {next_earnings_dist}d — beyond {EARNINGS_THRESHOLD_DAYS}d threshold (post-earnings, no informational edge)"
            )

    @staticmethod
    def _get_earnings_dates(ticker: str) -> list[str]:
        """Get sorted list of historical + future earnings dates. Cached per ticker."""
        if ticker in SignalFilter._earnings_cache:
            return SignalFilter._earnings_cache[ticker]

        dates = SignalFilter._fetch_earnings_dates(ticker)
        SignalFilter._earnings_cache[ticker] = dates
        return dates

    @staticmethod
    def _fetch_earnings_dates(ticker: str) -> list[str]:
        """Fetch earnings dates from yfinance (limit=20 for historical coverage)."""
        ed = yf.Ticker(ticker).get_earnings_dates(limit=20)
        if ed is not None and len(ed) > 0:
            return sorted([d.strftime("%Y-%m-%d") for d in ed.index])
        return []
