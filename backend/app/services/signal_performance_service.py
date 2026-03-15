"""Service for computing and storing signal performance data in Neo4j.

Pre-computes delayed entry prices and returns for the showcase/track record page.
Runs during daily scanner or on-demand via API. The showcase page just queries
Neo4j — no yfinance calls, instant load.
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
from app.services.stock_price_service import StockPriceService

logger = logging.getLogger(__name__)

_executor = ThreadPoolExecutor(max_workers=6)

# Delay points to compute prices at
DELAY_DAYS = [0, 1, 2, 3, 5, 7]
HORIZON_DAYS = 90
MIN_AGE_DAYS = HORIZON_DAYS + max(DELAY_DAYS)  # 97 days


def _fetch_spy_history_sync(days: int = 400) -> dict[str, float]:
    """Fetch SPY price history. Returns {date_str: close_price}."""
    try:
        end = datetime.now()
        start = end - timedelta(days=days)
        df = yf.download(
            "SPY",
            start=start.strftime("%Y-%m-%d"),
            end=end.strftime("%Y-%m-%d"),
            progress=False,
        )
        if hasattr(df.columns, "levels"):
            df.columns = df.columns.get_level_values(0)
        result = {}
        for date, row in df.iterrows():
            result[date.strftime("%Y-%m-%d")] = float(row["Close"])
        return result
    except Exception as e:
        logger.warning(f"Failed to fetch SPY history: {e}")
        return {}


def _find_price(prices: dict[str, float], target_date: str, max_skip: int = 5) -> Optional[float]:
    """Find closing price on or up to max_skip trading days after target_date."""
    try:
        target = datetime.strptime(target_date, "%Y-%m-%d")
    except (ValueError, TypeError):
        return None
    for skip in range(max_skip + 1):
        check = (target + timedelta(days=skip)).strftime("%Y-%m-%d")
        if check in prices:
            return prices[check]
    return None


def _compute_signal_perf(cluster, spy_prices: dict[str, float], direction: str) -> Optional[dict]:
    """Compute performance data for a single cluster signal. Runs in thread pool."""
    if not cluster.ticker:
        return None

    signal_date = cluster.window_end
    try:
        signal_dt = datetime.strptime(signal_date, "%Y-%m-%d")
        age = (datetime.now() - signal_dt).days
    except (ValueError, TypeError):
        return None

    # Fetch price history
    try:
        price_data = StockPriceService.get_price_data(cluster.ticker, "2y")
    except Exception:
        return None
    if not price_data:
        return None

    prices = {p["date"]: p["close"] for p in price_data}

    # Get prices at each delay point
    delay_prices = {}
    for d in DELAY_DAYS:
        entry_date = (signal_dt + timedelta(days=d)).strftime("%Y-%m-%d")
        p = _find_price(prices, entry_date)
        if p is not None:
            delay_prices[d] = float(round(p, 2))

    if 0 not in delay_prices:
        return None  # Can't even find signal-date price

    # Get price at day 30
    exit_date = (signal_dt + timedelta(days=HORIZON_DAYS)).strftime("%Y-%m-%d")
    price_day30 = _find_price(prices, exit_date)
    is_mature = age >= MIN_AGE_DAYS and price_day30 is not None

    # Compute 30-day returns from each entry point
    returns = {}
    if price_day30 is not None:
        price_day30 = float(round(price_day30, 2))
        for d, entry_price in delay_prices.items():
            if entry_price > 0:
                ret = round((price_day30 - entry_price) / entry_price * 100, 2)
                returns[d] = float(ret)

    # SPY 30-day return from signal date
    spy_at_signal = _find_price(spy_prices, signal_date)
    spy_at_exit = _find_price(spy_prices, exit_date) if is_mature else None
    spy_return_30d = None
    if spy_at_signal and spy_at_exit and spy_at_signal > 0:
        spy_return_30d = float(round(
            (spy_at_exit - spy_at_signal) / spy_at_signal * 100, 2
        ))

    # Market cap and trade-as-% calculation
    market_cap = None
    pct_of_mcap = None
    try:
        market_cap = StockPriceService.get_market_cap(cluster.ticker)
        if market_cap and market_cap > 0:
            pct_of_mcap = round((cluster.total_buy_value / market_cap) * 100, 6)
    except Exception:
        pass

    result = {
        "signal_id": cluster.accession_number,
        "ticker": cluster.ticker,
        "company_name": cluster.company_name,
        "cik": cluster.cik,
        "signal_date": signal_date,
        "direction": direction,
        "signal_level": cluster.signal_level,
        "num_insiders": cluster.num_buyers,
        "total_value": float(cluster.total_buy_value),
        "conviction_tier": getattr(cluster, "conviction_tier", "watch"),
        "market_cap": market_cap,
        "pct_of_mcap": pct_of_mcap,
        "is_mature": is_mature,
        "computed_at": datetime.now().isoformat(),
        "price_day30": price_day30,
        "spy_return_30d": spy_return_30d,
    }

    # Add delay prices and returns
    for d in DELAY_DAYS:
        result[f"price_day{d}"] = delay_prices.get(d)
        result[f"return_day{d}"] = returns.get(d)

    return result


class SignalPerformanceService:
    """Computes and stores signal performance data in Neo4j."""

    @staticmethod
    async def compute_all(days: int = 365) -> dict:
        """Detect all clusters, compute performance, store in Neo4j.

        Returns summary of what was computed.
        """
        start_time = time.time()

        # 1. Detect clusters
        buy_clusters = await InsiderClusterService.detect_clusters(
            days=days, min_level="medium", direction="buy"
        )
        sell_clusters = await InsiderClusterService.detect_clusters(
            days=days, min_level="medium", direction="sell"
        )

        logger.info(f"Computing performance for {len(buy_clusters)} buy + {len(sell_clusters)} sell clusters")

        # 2. Fetch SPY history once
        loop = asyncio.get_event_loop()
        spy_prices = await loop.run_in_executor(_executor, _fetch_spy_history_sync, days + 60)

        # 3. Fetch industry for each CIK
        ciks = list(set(
            [c.cik for c in buy_clusters] + [c.cik for c in sell_clusters]
        ))
        industry_map = await SignalPerformanceService._fetch_industries(ciks)

        # 4. Compute performance in thread pool
        all_clusters = [(c, "buy") for c in buy_clusters] + [(c, "sell") for c in sell_clusters]
        tasks = [
            loop.run_in_executor(_executor, _compute_signal_perf, c, spy_prices, d)
            for c, d in all_clusters
        ]
        results = await asyncio.gather(*tasks)
        performances = [r for r in results if r is not None]

        # Add industry
        for perf in performances:
            perf["industry"] = industry_map.get(perf["cik"])

        # 5. Check 8-K follow for buy signals
        buy_ciks = list(set(p["cik"] for p in performances if p["direction"] == "buy"))
        eight_k_map = await SignalPerformanceService._fetch_8k_follow(buy_ciks)
        for perf in performances:
            if perf["direction"] == "buy":
                follow = eight_k_map.get(perf["cik"], {})
                # Find 8-K events AFTER signal date
                events_after = [
                    e for e in follow.get("events", [])
                    if e["filing_date"] and e["filing_date"] > perf["signal_date"]
                ]
                perf["followed_by_8k"] = len(events_after) > 0
                if events_after:
                    try:
                        first_dt = datetime.strptime(events_after[0]["filing_date"], "%Y-%m-%d")
                        signal_dt = datetime.strptime(perf["signal_date"], "%Y-%m-%d")
                        perf["days_to_8k"] = (first_dt - signal_dt).days
                    except (ValueError, TypeError):
                        perf["days_to_8k"] = None
                else:
                    perf["days_to_8k"] = None
            else:
                perf["followed_by_8k"] = None
                perf["days_to_8k"] = None

        # 6. Store in Neo4j
        stored = await SignalPerformanceService._store_batch(performances)

        elapsed = round(time.time() - start_time, 1)
        summary = {
            "total_clusters": len(all_clusters),
            "computed": len(performances),
            "stored": stored,
            "buy_count": sum(1 for p in performances if p["direction"] == "buy"),
            "sell_count": sum(1 for p in performances if p["direction"] == "sell"),
            "mature_count": sum(1 for p in performances if p["is_mature"]),
            "elapsed_seconds": elapsed,
        }
        logger.info(f"Signal performance computation complete: {summary}")
        return summary

    @staticmethod
    async def _fetch_industries(ciks: list[str]) -> dict[str, Optional[str]]:
        """Fetch SIC description for each CIK."""
        if not ciks:
            return {}
        query = """
            MATCH (c:Company)
            WHERE c.cik IN $ciks
            RETURN c.cik as cik, c.sic_description as industry
        """
        results = await Neo4jClient.execute_query(query, {"ciks": ciks})
        return {r["cik"]: r["industry"] for r in results}

    @staticmethod
    async def _fetch_8k_follow(ciks: list[str]) -> dict[str, dict]:
        """Fetch 8-K events for given CIKs, grouped by CIK."""
        if not ciks:
            return {}
        query = """
            MATCH (c:Company)-[:FILED_EVENT]->(e:Event)
            WHERE c.cik IN $ciks AND e.is_ma_signal = true
            RETURN c.cik as cik, e.filing_date as filing_date,
                   e.item_number as item_number
            ORDER BY c.cik, e.filing_date
        """
        results = await Neo4jClient.execute_query(query, {"ciks": ciks})
        grouped: dict[str, dict] = {}
        for r in results:
            cik = r["cik"]
            if cik not in grouped:
                grouped[cik] = {"events": []}
            grouped[cik]["events"].append({
                "filing_date": r["filing_date"],
                "item_number": r["item_number"],
            })
        return grouped

    @staticmethod
    async def _store_batch(performances: list[dict]) -> int:
        """Store SignalPerformance nodes in Neo4j via MERGE."""
        if not performances:
            return 0

        stored = 0
        for perf in performances:
            query = """
                MERGE (sp:SignalPerformance {signal_id: $signal_id})
                SET sp.ticker = $ticker,
                    sp.company_name = $company_name,
                    sp.cik = $cik,
                    sp.signal_date = $signal_date,
                    sp.direction = $direction,
                    sp.signal_level = $signal_level,
                    sp.num_insiders = $num_insiders,
                    sp.total_value = $total_value,
                    sp.conviction_tier = $conviction_tier,
                    sp.industry = $industry,
                    sp.market_cap = $market_cap,
                    sp.pct_of_mcap = $pct_of_mcap,
                    sp.price_day0 = $price_day0,
                    sp.price_day1 = $price_day1,
                    sp.price_day2 = $price_day2,
                    sp.price_day3 = $price_day3,
                    sp.price_day5 = $price_day5,
                    sp.price_day7 = $price_day7,
                    sp.price_day30 = $price_day30,
                    sp.return_day0 = $return_day0,
                    sp.return_day1 = $return_day1,
                    sp.return_day2 = $return_day2,
                    sp.return_day3 = $return_day3,
                    sp.return_day5 = $return_day5,
                    sp.return_day7 = $return_day7,
                    sp.spy_return_30d = $spy_return_30d,
                    sp.followed_by_8k = $followed_by_8k,
                    sp.days_to_8k = $days_to_8k,
                    sp.is_mature = $is_mature,
                    sp.computed_at = $computed_at
                WITH sp
                MATCH (c:Company {cik: $cik})
                MERGE (c)-[:HAS_SIGNAL_PERF]->(sp)
            """
            try:
                await Neo4jClient.execute_write(query, perf)
                stored += 1
            except Exception as e:
                logger.warning(f"Failed to store SignalPerformance {perf['signal_id']}: {e}")

        return stored

    @staticmethod
    async def get_all(
        direction: Optional[str] = None,
        mature_only: bool = False,
        meaningful_only: bool = False,
        limit: int = 500,
    ) -> list[dict]:
        """Query all SignalPerformance nodes from Neo4j.

        Args:
            meaningful_only: Filter to trades 0.01-1% of market cap (removes noise).
        """
        conditions = []
        params: dict = {"limit": limit}

        if direction:
            conditions.append("sp.direction = $direction")
            params["direction"] = direction
        if mature_only:
            conditions.append("sp.is_mature = true")
        if meaningful_only:
            conditions.append("sp.pct_of_mcap >= 0.01 AND sp.pct_of_mcap <= 1.0")

        where = "WHERE " + " AND ".join(conditions) if conditions else ""

        query = f"""
            MATCH (sp:SignalPerformance)
            {where}
            RETURN sp
            ORDER BY sp.signal_date DESC
            LIMIT $limit
        """
        results = await Neo4jClient.execute_query(query, params)
        return [dict(r["sp"]) for r in results]

    @staticmethod
    async def get_summary(meaningful_only: bool = False) -> dict:
        """Aggregate stats for the showcase page header."""
        mcap_filter = "AND sp.pct_of_mcap >= 0.01 AND sp.pct_of_mcap <= 1.0" if meaningful_only else ""
        query = f"""
            MATCH (sp:SignalPerformance)
            WHERE sp.is_mature = true {mcap_filter}
            WITH sp,
                 CASE WHEN sp.direction = 'buy' THEN 1 ELSE 0 END as is_buy,
                 CASE WHEN sp.direction = 'sell' THEN 1 ELSE 0 END as is_sell
            RETURN count(sp) as total,
                   sum(is_buy) as buy_count,
                   sum(is_sell) as sell_count,
                   avg(CASE WHEN sp.direction = 'buy' AND sp.return_day0 IS NOT NULL
                       THEN sp.return_day0 END) as buy_avg_return,
                   avg(CASE WHEN sp.direction = 'sell' AND sp.return_day0 IS NOT NULL
                       THEN -sp.return_day0 END) as sell_avg_short_return,
                   avg(sp.spy_return_30d) as avg_spy_return,
                   sum(CASE WHEN sp.direction = 'buy' AND sp.return_day0 IS NOT NULL
                       AND sp.return_day0 > 0 THEN 1 ELSE 0 END) as buy_wins,
                   sum(CASE WHEN sp.direction = 'sell' AND sp.return_day0 IS NOT NULL
                       AND sp.return_day0 < 0 THEN 1 ELSE 0 END) as sell_correct,
                   sum(CASE WHEN sp.followed_by_8k = true THEN 1 ELSE 0 END) as followed_by_8k
        """
        results = await Neo4jClient.execute_query(query, {})
        if not results:
            return {}

        r = results[0]
        buy_count = r["buy_count"] or 0
        sell_count = r["sell_count"] or 0

        return {
            "total_mature": r["total"],
            "buy_count": buy_count,
            "sell_count": sell_count,
            "buy_avg_return_30d": round(r["buy_avg_return"], 2) if r["buy_avg_return"] else None,
            "buy_win_rate": round((r["buy_wins"] or 0) / buy_count * 100, 1) if buy_count > 0 else None,
            "sell_avg_short_return": round(r["sell_avg_short_return"], 2) if r["sell_avg_short_return"] else None,
            "sell_correct_rate": round((r["sell_correct"] or 0) / sell_count * 100, 1) if sell_count > 0 else None,
            "avg_spy_return": round(r["avg_spy_return"], 2) if r["avg_spy_return"] else None,
            "eight_k_follow_rate": round((r["followed_by_8k"] or 0) / buy_count * 100, 1) if buy_count > 0 else None,
        }

    @staticmethod
    async def get_delayed_entry_stats(meaningful_only: bool = False) -> dict:
        """Aggregate delayed entry analysis: avg return at each delay point."""
        mcap_filter = "AND sp.pct_of_mcap >= 0.01 AND sp.pct_of_mcap <= 1.0" if meaningful_only else ""
        query = f"""
            MATCH (sp:SignalPerformance)
            WHERE sp.is_mature = true {mcap_filter}
            RETURN sp.direction as direction,
                   avg(sp.return_day0) as avg_day0,
                   avg(sp.return_day1) as avg_day1,
                   avg(sp.return_day2) as avg_day2,
                   avg(sp.return_day3) as avg_day3,
                   avg(sp.return_day5) as avg_day5,
                   avg(sp.return_day7) as avg_day7,
                   count(sp) as n,
                   avg(sp.spy_return_30d) as avg_spy
        """
        results = await Neo4jClient.execute_query(query, {})
        stats = {}
        for r in results:
            d = r["direction"]
            spy = r["avg_spy"] or 0
            entries = {}
            for day in [0, 1, 2, 3, 5, 7]:
                avg = r[f"avg_day{day}"]
                if avg is not None:
                    ret = round(float(avg), 2)
                    # For sell: invert return (short profit)
                    if d == "sell":
                        ret = round(-ret, 2)
                    entries[f"day{day}"] = {
                        "avg_return": ret,
                        "alpha": round(ret - (float(-spy) if d == "sell" else float(spy)), 2) if spy else None,
                    }
            stats[d] = {
                "entries": entries,
                "n": r["n"],
                "avg_spy_return": round(float(spy), 2) if spy else None,
            }
        return stats

    @staticmethod
    async def get_conviction_ladder(meaningful_only: bool = False) -> list[dict]:
        """Win rate by num_insiders threshold for sell signals."""
        mcap_filter = "AND sp.pct_of_mcap >= 0.01 AND sp.pct_of_mcap <= 1.0" if meaningful_only else ""
        query = f"""
            MATCH (sp:SignalPerformance)
            WHERE sp.is_mature = true AND sp.direction = 'sell' {mcap_filter}
            RETURN sp.num_insiders as num_insiders,
                   count(sp) as total,
                   sum(CASE WHEN sp.return_day0 < 0 THEN 1 ELSE 0 END) as correct,
                   avg(-sp.return_day0) as avg_short_return
            ORDER BY num_insiders
        """
        results = await Neo4jClient.execute_query(query, {})

        # Build cumulative thresholds (4+, 5+, 6+, 7+, 8+)
        ladder = []
        for threshold in [4, 5, 6, 7, 8]:
            matching = [r for r in results if (r["num_insiders"] or 0) >= threshold]
            if not matching:
                continue
            total = sum(r["total"] for r in matching)
            correct = sum(r["correct"] or 0 for r in matching)
            avg_ret = sum((r["avg_short_return"] or 0) * r["total"] for r in matching) / total if total > 0 else 0
            ladder.append({
                "threshold": f"{threshold}+",
                "total": total,
                "correct": correct,
                "correct_rate": round(correct / total * 100, 1) if total > 0 else None,
                "avg_short_return": round(float(avg_ret), 2),
            })
        return ladder

    @staticmethod
    async def get_industry_breakdown(meaningful_only: bool = False) -> list[dict]:
        """Win rate by industry for buy signals."""
        mcap_filter = "AND sp.pct_of_mcap >= 0.01 AND sp.pct_of_mcap <= 1.0" if meaningful_only else ""
        query = f"""
            MATCH (sp:SignalPerformance)
            WHERE sp.is_mature = true AND sp.direction = 'buy'
              AND sp.industry IS NOT NULL {mcap_filter}
            RETURN sp.industry as industry,
                   count(sp) as total,
                   sum(CASE WHEN sp.return_day0 > 0 THEN 1 ELSE 0 END) as wins,
                   avg(sp.return_day0) as avg_return
            ORDER BY total DESC
        """
        results = await Neo4jClient.execute_query(query, {})
        return [
            {
                "industry": r["industry"],
                "total": r["total"],
                "wins": r["wins"] or 0,
                "win_rate": round((r["wins"] or 0) / r["total"] * 100, 1) if r["total"] > 0 else None,
                "avg_return": round(float(r["avg_return"]), 2) if r["avg_return"] else None,
            }
            for r in results
            if r["total"] >= 3  # Min 3 signals for meaningful stats
        ]
