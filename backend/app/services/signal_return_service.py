"""Service for computing returns for every signal using stored daily prices.

Reads SignalPerformance + Company.price_series from Neo4j. No yfinance calls.
Used by the /performance page to show return for every signal from signal_date to today.
"""

import json
import logging
from datetime import datetime, timedelta
from typing import Optional

from app.db.neo4j_client import Neo4jClient

logger = logging.getLogger(__name__)


def _parse_series(series_json: Optional[str]) -> list[dict]:
    if not series_json:
        return []
    try:
        return json.loads(series_json)
    except (ValueError, TypeError):
        return []


def _find_close_on_or_after(series: list[dict], target_date: str, max_skip: int = 7) -> Optional[float]:
    """Find close on or after target_date, skipping weekends/holidays."""
    if not series:
        return None
    try:
        target = datetime.strptime(target_date, "%Y-%m-%d")
    except (ValueError, TypeError):
        return None

    # Build a date->close lookup once
    by_date = {e.get("d"): float(e.get("c", 0)) for e in series if e.get("d")}

    for skip in range(max_skip + 1):
        check = (target + timedelta(days=skip)).strftime("%Y-%m-%d")
        if check in by_date:
            return by_date[check]
    return None


class SignalReturnService:
    """Compute live returns for signals using stored daily prices."""

    @staticmethod
    async def get_signal_returns(
        direction: Optional[str] = None,
        month: Optional[int] = None,
        year: Optional[int] = None,
        limit: int = 2000,
    ) -> list[dict]:
        """Return all signals with computed returns from signal_date to today.

        Args:
            direction: "buy" or "sell" filter, None for all
            month: 1-12 filter on signal_date month, None for all
            year: 4-digit year filter on signal_date, None for all
            limit: max results

        Returns:
            list of signal dicts with entry_price, current_price, return_pct, etc.
        """
        # Build WHERE clause
        conditions = ["sp.ticker IS NOT NULL", "sp.signal_date IS NOT NULL"]
        params: dict = {"limit": limit}

        if direction in ("buy", "sell"):
            conditions.append("sp.direction = $direction")
            params["direction"] = direction

        if year:
            conditions.append("sp.signal_date STARTS WITH $year_str")
            params["year_str"] = str(year)

        if month and year:
            month_prefix = f"{year}-{month:02d}"
            # Override the year_str condition with the month-prefix one
            conditions = [c for c in conditions if "year_str" not in c]
            conditions.append("sp.signal_date STARTS WITH $month_prefix")
            params["month_prefix"] = month_prefix

        where_clause = " AND ".join(conditions)

        query = f"""
            MATCH (sp:SignalPerformance)
            WHERE {where_clause}
            OPTIONAL MATCH (c:Company {{cik: sp.cik}})
            RETURN sp.signal_id AS signal_id,
                   sp.ticker AS ticker,
                   sp.company_name AS company_name,
                   sp.cik AS cik,
                   sp.signal_date AS signal_date,
                   sp.direction AS direction,
                   sp.signal_level AS signal_level,
                   sp.conviction_tier AS conviction_tier,
                   sp.num_insiders AS num_insiders,
                   sp.total_value AS total_value,
                   sp.industry AS industry,
                   sp.market_cap AS market_cap,
                   sp.is_mature AS is_mature,
                   c.price_series AS price_series
            ORDER BY sp.signal_date DESC
            LIMIT $limit
        """

        results = await Neo4jClient.execute_query(query, params)
        signals = []

        for r in results:
            series = _parse_series(r.get("price_series"))
            if not series:
                continue

            signal_date = r["signal_date"]
            entry = _find_close_on_or_after(series, signal_date)
            if entry is None or entry == 0:
                continue

            # Use most recent close as current price
            latest = series[-1]
            current = float(latest.get("c", 0))
            current_date = latest.get("d", "")
            if current == 0:
                continue

            return_pct = round((current - entry) / entry * 100, 2)

            # Today's change — last vs second-to-last
            today_change = None
            if len(series) >= 2:
                prev = float(series[-2].get("c", 0))
                if prev > 0:
                    today_change = round((current - prev) / prev * 100, 2)

            signals.append({
                "signal_id": r["signal_id"],
                "ticker": r["ticker"],
                "company_name": r["company_name"],
                "cik": r["cik"],
                "signal_date": signal_date,
                "direction": r["direction"],
                "signal_level": r["signal_level"],
                "conviction_tier": r["conviction_tier"],
                "num_insiders": r["num_insiders"],
                "total_value": r["total_value"],
                "industry": r["industry"],
                "market_cap": r["market_cap"],
                "is_mature": r["is_mature"],
                "entry_price": round(entry, 2),
                "current_price": round(current, 2),
                "current_date": current_date,
                "return_pct": return_pct,
                "today_change_pct": today_change,
                "in_profit": (return_pct > 0 and r["direction"] == "buy") or (return_pct < 0 and r["direction"] == "sell"),
            })

        return signals

    @staticmethod
    async def get_summary(
        direction: Optional[str] = None,
        month: Optional[int] = None,
        year: Optional[int] = None,
    ) -> dict:
        """Compute summary stats for the performance page header.

        Returns 4 stat cards: total signals, avg return, total conviction, hit rate.
        """
        signals = await SignalReturnService.get_signal_returns(
            direction=direction, month=month, year=year, limit=5000
        )

        if not signals:
            return {
                "total": 0,
                "buy_count": 0,
                "sell_count": 0,
                "avg_return": 0,
                "total_conviction": 0,
                "hit_rate": 0,
                "in_profit_count": 0,
            }

        buy_count = sum(1 for s in signals if s["direction"] == "buy")
        sell_count = sum(1 for s in signals if s["direction"] == "sell")
        avg_return = round(sum(s["return_pct"] for s in signals) / len(signals), 2)
        total_conviction = sum(abs(s["total_value"] or 0) for s in signals)
        in_profit = sum(1 for s in signals if s["in_profit"])
        hit_rate = round(in_profit / len(signals) * 100, 1) if signals else 0

        return {
            "total": len(signals),
            "buy_count": buy_count,
            "sell_count": sell_count,
            "avg_return": avg_return,
            "total_conviction": total_conviction,
            "hit_rate": hit_rate,
            "in_profit_count": in_profit,
        }
