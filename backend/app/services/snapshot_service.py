"""Weekly snapshot service — live scorecard for recent signals.

Shows how signals from the last 30 days are performing right now,
using stored daily prices from Company.price_series (no yfinance calls).
Buy side: strong_buy conviction only. Sell side: high clusters, separate stats.
"""

import json
import logging
import time
from datetime import datetime, timedelta
from typing import Optional

from app.db.neo4j_client import Neo4jClient
from app.services.insider_cluster_service import InsiderClusterService

logger = logging.getLogger(__name__)

# Short cache for live data (15 min)
_snapshot_cache: dict[str, tuple[float, dict]] = {}
_CACHE_TTL = 15 * 60

# Maturity threshold: signals must be held this many days to count as "mature"
MATURE_DAYS = 14


def _parse_series(series_json: Optional[str]) -> list[dict]:
    if not series_json:
        return []
    try:
        return json.loads(series_json)
    except (ValueError, TypeError):
        return []


def _find_close(series: list[dict], target_date: str, max_skip: int = 7) -> Optional[float]:
    """Find close on or after target_date, within max_skip days."""
    if not series:
        return None
    try:
        target = datetime.strptime(target_date[:10], "%Y-%m-%d")
    except (ValueError, TypeError):
        return None
    by_date = {e.get("d"): float(e.get("c", 0)) for e in series if e.get("d")}
    for skip in range(max_skip + 1):
        check = (target + timedelta(days=skip)).strftime("%Y-%m-%d")
        if check in by_date:
            return by_date[check]
    return None


class SnapshotService:
    """Generates scorecards for recent signals. Uses precomputed blob when available."""

    @staticmethod
    async def get_weekly_snapshot(days: int = 30, date: str = None) -> dict:
        cache_key = f"weekly_{days}" if not date else f"weekly_{days}_{date}"
        if cache_key in _snapshot_cache:
            ts, data = _snapshot_cache[cache_key]
            if time.time() - ts < _CACHE_TTL:
                return data

        # Try precomputed blob first (for default 30d/60d/90d without date filter)
        if not date and days in (30, 60, 90):
            blob = await SnapshotService._load_precomputed(days)
            if blob:
                _snapshot_cache[cache_key] = (time.time(), blob)
                return blob

        now = datetime.now()

        # 1. Get recent buy clusters, sell clusters, and compound signals
        buy_clusters = await InsiderClusterService.detect_clusters(
            days=days, min_level="high", direction="buy"
        )
        buy_clusters = InsiderClusterService.apply_market_cap_filter(buy_clusters)
        buy_clusters = [c for c in buy_clusters if c.conviction_tier == "strong_buy"]

        sell_clusters = await InsiderClusterService.detect_clusters(
            days=days, min_level="high", direction="sell"
        )
        sell_clusters = InsiderClusterService.apply_market_cap_filter(sell_clusters)

        # 2. Build unified signal list (insider clusters only — compound signals excluded per research)
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

        # 3. Deduplicate by ticker+action
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

        deduped_signals.sort(
            key=lambda s: (level_rank.get(s["signal_level"], 2), -(s.get("total_value") or 0))
        )

        # 4. Batch-fetch price_series + SIC codes for all companies
        all_ciks = list(set(s["cik"] for s in deduped_signals if s.get("cik")))
        company_data: dict[str, dict] = {}
        if all_ciks:
            results = await Neo4jClient.execute_query(
                "UNWIND $ciks as cik MATCH (c:Company {cik: cik}) "
                "RETURN c.cik as cik, c.sic as sic, c.price_series as price_series",
                {"ciks": all_ciks},
            )
            for r in results:
                company_data[r["cik"]] = {
                    "sic": r.get("sic") or "",
                    "series": _parse_series(r.get("price_series")),
                }

        # 5. Fetch SPY price series from stored data (or fall back to any company's SPY-like approach)
        spy_series: list[dict] = []
        spy_result = await Neo4jClient.execute_query(
            "MATCH (c:Company) WHERE c.ticker = 'SPY' RETURN c.price_series as ps LIMIT 1"
        )
        if spy_result and spy_result[0].get("ps"):
            spy_series = _parse_series(spy_result[0]["ps"])

        spy_prices: dict[str, float] = {p["d"]: p["c"] for p in spy_series}
        spy_latest = spy_series[-1]["c"] if spy_series else None

        def _find_spy_near(target_date: str) -> Optional[float]:
            if not spy_series:
                return None
            return _find_close(spy_series, target_date)

        # 6. Score each signal using stored prices
        scored_signals = []
        for sig in deduped_signals:
            cik = sig.get("cik")
            ticker = sig.get("ticker")
            signal_date = sig.get("signal_date")
            if not cik or not ticker or not signal_date:
                continue

            cd = company_data.get(cik, {})
            series = cd.get("series", [])
            if not series:
                continue

            entry_price = _find_close(series, signal_date)
            if not entry_price or entry_price <= 0:
                continue

            # Current price = latest in the series
            latest = series[-1]
            current_price = float(latest.get("c", 0))
            if current_price <= 0:
                continue

            return_pct = round((current_price - entry_price) / entry_price * 100, 2)

            try:
                sig_dt = datetime.strptime(signal_date[:10], "%Y-%m-%d")
                days_held = (now - sig_dt).days
            except (ValueError, TypeError):
                days_held = 0

            # SPY alpha
            spy_return_pct = None
            alpha_pct = None
            spy_entry = _find_spy_near(signal_date)
            if spy_entry and spy_latest and spy_entry > 0:
                spy_return_pct = round((spy_latest - spy_entry) / spy_entry * 100, 2)
                alpha_pct = round(return_pct - spy_return_pct, 2)

            is_pass = sig["signal_action"] == "PASS"
            scored_signals.append({
                "ticker": ticker,
                "company_name": sig["company_name"],
                "cik": cik,
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
                "pass_correct": bool(is_pass and return_pct <= 0),
                "avoided_loss_pct": float(round(abs(min(return_pct, 0)), 2)) if is_pass else None,
                "sic_code": cd.get("sic", ""),
            })

        # Sort by return descending
        scored_signals.sort(key=lambda s: s["return_pct"], reverse=True)

        # Apply date filter if provided
        if date:
            scored_signals = [s for s in scored_signals if s["signal_date"][:10] == date[:10]]

        # Split into buy and sell
        buy_signals = [s for s in scored_signals if s["signal_action"] != "PASS"]
        sell_signals = [s for s in scored_signals if s["signal_action"] == "PASS"]

        # === BUY STATS ===
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

        # === SELL STATS ===
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
        if spy_series and len(spy_series) >= 2:
            cutoff = (now - timedelta(days=days)).strftime("%Y-%m-%d")
            spy_start = _find_close(spy_series, cutoff)
            spy_end = spy_series[-1]["c"] if spy_series else None
            if spy_start and spy_end and spy_start > 0:
                spy_return = round((spy_end - spy_start) / spy_start * 100, 2)

        result = {
            "period_days": days,
            "generated_at": now.isoformat(),
            "mature_days": MATURE_DAYS,
            "spy_return": spy_return,
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
            "buy_stats": buy_stats,
            "sell_stats": sell_stats,
            "pass_stats": {
                "total": sell_stats["total"],
                "mature": sell_stats["mature_total"],
                "correct": sell_stats["mature_correct"],
                "correct_rate": sell_stats["mature_correct_rate"],
                "avg_avoided_loss": sell_stats["avg_avoided_loss"],
            },
            "signals": scored_signals,
        }

        _snapshot_cache[cache_key] = (time.time(), result)
        return result

    @staticmethod
    async def _load_precomputed(days: int) -> Optional[dict]:
        """Load precomputed snapshot blob from Neo4j."""
        result = await Neo4jClient.execute_query(
            "MATCH (ss:SnapshotBlob {days: $days}) RETURN ss.data as data",
            {"days": days},
        )
        if result and result[0].get("data"):
            try:
                return json.loads(result[0]["data"])
            except (ValueError, TypeError):
                pass
        return None

    @staticmethod
    async def precompute_and_save(days_list: list[int] = None) -> dict:
        """Precompute snapshots for common day ranges and save as blobs.

        Called after signal performance compute. Saves 30d, 60d, 90d snapshots
        so dashboard loads instantly without live cluster detection.
        """
        if days_list is None:
            days_list = [30, 60, 90]

        saved = 0
        for days in days_list:
            # Clear in-memory cache to force fresh computation
            cache_key = f"weekly_{days}"
            _snapshot_cache.pop(cache_key, None)

            # Compute fresh
            result = await SnapshotService.get_weekly_snapshot(days=days)

            # Save as blob
            data_json = json.dumps(result, default=str)
            await Neo4jClient.execute_query(
                "MERGE (ss:SnapshotBlob {days: $days}) "
                "SET ss.data = $data, ss.computed_at = $computed_at",
                {"days": days, "data": data_json, "computed_at": datetime.now().isoformat()},
            )
            saved += 1
            logger.info(f"Snapshot blob saved for {days}d ({len(result.get('signals', []))} signals)")

        return {"saved": saved, "days": days_list}
