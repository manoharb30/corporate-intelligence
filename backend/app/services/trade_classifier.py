"""Shared trade type classification utility.

Classifies SEC Form 4 transaction codes into semantic trade types,
with special handling for exercise (M) transactions that require
same-day grouping to determine if it's exercise+hold vs exercise+sell.
"""

# Trade type constants
BULLISH_TRADE_TYPES = {"buy", "exercise_hold"}
BEARISH_TRADE_TYPES = {"sell", "disposition"}
NEUTRAL_TRADE_TYPES = {"exercise_sell", "award", "tax", "gift", "conversion", "will", "other"}

# Simple code → trade_type mapping (for codes that don't need context)
_SIMPLE_CODE_MAP = {
    "P": "buy",
    "S": "sell",
    "A": "award",
    "D": "disposition",
    "G": "gift",
    "C": "conversion",
    "W": "will",
}


def classify_trade(code: str, same_day_codes: set[str] | None = None) -> str:
    """Classify a single transaction code into a trade type.

    Args:
        code: SEC transaction code (P, S, M, A, F, D, G, C, W)
        same_day_codes: Set of all transaction codes for the same (person, date).
                        Required for M and F codes to determine context.

    Returns:
        Trade type string: buy, sell, exercise_hold, exercise_sell, award,
        tax, disposition, gift, conversion, will, or other.
    """
    code = (code or "").strip().upper()

    if code in _SIMPLE_CODE_MAP:
        return _SIMPLE_CODE_MAP[code]

    if code == "M":
        if same_day_codes and "S" in same_day_codes:
            return "exercise_sell"
        return "exercise_hold"

    if code == "F":
        # F alone = tax withholding; F with M = part of exercise (M classifies itself)
        return "tax"

    return "other"


def classify_trades_batch(
    trades: list[dict],
    name_key: str = "insider_name",
    date_key: str = "transaction_date",
    code_key: str = "transaction_code",
) -> list[str]:
    """Classify a batch of trades, using same-day grouping for context.

    Groups trades by (person, date) to build code sets, then classifies
    each trade individually using that context.

    Args:
        trades: List of trade dicts.
        name_key: Key for insider name in each dict.
        date_key: Key for transaction date in each dict.
        code_key: Key for transaction code in each dict.

    Returns:
        List of trade_type strings, one per input trade, in the same order.
    """
    # Build {(name, date): set_of_codes} index
    group_codes: dict[tuple[str, str], set[str]] = {}
    for t in trades:
        name = (t.get(name_key) or "").strip().upper()
        date = (t.get(date_key) or "").strip()
        code = (t.get(code_key) or "").strip().upper()
        if name and date and code:
            key = (name, date)
            if key not in group_codes:
                group_codes[key] = set()
            group_codes[key].add(code)

    # Classify each trade
    result = []
    for t in trades:
        name = (t.get(name_key) or "").strip().upper()
        date = (t.get(date_key) or "").strip()
        code = (t.get(code_key) or "").strip().upper()
        same_day = group_codes.get((name, date))
        result.append(classify_trade(code, same_day))

    return result


def is_bullish_trade(trade_type: str) -> bool:
    """Check if a trade type is bullish (buy or exercise & hold)."""
    return trade_type in BULLISH_TRADE_TYPES


def is_bearish_trade(trade_type: str) -> bool:
    """Check if a trade type is bearish (sell or disposition)."""
    return trade_type in BEARISH_TRADE_TYPES
