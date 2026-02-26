"""Service for dashboard pulse data — aggregated real-time stats."""

import logging
import time
from datetime import datetime, timedelta

from app.services.feed_service import FeedService
from app.services.stock_price_service import StockPriceService

logger = logging.getLogger(__name__)

_pulse_cache: dict[str, tuple[float, dict]] = {}
_PULSE_TTL = 1800  # 30 minutes


class DashboardService:

    @staticmethod
    async def get_pulse() -> dict:
        cache_key = "pulse"
        now = time.time()
        if cache_key in _pulse_cache:
            ts, data = _pulse_cache[cache_key]
            if now - ts < _PULSE_TTL:
                return data

        try:
            result = await DashboardService._build_pulse()
            _pulse_cache[cache_key] = (now, result)
            return result
        except Exception as e:
            logger.error(f"Failed to build dashboard pulse: {e}")
            if cache_key in _pulse_cache:
                return _pulse_cache[cache_key][1]
            return DashboardService._empty_pulse()

    @staticmethod
    async def _build_pulse() -> dict:
        signals, _ = await FeedService.get_feed(days=30, min_level="medium")

        today_str = datetime.now().strftime("%Y-%m-%d")
        week_ago = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")

        # Last signal
        last_signal = None
        if signals:
            s = signals[0]
            days_ago = (datetime.now() - datetime.strptime(s.filing_date, "%Y-%m-%d")).days
            last_signal = {
                "company_name": s.company_name,
                "ticker": s.ticker,
                "signal_summary": s.signal_summary,
                "signal_type": s.signal_type or "8k",
                "filing_date": s.filing_date,
                "days_ago": days_ago,
                "accession_number": s.accession_number,
            }

        # Today's counts
        today_signals = [s for s in signals if s.filing_date == today_str]
        today = {
            "signal_count": len(today_signals),
            "buy_cluster_count": sum(1 for s in today_signals if s.signal_type == "insider_cluster"),
            "sell_cluster_count": sum(1 for s in today_signals if s.signal_type == "insider_sell_cluster"),
            "total_buy_volume": sum(
                (s.insider_context.total_buy_value if s.insider_context else 0) for s in today_signals
            ),
            "total_sell_volume": sum(
                (s.insider_context.total_sell_value if s.insider_context else 0) for s in today_signals
            ),
        }

        # Market mood (30 days)
        buy_clusters = [s for s in signals if s.signal_type == "insider_cluster"]
        sell_clusters = [s for s in signals if s.signal_type == "insider_sell_cluster"]
        buy_volume = sum((s.insider_context.total_buy_value if s.insider_context else 0) for s in buy_clusters)
        sell_volume = sum((s.insider_context.total_sell_value if s.insider_context else 0) for s in sell_clusters)
        bc = len(buy_clusters)
        sc = len(sell_clusters)
        if sc > 2 * bc:
            mood_label = "Bearish"
        elif bc > 2 * sc:
            mood_label = "Bullish"
        else:
            mood_label = "Neutral"

        market_mood = {
            "buy_clusters": bc,
            "sell_clusters": sc,
            "buy_volume": buy_volume,
            "sell_volume": sell_volume,
            "ratio": round(sc / bc, 1) if bc > 0 else sc,
            "label": mood_label,
        }

        # Week scorecard
        week_signals = [s for s in signals if s.filing_date >= week_ago]
        week_buy = [s for s in week_signals if s.signal_type == "insider_cluster"]
        week_sell = [s for s in week_signals if s.signal_type == "insider_sell_cluster"]

        week_scorecard = {
            "total_signals": len(week_signals),
            "buy_signals": len(week_buy),
            "sell_signals": len(week_sell),
            "buy_avg_return": None,
            "sell_avg_return": None,
        }

        # Biggest movers — get price change for cluster signals (cap at 10 lookups)
        cluster_signals = [s for s in signals if s.signal_type in ("insider_cluster", "insider_sell_cluster") and s.ticker]
        movers = []
        for s in cluster_signals[:10]:
            try:
                price_data = await StockPriceService.get_price_at_date(s.ticker, s.filing_date)
                if price_data and price_data.get("price_change_pct") is not None:
                    movers.append({
                        "ticker": s.ticker,
                        "company_name": s.company_name,
                        "price_change_pct": price_data["price_change_pct"],
                        "signal_summary": s.signal_summary,
                        "accession_number": s.accession_number,
                        "signal_type": s.signal_type,
                    })
            except Exception:
                continue

        top_gainer = max(movers, key=lambda m: m["price_change_pct"]) if movers else None
        top_loser = min(movers, key=lambda m: m["price_change_pct"]) if movers else None

        # Compute avg returns for week scorecard from movers
        week_buy_movers = [m for m in movers if m["signal_type"] == "insider_cluster"]
        week_sell_movers = [m for m in movers if m["signal_type"] == "insider_sell_cluster"]
        if week_buy_movers:
            week_scorecard["buy_avg_return"] = round(
                sum(m["price_change_pct"] for m in week_buy_movers) / len(week_buy_movers), 1
            )
        if week_sell_movers:
            week_scorecard["sell_avg_return"] = round(
                sum(m["price_change_pct"] for m in week_sell_movers) / len(week_sell_movers), 1
            )

        return {
            "last_signal": last_signal,
            "today": today,
            "market_mood": market_mood,
            "biggest_movers": {
                "top_gainer": top_gainer,
                "top_loser": top_loser,
            },
            "week_scorecard": week_scorecard,
        }

    @staticmethod
    def _empty_pulse() -> dict:
        return {
            "last_signal": None,
            "today": {"signal_count": 0, "buy_cluster_count": 0, "sell_cluster_count": 0, "total_buy_volume": 0, "total_sell_volume": 0},
            "market_mood": {"buy_clusters": 0, "sell_clusters": 0, "buy_volume": 0, "sell_volume": 0, "ratio": 0, "label": "Neutral"},
            "biggest_movers": {"top_gainer": None, "top_loser": None},
            "week_scorecard": {"total_signals": 0, "buy_signals": 0, "sell_signals": 0, "buy_avg_return": None, "sell_avg_return": None},
        }
