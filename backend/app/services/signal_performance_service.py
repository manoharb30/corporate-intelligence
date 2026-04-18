"""Signal performance service — computes returns, alpha, conviction tiers.

Uses STORED data only (Company.price_series, Company.market_cap).
Zero yfinance calls during computation.
Historical market cap estimated from price ratio.
Deletes all SignalPerformance before recomputing (no stale nodes).

Rewritten 2026-04-17 via TDD. 33 tests define the contract.
"""

import asyncio
import json
import logging
import time
from datetime import datetime, timedelta
from typing import Optional

from app.db.neo4j_client import Neo4jClient
from app.services.insider_cluster_service import InsiderClusterService

logger = logging.getLogger(__name__)

DELAY_DAYS = [0, 1, 2, 3, 5, 7]
HORIZON_DAYS = 90
MIN_AGE_DAYS = HORIZON_DAYS + max(DELAY_DAYS)  # 97


# === Pure computation functions (no DB, fully testable) ===


def find_price(series: list[dict] | None, target_date: str, max_skip: int = 5) -> Optional[float]:
    """Find closing price on or up to max_skip days after target_date.

    Args:
        series: list of {"d": "YYYY-MM-DD", "c": float} sorted by date
        target_date: date string "YYYY-MM-DD"
        max_skip: max days to scan forward (for weekends/holidays)

    Returns:
        closing price or None if not found within window
    """
    if not series:
        return None
    try:
        target = datetime.strptime(target_date[:10], "%Y-%m-%d")
    except (ValueError, TypeError):
        return None

    by_date = {e["d"]: float(e["c"]) for e in series if "d" in e and "c" in e}
    for skip in range(max_skip + 1):
        check = (target + timedelta(days=skip)).strftime("%Y-%m-%d")
        if check in by_date:
            return by_date[check]
    return None


def estimate_historical_mcap(
    current_mcap: Optional[float],
    current_price: Optional[float],
    signal_price: Optional[float],
) -> Optional[float]:
    """Estimate market cap at signal date from price ratio.

    Formula: historical_mcap = current_mcap × (signal_price / current_price)
    Assumes shares outstanding stayed roughly constant.
    """
    if not current_mcap or not current_price or not signal_price:
        return None
    if current_price <= 0:
        return None
    return round(current_mcap * (signal_price / current_price))


def compute_returns(
    entry_prices: dict[int, float], exit_price: Optional[float]
) -> dict[int, float]:
    """Compute 90-day return from each delay entry point.

    Args:
        entry_prices: {delay_day: price} e.g., {0: 50.0, 1: 51.0}
        exit_price: price at day 90

    Returns:
        {delay_day: return_pct} e.g., {0: 20.0, 1: 17.65}
    """
    if exit_price is None:
        return {}
    results = {}
    for day, entry in entry_prices.items():
        if entry and entry > 0:
            ret = round((exit_price - entry) / entry * 100, 2)
            results[day] = float(ret)
    return results


def compute_conviction_tier(
    historical_mcap: Optional[float],
    total_value: float,
    num_buyers: int,
) -> str:
    """Compute conviction tier from historical market cap and cluster criteria.

    strong_buy: midcap ($300M-$5B) + $100K+ value + 2+ buyers
    buy: midcap OR $100K+ (one condition met, 2+ buyers)
    watch: below both thresholds or single buyer

    Upper cap tightened from $10B to $5B based on analysis:
    $5B-$10B bucket had 38.1% HR vs 67.4% for <$5B (p=0.018, CIs don't overlap).
    """
    if num_buyers < 2:
        return "watch"

    is_midcap = (
        historical_mcap is not None
        and 300_000_000 <= historical_mcap <= 5_000_000_000
    )
    has_value = total_value >= 100_000

    if is_midcap and has_value:
        return "strong_buy"
    if is_midcap or has_value:
        return "buy"
    return "watch"


def compute_alpha(
    signal_return: Optional[float], spy_return: Optional[float]
) -> Optional[float]:
    """Compute alpha: signal return minus SPY return."""
    if signal_return is None or spy_return is None:
        return None
    return round(signal_return - spy_return, 2)


def compute_pct_of_mcap(
    total_value: float, historical_mcap: Optional[float]
) -> Optional[float]:
    """Compute buy value as percentage of market cap."""
    if not historical_mcap or historical_mcap <= 0:
        return None
    return round((total_value / historical_mcap) * 100, 6)


def check_maturity(age_days: int, price_day90: Optional[float]) -> bool:
    """Check if signal is mature (97+ days old with day-90 price available)."""
    return age_days >= MIN_AGE_DAYS and price_day90 is not None


# === Service class (DB interaction) ===


class SignalPerformanceService:
    """Computes and stores signal performance data in Neo4j."""

    @staticmethod
    async def compute_all(days: int = 730) -> dict:
        """Detect all clusters, compute performance from stored data, store in Neo4j.

        1. DELETE all existing SignalPerformance nodes
        2. Detect clusters
        3. Batch-fetch price_series + market_cap for all companies + SPY
        4. Compute performance for each cluster
        5. Batch-store via UNWIND
        """
        start_time = time.time()

        # 1. Clean slate
        del_result = await Neo4jClient.execute_query(
            "MATCH (sp:SignalPerformance) DETACH DELETE sp RETURN count(sp) as deleted"
        )
        deleted = del_result[0]["deleted"] if del_result else 0
        logger.info(f"Deleted {deleted} existing SignalPerformance nodes")

        # 2. Detect clusters
        buy_clusters = await InsiderClusterService.detect_clusters(
            days=days, min_level="medium", direction="buy"
        )
        sell_clusters = await InsiderClusterService.detect_clusters(
            days=days, min_level="medium", direction="sell"
        )
        logger.info(
            f"Detected {len(buy_clusters)} buy + {len(sell_clusters)} sell clusters"
        )

        # 3. Batch-fetch company data + SPY + filing dates
        all_ciks = list(
            set(c.cik for c in buy_clusters + sell_clusters if c.cik)
        )
        company_data = await SignalPerformanceService._fetch_company_data(all_ciks)
        spy_series = await SignalPerformanceService._fetch_spy_series()
        industry_map = await SignalPerformanceService._fetch_industries(all_ciks)
        filing_date_map = await SignalPerformanceService._fetch_filing_dates(all_ciks)

        now = datetime.now()

        # 4. Compute performance for each cluster
        performances = []
        all_clusters = [(c, "buy") for c in buy_clusters] + [
            (c, "sell") for c in sell_clusters
        ]

        for cluster, direction in all_clusters:
            perf = SignalPerformanceService._compute_one(
                cluster, direction, company_data, spy_series, industry_map, filing_date_map, now
            )
            if perf:
                performances.append(perf)

        # 5. Batch-store
        stored = await SignalPerformanceService._store_batch(performances)

        # 6. Precompute dashboard hero stats and save as blob
        await SignalPerformanceService._save_dashboard_stats(performances)

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
        logger.info(f"Signal performance complete: {summary}")
        return summary

    @staticmethod
    def _compute_one(
        cluster,
        direction: str,
        company_data: dict,
        spy_series: list[dict],
        industry_map: dict,
        filing_date_map: dict,
        now: datetime,
    ) -> Optional[dict]:
        """Compute performance for a single cluster using stored data.

        Returns are calculated from the FILING DATE (when public knows),
        not the transaction date (when insider traded). This avoids look-ahead bias.
        signal_date (transaction date) is kept for display purposes.
        """
        if not cluster.ticker or not cluster.cik:
            return None

        signal_date = cluster.window_end  # transaction date — for display
        try:
            signal_dt = datetime.strptime(signal_date[:10], "%Y-%m-%d")
        except (ValueError, TypeError):
            return None

        # Actionable date = latest filing_date for this cluster's transactions
        # This is when a hedge fund could first act on the information
        cik_filings = filing_date_map.get(cluster.cik, {})
        actionable_date = cik_filings.get(signal_date, signal_date)  # fall back to signal_date
        try:
            actionable_dt = datetime.strptime(actionable_date[:10], "%Y-%m-%d")
            age = (now - actionable_dt).days
        except (ValueError, TypeError):
            actionable_dt = signal_dt
            age = (now - signal_dt).days

        cd = company_data.get(cluster.cik, {})
        series = cd.get("series", [])
        current_mcap = cd.get("market_cap")

        if not series:
            return None

        # Entry prices at each delay point — FROM ACTIONABLE DATE (filing date)
        delay_prices = {}
        for d in DELAY_DAYS:
            entry_date = (actionable_dt + timedelta(days=d)).strftime("%Y-%m-%d")
            p = find_price(series, entry_date)
            if p is not None:
                delay_prices[d] = float(round(p, 2))

        if 0 not in delay_prices:
            return None

        # Exit price at day 90 FROM ACTIONABLE DATE
        exit_date = (actionable_dt + timedelta(days=HORIZON_DAYS)).strftime("%Y-%m-%d")
        price_day90 = find_price(series, exit_date)
        if price_day90 is not None:
            price_day90 = float(round(price_day90, 2))

        # Maturity
        is_mature = check_maturity(age, price_day90)

        # Returns
        returns = compute_returns(delay_prices, price_day90)

        # Current price (latest in series) + current return
        current_price = float(round(series[-1]["c"], 2)) if series else None
        current_date = series[-1]["d"] if series else None
        signal_price = delay_prices.get(0)
        return_current = None
        if current_price and signal_price and signal_price > 0:
            return_current = float(round((current_price - signal_price) / signal_price * 100, 2))

        # Historical market cap (uses signal_date price for estimation, not actionable)
        hist_price = find_price(series, signal_date)
        historical_mcap = estimate_historical_mcap(current_mcap, current_price, hist_price)

        # Conviction tier (using historical market cap)
        conviction_tier = compute_conviction_tier(
            historical_mcap, cluster.total_buy_value, cluster.num_buyers
        )

        # SPY return + alpha FROM ACTIONABLE DATE
        spy_at_actionable = find_price(spy_series, actionable_date)
        spy_at_exit = find_price(spy_series, exit_date) if is_mature else None
        spy_return_90d = None
        if spy_at_actionable and spy_at_exit and spy_at_actionable > 0:
            spy_return_90d = float(
                round((spy_at_exit - spy_at_actionable) / spy_at_actionable * 100, 2)
            )

        # pct_of_mcap
        pct_of_mcap = compute_pct_of_mcap(cluster.total_buy_value, historical_mcap)

        result = {
            "signal_id": cluster.accession_number,
            "ticker": cluster.ticker,
            "company_name": cluster.company_name,
            "cik": cluster.cik,
            "signal_date": signal_date,
            "actionable_date": actionable_date,
            "direction": direction,
            "signal_level": cluster.signal_level,
            "num_insiders": cluster.num_buyers,
            "total_value": float(cluster.total_buy_value),
            "conviction_tier": conviction_tier,
            "industry": industry_map.get(cluster.cik),
            "market_cap": historical_mcap,
            "pct_of_mcap": pct_of_mcap,
            "price_day90": price_day90,
            "price_current": current_price,
            "price_current_date": current_date,
            "return_current": return_current,
            "spy_return_90d": spy_return_90d,
            "is_mature": is_mature,
            "computed_at": now.isoformat(),
        }

        for d in DELAY_DAYS:
            result[f"price_day{d}"] = delay_prices.get(d)
            result[f"return_day{d}"] = returns.get(d)

        return result

    @staticmethod
    async def _fetch_company_data(ciks: list[str]) -> dict:
        """Batch-fetch price_series + market_cap for all companies."""
        if not ciks:
            return {}
        results = await Neo4jClient.execute_query(
            "UNWIND $ciks AS cik "
            "MATCH (c:Company {cik: cik}) "
            "RETURN c.cik AS cik, c.market_cap AS market_cap, c.price_series AS price_series",
            {"ciks": ciks},
        )
        data = {}
        for r in results:
            series = []
            if r.get("price_series"):
                try:
                    series = json.loads(r["price_series"])
                except (ValueError, TypeError):
                    pass
            data[r["cik"]] = {
                "market_cap": r.get("market_cap"),
                "series": series,
            }
        return data

    @staticmethod
    async def _fetch_spy_series() -> list[dict]:
        """Fetch SPY price_series from Company node."""
        result = await Neo4jClient.execute_query(
            "MATCH (c:Company {ticker: 'SPY'}) RETURN c.price_series AS ps"
        )
        if result and result[0].get("ps"):
            try:
                return json.loads(result[0]["ps"])
            except (ValueError, TypeError):
                pass
        return []

    @staticmethod
    async def _fetch_filing_dates(ciks: list[str]) -> dict:
        """Fetch latest filing_date per (CIK, transaction_date) for actionable date.

        Returns: {cik: {transaction_date: latest_filing_date}}
        For each cluster, the actionable date is the latest filing_date
        among transactions on the cluster's window_end date.
        """
        if not ciks:
            return {}
        results = await Neo4jClient.execute_query(
            "MATCH (c:Company)-[:INSIDER_TRADE_OF]->(t:InsiderTransaction) "
            "WHERE c.cik IN $ciks AND t.transaction_code = 'P' "
            "AND t.classification = 'GENUINE' AND t.filing_date IS NOT NULL "
            "RETURN c.cik AS cik, t.transaction_date AS txn_date, "
            "max(t.filing_date) AS latest_filing_date",
            {"ciks": ciks},
        )
        filing_map: dict[str, dict[str, str]] = {}
        for r in results:
            cik = r["cik"]
            txn_date = str(r["txn_date"] or "")[:10]
            filing_date = str(r["latest_filing_date"] or "")[:10]
            if cik not in filing_map:
                filing_map[cik] = {}
            # Keep the latest filing_date for each transaction_date
            existing = filing_map[cik].get(txn_date, "")
            if filing_date > existing:
                filing_map[cik][txn_date] = filing_date
        return filing_map

    @staticmethod
    async def _fetch_industries(ciks: list[str]) -> dict:
        """Fetch SIC description for each CIK."""
        if not ciks:
            return {}
        results = await Neo4jClient.execute_query(
            "MATCH (c:Company) WHERE c.cik IN $ciks "
            "RETURN c.cik AS cik, c.sic_description AS industry",
            {"ciks": ciks},
        )
        return {r["cik"]: r["industry"] for r in results}

    @staticmethod
    async def _store_batch(performances: list[dict]) -> int:
        """Batch-store SignalPerformance nodes via UNWIND."""
        if not performances:
            return 0

        # Process in chunks of 100
        stored = 0
        for i in range(0, len(performances), 100):
            chunk = performances[i : i + 100]
            try:
                await Neo4jClient.execute_query(
                    """
                    UNWIND $batch AS row
                    CREATE (sp:SignalPerformance {
                        signal_id: row.signal_id,
                        ticker: row.ticker,
                        company_name: row.company_name,
                        cik: row.cik,
                        signal_date: row.signal_date,
                        actionable_date: COALESCE(row.actionable_date, row.signal_date),
                        direction: row.direction,
                        signal_level: row.signal_level,
                        num_insiders: row.num_insiders,
                        total_value: row.total_value,
                        conviction_tier: row.conviction_tier,
                        industry: row.industry,
                        market_cap: row.market_cap,
                        pct_of_mcap: row.pct_of_mcap,
                        price_day0: row.price_day0,
                        price_day1: row.price_day1,
                        price_day2: row.price_day2,
                        price_day3: row.price_day3,
                        price_day5: row.price_day5,
                        price_day7: row.price_day7,
                        price_day90: row.price_day90,
                        price_current: row.price_current,
                        price_current_date: row.price_current_date,
                        return_current: row.return_current,
                        return_day0: row.return_day0,
                        return_day1: row.return_day1,
                        return_day2: row.return_day2,
                        return_day3: row.return_day3,
                        return_day5: row.return_day5,
                        return_day7: row.return_day7,
                        spy_return_90d: row.spy_return_90d,
                        is_mature: row.is_mature,
                        computed_at: row.computed_at
                    })
                    WITH sp, row
                    MATCH (c:Company {cik: row.cik})
                    MERGE (c)-[:HAS_SIGNAL_PERF]->(sp)
                    """,
                    {"batch": chunk},
                )
                stored += len(chunk)
            except Exception as e:
                logger.warning(f"Failed to store batch {i}-{i+len(chunk)}: {e}")

        return stored

    # === Query methods (unchanged interface for routes) ===

    @staticmethod
    async def get_all(
        direction: Optional[str] = None,
        mature_only: bool = False,
        meaningful_only: bool = False,
        limit: int = 500,
    ) -> list[dict]:
        """Query SignalPerformance nodes from Neo4j."""
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
        """Aggregate stats for the dashboard header."""
        mcap_filter = (
            "AND sp.pct_of_mcap >= 0.01 AND sp.pct_of_mcap <= 1.0"
            if meaningful_only
            else ""
        )
        query = f"""
            MATCH (sp:SignalPerformance)
            WHERE sp.is_mature = true {mcap_filter}
            WITH sp,
                 CASE WHEN sp.direction = 'buy' THEN 1 ELSE 0 END AS is_buy,
                 CASE WHEN sp.direction = 'sell' THEN 1 ELSE 0 END AS is_sell
            RETURN count(sp) AS total,
                   sum(is_buy) AS buy_count,
                   sum(is_sell) AS sell_count,
                   avg(CASE WHEN sp.direction = 'buy' AND sp.return_day0 IS NOT NULL
                       THEN sp.return_day0 END) AS buy_avg_return,
                   avg(sp.spy_return_90d) AS avg_spy_return,
                   sum(CASE WHEN sp.direction = 'buy' AND sp.return_day0 IS NOT NULL
                       AND sp.return_day0 > 0 THEN 1 ELSE 0 END) AS buy_wins
        """
        results = await Neo4jClient.execute_query(query, {})
        if not results:
            return {}

        r = results[0]
        buy_count = r["buy_count"] or 0

        return {
            "total_mature": r["total"],
            "buy_count": buy_count,
            "sell_count": r["sell_count"] or 0,
            "buy_avg_return_90d": (
                round(r["buy_avg_return"], 2) if r["buy_avg_return"] else None
            ),
            "buy_win_rate": (
                round((r["buy_wins"] or 0) / buy_count * 100, 1)
                if buy_count > 0
                else None
            ),
            "avg_spy_return": (
                round(r["avg_spy_return"], 2) if r["avg_spy_return"] else None
            ),
        }

    @staticmethod
    async def _save_dashboard_stats(performances: list[dict]) -> None:
        """Precompute and save dashboard hero stats as a single node.

        Called after compute_all. Dashboard reads this blob instead of
        fetching all 500+ SignalPerformance records.
        """
        strong_buy_mature = [
            p for p in performances
            if p["direction"] == "buy"
            and p["conviction_tier"] == "strong_buy"
            and p["is_mature"]
        ]

        n = len(strong_buy_mature)
        if n == 0:
            return

        wins = sum(1 for p in strong_buy_mature if (p.get("return_day0") or 0) > 0)
        hit_rate = round(wins / n * 100, 1)

        with_spy = [p for p in strong_buy_mature if p.get("spy_return_90d") is not None]
        alphas = [(p.get("return_day0") or 0) - (p.get("spy_return_90d") or 0) for p in with_spy]
        avg_alpha = round(sum(alphas) / len(alphas), 1) if alphas else 0
        beat_spy = sum(1 for a in alphas if a > 0)
        beat_spy_pct = round(beat_spy / len(with_spy) * 100, 1) if with_spy else 0

        avg_return = round(
            sum(p.get("return_day0") or 0 for p in strong_buy_mature) / n, 1
        )

        stats = {
            "total_signals": n,
            "wins": wins,
            "losses": n - wins,
            "hit_rate": hit_rate,
            "avg_return": avg_return,
            "avg_alpha": avg_alpha,
            "beat_spy_pct": beat_spy_pct,
            "computed_at": datetime.now().isoformat(),
        }

        await Neo4jClient.execute_query(
            "MERGE (ds:DashboardStats {id: 'hero'}) "
            "SET ds.total_signals = $total_signals, "
            "    ds.wins = $wins, "
            "    ds.losses = $losses, "
            "    ds.hit_rate = $hit_rate, "
            "    ds.avg_return = $avg_return, "
            "    ds.avg_alpha = $avg_alpha, "
            "    ds.beat_spy_pct = $beat_spy_pct, "
            "    ds.computed_at = $computed_at",
            stats,
        )
        logger.info(f"Dashboard stats saved: {stats}")

    @staticmethod
    async def get_dashboard_stats() -> Optional[dict]:
        """Read precomputed dashboard hero stats. Instant — no computation."""
        results = await Neo4jClient.execute_query(
            "MATCH (ds:DashboardStats {id: 'hero'}) "
            "RETURN ds.total_signals as total_signals, ds.wins as wins, "
            "ds.losses as losses, ds.hit_rate as hit_rate, "
            "ds.avg_return as avg_return, ds.avg_alpha as avg_alpha, "
            "ds.beat_spy_pct as beat_spy_pct, ds.computed_at as computed_at"
        )
        if not results:
            return None
        return dict(results[0])
