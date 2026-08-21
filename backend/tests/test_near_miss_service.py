"""Tests for near_miss_service — the Research Queue.

These cover clusters dropped *solely* on earnings proximity: rows the LLM already
classified GENUINE, which merge_classifications.py then rewrote to
classification='FILTERED' with classification_rule='EARNINGS_FILTER'.

No existing fixture builds a row in that state, so _make_filtered_trade() below is
the FILTERED-state factory for this suite.
"""

import pytest
from unittest.mock import AsyncMock, patch

from app.services.insider_cluster_service import (
    EXCLUDED_CIKS,
    MIN_CLUSTER_INSIDERS,
    MIN_CLUSTER_VALUE_USD,
    MIN_MARKET_CAP_USD,
    MAX_MARKET_CAP_USD,
    CLUSTER_WINDOW_DAYS,
)


# === FILTERED-state fixture factory ===

def _make_filtered_trade(
    insider_name,
    value,
    date,
    cik="0001234567",
    ticker="TEST",
    company_name="Test Corp",
    market_cap=1_000_000_000,
    title="Director",
    classification="FILTERED",
    classification_rule="EARNINGS_FILTER",
    classification_reason="Earnings in 98d",
):
    """One InsiderTransaction row in the FILTERED / EARNINGS_FILTER state.

    Property names mirror the write path in ingest_genuine_p_to_neo4j.py
    (classification / classification_rule / classification_reason) plus the
    Company.market_cap carried by the join.
    """
    return {
        "cik": cik,
        "company_name": company_name,
        "ticker": ticker,
        "transaction_date": date,
        "transaction_code": "P",
        "total_value": value,
        "shares": int(value / 10) if value else 0,
        "insider_name": insider_name,
        "insider_title": title,
        "market_cap": market_cap,
        "classification": classification,
        "classification_rule": classification_rule,
        "classification_reason": classification_reason,
    }


def _two_buyers(**overrides):
    """Minimal qualifying near-miss: 2 insiders, $200K, 12 days apart."""
    return [
        _make_filtered_trade("ALPHA JANE", 120_000, "2026-08-01", **overrides),
        _make_filtered_trade("BETA JOHN", 80_000, "2026-08-13", **overrides),
    ]


class TestFixtureFactory:
    """The factory itself must produce the state the page depends on."""

    def test_row_is_filtered_by_the_earnings_rule(self):
        row = _make_filtered_trade("ALPHA JANE", 120_000, "2026-08-01")
        assert row["classification"] == "FILTERED"
        assert row["classification_rule"] == "EARNINGS_FILTER"


class TestThresholdsAreImportedNotRedeclared:
    """Gates must be the same objects the live cluster service uses."""

    def test_service_reuses_cluster_service_thresholds(self):
        from app.services import near_miss_service as nm
        from app.services import insider_cluster_service as ics

        assert nm.MIN_CLUSTER_INSIDERS is ics.MIN_CLUSTER_INSIDERS
        assert nm.MIN_CLUSTER_VALUE_USD is ics.MIN_CLUSTER_VALUE_USD
        assert nm.MIN_MARKET_CAP_USD is ics.MIN_MARKET_CAP_USD
        assert nm.MAX_MARKET_CAP_USD is ics.MAX_MARKET_CAP_USD
        assert nm.CLUSTER_WINDOW_DAYS is ics.CLUSTER_WINDOW_DAYS

    def test_threshold_values_match_the_documented_signal_model(self):
        assert MIN_CLUSTER_INSIDERS == 2
        assert MIN_CLUSTER_VALUE_USD == 100_000
        assert MIN_MARKET_CAP_USD == 300_000_000
        assert MAX_MARKET_CAP_USD == 5_000_000_000
        assert CLUSTER_WINDOW_DAYS == 30


# === Pure aggregation: build_near_misses(rows) ===

class TestBuildNearMissesGates:
    def test_two_insiders_over_100k_qualifies(self):
        from app.services.near_miss_service import NearMissService

        out = NearMissService.build_near_misses(_two_buyers())
        assert len(out) == 1
        assert out[0].ticker == "TEST"
        assert out[0].insider_count == 2
        assert out[0].total_value == 200_000

    def test_solo_buyer_is_dropped(self):
        from app.services.near_miss_service import NearMissService

        rows = [_make_filtered_trade("ALPHA JANE", 500_000, "2026-08-01")]
        assert NearMissService.build_near_misses(rows) == []

    def test_same_insider_twice_is_still_one_insider(self):
        from app.services.near_miss_service import NearMissService

        rows = [
            _make_filtered_trade("ALPHA JANE", 300_000, "2026-08-01"),
            _make_filtered_trade("ALPHA JANE", 300_000, "2026-08-05"),
        ]
        assert NearMissService.build_near_misses(rows) == []

    def test_below_value_floor_is_dropped(self):
        from app.services.near_miss_service import NearMissService

        rows = [
            _make_filtered_trade("ALPHA JANE", 40_000, "2026-08-01"),
            _make_filtered_trade("BETA JOHN", 50_000, "2026-08-05"),
        ]
        assert NearMissService.build_near_misses(rows) == []

    def test_value_floor_is_inclusive(self):
        from app.services.near_miss_service import NearMissService

        rows = [
            _make_filtered_trade("ALPHA JANE", 50_000, "2026-08-01"),
            _make_filtered_trade("BETA JOHN", 50_000, "2026-08-05"),
        ]
        assert len(NearMissService.build_near_misses(rows)) == 1

    def test_below_mcap_floor_is_dropped(self):
        from app.services.near_miss_service import NearMissService

        assert NearMissService.build_near_misses(_two_buyers(market_cap=299_000_000)) == []

    def test_above_mcap_ceiling_is_dropped(self):
        from app.services.near_miss_service import NearMissService

        assert NearMissService.build_near_misses(_two_buyers(market_cap=5_100_000_000)) == []

    def test_mcap_bounds_are_inclusive(self):
        from app.services.near_miss_service import NearMissService

        assert len(NearMissService.build_near_misses(_two_buyers(market_cap=300_000_000))) == 1
        assert len(NearMissService.build_near_misses(_two_buyers(market_cap=5_000_000_000))) == 1

    def test_missing_market_cap_is_dropped(self):
        from app.services.near_miss_service import NearMissService

        assert NearMissService.build_near_misses(_two_buyers(market_cap=None)) == []
        assert NearMissService.build_near_misses(_two_buyers(market_cap=0)) == []

    def test_blocklisted_cik_is_dropped(self):
        from app.services.near_miss_service import NearMissService

        blocked = sorted(EXCLUDED_CIKS)[0]
        assert NearMissService.build_near_misses(_two_buyers(cik=blocked)) == []


class TestBuildNearMissesWindow:
    def test_trades_outside_30_day_window_do_not_form_a_cluster(self):
        from app.services.near_miss_service import NearMissService

        rows = [
            _make_filtered_trade("ALPHA JANE", 150_000, "2026-07-01"),
            _make_filtered_trade("BETA JOHN", 150_000, "2026-08-13"),  # 43 days later
        ]
        assert NearMissService.build_near_misses(rows) == []

    def test_window_edge_is_inclusive(self):
        from app.services.near_miss_service import NearMissService

        rows = [
            _make_filtered_trade("ALPHA JANE", 150_000, "2026-07-14"),
            _make_filtered_trade("BETA JOHN", 150_000, "2026-08-13"),  # exactly 30 days
        ]
        out = NearMissService.build_near_misses(rows)
        assert len(out) == 1
        assert out[0].window_start == "2026-07-14"
        assert out[0].window_end == "2026-08-13"

    def test_out_of_window_trade_is_excluded_from_totals(self):
        from app.services.near_miss_service import NearMissService

        rows = [
            _make_filtered_trade("OLD HAND", 900_000, "2026-05-01"),
            _make_filtered_trade("ALPHA JANE", 150_000, "2026-08-01"),
            _make_filtered_trade("BETA JOHN", 150_000, "2026-08-13"),
        ]
        out = NearMissService.build_near_misses(rows)
        assert len(out) == 1
        assert out[0].total_value == 300_000
        assert out[0].insider_count == 2

    def test_timezone_suffixed_dates_are_truncated(self):
        from app.services.near_miss_service import NearMissService

        rows = [
            _make_filtered_trade("ALPHA JANE", 150_000, "2026-08-01T00:00:00-05:00"),
            _make_filtered_trade("BETA JOHN", 150_000, "2026-08-13-05:00"),
        ]
        out = NearMissService.build_near_misses(rows)
        assert len(out) == 1
        assert out[0].window_start == "2026-08-01"
        assert out[0].window_end == "2026-08-13"


class TestBuildNearMissesPremise:
    """The page's whole claim is 'rejected on timing alone'."""

    def test_rows_not_filtered_by_the_earnings_rule_are_dropped(self):
        from app.services.near_miss_service import NearMissService

        rows = [
            _make_filtered_trade(
                "ALPHA JANE", 150_000, "2026-08-01",
                classification="FILTERED", classification_rule="STRUCTURED_DEAL",
                classification_reason="Private placement",
            ),
            _make_filtered_trade(
                "BETA JOHN", 150_000, "2026-08-05",
                classification="FILTERED", classification_rule="STRUCTURED_DEAL",
                classification_reason="Private placement",
            ),
        ]
        assert NearMissService.build_near_misses(rows) == []

    def test_genuine_rows_are_dropped(self):
        from app.services.near_miss_service import NearMissService

        rows = [
            _make_filtered_trade(
                "ALPHA JANE", 150_000, "2026-08-01",
                classification="GENUINE", classification_rule=None,
                classification_reason="Open-market purchase",
            ),
            _make_filtered_trade(
                "BETA JOHN", 150_000, "2026-08-05",
                classification="GENUINE", classification_rule=None,
                classification_reason="Open-market purchase",
            ),
        ]
        assert NearMissService.build_near_misses(rows) == []

    def test_mixed_rows_count_only_the_earnings_filtered_ones(self):
        from app.services.near_miss_service import NearMissService

        rows = _two_buyers() + [
            _make_filtered_trade(
                "GAMMA GREY", 900_000, "2026-08-06",
                classification="GENUINE", classification_rule=None,
            )
        ]
        out = NearMissService.build_near_misses(rows)
        assert len(out) == 1
        assert out[0].insider_count == 2
        assert out[0].total_value == 200_000


class TestCommitmentRanking:
    """Default sort = insider commitment as % of market cap (KMPR vs CDNL)."""

    def test_pct_of_mcap_is_computed(self):
        from app.services.near_miss_service import NearMissService

        out = NearMissService.build_near_misses(_two_buyers(market_cap=1_000_000_000))
        assert out[0].pct_of_mcap == pytest.approx(0.02)

    def test_default_sort_is_pct_of_mcap_descending(self):
        from app.services.near_miss_service import NearMissService

        trivial = _two_buyers(
            cik="0000860748", ticker="KMPR", company_name="Kemper", market_cap=4_000_000_000
        )  # $200K on $4B = 0.005%
        extraordinary = [
            _make_filtered_trade(
                "CDNL ONE", 4_000_000, "2026-08-04",
                cik="0001973266", ticker="CDNL", company_name="Cardinal", market_cap=800_000_000,
            ),
            _make_filtered_trade(
                "CDNL TWO", 4_250_000, "2026-08-05",
                cik="0001973266", ticker="CDNL", company_name="Cardinal", market_cap=800_000_000,
            ),
        ]  # $8.25M on $800M = 1.03%
        out = NearMissService.build_near_misses(trivial + extraordinary)
        assert [n.ticker for n in out] == ["CDNL", "KMPR"]
        assert out[0].pct_of_mcap > out[1].pct_of_mcap

    def test_buyers_are_listed_with_role_and_value(self):
        from app.services.near_miss_service import NearMissService

        rows = [
            _make_filtered_trade("ALPHA JANE", 120_000, "2026-08-01", title="Chief Executive Officer"),
            _make_filtered_trade("BETA JOHN", 80_000, "2026-08-13", title="Director"),
        ]
        out = NearMissService.build_near_misses(rows)
        buyers = {b.insider_name: b for b in out[0].buyers}
        assert buyers["ALPHA JANE"].role == "officer"
        assert buyers["BETA JOHN"].role == "director"
        assert buyers["ALPHA JANE"].value == 120_000


class TestResearchNoteJoin:
    def test_notes_attach_by_cik(self):
        from app.services.near_miss_service import NearMissService

        note = {"note_date": "2026-08-19", "verdict": "watch", "thesis": "C-suite bought the print.",
                "risk_flags": ["recent_dilution"], "catalysts": [], "sources": []}
        out = NearMissService.build_near_misses(
            _two_buyers(cik="0001234567"), notes_by_cik={"0001234567": [note]}
        )
        assert out[0].research_notes == [note]
        assert out[0].verdict == "watch"

    def test_no_note_yields_empty_list_and_no_verdict(self):
        from app.services.near_miss_service import NearMissService

        out = NearMissService.build_near_misses(_two_buyers())
        assert out[0].research_notes == []
        assert out[0].verdict is None

    def test_notes_lookup_is_cik_zero_padded(self):
        from app.services.near_miss_service import NearMissService

        note = {"note_date": "2026-08-19", "verdict": "pass", "thesis": "Family entities.",
                "risk_flags": [], "catalysts": [], "sources": []}
        out = NearMissService.build_near_misses(
            _two_buyers(cik="1234567"), notes_by_cik={"0001234567": [note]}
        )
        assert out[0].research_notes == [note]


# === Async read path (live compute, mocked DB) ===

class TestGetNearMisses:
    @pytest.mark.asyncio
    async def test_computes_live_from_transactions_and_joins_notes(self):
        from app.services.near_miss_service import NearMissService

        with patch("app.services.near_miss_service.Neo4jClient") as mock_db, \
             patch("app.services.near_miss_service.ResearchNoteService") as mock_notes:
            mock_db.execute_query = AsyncMock(return_value=_two_buyers())
            mock_notes.get_notes_for_ciks = AsyncMock(return_value={})

            out = await NearMissService.get_near_misses(since_date="2026-07-01")

        assert len(out) == 1
        assert out[0]["ticker"] == "TEST"
        assert out[0]["insider_count"] == 2
        assert out[0]["research_notes"] == []
        # one aggregation query over raw transactions — no precomputed snapshot blob
        assert mock_db.execute_query.await_count == 1
        cypher = mock_db.execute_query.await_args.args[0]
        assert "InsiderTransaction" in cypher
        assert "Snapshot" not in cypher

    @pytest.mark.asyncio
    async def test_notes_are_fetched_only_for_surviving_ciks(self):
        from app.services.near_miss_service import NearMissService

        rows = _two_buyers() + [
            _make_filtered_trade("SOLO SAM", 900_000, "2026-08-02",
                                 cik="0009999999", ticker="SOLO")
        ]
        with patch("app.services.near_miss_service.Neo4jClient") as mock_db, \
             patch("app.services.near_miss_service.ResearchNoteService") as mock_notes:
            mock_db.execute_query = AsyncMock(return_value=rows)
            mock_notes.get_notes_for_ciks = AsyncMock(return_value={})

            await NearMissService.get_near_misses(since_date="2026-07-01")

        assert mock_notes.get_notes_for_ciks.await_args.args[0] == ["0001234567"]

    @pytest.mark.asyncio
    async def test_empty_result_skips_the_note_lookup(self):
        from app.services.near_miss_service import NearMissService

        with patch("app.services.near_miss_service.Neo4jClient") as mock_db, \
             patch("app.services.near_miss_service.ResearchNoteService") as mock_notes:
            mock_db.execute_query = AsyncMock(return_value=[])
            mock_notes.get_notes_for_ciks = AsyncMock(return_value={})

            out = await NearMissService.get_near_misses(since_date="2026-07-01")

        assert out == []
        mock_notes.get_notes_for_ciks.assert_not_awaited()
