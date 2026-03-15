"""Tests for insider_cluster_service module."""

import pytest
from unittest.mock import AsyncMock, patch
from datetime import datetime, timedelta

from app.services.insider_cluster_service import (
    InsiderClusterService,
    InsiderClusterSignal,
    BuyerDetail,
    classify_insider_role,
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


class TestClassifyInsiderRole:
    """Tests for classify_insider_role()."""

    def test_ceo(self):
        assert classify_insider_role("CEO") == "officer"

    def test_chief_executive_officer(self):
        assert classify_insider_role("Chief Executive Officer") == "officer"

    def test_cfo(self):
        assert classify_insider_role("CFO") == "officer"

    def test_president(self):
        assert classify_insider_role("President and CEO") == "officer"

    def test_vp(self):
        assert classify_insider_role("VP of Engineering") == "officer"

    def test_vice_president(self):
        assert classify_insider_role("Senior Vice President") == "officer"

    def test_evp(self):
        assert classify_insider_role("EVP, General Counsel") == "officer"

    def test_treasurer(self):
        assert classify_insider_role("Treasurer") == "officer"

    def test_general_counsel(self):
        assert classify_insider_role("VP, General Counsel and Secretary") == "officer"

    def test_director(self):
        assert classify_insider_role("Director") == "director"

    def test_director_complex(self):
        assert classify_insider_role("Independent Director") == "director"

    def test_ten_percent_owner(self):
        assert classify_insider_role("10% Owner") == "owner_10pct"

    def test_ten_percent_with_director(self):
        # "10%" takes precedence
        assert classify_insider_role("10% Owner, Director") == "owner_10pct"

    def test_beneficial_owner(self):
        assert classify_insider_role("Beneficial Owner") == "owner_10pct"

    def test_empty_string(self):
        assert classify_insider_role("") == "other"

    def test_none_input(self):
        assert classify_insider_role("") == "other"

    def test_unknown_title(self):
        assert classify_insider_role("Consultant") == "other"


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
    async def test_one_buyer_large_value_is_low(self):
        """1 buyer with >$500K total -> LOW signal (single-buyer noise filtered)."""
        trades = [
            _make_trade("Alice", "P", 300000, _today_minus(5)),
            _make_trade("Alice", "P", 300000, _today_minus(10)),
        ]

        with patch("app.services.insider_cluster_service.Neo4jClient") as mock_db:
            mock_db.execute_query = AsyncMock(return_value=trades)
            result = await InsiderClusterService.detect_clusters(days=90, min_level="low")

        assert len(result) == 1
        assert result[0].signal_level == "low"
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
    async def test_exercise_hold_excluded_from_clusters(self):
        """M (exercise_hold) excluded from cluster detection — only P-code counts."""
        trades = [
            _make_trade("Alice", "P", 100000, _today_minus(5)),
            _make_trade("Bob", "P", 50000, _today_minus(10)),
            _make_trade("Charlie", "M", 75000, _today_minus(15)),  # exercise_hold — excluded
        ]

        with patch("app.services.insider_cluster_service.Neo4jClient") as mock_db:
            mock_db.execute_query = AsyncMock(return_value=trades)
            result = await InsiderClusterService.detect_clusters(days=90, min_level="low")

        assert len(result) == 1
        assert result[0].signal_level == "medium"  # Only 2 P-code buyers
        assert result[0].num_buyers == 2

    @pytest.mark.asyncio
    async def test_m_and_s_codes_excluded_from_clusters(self):
        """Only P-code trades count for cluster detection. M and S are ignored."""
        date_15 = _today_minus(15)
        trades = [
            _make_trade("Alice", "P", 100000, _today_minus(5)),
            _make_trade("Charlie", "M", 75000, date_15),  # exercise — excluded
            {"cik": "0001234567", "company_name": "Test Corp", "tickers": ["TEST"],
             "transaction_date": date_15, "transaction_code": "S",
             "total_value": 75000, "shares": 7500,
             "insider_name": "Charlie", "insider_title": "VP"},  # sell — excluded
        ]

        with patch("app.services.insider_cluster_service.Neo4jClient") as mock_db:
            mock_db.execute_query = AsyncMock(return_value=trades)
            result = await InsiderClusterService.detect_clusters(days=90, min_level="low")

        # Only Alice (P-code) counts
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


class TestOfficerPromotion:
    """Tests for officer-based signal promotion (Change 2)."""

    @pytest.mark.asyncio
    async def test_two_officers_promoted_to_high(self):
        """2 officers buying with >$200K total -> promoted to HIGH."""
        trades = [
            _make_trade("Alice", "P", 150000, _today_minus(5), "CEO"),
            _make_trade("Bob", "P", 100000, _today_minus(10), "CFO"),
        ]

        with patch("app.services.insider_cluster_service.Neo4jClient") as mock_db:
            mock_db.execute_query = AsyncMock(return_value=trades)
            result = await InsiderClusterService.detect_clusters(days=90, min_level="low")

        assert len(result) == 1
        assert result[0].signal_level == "high"
        assert "Officer Cluster" in result[0].signal_summary

    @pytest.mark.asyncio
    async def test_two_officers_low_value_stays_medium(self):
        """2 officers buying with <$200K total -> stays MEDIUM (no promotion)."""
        trades = [
            _make_trade("Alice", "P", 50000, _today_minus(5), "CEO"),
            _make_trade("Bob", "P", 50000, _today_minus(10), "CFO"),
        ]

        with patch("app.services.insider_cluster_service.Neo4jClient") as mock_db:
            mock_db.execute_query = AsyncMock(return_value=trades)
            result = await InsiderClusterService.detect_clusters(days=90, min_level="low")

        assert len(result) == 1
        assert result[0].signal_level == "medium"  # <$200K, no promotion

    @pytest.mark.asyncio
    async def test_director_and_owner_not_promoted(self):
        """Director + 10% Owner buying -> stays MEDIUM (not officers)."""
        trades = [
            _make_trade("Alice", "P", 200000, _today_minus(5), "Director"),
            _make_trade("Bob", "P", 200000, _today_minus(10), "10% Owner"),
        ]

        with patch("app.services.insider_cluster_service.Neo4jClient") as mock_db:
            mock_db.execute_query = AsyncMock(return_value=trades)
            result = await InsiderClusterService.detect_clusters(days=90, min_level="low")

        assert len(result) == 1
        assert result[0].signal_level == "medium"

    @pytest.mark.asyncio
    async def test_buyer_roles_populated(self):
        """Buyer details should have role field populated."""
        trades = [
            _make_trade("Alice", "P", 100000, _today_minus(5), "CEO"),
            _make_trade("Bob", "P", 50000, _today_minus(10), "Director"),
            _make_trade("Charlie", "P", 75000, _today_minus(15), "10% Owner"),
        ]

        with patch("app.services.insider_cluster_service.Neo4jClient") as mock_db:
            mock_db.execute_query = AsyncMock(return_value=trades)
            result = await InsiderClusterService.detect_clusters(days=90, min_level="low")

        roles = {b.name: b.role for b in result[0].buyers}
        assert roles["Alice"] == "officer"
        assert roles["Bob"] == "director"
        assert roles["Charlie"] == "owner_10pct"


class TestConvictionTiers:
    """Tests for conviction tier classification (Change 6)."""

    @pytest.mark.asyncio
    async def test_three_buyers_two_officers_strong_buy(self):
        """3+ buyers with 2+ officers -> strong_buy."""
        trades = [
            _make_trade("Alice", "P", 100000, _today_minus(5), "CEO"),
            _make_trade("Bob", "P", 50000, _today_minus(10), "CFO"),
            _make_trade("Charlie", "P", 75000, _today_minus(15), "COO"),
        ]

        with patch("app.services.insider_cluster_service.Neo4jClient") as mock_db:
            mock_db.execute_query = AsyncMock(return_value=trades)
            result = await InsiderClusterService.detect_clusters(days=90, min_level="low")

        assert result[0].conviction_tier == "strong_buy"

    @pytest.mark.asyncio
    async def test_three_buyers_no_officers_buy(self):
        """3+ buyers but no officers -> buy (not strong_buy)."""
        trades = [
            _make_trade("Alice", "P", 100000, _today_minus(5), "Director"),
            _make_trade("Bob", "P", 50000, _today_minus(10), "Director"),
            _make_trade("Charlie", "P", 75000, _today_minus(15), "10% Owner"),
        ]

        with patch("app.services.insider_cluster_service.Neo4jClient") as mock_db:
            mock_db.execute_query = AsyncMock(return_value=trades)
            result = await InsiderClusterService.detect_clusters(days=90, min_level="low")

        assert result[0].conviction_tier == "buy"

    @pytest.mark.asyncio
    async def test_two_buyers_one_officer_buy(self):
        """2 buyers with 1 officer -> buy."""
        trades = [
            _make_trade("Alice", "P", 100000, _today_minus(5), "CEO"),
            _make_trade("Bob", "P", 50000, _today_minus(10), "Director"),
        ]

        with patch("app.services.insider_cluster_service.Neo4jClient") as mock_db:
            mock_db.execute_query = AsyncMock(return_value=trades)
            result = await InsiderClusterService.detect_clusters(days=90, min_level="low")

        assert result[0].conviction_tier == "buy"

    @pytest.mark.asyncio
    async def test_two_buyers_no_officers_watch(self):
        """2 buyers with no officers -> watch."""
        trades = [
            _make_trade("Alice", "P", 100000, _today_minus(5), "Director"),
            _make_trade("Bob", "P", 50000, _today_minus(10), "10% Owner"),
        ]

        with patch("app.services.insider_cluster_service.Neo4jClient") as mock_db:
            mock_db.execute_query = AsyncMock(return_value=trades)
            result = await InsiderClusterService.detect_clusters(days=90, min_level="low")

        assert result[0].conviction_tier == "watch"

    @pytest.mark.asyncio
    async def test_sell_cluster_always_watch(self):
        """Sell clusters should always have conviction_tier='watch'."""
        trades = [
            _make_trade("Alice", "S", 50000, _today_minus(5), "CEO"),
            _make_trade("Bob", "S", 30000, _today_minus(10), "CFO"),
            _make_trade("Charlie", "S", 25000, _today_minus(15), "COO"),
            _make_trade("Dave", "S", 20000, _today_minus(20), "VP"),
        ]

        with patch("app.services.insider_cluster_service.Neo4jClient") as mock_db:
            mock_db.execute_query = AsyncMock(return_value=trades)
            result = await InsiderClusterService.detect_sell_clusters(days=90, min_level="medium")

        assert len(result) == 1
        assert result[0].conviction_tier == "watch"

    def test_conviction_tier_in_signal_dict(self):
        """conviction_tier should appear in to_signal_dict() output."""
        signal = InsiderClusterSignal(
            cik="0001234567",
            company_name="Test Corp",
            ticker="TEST",
            window_start="2026-01-01",
            window_end="2026-01-31",
            signal_level="high",
            signal_summary="Open Market Cluster: 3 insiders buying",
            num_buyers=3,
            total_buy_value=225000,
            buyers=[
                BuyerDetail(name="Alice", title="CEO", total_value=100000, trade_count=1, role="officer"),
            ],
            conviction_tier="strong_buy",
        )

        d = signal.to_signal_dict()
        assert d["conviction_tier"] == "strong_buy"
        assert d["cluster_detail"]["conviction_tier"] == "strong_buy"


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
                BuyerDetail(name="Alice", title="CEO", total_value=100000, trade_count=1, role="officer"),
                BuyerDetail(name="Bob", title="CFO", total_value=75000, trade_count=1, role="officer"),
                BuyerDetail(name="Charlie", title="COO", total_value=50000, trade_count=1, role="officer"),
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

        # Role in buyer dicts
        assert d["cluster_detail"]["buyers"][0]["role"] == "officer"

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


class TestDetectSellClusters:
    """Tests for sell-side cluster detection."""

    @pytest.mark.asyncio
    async def test_four_sellers_is_high(self):
        """4 distinct sellers with >$100K total -> HIGH signal."""
        trades = [
            _make_trade("Alice", "S", 50000, _today_minus(5), "CEO"),
            _make_trade("Bob", "S", 30000, _today_minus(10), "CFO"),
            _make_trade("Charlie", "S", 25000, _today_minus(15), "COO"),
            _make_trade("Dave", "S", 20000, _today_minus(20), "VP"),
        ]

        with patch("app.services.insider_cluster_service.Neo4jClient") as mock_db:
            mock_db.execute_query = AsyncMock(return_value=trades)
            result = await InsiderClusterService.detect_sell_clusters(days=90, min_level="medium")

        assert len(result) == 1
        assert result[0].signal_level == "high"
        assert result[0].num_buyers == 4
        assert result[0].direction == "sell"
        assert "4 insiders selling" in result[0].signal_summary

    @pytest.mark.asyncio
    async def test_three_sellers_is_medium(self):
        """3 sellers with >$100K -> MEDIUM signal."""
        trades = [
            _make_trade("Alice", "S", 50000, _today_minus(5)),
            _make_trade("Bob", "S", 30000, _today_minus(10)),
            _make_trade("Charlie", "S", 25000, _today_minus(15)),
        ]

        with patch("app.services.insider_cluster_service.Neo4jClient") as mock_db:
            mock_db.execute_query = AsyncMock(return_value=trades)
            result = await InsiderClusterService.detect_sell_clusters(days=90, min_level="medium")

        assert len(result) == 1
        assert result[0].signal_level == "medium"
        assert result[0].num_buyers == 3

    @pytest.mark.asyncio
    async def test_two_sellers_excluded(self):
        """2 sellers -> no signal (below threshold)."""
        trades = [
            _make_trade("Alice", "S", 200000, _today_minus(5)),
            _make_trade("Bob", "S", 100000, _today_minus(10)),
        ]

        with patch("app.services.insider_cluster_service.Neo4jClient") as mock_db:
            mock_db.execute_query = AsyncMock(return_value=trades)
            result = await InsiderClusterService.detect_sell_clusters(days=90, min_level="medium")

        assert len(result) == 0

    @pytest.mark.asyncio
    async def test_below_100k_excluded(self):
        """3 sellers but <$100K total -> no signal."""
        trades = [
            _make_trade("Alice", "S", 10000, _today_minus(5)),
            _make_trade("Bob", "S", 10000, _today_minus(10)),
            _make_trade("Charlie", "S", 10000, _today_minus(15)),
        ]

        with patch("app.services.insider_cluster_service.Neo4jClient") as mock_db:
            mock_db.execute_query = AsyncMock(return_value=trades)
            result = await InsiderClusterService.detect_sell_clusters(days=90, min_level="medium")

        assert len(result) == 0

    def test_sell_cluster_accession_format(self):
        """Sell cluster accession number should use SELL-CLUSTER- prefix."""
        signal = InsiderClusterSignal(
            cik="0001234567",
            company_name="Test Corp",
            ticker="TEST",
            window_start="2026-01-01",
            window_end="2026-01-31",
            signal_level="high",
            signal_summary="",
            num_buyers=4,
            total_buy_value=200000,
            direction="sell",
        )
        assert signal.accession_number == "SELL-CLUSTER-0001234567-2026-01-31"

    def test_sell_signal_dict_type(self):
        """to_signal_dict() for sell direction should have correct signal_type and direction."""
        signal = InsiderClusterSignal(
            cik="0001234567",
            company_name="Test Corp",
            ticker="TEST",
            window_start="2026-01-01",
            window_end="2026-01-31",
            signal_level="high",
            signal_summary="Insider Sell Cluster: 4 insiders selling",
            num_buyers=4,
            total_buy_value=200000,
            buyers=[
                BuyerDetail(name="Alice", title="CEO", total_value=50000, trade_count=1),
            ],
            direction="sell",
        )

        d = signal.to_signal_dict()
        assert d["signal_type"] == "insider_sell_cluster"
        assert d["cluster_detail"]["direction"] == "sell"
        assert d["insider_context"]["net_direction"] == "selling"
        assert "sold" in d["insider_context"]["notable_trades"][0]

    def test_buy_direction_unchanged(self):
        """Existing buy direction behavior should be unaffected."""
        signal = InsiderClusterSignal(
            cik="0001234567",
            company_name="Test Corp",
            ticker="TEST",
            window_start="2026-01-01",
            window_end="2026-01-31",
            signal_level="high",
            signal_summary="Open Market Cluster: 3 insiders buying",
            num_buyers=3,
            total_buy_value=225000,
            buyers=[
                BuyerDetail(name="Alice", title="CEO", total_value=100000, trade_count=1),
            ],
            direction="buy",
        )

        assert signal.accession_number == "CLUSTER-0001234567-2026-01-31"
        d = signal.to_signal_dict()
        assert d["signal_type"] == "insider_cluster"
        assert d["insider_context"]["net_direction"] == "buying"
        assert "bought" in d["insider_context"]["notable_trades"][0]
