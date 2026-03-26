"""Weekly snapshot service — live scorecard for recent signals.

Shows how signals from the last 30 days are performing right now,
with live price comparisons, alpha vs SPY, and win/loss tracking.
Buy side: strong_buy conviction only. Sell side: high clusters, separate stats.
"""

import asyncio
import logging
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
from typing import Optional

import yfinance as yf

from app.db.neo4j_client import Neo4jClient
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
            days=days, min_level="high", direction="buy"
        )
        buy_clusters = InsiderClusterService.apply_market_cap_filter(buy_clusters)
        # Only strong_buy conviction for the scorecard
        buy_clusters = [c for c in buy_clusters if c.conviction_tier == "strong_buy"]

        sell_clusters = await InsiderClusterService.detect_clusters(
            days=days, min_level="high", direction="sell"
        )
        sell_clusters = InsiderClusterService.apply_market_cap_filter(sell_clusters)

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
                "signal_action": "BUY",
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

        # 3. Deduplicate by ticker+action (keep highest-level signal per ticker per side)
        level_rank = {"high": 0, "medium": 1, "low": 2}
        seen: dict[str, dict] = {}
        for sig in raw_signals:
            ticker = sig.get("ticker")
            if not ticker or not sig.get("signal_date"):
                continue
            key = f"{ticker}_{sig['signal_action']}"
            existing = seen.get(key)
            if not existing or level_rank.get(sig["signal_level"], 2) < level_rank.get(existing["signal_level"], 2):
                seen[key] = sig
        deduped_signals = list(seen.values())

        # Sort by level then value
        deduped_signals.sort(
            key=lambda s: (level_rank.get(s["signal_level"], 2), -(s.get("total_value") or 0))
        )

        # Batch-fetch SIC codes for all companies (async, before threaded price fetch)
        all_ciks = list(set(s["cik"] for s in deduped_signals if s.get("cik")))
        sic_map: dict[str, str] = {}
        if all_ciks:
            sic_results = await Neo4jClient.execute_query(
                "UNWIND $ciks as cik MATCH (c:Company {cik: cik}) WHERE c.sic IS NOT NULL "
                "RETURN c.cik as cik, c.sic as sic",
                {"ciks": all_ciks},
            )
            sic_map = {r["cik"]: r["sic"] for r in sic_results}

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
                # Handle MultiIndex columns from yfinance
                if hasattr(spy_df.columns, "nlevels") and spy_df.columns.nlevels > 1:
                    spy_df.columns = spy_df.columns.get_level_values(0)
                if len(spy_df) < 2:
                    return []
                result = []
                for date, row in spy_df.iterrows():
                    close = row.iloc[0] if "Close" not in spy_df.columns else row["Close"]
                    result.append({
                        "date": date.strftime("%Y-%m-%d"),
                        "close": float(close),
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
            """Find SPY close on or nearest to target_date, within 7 days."""
            if not spy_history:
                return None
            try:
                target = datetime.strptime(target_date[:10], "%Y-%m-%d")
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
            for sig in deduped_signals
        ]
        results = await asyncio.gather(*tasks)
        scored_signals = [r for r in results if r is not None]

        # Inject SIC codes from pre-fetched map
        for sig in scored_signals:
            sig["sic_code"] = sic_map.get(sig.get("cik"), "")

        # Sort by return descending
        scored_signals.sort(key=lambda s: s["return_pct"], reverse=True)

        # Split into buy and sell
        buy_signals = [s for s in scored_signals if s["signal_action"] != "PASS"]
        sell_signals = [s for s in scored_signals if s["signal_action"] == "PASS"]

        # === BUY STATS (strong_buy only) ===
        def _compute_buy_stats(signals: list[dict]) -> dict:
            total = len(signals)
            if total == 0:
                return {"total": 0, "win_count": 0, "loss_count": 0, "avg_return": 0,
                        "avg_alpha": None, "beat_spy_count": 0, "mature_total": 0,
                        "mature_wins": 0, "mature_avg_return": 0, "mature_avg_alpha": None,
                        "best": None, "worst": None}
            wins = [s for s in signals if s["return_pct"] > 0]
            alphas = [s["alpha_pct"] for s in signals if s["alpha_pct"] is not None]
            beat_spy = [a for a in alphas if a > 0]
            avg_ret = round(sum(s["return_pct"] for s in signals) / total, 2)
            avg_alpha = round(sum(alphas) / len(alphas), 2) if alphas else None

            mature = [s for s in signals if s["days_held"] >= MATURE_DAYS]
            m_wins = [s for s in mature if s["return_pct"] > 0]
            m_alphas = [s["alpha_pct"] for s in mature if s["alpha_pct"] is not None]
            m_avg_ret = round(sum(s["return_pct"] for s in mature) / len(mature), 2) if mature else 0
            m_avg_alpha = round(sum(m_alphas) / len(m_alphas), 2) if m_alphas else None

            sorted_by_ret = sorted(signals, key=lambda s: s["return_pct"], reverse=True)
            best = {"ticker": sorted_by_ret[0]["ticker"], "return_pct": sorted_by_ret[0]["return_pct"]}
            worst = {"ticker": sorted_by_ret[-1]["ticker"], "return_pct": sorted_by_ret[-1]["return_pct"]}

            return {
                "total": total,
                "win_count": len(wins),
                "loss_count": total - len(wins),
                "avg_return": avg_ret,
                "avg_alpha": avg_alpha,
                "beat_spy_count": len(beat_spy),
                "mature_total": len(mature),
                "mature_wins": len(m_wins),
                "mature_avg_return": m_avg_ret,
                "mature_avg_alpha": m_avg_alpha,
                "best": best,
                "worst": worst,
            }

        # === SELL STATS (high sell clusters) ===
        def _compute_sell_stats(signals: list[dict]) -> dict:
            total = len(signals)
            if total == 0:
                return {"total": 0, "correct": 0, "correct_rate": None,
                        "avg_price_change": 0, "avg_avoided_loss": None,
                        "mature_total": 0, "mature_correct": 0, "mature_correct_rate": None,
                        "mature_avg_drop": None, "biggest_avoided": []}
            correct = [s for s in signals if s["return_pct"] < 0]
            correct_rate = round(len(correct) / total * 100, 1)
            avg_change = round(sum(s["return_pct"] for s in signals) / total, 2)
            avg_avoided = round(
                sum(abs(s["return_pct"]) for s in correct) / len(correct), 2
            ) if correct else None

            mature = [s for s in signals if s["days_held"] >= MATURE_DAYS]
            m_correct = [s for s in mature if s["return_pct"] < 0]
            m_rate = round(len(m_correct) / len(mature) * 100, 1) if mature else None
            m_avg_drop = round(
                sum(s["return_pct"] for s in m_correct) / len(m_correct), 2
            ) if m_correct else None

            biggest = sorted(correct, key=lambda s: s["return_pct"])[:5]
            biggest_avoided = [
                {"ticker": s["ticker"], "drop_pct": s["return_pct"]} for s in biggest
            ]

            return {
                "total": total,
                "correct": len(correct),
                "correct_rate": correct_rate,
                "avg_price_change": avg_change,
                "avg_avoided_loss": avg_avoided,
                "mature_total": len(mature),
                "mature_correct": len(m_correct),
                "mature_correct_rate": m_rate,
                "mature_avg_drop": m_avg_drop,
                "biggest_avoided": biggest_avoided,
            }

        buy_stats = _compute_buy_stats(buy_signals)
        sell_stats = _compute_sell_stats(sell_signals)

        # SPY benchmark return over the full period
        spy_return = None
        if spy_history and len(spy_history) >= 2:
            spy_start_price = spy_history[0]["close"]
            spy_end_price = spy_history[-1]["close"]
            if spy_start_price > 0:
                spy_return = round(
                    (spy_end_price - spy_start_price) / spy_start_price * 100, 2
                )

        # Legacy top-level fields (backward compat) — now driven by buy-side only
        total = len(scored_signals)

        result = {
            "period_days": days,
            "generated_at": now.isoformat(),
            "mature_days": MATURE_DAYS,
            "spy_return": spy_return,
            # Buy-side headline stats (strong_buy only)
            "total_signals": buy_stats["total"],
            "win_count": buy_stats["win_count"],
            "loss_count": buy_stats["loss_count"],
            "avg_return": buy_stats["avg_return"],
            "avg_alpha": buy_stats["avg_alpha"],
            "mature_total": buy_stats["mature_total"],
            "mature_wins": buy_stats["mature_wins"],
            "mature_avg_return": buy_stats["mature_avg_return"],
            "mature_avg_alpha": buy_stats["mature_avg_alpha"],
            "best_performer": buy_stats["best"],
            "worst_performer": buy_stats["worst"],
            # Structured buy/sell stats
            "buy_stats": buy_stats,
            "sell_stats": sell_stats,
            # Legacy pass_stats (now superseded by sell_stats)
            "pass_stats": {
                "total": sell_stats["total"],
                "mature": sell_stats["mature_total"],
                "correct": sell_stats["mature_correct"],
                "correct_rate": sell_stats["mature_correct_rate"],
                "avg_avoided_loss": sell_stats["avg_avoided_loss"],
            },
            # All signals for the table
            "signals": scored_signals,
        }

        _snapshot_cache[cache_key] = (time.time(), result)
        return result
