"""Tests for compound signal scoring and decision logic."""

import pytest
from app.services.compound_signal_service import (
    score_compound,
    decide_action,
    CompoundSignal,
)


class TestScoreCompound:
    """Tests for score_compound() scoring function."""

    def test_two_source_base_score(self):
        """2-source compound starts at 60."""
        sc = score_compound(
            activist_pct=5.0, insider_value=50_000, insider_count=2,
            has_8k=False, timing_gap_days=20, source_count=2,
        )
        assert sc == 60

    def test_three_source_base_score(self):
        """3-source compound starts at 85."""
        sc = score_compound(
            activist_pct=5.0, insider_value=50_000, insider_count=2,
            has_8k=False, timing_gap_days=20, source_count=3,
        )
        assert sc == 85

    def test_activist_pct_bonus_high(self):
        """Activist >10% gets +10 bonus."""
        sc = score_compound(
            activist_pct=12.0, insider_value=50_000, insider_count=2,
            has_8k=False, timing_gap_days=20, source_count=2,
        )
        assert sc == 70  # 60 + 10

    def test_activist_pct_bonus_medium(self):
        """Activist 7-10% gets +5 bonus."""
        sc = score_compound(
            activist_pct=8.0, insider_value=50_000, insider_count=2,
            has_8k=False, timing_gap_days=20, source_count=2,
        )
        assert sc == 65  # 60 + 5

    def test_insider_value_bonus_high(self):
        """Insider value >$500K gets +10 bonus."""
        sc = score_compound(
            activist_pct=5.0, insider_value=600_000, insider_count=3,
            has_8k=False, timing_gap_days=20, source_count=2,
        )
        assert sc == 70  # 60 + 10

    def test_insider_value_bonus_medium(self):
        """Insider value >$100K gets +5 bonus."""
        sc = score_compound(
            activist_pct=5.0, insider_value=200_000, insider_count=3,
            has_8k=False, timing_gap_days=20, source_count=2,
        )
        assert sc == 65  # 60 + 5

    def test_timing_proximity_bonus_tight(self):
        """Timing <=7 days gets +10 bonus."""
        sc = score_compound(
            activist_pct=5.0, insider_value=50_000, insider_count=2,
            has_8k=False, timing_gap_days=5, source_count=2,
        )
        assert sc == 70  # 60 + 10

    def test_timing_proximity_bonus_moderate(self):
        """Timing 8-14 days gets +5 bonus."""
        sc = score_compound(
            activist_pct=5.0, insider_value=50_000, insider_count=2,
            has_8k=False, timing_gap_days=10, source_count=2,
        )
        assert sc == 65  # 60 + 5

    def test_8k_bonus(self):
        """8-K material agreement presence gets +5 bonus."""
        sc = score_compound(
            activist_pct=5.0, insider_value=50_000, insider_count=2,
            has_8k=True, timing_gap_days=20, source_count=2,
        )
        assert sc == 65  # 60 + 5

    def test_max_score_capped_at_100(self):
        """Score is capped at 100 even with all bonuses."""
        sc = score_compound(
            activist_pct=15.0, insider_value=1_000_000, insider_count=5,
            has_8k=True, timing_gap_days=3, source_count=3,
        )
        assert sc == 100  # 85 + 10 + 10 + 10 + 5 = 120 → capped at 100

    def test_all_bonuses_combined_two_source(self):
        """All bonuses on 2-source: 60 + 10 + 10 + 10 + 5 = 95."""
        sc = score_compound(
            activist_pct=12.0, insider_value=600_000, insider_count=3,
            has_8k=True, timing_gap_days=5, source_count=2,
        )
        assert sc == 95

    def test_typical_insider_activist(self):
        """Typical insider_activist: 2 source, moderate activist, decent timing."""
        sc = score_compound(
            activist_pct=7.5, insider_value=250_000, insider_count=3,
            has_8k=False, timing_gap_days=12, source_count=2,
        )
        # 60 + 5 (pct 7-10) + 5 (value >100k) + 5 (timing 8-14) = 75
        assert sc == 75


class TestDecideAction:
    """Tests for decide_action()."""

    def test_buy_high_score(self):
        assert decide_action("insider_activist", 80) == "BUY"

    def test_buy_threshold(self):
        assert decide_action("insider_activist", 70) == "BUY"

    def test_watch_medium_score(self):
        assert decide_action("insider_activist", 60) == "WATCH"

    def test_watch_threshold(self):
        assert decide_action("insider_activist", 50) == "WATCH"

    def test_pass_low_score(self):
        assert decide_action("insider_activist", 40) == "PASS"

    def test_sell_always_pass(self):
        """Sell compound always returns PASS regardless of score."""
        assert decide_action("insider_activist_sell", 90) == "PASS"
        assert decide_action("insider_activist_sell", 50) == "PASS"

    def test_triple_convergence_buy(self):
        assert decide_action("triple_convergence", 85) == "BUY"

    def test_activist_8k_watch(self):
        assert decide_action("activist_8k", 65) == "WATCH"


class TestCompoundSignalDataclass:
    """Tests for CompoundSignal dataclass."""

    def test_accession_number_format(self):
        sig = CompoundSignal(
            cik="0001234567", company_name="Test Corp", ticker="TEST",
            compound_type="insider_activist", score=75,
            signal_date="2026-02-15",
        )
        assert sig.accession_number == "COMPOUND-0001234567-2026-02-15"

    def test_to_dict_keys(self):
        sig = CompoundSignal(
            cik="0001234567", company_name="Test Corp", ticker="TEST",
            compound_type="triple_convergence", score=90,
            signal_date="2026-02-15",
            one_liner="3 insiders buying + activist 12% stake + material agreement",
            decision="BUY",
        )
        d = sig.to_dict()
        assert d["cik"] == "0001234567"
        assert d["compound_type"] == "triple_convergence"
        assert d["score"] == 90
        assert d["decision"] == "BUY"
        assert d["one_liner"].startswith("3 insiders")
        assert d["accession_number"] == "COMPOUND-0001234567-2026-02-15"

    def test_default_values(self):
        sig = CompoundSignal(
            cik="123", company_name="X", ticker=None,
            compound_type="activist_8k", score=60,
            signal_date="2026-01-01",
        )
        assert sig.decision == "WATCH"
        assert sig.components == []
        assert sig.activist_filing is None
        assert sig.insider_context is None
        assert sig.event_context is None
