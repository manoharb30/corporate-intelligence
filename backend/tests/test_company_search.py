"""Tests for Company Search API."""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from ingestion.sec_edgar.edgar_client import SECEdgarClient, CompanySearchResult


# Valid user agent for tests
TEST_USER_AGENT = "LookInsight hello@lookinsight.ai"


class TestSECEdgarCompanySearch:
    """Tests for SEC EDGAR company search functionality."""

    def test_company_search_result_dataclass(self):
        """Test CompanySearchResult dataclass."""
        result = CompanySearchResult(
            cik="0001234567",
            name="Test Company Inc",
            ticker="TEST",
            in_graph=False,
        )
        assert result.cik == "0001234567"
        assert result.name == "Test Company Inc"
        assert result.ticker == "TEST"
        assert result.in_graph is False

    def test_company_search_result_no_ticker(self):
        """Test CompanySearchResult with no ticker."""
        result = CompanySearchResult(
            cik="0001234567",
            name="Test Company Inc",
        )
        assert result.ticker is None
        assert result.in_graph is False

    @pytest.mark.asyncio
    async def test_search_companies_exact_ticker_match(self):
        """Test that exact ticker matches get highest priority."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "0": {"cik_str": "1318605", "ticker": "TSLA", "title": "Tesla, Inc."},
            "1": {"cik_str": "789019", "ticker": "MSFT", "title": "MICROSOFT CORP"},
            "2": {"cik_str": "1234567", "ticker": "TSLX", "title": "Some Other Company"},
        }

        with patch.object(SECEdgarClient, "_request", new_callable=AsyncMock) as mock_request:
            mock_request.return_value = mock_response

            client = SECEdgarClient(user_agent=TEST_USER_AGENT)
            results = await client.search_companies("TSLA", limit=10)
            await client.close()

            # Exact ticker match should be first
            assert len(results) > 0
            assert results[0].ticker == "TSLA"
            assert results[0].name == "Tesla, Inc."

    @pytest.mark.asyncio
    async def test_search_companies_name_match(self):
        """Test that name matches work correctly."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "0": {"cik_str": "1318605", "ticker": "TSLA", "title": "Tesla, Inc."},
            "1": {"cik_str": "789019", "ticker": "MSFT", "title": "MICROSOFT CORP"},
            "2": {"cik_str": "320193", "ticker": "AAPL", "title": "Apple Inc."},
        }

        with patch.object(SECEdgarClient, "_request", new_callable=AsyncMock) as mock_request:
            mock_request.return_value = mock_response

            client = SECEdgarClient(user_agent=TEST_USER_AGENT)
            results = await client.search_companies("Tesla", limit=10)
            await client.close()

            # Tesla should be found
            tesla_results = [r for r in results if "Tesla" in r.name]
            assert len(tesla_results) > 0

    @pytest.mark.asyncio
    async def test_search_companies_empty_query(self):
        """Test that empty query returns empty results."""
        client = SECEdgarClient(user_agent=TEST_USER_AGENT)
        results = await client.search_companies("", limit=10)
        await client.close()
        assert results == []

    @pytest.mark.asyncio
    async def test_search_companies_respects_limit(self):
        """Test that search respects the limit parameter."""
        # Create many mock companies
        mock_data = {
            str(i): {"cik_str": str(1000000 + i), "ticker": f"TST{i}", "title": f"Test Company {i}"}
            for i in range(100)
        }
        mock_response = MagicMock()
        mock_response.json.return_value = mock_data

        with patch.object(SECEdgarClient, "_request", new_callable=AsyncMock) as mock_request:
            mock_request.return_value = mock_response

            client = SECEdgarClient(user_agent=TEST_USER_AGENT)
            results = await client.search_companies("Test", limit=5)
            await client.close()

            assert len(results) <= 5


class TestCompanySearchResponse:
    """Tests for CompanySearchResponse model."""

    def test_response_model(self):
        """Test CompanySearchResponse model."""
        from app.models import CompanySearchResponse, CompanySearchResult

        response = CompanySearchResponse(
            query="Tesla",
            results=[
                CompanySearchResult(
                    cik="0001318605",
                    name="Tesla, Inc.",
                    ticker="TSLA",
                    in_graph=True,
                    company_id="abc123",
                )
            ],
            graph_count=1,
            edgar_count=0,
        )

        assert response.query == "Tesla"
        assert len(response.results) == 1
        assert response.results[0].in_graph is True
        assert response.graph_count == 1
        assert response.edgar_count == 0


class TestCompanyServiceCombinedSearch:
    """Tests for CompanyService.search_combined method."""

    @pytest.mark.asyncio
    async def test_combined_search_graph_only(self):
        """Test combined search with only graph results."""
        from app.services.company_service import CompanyService
        from app.db.neo4j_client import Neo4jClient

        # Mock graph search returning results
        mock_records = [
            {"id": "uuid1", "name": "Nikola Corporation", "cik": "0001731289"},
        ]

        with patch.object(Neo4jClient, "execute_query", new_callable=AsyncMock) as mock_query:
            mock_query.return_value = mock_records

            # Also mock SEC EDGAR to return empty (avoid actual API call)
            with patch.object(SECEdgarClient, "search_companies", new_callable=AsyncMock) as mock_sec:
                mock_sec.return_value = []

                response = await CompanyService.search_combined("Nikola", limit=10)

                assert response.query == "Nikola"
                assert response.graph_count == 1
                assert len(response.results) >= 1
                assert response.results[0].in_graph is True
