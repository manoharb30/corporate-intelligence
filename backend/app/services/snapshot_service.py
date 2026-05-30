"""Weekly snapshot service — live scorecard for recent signals.

Reads clusters from SignalPerformance (the authoritative store written at
ingest by InsiderClusterService.process_incremental) — same source as the
Performance Tracker and /api/signal-performance. Applies live price/alpha
lookups from Company.price_series for the display layer.
"""

import json
import logging
import time
from datetime import datetime, timedelta
from typing import Optional

from app.db.neo4j_client import Neo4jClient

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

        now = datetime.now()

        # 1. Read recent strong_buy clusters from SignalPerformance — the
        #    authoritative store written at ingest. Filter by signal_date
        #    within the requested window. No re-derivation from raw transactions.
        cutoff = (now - timedelta(days=days)).strftime("%Y-%m-%d")
        sp_rows = await Neo4jClient.execute_query(
            "MATCH (sp:SignalPerformance) "
            "WHERE sp.direction = 'buy' "
            "  AND sp.conviction_tier = 'strong_buy' "
            "  AND substring(sp.signal_date, 0, 10) >= $cutoff "
            "  AND sp.ticker IS NOT NULL AND sp.ticker <> '' "
            "RETURN sp.signal_id AS signal_id, sp.ticker AS ticker, "
            "       sp.company_name AS company_name, sp.cik AS cik, "
            "       substring(sp.signal_date, 0, 10) AS signal_date, "
            "       sp.signal_level AS signal_level, "
            "       sp.num_insiders AS num_insiders, "
            "       sp.total_value AS total_value, "
            "       sp.conviction_tier AS conviction_tier "
            "ORDER BY sp.signal_date DESC",
            {"cutoff": cutoff},
        )

        # 2. Build unified signal list (insider clusters only — compound signals excluded per research)
        raw_signals = [
            {
                "ticker": r["ticker"],
                "company_name": r["company_name"],
                "cik": r["cik"],
                "signal_type": "insider_cluster",
                "signal_date": r["signal_date"],
                "signal_level": r["signal_level"],
                "num_insiders": r["num_insiders"],
                "total_value": r["total_value"],
                "accession_number": r["signal_id"],
                "signal_action": "BUY",
                "conviction_tier": r["conviction_tier"],
            }
            for r in sp_rows
        ]

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

        # v1.3: only buy signals exist — sell clusters dropped from snapshot
        buy_signals = scored_signals

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

        buy_stats = _compute_buy_stats(buy_signals)

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
            "signals": scored_signals,
        }

        _snapshot_cache[cache_key] = (time.time(), result)
        return result
