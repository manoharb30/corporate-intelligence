"""Weekly snapshot service — live scorecard for recent signals.

Shows how signals from the last 30 days are performing right now,
with live price comparisons, alpha vs SPY, and win/loss tracking.
"""

import asyncio
import logging
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
from typing import Optional

import yfinance as yf

from app.services.insider_cluster_service import InsiderClusterService
from app.services.compound_signal_service import CompoundSignalService
from app.services.stock_price_service import StockPriceService

_price_executor = ThreadPoolExecutor(max_workers=4)

logger = logging.getLogger(__name__)

# Short cache for live data (15 min)
_snapshot_cache: dict[str, tuple[float, dict]] = {}
_CACHE_TTL = 15 * 60

# Maturity threshold: signals must be held this many days to count as "mature"
MATURE_DAYS = 14


class SnapshotService:
    """Generates live scorecards for recent signals."""

    @staticmethod
    async def get_weekly_snapshot(days: int = 30) -> dict:
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
        # Apply market cap filter to remove noise from mega-cap single buys
        buy_clusters = InsiderClusterService.apply_market_cap_filter(buy_clusters)

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
                "conviction_tier": c.conviction_tier,
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
                "conviction_tier": "watch",
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
                "conviction_tier": "buy",
            })

        # 3. Deduplicate by ticker (keep highest-level signal per ticker)
        level_rank = {"high": 0, "medium": 1, "low": 2}
        seen: dict[str, dict] = {}
        for sig in raw_signals:
            ticker = sig.get("ticker")
            if not ticker or not sig.get("signal_date"):
                continue
            existing = seen.get(ticker)
            if not existing or level_rank.get(sig["signal_level"], 2) < level_rank.get(existing["signal_level"], 2):
                seen[ticker] = sig
        deduped_signals = list(seen.values())

        # Cap at 50 signals to avoid blocking the server
        deduped_signals.sort(
            key=lambda s: (level_rank.get(s["signal_level"], 2), -(s.get("total_value") or 0))
        )
        capped_signals = deduped_signals[:50]

        # Fetch SPY price history once for per-signal alpha computation
        def _fetch_spy_history() -> list[dict]:
            try:
                end_dt = now
                start_dt = now - timedelta(days=days + 10)
                spy_df = yf.download(
                    "SPY",
                    start=start_dt.strftime("%Y-%m-%d"),
                    end=end_dt.strftime("%Y-%m-%d"),
                    progress=False,
                )
                if hasattr(spy_df.columns, "levels"):
                    spy_df.columns = spy_df.columns.get_level_values(0)
                if len(spy_df) < 2:
                    return []
                result = []
                for date, row in spy_df.iterrows():
                    result.append({
                        "date": date.strftime("%Y-%m-%d"),
                        "close": float(row["Close"]),
                    })
                return result
            except Exception as e:
                logger.warning(f"SPY history fetch failed: {e}")
                return []

        loop = asyncio.get_event_loop()
        spy_history = await loop.run_in_executor(_price_executor, _fetch_spy_history)

        # Build SPY date->close lookup for per-signal alpha
        spy_prices: dict[str, float] = {p["date"]: p["close"] for p in spy_history}
        spy_latest = spy_history[-1]["close"] if spy_history else None

        def _find_spy_price_near(target_date: str) -> Optional[float]:
            """Find SPY close on or nearest to target_date, within 5 trading days."""
            if not spy_history:
                return None
            try:
                target = datetime.strptime(target_date, "%Y-%m-%d")
            except (ValueError, TypeError):
                return None
            best_price = None
            best_diff = None
            for p in spy_history:
                d = datetime.strptime(p["date"], "%Y-%m-%d")
                diff = abs((d - target).days)
                if best_diff is None or diff < best_diff:
                    best_price = p["close"]
                    best_diff = diff
            if best_diff is not None and best_diff <= 7:
                return best_price
            return None

        # Fetch prices in a thread pool so we don't block the event loop
        def _fetch_price(sig: dict) -> Optional[dict]:
            ticker = sig["ticker"]
            signal_date = sig["signal_date"]
            try:
                price_data = StockPriceService.get_price_at_date(ticker, signal_date)
                if not price_data or not price_data.get("price_at_date"):
                    return None
                entry_price = price_data["price_at_date"]
                current_price = price_data["price_current"]
                if entry_price <= 0:
                    return None
                return_pct = round(
                    (current_price - entry_price) / entry_price * 100, 2
                )
                try:
                    sig_dt = datetime.strptime(signal_date[:10], "%Y-%m-%d")
                    days_held = (now - sig_dt).days
                except (ValueError, TypeError):
                    days_held = 0

                # Compute per-signal SPY return and alpha
                spy_return_pct = None
                alpha_pct = None
                spy_entry = _find_spy_price_near(signal_date)
                if spy_entry and spy_latest and spy_entry > 0:
                    spy_return_pct = round(
                        (spy_latest - spy_entry) / spy_entry * 100, 2
                    )
                    alpha_pct = round(return_pct - spy_return_pct, 2)

                is_pass = sig["signal_action"] == "PASS"
                return {
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
                    "conviction_tier": sig.get("conviction_tier", "watch"),
                    "entry_price": float(round(entry_price, 2)),
                    "current_price": float(round(current_price, 2)),
                    "return_pct": float(return_pct),
                    "spy_return_pct": float(spy_return_pct) if spy_return_pct is not None else None,
                    "alpha_pct": float(alpha_pct) if alpha_pct is not None else None,
                    "days_held": days_held,
                    "status": "winning" if return_pct > 0 else "losing",
                    # PASS-specific fields
                    "pass_correct": bool(is_pass and return_pct <= 0),
                    "avoided_loss_pct": float(round(abs(min(return_pct, 0)), 2)) if is_pass else None,
                }
            except Exception as e:
                logger.warning(f"Snapshot price fetch failed for {ticker}: {e}")
                return None

        tasks = [
            loop.run_in_executor(_price_executor, _fetch_price, sig)
            for sig in capped_signals
        ]
        results = await asyncio.gather(*tasks)
        scored_signals = [r for r in results if r is not None]

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

        # 5. Mature signals only (21+ days held)
        mature = [s for s in scored_signals if s["days_held"] >= MATURE_DAYS]
        mature_total = len(mature)
        mature_wins = len([s for s in mature if s["return_pct"] > 0])
        mature_returns = [s["return_pct"] for s in mature]
        mature_avg_return = (
            round(sum(mature_returns) / mature_total, 2)
            if mature_total > 0 else 0
        )

        # Aggregate alpha
        alphas = [s["alpha_pct"] for s in scored_signals if s["alpha_pct"] is not None]
        avg_alpha = round(sum(alphas) / len(alphas), 2) if alphas else None
        mature_alphas = [s["alpha_pct"] for s in mature if s["alpha_pct"] is not None]
        mature_avg_alpha = round(sum(mature_alphas) / len(mature_alphas), 2) if mature_alphas else None

        # 6. SPY benchmark return over the full period
        spy_return = None
        if spy_history and len(spy_history) >= 2:
            spy_start_price = spy_history[0]["close"]
            spy_end_price = spy_history[-1]["close"]
            if spy_start_price > 0:
                spy_return = round(
                    (spy_end_price - spy_start_price) / spy_start_price * 100, 2
                )

        # 7. PASS signal stats
        pass_signals = [s for s in scored_signals if s["signal_action"] == "PASS"]
        mature_pass = [s for s in pass_signals if s["days_held"] >= MATURE_DAYS]
        pass_correct_list = [s for s in mature_pass if s["pass_correct"]]
        pass_stats = {
            "total": len(pass_signals),
            "mature": len(mature_pass),
            "correct": len(pass_correct_list),
            "correct_rate": round(len(pass_correct_list) / len(mature_pass) * 100, 1) if mature_pass else None,
            "avg_avoided_loss": round(
                sum(s["avoided_loss_pct"] for s in pass_correct_list) / len(pass_correct_list), 2
            ) if pass_correct_list else None,
        }

        result = {
            "period_days": days,
            "generated_at": now.isoformat(),
            "total_signals": total,
            "win_count": len(wins),
            "loss_count": len(losses),
            "avg_return": avg_return,
            "avg_alpha": avg_alpha,
            "mature_total": mature_total,
            "mature_wins": mature_wins,
            "mature_avg_return": mature_avg_return,
            "mature_avg_alpha": mature_avg_alpha,
            "mature_days": MATURE_DAYS,
            "spy_return": spy_return,
            "pass_stats": pass_stats,
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
