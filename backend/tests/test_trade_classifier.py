"""Tests for trade_classifier module."""

import pytest

from app.services.trade_classifier import (
    BULLISH_TRADE_TYPES,
    BEARISH_TRADE_TYPES,
    classify_trade,
    classify_trades_batch,
    is_bullish_trade,
    is_bearish_trade,
)


# --- classify_trade ---

class TestClassifyTrade:
    def test_purchase(self):
        assert classify_trade("P") == "buy"

    def test_sale(self):
        assert classify_trade("S") == "sell"

    def test_award(self):
        assert classify_trade("A") == "award"

    def test_disposition(self):
        assert classify_trade("D") == "disposition"

    def test_gift(self):
        assert classify_trade("G") == "gift"

    def test_conversion(self):
        assert classify_trade("C") == "conversion"

    def test_will(self):
        assert classify_trade("W") == "will"

    def test_exercise_alone_is_hold(self):
        assert classify_trade("M") == "exercise_hold"
        assert classify_trade("M", same_day_codes={"M"}) == "exercise_hold"

    def test_exercise_with_same_day_sale(self):
        assert classify_trade("M", same_day_codes={"M", "S"}) == "exercise_sell"

    def test_exercise_with_same_day_f(self):
        # F is tax withholding; M + F = exercise_hold (no sale)
        assert classify_trade("M", same_day_codes={"M", "F"}) == "exercise_hold"

    def test_f_alone_is_tax(self):
        assert classify_trade("F") == "tax"

    def test_unknown_code(self):
        assert classify_trade("X") == "other"
        assert classify_trade("") == "other"

    def test_lowercase_code(self):
        assert classify_trade("p") == "buy"
        assert classify_trade("m") == "exercise_hold"


# --- classify_trades_batch ---

class TestClassifyTradesBatch:
    def test_basic_codes(self):
        trades = [
            {"insider_name": "Alice", "transaction_date": "2025-01-01", "transaction_code": "P"},
            {"insider_name": "Bob", "transaction_date": "2025-01-01", "transaction_code": "S"},
            {"insider_name": "Carol", "transaction_date": "2025-01-02", "transaction_code": "A"},
        ]
        result = classify_trades_batch(trades)
        assert result == ["buy", "sell", "award"]

    def test_exercise_hold_no_same_day_sale(self):
        trades = [
            {"insider_name": "Alice", "transaction_date": "2025-01-01", "transaction_code": "M"},
        ]
        result = classify_trades_batch(trades)
        assert result == ["exercise_hold"]

    def test_exercise_sell_same_person_same_day(self):
        trades = [
            {"insider_name": "Alice", "transaction_date": "2025-01-01", "transaction_code": "M"},
            {"insider_name": "Alice", "transaction_date": "2025-01-01", "transaction_code": "S"},
        ]
        result = classify_trades_batch(trades)
        assert result[0] == "exercise_sell"  # M → exercise_sell because Alice also sold
        assert result[1] == "sell"  # S → still sell

    def test_exercise_hold_with_f(self):
        trades = [
            {"insider_name": "Alice", "transaction_date": "2025-01-01", "transaction_code": "M"},
            {"insider_name": "Alice", "transaction_date": "2025-01-01", "transaction_code": "F"},
        ]
        result = classify_trades_batch(trades)
        assert result[0] == "exercise_hold"  # M + F = exercise_hold (tax withholding only)
        assert result[1] == "tax"

    def test_exercise_different_persons_no_cross_pairing(self):
        """M by Alice + S by Bob should NOT make Alice's M an exercise_sell."""
        trades = [
            {"insider_name": "Alice", "transaction_date": "2025-01-01", "transaction_code": "M"},
            {"insider_name": "Bob", "transaction_date": "2025-01-01", "transaction_code": "S"},
        ]
        result = classify_trades_batch(trades)
        assert result[0] == "exercise_hold"  # Alice's M = hold (Bob's sale is irrelevant)
        assert result[1] == "sell"

    def test_exercise_different_dates_no_cross_pairing(self):
        """M on Jan 1 + S on Jan 2 by the same person should NOT pair."""
        trades = [
            {"insider_name": "Alice", "transaction_date": "2025-01-01", "transaction_code": "M"},
            {"insider_name": "Alice", "transaction_date": "2025-01-02", "transaction_code": "S"},
        ]
        result = classify_trades_batch(trades)
        assert result[0] == "exercise_hold"  # Different date → no pairing
        assert result[1] == "sell"

    def test_custom_key_names(self):
        trades = [
            {"name": "Alice", "date": "2025-01-01", "code": "P"},
        ]
        result = classify_trades_batch(trades, name_key="name", date_key="date", code_key="code")
        assert result == ["buy"]

    def test_empty_list(self):
        assert classify_trades_batch([]) == []

    def test_missing_fields(self):
        trades = [
            {"insider_name": None, "transaction_date": "", "transaction_code": "P"},
        ]
        result = classify_trades_batch(trades)
        assert result == ["buy"]

    def test_batch_alignment(self):
        """Result list has same length and order as input."""
        trades = [
            {"insider_name": "A", "transaction_date": "2025-01-01", "transaction_code": "P"},
            {"insider_name": "B", "transaction_date": "2025-01-01", "transaction_code": "S"},
            {"insider_name": "C", "transaction_date": "2025-01-01", "transaction_code": "M"},
            {"insider_name": "D", "transaction_date": "2025-01-01", "transaction_code": "A"},
            {"insider_name": "E", "transaction_date": "2025-01-01", "transaction_code": "D"},
        ]
        result = classify_trades_batch(trades)
        assert len(result) == 5
        assert result == ["buy", "sell", "exercise_hold", "award", "disposition"]


# --- is_bullish_trade / is_bearish_trade ---

class TestSentimentHelpers:
    def test_bullish_types(self):
        assert is_bullish_trade("buy") is True
        assert is_bullish_trade("exercise_hold") is True
        assert is_bullish_trade("sell") is False
        assert is_bullish_trade("exercise_sell") is False
        assert is_bullish_trade("award") is False
        assert is_bullish_trade("other") is False

    def test_bearish_types(self):
        assert is_bearish_trade("sell") is True
        assert is_bearish_trade("disposition") is True
        assert is_bearish_trade("buy") is False
        assert is_bearish_trade("exercise_hold") is False
        assert is_bearish_trade("exercise_sell") is False

    def test_constants_disjoint(self):
        """Bullish and bearish sets should not overlap."""
        assert BULLISH_TRADE_TYPES & BEARISH_TRADE_TYPES == set()
