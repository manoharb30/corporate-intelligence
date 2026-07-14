"""Portfolio service — reads the Alpaca paper account and composes the
Portfolio page snapshot.

Read-only against Alpaca (account, positions, fills, equity history). Signal
context (day-0 price, day-90 exit) comes from SignalPerformance nodes; the gap
between a position's average fill and its signal day-0 price is tracked as
implementation shortfall so live results stay comparable to published stats.

Order execution (3-tranche entry/exit, SGOV sweep) lives in operator scripts,
not here — this service never places orders.
"""

import logging
from datetime import datetime, timedelta
from typing import Any, Optional

import httpx

from app.config import settings
from app.db.neo4j_client import Neo4jClient

logger = logging.getLogger(__name__)

INITIAL_CAPITAL = 100_000.0
SWEEP_SYMBOL = "SGOV"
POSITION_SLICE = 5_000.0


def compute_shortfall(day0_price: Optional[float], avg_fill: Optional[float]) -> Optional[float]:
    """Implementation shortfall in percent: how much worse the avg fill was
    than the signal's day-0 price. Positive = paid up vs day-0."""
    if not day0_price or not avg_fill or day0_price <= 0:
        return None
    return round((avg_fill - day0_price) / day0_price * 100, 2)


def compute_allocation(positions_value: float, sweep_value: float, cash: float) -> dict:
    """Allocation split in percent of total account value."""
    total = positions_value + sweep_value + cash
    if total <= 0:
        return {"positions_pct": 0.0, "sweep_pct": 0.0, "cash_pct": 0.0}
    return {
        "positions_pct": round(positions_value / total * 100, 1),
        "sweep_pct": round(sweep_value / total * 100, 1),
        "cash_pct": round(cash / total * 100, 1),
    }


def day90_exit(actionable_date: Optional[str]) -> tuple[Optional[str], Optional[int]]:
    """Exit date (actionable day-0 + 90) and calendar days remaining."""
    if not actionable_date:
        return None, None
    try:
        d0 = datetime.strptime(actionable_date[:10], "%Y-%m-%d")
    except ValueError:
        return None, None
    exit_dt = d0 + timedelta(days=90)
    days_left = (exit_dt - datetime.now()).days
    return exit_dt.strftime("%Y-%m-%d"), max(days_left, 0)


class AlpacaPortfolioService:
    """Composes the /api/portfolio snapshot from Alpaca + SignalPerformance."""

    @staticmethod
    def _headers() -> dict:
        return {
            "APCA-API-KEY-ID": settings.ALPACA_API_KEY,
            "APCA-API-SECRET-KEY": settings.ALPACA_SECRET_KEY,
        }

    @staticmethod
    def configured() -> bool:
        return bool(settings.ALPACA_API_KEY and settings.ALPACA_SECRET_KEY)

    @classmethod
    async def _get(cls, client: httpx.AsyncClient, path: str, params: dict | None = None) -> Any:
        resp = await client.get(
            f"{settings.ALPACA_BASE_URL}{path}", headers=cls._headers(), params=params or {}
        )
        resp.raise_for_status()
        return resp.json()

    @staticmethod
    async def _signal_context(tickers: list[str]) -> dict[str, dict]:
        """Day-0 price + actionable date per ticker from immature strong_buy SPs."""
        if not tickers:
            return {}
        rows = await Neo4jClient.execute_query(
            """
            MATCH (sp:SignalPerformance)
            WHERE sp.ticker IN $tickers AND sp.conviction_tier = 'strong_buy'
            RETURN sp.ticker AS ticker, sp.signal_date AS signal_date,
                   sp.actionable_date AS actionable_date, sp.price_day0 AS price_day0,
                   sp.num_insiders AS num_insiders, sp.total_value AS total_value,
                   sp.company_name AS company_name
            ORDER BY sp.signal_date DESC
            """,
            {"tickers": tickers},
        )
        # Keep the most recent signal per ticker (rows are date-desc)
        ctx: dict[str, dict] = {}
        for r in rows:
            ctx.setdefault(r["ticker"], dict(r))
        return ctx

    @classmethod
    async def get_snapshot(cls) -> dict:
        """Full Portfolio page payload."""
        if not cls.configured():
            return {"configured": False}

        async with httpx.AsyncClient(timeout=15.0) as client:
            account = await cls._get(client, "/v2/account")
            raw_positions = await cls._get(client, "/v2/positions")
            history = await cls._get(
                client,
                "/v2/account/portfolio/history",
                {"period": "3M", "timeframe": "1D", "pnl_reset": "no_reset"},
            )
            fills = await cls._get(
                client,
                "/v2/account/activities/FILL",
                {"page_size": 50, "direction": "desc"},
            )

        equity = float(account.get("equity") or 0)
        cash = float(account.get("cash") or 0)

        sweep = None
        signal_positions = []
        tickers = [p["symbol"] for p in raw_positions if p["symbol"] != SWEEP_SYMBOL]
        ctx = await cls._signal_context(tickers)

        for p in raw_positions:
            base = {
                "ticker": p["symbol"],
                "qty": float(p["qty"]),
                "avg_fill": float(p["avg_entry_price"]),
                "last_price": float(p["current_price"] or 0),
                "market_value": float(p["market_value"] or 0),
                "cost_basis": float(p["cost_basis"] or 0),
                "unrealized_pl": float(p["unrealized_pl"] or 0),
                "unrealized_plpc": round(float(p["unrealized_plpc"] or 0) * 100, 2),
            }
            if p["symbol"] == SWEEP_SYMBOL:
                sweep = base
                continue
            sctx = ctx.get(p["symbol"], {})
            exit_date, days_left = day90_exit(
                sctx.get("actionable_date") or sctx.get("signal_date")
            )
            base.update({
                "company_name": sctx.get("company_name"),
                "signal_date": (sctx.get("signal_date") or "")[:10] or None,
                "day0_price": sctx.get("price_day0"),
                "shortfall_pct": compute_shortfall(sctx.get("price_day0"), base["avg_fill"]),
                "num_insiders": sctx.get("num_insiders"),
                "cluster_value": sctx.get("total_value"),
                "exit_date": exit_date,
                "days_left": days_left,
            })
            signal_positions.append(base)

        positions_value = sum(p["market_value"] for p in signal_positions)
        sweep_value = sweep["market_value"] if sweep else 0.0

        shortfalls = [p["shortfall_pct"] for p in signal_positions if p["shortfall_pct"] is not None]
        avg_shortfall = round(sum(shortfalls) / len(shortfalls), 2) if shortfalls else None

        curve = []
        for ts, eq in zip(history.get("timestamp") or [], history.get("equity") or []):
            # Alpaca pads pre-inception days with 0.0 equity — skip them
            if not eq or float(eq) <= 0:
                continue
            curve.append({
                "date": datetime.fromtimestamp(ts).strftime("%Y-%m-%d"),
                "equity": round(float(eq), 2),
            })

        activities = [
            {
                "time": f.get("transaction_time"),
                "symbol": f.get("symbol"),
                "side": f.get("side"),
                "qty": float(f.get("qty") or 0),
                "price": float(f.get("price") or 0),
                "type": "sweep" if f.get("symbol") == SWEEP_SYMBOL else "order",
            }
            for f in fills
        ]

        return {
            "configured": True,
            "as_of": datetime.now().isoformat(),
            "account": {
                "value": equity,
                "cash": cash,
                "initial_capital": INITIAL_CAPITAL,
                "pnl": round(equity - INITIAL_CAPITAL, 2),
                "pnl_pct": round((equity - INITIAL_CAPITAL) / INITIAL_CAPITAL * 100, 2),
                "position_slice": POSITION_SLICE,
            },
            "allocation": compute_allocation(positions_value, sweep_value, cash),
            "positions": signal_positions,
            "positions_value": round(positions_value, 2),
            "avg_shortfall_pct": avg_shortfall,
            "sweep": sweep,
            "equity_curve": curve,
            "activities": activities,
        }
