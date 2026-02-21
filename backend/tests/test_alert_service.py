"""Tests for AlertService (unit tests with mocked Neo4j)."""

import pytest
from unittest.mock import AsyncMock, patch
from datetime import datetime

from app.services.alert_service import AlertService, AlertItem


@pytest.fixture
def mock_execute_query():
    with patch("app.services.alert_service.Neo4jClient.execute_query", new_callable=AsyncMock) as mock:
        yield mock


class TestCreateAlert:
    @pytest.mark.asyncio
    async def test_creates_alert_returns_id(self, mock_execute_query):
        mock_execute_query.return_value = [{"id": "abc-123"}]

        result = await AlertService.create_alert(
            alert_type="insider_cluster",
            severity="high",
            cik="0001234567",
            name="Test Corp",
            ticker="TEST",
            title="Cluster Buy Detected",
            description="3 insiders buying",
        )

        assert result == "abc-123"
        mock_execute_query.assert_called_once()
        call_args = mock_execute_query.call_args
        params = call_args[0][1]
        assert params["alert_type"] == "insider_cluster"
        assert params["severity"] == "high"
        assert params["cik"] == "0001234567"
        assert "insider_cluster" in params["dedup_key"]

    @pytest.mark.asyncio
    async def test_dedup_key_format(self, mock_execute_query):
        mock_execute_query.return_value = [{"id": "xyz"}]
        today = datetime.utcnow().strftime("%Y-%m-%d")

        await AlertService.create_alert(
            alert_type="large_purchase",
            severity="medium",
            cik="0009999999",
            name="Big Corp",
            ticker="BIG",
            title="Large Purchase",
            description="$1M buy",
        )

        params = mock_execute_query.call_args[0][1]
        assert params["dedup_key"] == f"0009999999_large_purchase_{today}"

    @pytest.mark.asyncio
    async def test_returns_none_on_empty_result(self, mock_execute_query):
        mock_execute_query.return_value = []

        result = await AlertService.create_alert(
            alert_type="insider_cluster",
            severity="high",
            cik="0001234567",
            name="Test Corp",
            ticker=None,
            title="Test",
            description="Test",
        )

        assert result is None

    @pytest.mark.asyncio
    async def test_returns_none_on_error(self, mock_execute_query):
        mock_execute_query.side_effect = Exception("DB error")

        result = await AlertService.create_alert(
            alert_type="insider_cluster",
            severity="high",
            cik="0001234567",
            name="Test Corp",
            ticker=None,
            title="Test",
            description="Test",
        )

        assert result is None


class TestGetAlerts:
    @pytest.mark.asyncio
    async def test_returns_alert_items(self, mock_execute_query):
        mock_execute_query.return_value = [
            {
                "id": "a1",
                "alert_type": "insider_cluster",
                "severity": "high",
                "company_cik": "0001234567",
                "company_name": "Test Corp",
                "ticker": "TEST",
                "title": "Cluster Buy",
                "description": "3 insiders buying",
                "created_at": "2026-02-21T10:00:00",
                "acknowledged": False,
                "acknowledged_at": None,
                "dedup_key": "0001234567_insider_cluster_2026-02-21",
            }
        ]

        alerts = await AlertService.get_alerts(days=7)

        assert len(alerts) == 1
        assert alerts[0].id == "a1"
        assert alerts[0].severity == "high"
        assert isinstance(alerts[0], AlertItem)

    @pytest.mark.asyncio
    async def test_severity_filter(self, mock_execute_query):
        mock_execute_query.return_value = []

        await AlertService.get_alerts(days=7, severity="high")

        query = mock_execute_query.call_args[0][0]
        params = mock_execute_query.call_args[0][1]
        assert "a.severity = $severity" in query
        assert params["severity"] == "high"

    @pytest.mark.asyncio
    async def test_acknowledged_filter(self, mock_execute_query):
        mock_execute_query.return_value = []

        await AlertService.get_alerts(days=7, acknowledged=False)

        query = mock_execute_query.call_args[0][0]
        params = mock_execute_query.call_args[0][1]
        assert "a.acknowledged = $acknowledged" in query
        assert params["acknowledged"] is False

    @pytest.mark.asyncio
    async def test_to_dict(self, mock_execute_query):
        mock_execute_query.return_value = [
            {
                "id": "a1",
                "alert_type": "large_purchase",
                "severity": "medium",
                "company_cik": "0001234567",
                "company_name": "Test Corp",
                "ticker": None,
                "title": "Large Buy",
                "description": "CEO bought $1M",
                "created_at": "2026-02-21T10:00:00",
                "acknowledged": False,
                "acknowledged_at": None,
                "dedup_key": "key",
            }
        ]

        alerts = await AlertService.get_alerts()
        d = alerts[0].to_dict()

        assert d["id"] == "a1"
        assert d["alert_type"] == "large_purchase"
        assert "dedup_key" not in d  # dedup_key not in to_dict


class TestGetAlertStats:
    @pytest.mark.asyncio
    async def test_returns_stats(self, mock_execute_query):
        mock_execute_query.return_value = [
            {"total": 5, "high": 2, "medium": 2, "low": 1}
        ]

        stats = await AlertService.get_alert_stats()

        assert stats["total"] == 5
        assert stats["unread"] == 5
        assert stats["by_severity"]["high"] == 2

    @pytest.mark.asyncio
    async def test_empty_stats(self, mock_execute_query):
        mock_execute_query.return_value = []

        stats = await AlertService.get_alert_stats()

        assert stats["total"] == 0
        assert stats["unread"] == 0


class TestAcknowledgeAlert:
    @pytest.mark.asyncio
    async def test_acknowledge_success(self, mock_execute_query):
        mock_execute_query.return_value = [{"id": "a1"}]

        result = await AlertService.acknowledge_alert("a1")

        assert result is True

    @pytest.mark.asyncio
    async def test_acknowledge_not_found(self, mock_execute_query):
        mock_execute_query.return_value = []

        result = await AlertService.acknowledge_alert("nonexistent")

        assert result is False
