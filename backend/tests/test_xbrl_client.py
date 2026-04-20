"""Unit tests for XBRLClient (v1.4 Phase 9)."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch


class TestPickSharesAtOrBefore:
    """XBRLClient.pick_shares_at_or_before: latest entry with end_date <= signal_date."""

    def _make_entry(self, end_date: str, shares: int = 1_000_000):
        from ingestion.sec_edgar.xbrl_client import SharesOutstandingEntry
        return SharesOutstandingEntry(
            end_date=end_date,
            shares=shares,
            form="10-Q",
            fiscal_year=2024,
            fiscal_period="Q1",
            accession="0000000000-00-000000",
        )

    def test_returns_latest_preceding_entry(self):
        from ingestion.sec_edgar.xbrl_client import XBRLClient
        entries = [
            self._make_entry("2023-12-31", shares=1_000),
            self._make_entry("2024-03-31", shares=2_000),
            self._make_entry("2024-06-30", shares=3_000),
        ]
        picked = XBRLClient.pick_shares_at_or_before(entries, "2024-05-15")
        assert picked is not None
        assert picked.end_date == "2024-03-31"
        assert picked.shares == 2_000

    def test_returns_none_when_all_after(self):
        from ingestion.sec_edgar.xbrl_client import XBRLClient
        entries = [
            self._make_entry("2025-01-01"),
            self._make_entry("2025-04-01"),
        ]
        picked = XBRLClient.pick_shares_at_or_before(entries, "2024-05-15")
        assert picked is None

    def test_returns_none_for_empty_list(self):
        from ingestion.sec_edgar.xbrl_client import XBRLClient
        assert XBRLClient.pick_shares_at_or_before([], "2024-05-15") is None

    def test_exact_date_match_is_picked(self):
        from ingestion.sec_edgar.xbrl_client import XBRLClient
        entries = [
            self._make_entry("2024-05-15", shares=5_000),
            self._make_entry("2024-06-30", shares=6_000),
        ]
        picked = XBRLClient.pick_shares_at_or_before(entries, "2024-05-15")
        assert picked is not None
        assert picked.end_date == "2024-05-15"


class TestGetSharesOutstanding:
    """XBRLClient.get_shares_outstanding: fetch + parse companyfacts JSON."""

    def _build_mock_response(self, status_code: int, payload: dict):
        """Build a mock httpx.Response."""
        resp = MagicMock()
        resp.status_code = status_code
        resp.json = MagicMock(return_value=payload)
        resp.text = "mocked body"
        resp.request = MagicMock()
        return resp

    @pytest.mark.asyncio
    async def test_parses_dei_key_first(self, monkeypatch):
        """When both dei and us-gaap keys are present, dei wins."""
        from ingestion.sec_edgar.xbrl_client import XBRLClient

        payload = {
            "facts": {
                "dei": {
                    "EntityCommonStockSharesOutstanding": {
                        "units": {
                            "shares": [
                                {"end": "2024-03-31", "val": 1_000_000, "form": "10-Q",
                                 "fy": 2024, "fp": "Q1", "accn": "A-1"},
                            ]
                        }
                    }
                },
                "us-gaap": {
                    "CommonStockSharesOutstanding": {
                        "units": {
                            "shares": [
                                {"end": "2024-03-31", "val": 9_999_999, "form": "10-Q",
                                 "fy": 2024, "fp": "Q1", "accn": "B-1"},
                            ]
                        }
                    }
                },
            }
        }
        resp = self._build_mock_response(200, payload)

        async def fake_get(self, url, headers=None):
            return resp

        monkeypatch.setattr("httpx.AsyncClient.get", fake_get)

        entries = await XBRLClient.get_shares_outstanding("0000000001")
        assert len(entries) == 1
        assert entries[0].shares == 1_000_000  # dei wins

    @pytest.mark.asyncio
    async def test_falls_back_to_us_gaap_when_dei_missing(self, monkeypatch):
        from ingestion.sec_edgar.xbrl_client import XBRLClient

        payload = {
            "facts": {
                "us-gaap": {
                    "CommonStockSharesOutstanding": {
                        "units": {
                            "shares": [
                                {"end": "2024-03-31", "val": 2_500_000, "form": "10-Q",
                                 "fy": 2024, "fp": "Q1", "accn": "C-1"},
                            ]
                        }
                    }
                }
            }
        }
        resp = self._build_mock_response(200, payload)

        async def fake_get(self, url, headers=None):
            return resp

        monkeypatch.setattr("httpx.AsyncClient.get", fake_get)

        entries = await XBRLClient.get_shares_outstanding("0000000002")
        assert len(entries) == 1
        assert entries[0].shares == 2_500_000

    @pytest.mark.asyncio
    async def test_returns_empty_on_404(self, monkeypatch):
        from ingestion.sec_edgar.xbrl_client import XBRLClient

        resp = self._build_mock_response(404, {})

        async def fake_get(self, url, headers=None):
            return resp

        monkeypatch.setattr("httpx.AsyncClient.get", fake_get)

        entries = await XBRLClient.get_shares_outstanding("0000000003")
        assert entries == []

    @pytest.mark.asyncio
    async def test_filters_to_10q_and_10k_only(self, monkeypatch):
        from ingestion.sec_edgar.xbrl_client import XBRLClient

        payload = {
            "facts": {
                "dei": {
                    "EntityCommonStockSharesOutstanding": {
                        "units": {
                            "shares": [
                                {"end": "2024-03-31", "val": 1_000_000, "form": "10-Q",
                                 "fy": 2024, "fp": "Q1", "accn": "A-1"},
                                {"end": "2024-03-31", "val": 9_999_000, "form": "8-K",
                                 "fy": 2024, "fp": "Q1", "accn": "A-2"},
                                {"end": "2023-12-31", "val": 2_000_000, "form": "10-K",
                                 "fy": 2023, "fp": "FY", "accn": "A-3"},
                            ]
                        }
                    }
                }
            }
        }
        resp = self._build_mock_response(200, payload)

        async def fake_get(self, url, headers=None):
            return resp

        monkeypatch.setattr("httpx.AsyncClient.get", fake_get)

        entries = await XBRLClient.get_shares_outstanding("0000000004")
        # Only 10-Q and 10-K, sorted ascending by end_date
        assert len(entries) == 2
        assert [e.form for e in entries] == ["10-K", "10-Q"]
        assert [e.end_date for e in entries] == ["2023-12-31", "2024-03-31"]

    @pytest.mark.asyncio
    async def test_returns_empty_when_no_concept_has_data(self, monkeypatch):
        from ingestion.sec_edgar.xbrl_client import XBRLClient

        payload = {"facts": {"dei": {"SomeOtherFact": {}}}}
        resp = self._build_mock_response(200, payload)

        async def fake_get(self, url, headers=None):
            return resp

        monkeypatch.setattr("httpx.AsyncClient.get", fake_get)

        entries = await XBRLClient.get_shares_outstanding("0000000005")
        assert entries == []

    @pytest.mark.asyncio
    async def test_falls_through_when_sanity_filter_removes_all(self, monkeypatch):
        """FNKO case: CommonStockSharesOutstanding has only placeholder entries
        (e.g., 100 shares from S-1 registration). Must fall through to next
        concept instead of returning empty."""
        from ingestion.sec_edgar.xbrl_client import XBRLClient

        payload = {
            "facts": {
                "us-gaap": {
                    # Placeholders — all below 100k threshold
                    "CommonStockSharesOutstanding": {
                        "units": {
                            "shares": [
                                {"end": "2017-09-30", "val": 100, "form": "10-K",
                                 "fy": 2017, "fp": "FY", "accn": "X-1"},
                                {"end": "2017-12-31", "val": 50, "form": "10-Q",
                                 "fy": 2017, "fp": "Q4", "accn": "X-2"},
                            ]
                        }
                    },
                    # The real data lives here
                    "WeightedAverageNumberOfSharesOutstandingBasic": {
                        "units": {
                            "shares": [
                                {"end": "2024-12-31", "val": 52_000_000, "form": "10-K",
                                 "fy": 2024, "fp": "FY", "accn": "Y-1"},
                            ]
                        }
                    },
                }
            }
        }
        resp = self._build_mock_response(200, payload)

        async def fake_get(self, url, headers=None):
            return resp

        monkeypatch.setattr("httpx.AsyncClient.get", fake_get)

        entries = await XBRLClient.get_shares_outstanding("0001704711")
        assert len(entries) == 1
        assert entries[0].shares == 52_000_000  # got the WeightedAvg fallback

    @pytest.mark.asyncio
    async def test_pads_cik_to_10_digits(self, monkeypatch):
        """Short CIK inputs are padded to 10 digits in the URL."""
        from ingestion.sec_edgar.xbrl_client import XBRLClient

        captured_url = {}

        async def fake_get(self, url, headers=None):
            captured_url["url"] = url
            resp = MagicMock()
            resp.status_code = 404
            resp.text = ""
            return resp

        monkeypatch.setattr("httpx.AsyncClient.get", fake_get)

        await XBRLClient.get_shares_outstanding("320193")  # Apple, unpadded
        assert "CIK0000320193.json" in captured_url["url"]
