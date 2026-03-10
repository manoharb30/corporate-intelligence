"""Weekly snapshot service — live scorecard for recent signals.

Shows how signals from the last 7-14 days are performing right now,
with live price comparisons and win/loss tracking.
"""

import logging
import time
from datetime import datetime, timedelta
from typing import Optional

import yfinance as yf

from app.services.insider_cluster_service import InsiderClusterService
from app.services.compound_signal_service import CompoundSignalService
from app.services.stock_price_service import StockPriceService

logger = logging.getLogger(__name__)

# Short cache for live data (15 min)
_snapshot_cache: dict[str, tuple[float, dict]] = {}
_CACHE_TTL = 15 * 60


class SnapshotService:
    """Generates live scorecards for recent signals."""

    @staticmethod
    async def get_weekly_snapshot(days: int = 14) -> dict:
        cache_key = f"weekly_{days}"
        if cache_key in _snapshot_cache:
            ts, data = _snapshot_cache[cache_key]
            if time.time() - ts < _CACHE_TTL:
                return data

        now = datetime.now()

        # 1. Get recent buy clusters, sell clusters, and compound signals
        buy_clusters = await InsiderClusterService.detect_clusters(
            days=days, min_level="medium", direction="buy"
        )
        sell_clusters = await InsiderClusterService.detect_clusters(
            days=days, min_level="medium", direction="sell"
        )
        compounds = await CompoundSignalService.detect_compound_signals(days=days)

        # Filter compounds to only those with cluster (insider_activist, triple_convergence)
        compounds = [
            c for c in compounds
            if c.compound_type in ("insider_activist", "triple_convergence")
        ]

        # 2. Build unified signal list
        raw_signals = []

        for c in buy_clusters:
            raw_signals.append({
                "ticker": c.ticker,
                "company_name": c.company_name,
                "cik": c.cik,
                "signal_type": "insider_cluster",
                "signal_date": c.window_end,
                "signal_level": c.signal_level,
                "num_insiders": c.num_buyers,
                "total_value": c.total_buy_value,
                "accession_number": c.accession_number,
                "signal_action": "BUY" if c.signal_level == "high" else "WATCH",
            })

        for c in sell_clusters:
            raw_signals.append({
                "ticker": c.ticker,
                "company_name": c.company_name,
                "cik": c.cik,
                "signal_type": "insider_sell_cluster",
                "signal_date": c.window_end,
                "signal_level": c.signal_level,
                "num_insiders": c.num_buyers,
                "total_value": c.total_buy_value,
                "accession_number": c.accession_number,
                "signal_action": "PASS",
            })

        for c in compounds:
            raw_signals.append({
                "ticker": c.ticker,
                "company_name": c.company_name,
                "cik": c.cik,
                "signal_type": "compound",
                "signal_date": c.signal_date,
                "signal_level": "high",
                "num_insiders": 0,
                "total_value": 0,
                "accession_number": c.accession_number,
                "signal_action": c.decision,
            })

        # 3. Fetch prices and compute live returns
        scored_signals = []
        for sig in raw_signals:
            ticker = sig["ticker"]
            signal_date = sig["signal_date"]
            if not ticker or not signal_date:
                continue

            try:
                price_data = StockPriceService.get_price_at_date(ticker, signal_date)
                if not price_data or not price_data.get("price_at_date"):
                    continue

                entry_price = price_data["price_at_date"]
                current_price = price_data["price_current"]
                if entry_price <= 0:
                    continue

                return_pct = round(
                    (current_price - entry_price) / entry_price * 100, 2
                )

                try:
                    sig_dt = datetime.strptime(signal_date[:10], "%Y-%m-%d")
                    days_held = (now - sig_dt).days
                except (ValueError, TypeError):
                    days_held = 0

                scored_signals.append({
                    "ticker": ticker,
                    "company_name": sig["company_name"],
                    "cik": sig["cik"],
                    "signal_type": sig["signal_type"],
                    "signal_date": signal_date,
                    "signal_level": sig["signal_level"],
                    "signal_action": sig["signal_action"],
                    "num_insiders": sig["num_insiders"],
                    "total_value": sig["total_value"],
                    "accession_number": sig["accession_number"],
                    "entry_price": round(entry_price, 2),
                    "current_price": round(current_price, 2),
                    "return_pct": return_pct,
                    "days_held": days_held,
                    "status": "winning" if return_pct > 0 else "losing",
                })
            except Exception as e:
                logger.warning(f"Snapshot price fetch failed for {ticker}: {e}")
                continue

        # Sort by return descending
        scored_signals.sort(key=lambda s: s["return_pct"], reverse=True)

        # 4. Compute aggregates (all signals)
        total = len(scored_signals)
        wins = [s for s in scored_signals if s["return_pct"] > 0]
        losses = [s for s in scored_signals if s["return_pct"] <= 0]
        returns = [s["return_pct"] for s in scored_signals]
        avg_return = round(sum(returns) / total, 2) if total > 0 else 0

        best = scored_signals[0] if scored_signals else None
        worst = scored_signals[-1] if scored_signals else None

        # 5. Mature signals only (5+ days held)
        mature = [s for s in scored_signals if s["days_held"] >= 5]
        mature_total = len(mature)
        mature_wins = len([s for s in mature if s["return_pct"] > 0])
        mature_returns = [s["return_pct"] for s in mature]
        mature_avg_return = (
            round(sum(mature_returns) / mature_total, 2)
            if mature_total > 0 else 0
        )

        # 6. SPY benchmark return over the same period
        spy_return = None
        try:
            end_dt = now
            start_dt = now - timedelta(days=days + 5)
            spy_df = yf.download(
                "SPY",
                start=start_dt.strftime("%Y-%m-%d"),
                end=end_dt.strftime("%Y-%m-%d"),
                progress=False,
            )
            if hasattr(spy_df.columns, "levels"):
                spy_df.columns = spy_df.columns.get_level_values(0)
            if len(spy_df) >= 2:
                spy_start = float(spy_df["Close"].iloc[0])
                spy_end = float(spy_df["Close"].iloc[-1])
                if spy_start > 0:
                    spy_return = round(
                        (spy_end - spy_start) / spy_start * 100, 2
                    )
        except Exception as e:
            logger.warning(f"SPY benchmark fetch failed: {e}")

        result = {
            "period_days": days,
            "generated_at": now.isoformat(),
            "total_signals": total,
            "win_count": len(wins),
            "loss_count": len(losses),
            "avg_return": avg_return,
            "mature_total": mature_total,
            "mature_wins": mature_wins,
            "mature_avg_return": mature_avg_return,
            "spy_return": spy_return,
            "best_performer": {
                "ticker": best["ticker"],
                "return_pct": best["return_pct"],
            } if best else None,
            "worst_performer": {
                "ticker": worst["ticker"],
                "return_pct": worst["return_pct"],
            } if worst else None,
            "signals": scored_signals,
        }

        _snapshot_cache[cache_key] = (time.time(), result)
        return result
