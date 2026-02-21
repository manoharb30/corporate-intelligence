"""Tests for Form 4 Scanner (unit tests with mocked dependencies)."""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from datetime import datetime, timedelta

from scanner.form4_scanner import (
    get_checkpoint,
    update_checkpoint,
    detect_and_alert,
    run_scanner,
    SCANNER_ID,
    LARGE_PURCHASE_THRESHOLD,
)


@pytest.fixture
def mock_neo4j():
    with patch("scanner.form4_scanner.Neo4jClient") as mock:
        mock.connect = AsyncMock()
        mock.execute_query = AsyncMock(return_value=[])
        yield mock


class TestGetCheckpoint:
    @pytest.mark.asyncio
    async def test_returns_stored_checkpoint(self, mock_neo4j):
        mock_neo4j.execute_query.return_value = [{"last_checkpoint": "2026-02-20"}]

        result = await get_checkpoint()

        assert result == "2026-02-20"

    @pytest.mark.asyncio
    async def test_defaults_to_yesterday(self, mock_neo4j):
        mock_neo4j.execute_query.return_value = []

        result = await get_checkpoint()

        expected = (datetime.utcnow() - timedelta(days=1)).strftime("%Y-%m-%d")
        assert result == expected

    @pytest.mark.asyncio
    async def test_defaults_when_checkpoint_is_none(self, mock_neo4j):
        mock_neo4j.execute_query.return_value = [{"last_checkpoint": None}]

        result = await get_checkpoint()

        expected = (datetime.utcnow() - timedelta(days=1)).strftime("%Y-%m-%d")
        assert result == expected


class TestUpdateCheckpoint:
    @pytest.mark.asyncio
    async def test_calls_merge(self, mock_neo4j):
        await update_checkpoint("2026-02-21", "success", {"companies_scanned": 5})

        mock_neo4j.execute_query.assert_called_once()
        query = mock_neo4j.execute_query.call_args[0][0]
        assert "MERGE" in query
        params = mock_neo4j.execute_query.call_args[0][1]
        assert params["scanner_id"] == SCANNER_ID
        assert params["checkpoint"] == "2026-02-21"
        assert params["status"] == "success"


class TestDetectAndAlert:
    @pytest.mark.asyncio
    async def test_creates_alerts_for_clusters(self):
        with patch(
            "scanner.form4_scanner.InsiderClusterService.detect_clusters",
            new_callable=AsyncMock,
        ) as mock_detect, patch(
            "scanner.form4_scanner.AlertService.create_alert",
            new_callable=AsyncMock,
            return_value="alert-1",
        ) as mock_create, patch(
            "scanner.form4_scanner._check_large_purchases",
            new_callable=AsyncMock,
        ):
            mock_cluster = MagicMock()
            mock_cluster.cik = "0001234567"
            mock_cluster.company_name = "Test Corp"
            mock_cluster.ticker = "TEST"
            mock_cluster.signal_level = "high"
            mock_cluster.signal_summary = "3 insiders buying"
            mock_cluster.num_buyers = 3
            mock_detect.return_value = [mock_cluster]

            alerts = await detect_and_alert({"0001234567"})

        assert alerts >= 1
        mock_create.assert_called_once()

    @pytest.mark.asyncio
    async def test_filters_unaffected_ciks(self):
        with patch(
            "scanner.form4_scanner.InsiderClusterService.detect_clusters",
            new_callable=AsyncMock,
        ) as mock_detect, patch(
            "scanner.form4_scanner.AlertService.create_alert",
            new_callable=AsyncMock,
        ) as mock_create, patch(
            "scanner.form4_scanner._check_large_purchases",
            new_callable=AsyncMock,
        ):
            mock_cluster = MagicMock()
            mock_cluster.cik = "9999999999"  # Not in affected set
            mock_cluster.signal_level = "high"
            mock_detect.return_value = [mock_cluster]

            alerts = await detect_and_alert({"0001234567"})

        assert alerts == 0
        mock_create.assert_not_called()

    @pytest.mark.asyncio
    async def test_empty_clusters(self):
        with patch(
            "scanner.form4_scanner.InsiderClusterService.detect_clusters",
            new_callable=AsyncMock,
            return_value=[],
        ), patch(
            "scanner.form4_scanner._check_large_purchases",
            new_callable=AsyncMock,
        ):
            alerts = await detect_and_alert({"0001234567"})

        assert alerts == 0


class TestRunScanner:
    @pytest.mark.asyncio
    async def test_empty_filers_updates_checkpoint(self, mock_neo4j):
        """When no filers found, checkpoint updates and returns."""
        mock_neo4j.execute_query.return_value = []

        with patch(
            "scanner.form4_scanner.discover_form4_filers",
            new_callable=AsyncMock,
            return_value=[],
        ):
            result = await run_scanner()

        assert result["companies_discovered"] == 0
        assert result["companies_scanned"] == 0

    @pytest.mark.asyncio
    async def test_scans_discovered_companies(self, mock_neo4j):
        mock_neo4j.execute_query.return_value = []

        filers = [
            {"cik": "0001111111", "name": "Alpha Corp"},
            {"cik": "0002222222", "name": "Beta Inc"},
        ]

        with patch(
            "scanner.form4_scanner.discover_form4_filers",
            new_callable=AsyncMock,
            return_value=filers,
        ), patch(
            "scanner.form4_scanner.filter_investment_vehicles",
            new_callable=AsyncMock,
            side_effect=lambda x: x,
        ), patch(
            "scanner.form4_scanner.filter_already_scanned",
            new_callable=AsyncMock,
            side_effect=lambda f, _: f,
        ), patch(
            "scanner.form4_scanner.scan_company_form4s",
            new_callable=AsyncMock,
            return_value={"transactions_stored": 3},
        ), patch(
            "scanner.form4_scanner.detect_and_alert",
            new_callable=AsyncMock,
            return_value=1,
        ), patch(
            "scanner.form4_scanner.asyncio.sleep",
            new_callable=AsyncMock,
        ):
            result = await run_scanner()

        assert result["companies_discovered"] == 2
        assert result["companies_scanned"] == 2
        assert result["transactions_stored"] == 6
        assert result["alerts_created"] == 1

    @pytest.mark.asyncio
    async def test_handles_scan_errors_gracefully(self, mock_neo4j):
        mock_neo4j.execute_query.return_value = []

        filers = [{"cik": "0001111111", "name": "Bad Corp"}]

        with patch(
            "scanner.form4_scanner.discover_form4_filers",
            new_callable=AsyncMock,
            return_value=filers,
        ), patch(
            "scanner.form4_scanner.filter_investment_vehicles",
            new_callable=AsyncMock,
            side_effect=lambda x: x,
        ), patch(
            "scanner.form4_scanner.filter_already_scanned",
            new_callable=AsyncMock,
            side_effect=lambda f, _: f,
        ), patch(
            "scanner.form4_scanner.scan_company_form4s",
            new_callable=AsyncMock,
            side_effect=Exception("EDGAR timeout"),
        ), patch(
            "scanner.form4_scanner.detect_and_alert",
            new_callable=AsyncMock,
            return_value=0,
        ):
            result = await run_scanner()

        assert result["errors"] == 1
        assert result["companies_scanned"] == 0
        assert "EDGAR timeout" in result["last_error"]
