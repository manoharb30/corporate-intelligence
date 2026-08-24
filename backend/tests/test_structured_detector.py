"""Tests for the post-classification structured-deal detector.

The detector exists to catch director-allocation blocks that look like a real
insider cluster: several insiders buying the same issuer on the same day at
what is effectively one price.

Regression anchor: CODI (CIK 0001345126) produced this pattern twice. Both
times the transactions were stored GENUINE because the detector keyed on exact
price equality, and the reported prices were per-filing weighted averages that
differed in the fourth decimal. The 2023-01-03 block reached a live strong_buy
signal that had to be invalidated by hand.

Counter-anchor: NEWT 2024-06-17 must NOT be flagged. Three insiders each bought
a 1,000-share round lot that day, but at three different prices — ordinary
open-market buying, not an allocation.
"""

import pytest

from merge_classifications import detect_structured_clusters


def txn(insider, price, *, issuer="ACME CORP", date="2026-01-15",
        classification="GENUINE", shares=1000, value=None):
    return {
        "accession": f"acc-{insider}-{price}",
        "issuer": issuer,
        "insider": insider,
        "transaction_date": date,
        "price_per_share": price,
        "shares": shares,
        "total_value": value if value is not None else shares * price,
        "classification": classification,
        "reason": "open market purchase",
        "rule_triggered": "LLM",
    }


def flagged(results):
    return [r for r in results if r["rule_triggered"] == "POST_CLUSTER_CHECK"]


class TestKnownStructuredBlocks:
    """The two CODI events that defeated the exact-price key."""

    def test_codi_2024_weighted_average_block_is_flagged(self):
        # Seven directors, one allocation, weighted-average prices spanning
        # $21.3947-$21.4036 — a 0.042% spread.
        prices = [21.3947, 21.3957, 21.3961, 21.3974, 21.3983, 21.3987, 21.4036]
        results = [txn(f"director-{i}", p, issuer="COMPASS DIVERSIFIED HOLDINGS",
                       date="2024-01-18") for i, p in enumerate(prices)]

        count = detect_structured_clusters(results)

        assert count == 7
        assert all(r["classification"] == "AMBIGUOUS" for r in results)
        assert all(r["rule_triggered"] == "POST_CLUSTER_CHECK" for r in results)

    def test_codi_2023_weighted_average_block_is_flagged(self):
        prices = [19.125, 19.126, 19.128, 19.129, 19.130, 19.131, 19.133, 19.134]
        results = [txn(f"director-{i}", p, issuer="COMPASS DIVERSIFIED HOLDINGS",
                       date="2023-01-03") for i, p in enumerate(prices)]

        assert detect_structured_clusters(results) == 8
        assert all(r["classification"] == "AMBIGUOUS" for r in results)


class TestGenuineClustersAreLeftAlone:
    """False positives here silently delete real signals, so guard them."""

    def test_newt_round_lots_at_different_prices_not_flagged(self):
        # Identical 1,000-share counts, but three genuinely different prices.
        results = [
            txn("PRICE MICHAEL SCOTT", 12.5798, issuer="NEWTEK", date="2024-06-17"),
            txn("SLOANE BARRY", 12.917, issuer="NEWTEK", date="2024-06-17"),
            txn("Zink Gregory L", 12.92, issuer="NEWTEK", date="2024-06-17"),
        ]

        assert detect_structured_clusters(results) == 0
        assert all(r["classification"] == "GENUINE" for r in results)

    def test_two_insiders_at_one_price_is_not_enough(self):
        results = [txn("a", 10.0), txn("b", 10.0)]

        assert detect_structured_clusters(results) == 0

    def test_one_insider_filing_three_fills_is_not_a_cluster(self):
        # Distinct-insider count is what matters, not row count.
        results = [txn("solo", 10.0), txn("solo", 10.0), txn("solo", 10.0)]

        assert detect_structured_clusters(results) == 0

    def test_same_price_different_days_not_grouped(self):
        results = [
            txn("a", 10.0, date="2026-01-15"),
            txn("b", 10.0, date="2026-01-16"),
            txn("c", 10.0, date="2026-01-17"),
        ]

        assert detect_structured_clusters(results) == 0

    def test_same_price_different_issuers_not_grouped(self):
        results = [
            txn("a", 10.0, issuer="ACME"),
            txn("b", 10.0, issuer="BETA"),
            txn("c", 10.0, issuer="GAMMA"),
        ]

        assert detect_structured_clusters(results) == 0


class TestBehaviourPreserved:
    """Existing exact-price behaviour must survive the tolerance change."""

    def test_three_insiders_at_exactly_one_price_still_flagged(self):
        results = [txn("a", 10.0), txn("b", 10.0), txn("c", 10.0)]

        assert detect_structured_clusters(results) == 3
        assert all(r["classification"] == "AMBIGUOUS" for r in results)

    def test_non_genuine_rows_are_never_touched(self):
        results = [
            txn("a", 10.0, classification="NOT_GENUINE"),
            txn("b", 10.0, classification="NOT_GENUINE"),
            txn("c", 10.0, classification="NOT_GENUINE"),
        ]

        assert detect_structured_clusters(results) == 0
        assert all(r["classification"] == "NOT_GENUINE" for r in results)

    def test_rows_missing_price_or_date_are_skipped_not_crashed(self):
        results = [
            txn("a", 0),
            {"issuer": "ACME", "insider": "b", "classification": "GENUINE",
             "total_value": 1, "accession": "x", "reason": "", "rule_triggered": "LLM"},
            txn("c", 10.0),
        ]

        assert detect_structured_clusters(results) == 0


class TestToleranceBand:
    """The band is deliberately tight: it is a fraud tell, not a price filter."""

    def test_insiders_spread_wider_than_the_band_are_not_flagged(self):
        # 1% apart — normal intraday dispersion between three buyers.
        results = [txn("a", 10.00), txn("b", 10.05), txn("c", 10.10)]

        assert detect_structured_clusters(results) == 0

    def test_only_the_tight_subgroup_is_flagged(self):
        # Three insiders in a tight block plus two ordinary buyers far away.
        results = [
            txn("block-1", 50.0000),
            txn("block-2", 50.0100),
            txn("block-3", 50.0150),
            txn("ordinary-1", 51.4000),
            txn("ordinary-2", 52.7000),
        ]

        count = detect_structured_clusters(results)

        assert count == 3
        assert {r["insider"] for r in flagged(results)} == {
            "block-1", "block-2", "block-3"}
        assert [r["classification"] for r in results
                if r["insider"].startswith("ordinary")] == ["GENUINE", "GENUINE"]

    def test_wide_day_does_not_chain_into_one_group(self):
        # Prices each within tolerance of their neighbour but spanning far more
        # than the band overall — single-linkage chaining would flag all five.
        results = [
            txn("a", 100.00),
            txn("b", 100.09),
            txn("c", 100.18),
            txn("d", 100.27),
            txn("e", 100.36),
        ]

        count = detect_structured_clusters(results)

        assert count == 0, "prices must sit inside one band, not chain across it"

    def test_big_buyer_working_an_order_does_not_drag_in_tag_alongs(self):
        # AMRZ 2025-08-08: the CEO bought ~$23M across $46.22-$47.54 in many
        # fills, and two small buyers happened to trade inside 0.06% of one of
        # them. A participant in an allocation reports ONE weighted-average
        # price; someone working an order all day does not.
        results = [
            txn("Poletti", 46.22, shares=1280),
            txn("Brouwer", 46.25, shares=1000),
            txn("Jenisch", 46.25, shares=100000),
            txn("Jenisch", 46.38, shares=99546),
            txn("Jenisch", 47.40, shares=40000),
            txn("Jenisch", 47.54, shares=60000),
        ]

        assert detect_structured_clusters(results) == 0
        assert all(r["classification"] == "GENUINE" for r in results)

    def test_exact_price_match_survives_an_extra_odd_lot(self):
        # AUBN quarterly director plan: three directors at exactly $18.0778,
        # one of whom also has a small separate fill at another price. Exact
        # price agreement is a tell on its own and must not be lost.
        results = [
            txn("Barrett J Tutt", 17.7389, shares=34),
            txn("Barrett J Tutt", 18.0778, shares=67),
            txn("HAM WILLIAM F JR", 18.0778, shares=63),
            txn("HOUSEL DAVID E", 18.0778, shares=48),
        ]

        count = detect_structured_clusters(results)

        assert count == 3
        assert {r["insider"] for r in flagged(results)} == {
            "Barrett J Tutt", "HAM WILLIAM F JR", "HOUSEL DAVID E"}
        odd_lot = next(r for r in results if r["price_per_share"] == 17.7389)
        assert odd_lot["classification"] == "GENUINE"

    def test_allocation_participants_each_report_one_price(self):
        # Same three insiders, each with a single weighted-average fill.
        results = [txn("a", 46.22), txn("b", 46.25), txn("c", 46.25)]

        assert detect_structured_clusters(results) == 3

    def test_reason_records_the_band_not_a_single_price(self):
        results = [txn("a", 21.3947), txn("b", 21.3983), txn("c", 21.4036)]

        detect_structured_clusters(results)

        reason = results[0]["reason"]
        assert "3 insiders" in reason
        assert "21.3947" in reason and "21.4036" in reason


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
