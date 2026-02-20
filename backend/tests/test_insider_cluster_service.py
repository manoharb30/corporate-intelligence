"""Tests for insider_cluster_service module."""

import pytest
from unittest.mock import AsyncMock, patch
from datetime import datetime, timedelta

from app.services.insider_cluster_service import (
    InsiderClusterService,
    InsiderClusterSignal,
    BuyerDetail,
)


def _make_trade(name, code, value, date, title=""):
    """Helper to build a trade dict matching Neo4j result shape."""
    return {
        "cik": "0001234567",
        "company_name": "Test Corp",
        "tickers": ["TEST"],
        "transaction_date": date,
        "transaction_code": code,
        "total_value": value,
        "shares": int(value / 10) if value else 0,
        "insider_name": name,
        "insider_title": title,
    }


def _today_minus(days):
    return (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")


class TestDetectClusters:
    """Tests for InsiderClusterService.detect_clusters()."""

    @pytest.mark.asyncio
    async def test_three_buyers_is_high(self):
        """3 distinct buyers in 30d window -> HIGH signal."""
        trades = [
            _make_trade("Alice", "P", 100000, _today_minus(5), "CEO"),
            _make_trade("Bob", "P", 50000, _today_minus(10), "CFO"),
            _make_trade("Charlie", "P", 75000, _today_minus(15), "COO"),
        ]

        with patch("app.services.insider_cluster_service.Neo4jClient") as mock_db:
            mock_db.execute_query = AsyncMock(return_value=trades)
            result = await InsiderClusterService.detect_clusters(days=90, min_level="low")

        assert len(result) == 1
        assert result[0].signal_level == "high"
        assert result[0].num_buyers == 3
        assert "3 insiders" in result[0].signal_summary

    @pytest.mark.asyncio
    async def test_two_buyers_is_medium(self):
        """2 distinct buyers -> MEDIUM signal."""
        trades = [
            _make_trade("Alice", "P", 100000, _today_minus(5)),
            _make_trade("Bob", "P", 50000, _today_minus(10)),
        ]

        with patch("app.services.insider_cluster_service.Neo4jClient") as mock_db:
            mock_db.execute_query = AsyncMock(return_value=trades)
            result = await InsiderClusterService.detect_clusters(days=90, min_level="low")

        assert len(result) == 1
        assert result[0].signal_level == "medium"
        assert result[0].num_buyers == 2

    @pytest.mark.asyncio
    async def test_one_buyer_large_value_is_medium(self):
        """1 buyer with >$500K total -> MEDIUM signal."""
        trades = [
            _make_trade("Alice", "P", 300000, _today_minus(5)),
            _make_trade("Alice", "P", 300000, _today_minus(10)),
        ]

        with patch("app.services.insider_cluster_service.Neo4jClient") as mock_db:
            mock_db.execute_query = AsyncMock(return_value=trades)
            result = await InsiderClusterService.detect_clusters(days=90, min_level="low")

        assert len(result) == 1
        assert result[0].signal_level == "medium"
        assert result[0].num_buyers == 1
        assert result[0].total_buy_value == 600000

    @pytest.mark.asyncio
    async def test_one_buyer_small_value_is_low(self):
        """1 buyer with <$500K -> LOW signal."""
        trades = [
            _make_trade("Alice", "P", 50000, _today_minus(5)),
        ]

        with patch("app.services.insider_cluster_service.Neo4jClient") as mock_db:
            mock_db.execute_query = AsyncMock(return_value=trades)
            result = await InsiderClusterService.detect_clusters(days=90, min_level="low")

        assert len(result) == 1
        assert result[0].signal_level == "low"

    @pytest.mark.asyncio
    async def test_exercise_hold_counted_as_bullish(self):
        """M (exercise) without same-day S -> exercise_hold -> counted as bullish buyer."""
        trades = [
            _make_trade("Alice", "P", 100000, _today_minus(5)),
            _make_trade("Bob", "P", 50000, _today_minus(10)),
            _make_trade("Charlie", "M", 75000, _today_minus(15)),  # exercise_hold
        ]

        with patch("app.services.insider_cluster_service.Neo4jClient") as mock_db:
            mock_db.execute_query = AsyncMock(return_value=trades)
            result = await InsiderClusterService.detect_clusters(days=90, min_level="low")

        assert len(result) == 1
        assert result[0].signal_level == "high"
        assert result[0].num_buyers == 3

    @pytest.mark.asyncio
    async def test_exercise_sell_not_counted(self):
        """M + same-day S -> exercise_sell -> NOT counted as bullish buyer."""
        # Charlie has both M and S on the same day = exercise_sell (neutral)
        date_15 = _today_minus(15)
        trades = [
            _make_trade("Alice", "P", 100000, _today_minus(5)),
            _make_trade("Bob", "P", 50000, _today_minus(10)),
            _make_trade("Charlie", "M", 75000, date_15),
            # Need a same-day S for Charlie to trigger exercise_sell
            # But our query only fetches P and M codes, so exercise_sell detection
            # won't happen in isolation. This tests that M alone = exercise_hold.
        ]
        # To properly test exercise_sell, we need S in the trades.
        # Since the query filters to P and M, exercise_sell can only happen
        # if the batch classifier sees both M and S for the same person+date.
        # In practice, we only query P and M, so M without S = exercise_hold.
        # Let's test with a scenario where S is also present (simulate
        # a broader query result).
        trades_with_sell = [
            _make_trade("Alice", "P", 100000, _today_minus(5)),
            _make_trade("Charlie", "M", 75000, date_15),
            {"cik": "0001234567", "company_name": "Test Corp", "tickers": ["TEST"],
             "transaction_date": date_15, "transaction_code": "S",
             "total_value": 75000, "shares": 7500,
             "insider_name": "Charlie", "insider_title": "VP"},
        ]

        with patch("app.services.insider_cluster_service.Neo4jClient") as mock_db:
            mock_db.execute_query = AsyncMock(return_value=trades_with_sell)
            result = await InsiderClusterService.detect_clusters(days=90, min_level="low")

        # Alice (buy) + Charlie (exercise_sell = neutral, not bullish)
        # So only 1 buyer = LOW
        assert len(result) == 1
        assert result[0].num_buyers == 1
        assert result[0].signal_level == "low"

    @pytest.mark.asyncio
    async def test_min_level_filter(self):
        """min_level='medium' should exclude LOW signals."""
        trades = [
            _make_trade("Alice", "P", 50000, _today_minus(5)),
        ]

        with patch("app.services.insider_cluster_service.Neo4jClient") as mock_db:
            mock_db.execute_query = AsyncMock(return_value=trades)
            result = await InsiderClusterService.detect_clusters(days=90, min_level="medium")

        assert len(result) == 0

    @pytest.mark.asyncio
    async def test_empty_data_returns_empty(self):
        """No trades -> empty list."""
        with patch("app.services.insider_cluster_service.Neo4jClient") as mock_db:
            mock_db.execute_query = AsyncMock(return_value=[])
            result = await InsiderClusterService.detect_clusters(days=90, min_level="low")

        assert result == []


class TestDetectClustersExcluding8K:
    """Tests for InsiderClusterService.detect_clusters_excluding_8k()."""

    @pytest.mark.asyncio
    async def test_companies_with_8k_excluded(self):
        """Companies that have 8-K events should be excluded."""
        trades = [
            _make_trade("Alice", "P", 100000, _today_minus(5)),
            _make_trade("Bob", "P", 50000, _today_minus(10)),
            _make_trade("Charlie", "P", 75000, _today_minus(15)),
        ]

        with patch("app.services.insider_cluster_service.Neo4jClient") as mock_db:
            # First call: detect_clusters query returns trades
            # Second call: 8-K CIK query returns the same CIK
            mock_db.execute_query = AsyncMock(side_effect=[
                trades,  # detect_clusters query
                [{"cik": "0001234567"}],  # 8-K exclusion query
            ])
            result = await InsiderClusterService.detect_clusters_excluding_8k(
                days=90, min_level="low"
            )

        assert len(result) == 0  # Excluded because CIK has 8-K

    @pytest.mark.asyncio
    async def test_companies_without_8k_included(self):
        """Companies without 8-K events should remain in results."""
        trades = [
            _make_trade("Alice", "P", 100000, _today_minus(5)),
            _make_trade("Bob", "P", 50000, _today_minus(10)),
            _make_trade("Charlie", "P", 75000, _today_minus(15)),
        ]

        with patch("app.services.insider_cluster_service.Neo4jClient") as mock_db:
            mock_db.execute_query = AsyncMock(side_effect=[
                trades,  # detect_clusters query
                [{"cik": "9999999999"}],  # Different CIK has 8-K
            ])
            result = await InsiderClusterService.detect_clusters_excluding_8k(
                days=90, min_level="low"
            )

        assert len(result) == 1
        assert result[0].cik == "0001234567"


class TestSignalDict:
    """Tests for InsiderClusterSignal.to_signal_dict()."""

    def test_signal_dict_shape(self):
        """to_signal_dict() should match SignalItem.to_dict() shape."""
        signal = InsiderClusterSignal(
            cik="0001234567",
            company_name="Test Corp",
            ticker="TEST",
            window_start="2026-01-01",
            window_end="2026-01-31",
            signal_level="high",
            signal_summary="Insider Cluster: 3 insiders buying",
            num_buyers=3,
            total_buy_value=225000,
            buyers=[
                BuyerDetail(name="Alice", title="CEO", total_value=100000, trade_count=1),
                BuyerDetail(name="Bob", title="CFO", total_value=75000, trade_count=1),
                BuyerDetail(name="Charlie", title="COO", total_value=50000, trade_count=1),
            ],
        )

        d = signal.to_signal_dict()

        # Core fields match SignalItem shape
        assert d["company_name"] == "Test Corp"
        assert d["cik"] == "0001234567"
        assert d["ticker"] == "TEST"
        assert d["filing_date"] == "2026-01-31"
        assert d["signal_level"] == "high"
        assert d["accession_number"] == "CLUSTER-0001234567-2026-01-31"
        assert d["signal_type"] == "insider_cluster"
        assert d["items"] == []
        assert d["insider_context"]["net_direction"] == "buying"
        assert d["insider_context"]["cluster_activity"] is True

        # Cluster-specific fields
        assert d["cluster_detail"]["num_buyers"] == 3
        assert len(d["cluster_detail"]["buyers"]) == 3

    def test_accession_number_format(self):
        """accession_number should follow CLUSTER-{cik}-{window_end} format."""
        signal = InsiderClusterSignal(
            cik="0000718877",
            company_name="X",
            ticker=None,
            window_start="2026-01-01",
            window_end="2026-02-15",
            signal_level="medium",
            signal_summary="",
            num_buyers=2,
            total_buy_value=100000,
        )
        assert signal.accession_number == "CLUSTER-0000718877-2026-02-15"


class TestMultipleCompanies:
    """Tests for multi-company scenarios."""

    @pytest.mark.asyncio
    async def test_separate_clusters_per_company(self):
        """Trades from different companies should produce separate clusters."""
        trades = [
            {**_make_trade("Alice", "P", 100000, _today_minus(5)), "cik": "0001111111", "company_name": "Corp A", "tickers": ["A"]},
            {**_make_trade("Bob", "P", 50000, _today_minus(10)), "cik": "0001111111", "company_name": "Corp A", "tickers": ["A"]},
            {**_make_trade("Charlie", "P", 75000, _today_minus(5)), "cik": "0002222222", "company_name": "Corp B", "tickers": ["B"]},
            {**_make_trade("Dave", "P", 60000, _today_minus(10)), "cik": "0002222222", "company_name": "Corp B", "tickers": ["B"]},
            {**_make_trade("Eve", "P", 40000, _today_minus(15)), "cik": "0002222222", "company_name": "Corp B", "tickers": ["B"]},
        ]

        with patch("app.services.insider_cluster_service.Neo4jClient") as mock_db:
            mock_db.execute_query = AsyncMock(return_value=trades)
            result = await InsiderClusterService.detect_clusters(days=90, min_level="low")

        assert len(result) == 2
        ciks = {r.cik for r in result}
        assert "0001111111" in ciks  # 2 buyers = MEDIUM
        assert "0002222222" in ciks  # 3 buyers = HIGH

        # HIGH should sort first
        assert result[0].signal_level == "high"
        assert result[1].signal_level == "medium"
