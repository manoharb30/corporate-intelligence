"""Service for detecting standalone insider buying clusters as first-class signals.

Insider buying clusters often PRECEDE material announcements by weeks/months,
making them the most actionable leading indicator. This service detects clusters
purely from Form 4 data — no 8-K required.
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Optional

from app.db.neo4j_client import Neo4jClient
from app.services.feed_service import pick_ticker, FeedService, InsiderContext
from app.services.trade_classifier import (
    classify_trades_batch,
    is_bullish_trade,
    is_bearish_trade,
)
from app.services.stock_price_service import StockPriceService

logger = logging.getLogger(__name__)


@dataclass
class BuyerDetail:
    """Detail about a single insider buyer in a cluster."""

    name: str
    title: str
    total_value: float
    trade_count: int

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "title": self.title,
            "total_value": self.total_value,
            "trade_count": self.trade_count,
        }


@dataclass
class InsiderClusterSignal:
    """A standalone insider cluster signal (no 8-K required)."""

    cik: str
    company_name: str
    ticker: Optional[str]
    window_start: str  # YYYY-MM-DD
    window_end: str  # YYYY-MM-DD
    signal_level: str  # high, medium, low
    signal_summary: str
    num_buyers: int
    total_buy_value: float
    buyers: list[BuyerDetail] = field(default_factory=list)

    @property
    def accession_number(self) -> str:
        return f"CLUSTER-{self.cik}-{self.window_end}"

    def to_signal_dict(self) -> dict:
        """Shape output to match SignalItem.to_dict() for unified feed."""
        return {
            "company_name": self.company_name,
            "cik": self.cik,
            "ticker": self.ticker,
            "filing_date": self.window_end,
            "signal_level": self.signal_level,
            "signal_summary": self.signal_summary,
            "items": [],
            "item_names": [],
            "persons_mentioned": [],
            "accession_number": self.accession_number,
            "combined_signal_level": self.signal_level,
            "insider_context": {
                "net_direction": "buying",
                "total_buy_value": self.total_buy_value,
                "total_sell_value": 0,
                "notable_trades": [
                    f"{b.name} bought ${b.total_value:,.0f}"
                    for b in self.buyers[:5]
                ],
                "cluster_activity": True,
                "trade_count": sum(b.trade_count for b in self.buyers),
                "person_matches": [],
                "near_filing_count": sum(b.trade_count for b in self.buyers),
                "near_filing_direction": "buying",
            },
            "signal_type": "insider_cluster",
            "cluster_detail": {
                "window_start": self.window_start,
                "window_end": self.window_end,
                "num_buyers": self.num_buyers,
                "buyers": [b.to_dict() for b in self.buyers],
            },
        }


class InsiderClusterService:
    """Detects insider buying clusters as standalone signals."""

    @staticmethod
    async def detect_clusters(
        days: int = 90,
        window_days: int = 30,
        min_level: str = "medium",
    ) -> list[InsiderClusterSignal]:
        """
        Detect insider buying clusters from Form 4 data.

        1. Query all P (purchase) and M (exercise) trades in the last `days` days
        2. Group by company CIK
        3. Classify trades to handle exercise_hold vs exercise_sell
        4. Use a 30-day sliding window from the latest bullish trade backward
        5. Count distinct buyers -> classify: 3+ = HIGH, 2+ or >$500K = MEDIUM, 1 = LOW

        Args:
            days: Look back this many days for trades
            window_days: Sliding window size for cluster detection
            min_level: Minimum signal level to include

        Returns:
            List of InsiderClusterSignal sorted by level then date
        """
        since_date = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")

        query = """
            MATCH (c:Company)-[:INSIDER_TRADE_OF]->(t:InsiderTransaction)<-[:TRADED_BY]-(p:Person)
            WHERE t.transaction_date >= $since_date
              AND t.transaction_code IN ['P', 'M']
            RETURN c.cik as cik,
                   c.name as company_name,
                   c.tickers as tickers,
                   t.transaction_date as transaction_date,
                   t.transaction_code as transaction_code,
                   t.total_value as total_value,
                   t.shares as shares,
                   p.name as insider_name,
                   t.insider_title as insider_title
            ORDER BY t.transaction_date DESC
        """
        results = await Neo4jClient.execute_query(query, {"since_date": since_date})

        if not results:
            return []

        # Group by CIK
        trades_by_cik: dict[str, list[dict]] = {}
        company_info: dict[str, dict] = {}
        for r in results:
            cik = r["cik"]
            if cik not in trades_by_cik:
                trades_by_cik[cik] = []
                company_info[cik] = {
                    "name": r["company_name"],
                    "tickers": r.get("tickers"),
                }
            trades_by_cik[cik].append(r)

        level_order = {"high": 0, "medium": 1, "low": 2}
        min_level_order = level_order.get(min_level, 2)

        clusters = []
        for cik, trades in trades_by_cik.items():
            # Classify trades to determine exercise_hold vs exercise_sell
            trade_types = classify_trades_batch(
                trades,
                name_key="insider_name",
                date_key="transaction_date",
                code_key="transaction_code",
            )

            # Filter to only bullish trades with actual dollar value
            # $0 exercises are routine vesting events, not genuine buying signals
            bullish_trades = [
                (t, tt) for t, tt in zip(trades, trade_types)
                if is_bullish_trade(tt) and (t.get("total_value") or 0) > 0
            ]

            if not bullish_trades:
                continue

            # Find the latest bullish trade date as the window end
            latest_date = max(
                t["transaction_date"] for t, _ in bullish_trades
                if t["transaction_date"]
            )

            try:
                window_end_dt = datetime.strptime(latest_date, "%Y-%m-%d")
            except (ValueError, TypeError):
                continue

            window_start_dt = window_end_dt - timedelta(days=window_days)
            window_start = window_start_dt.strftime("%Y-%m-%d")

            # Collect bullish trades within the window
            window_trades = [
                (t, tt) for t, tt in bullish_trades
                if t["transaction_date"] and t["transaction_date"] >= window_start
            ]

            if not window_trades:
                continue

            # Aggregate by buyer
            buyer_agg: dict[str, BuyerDetail] = {}
            for t, _ in window_trades:
                name = t["insider_name"] or "Unknown"
                val = abs(t["total_value"] or 0)
                if name not in buyer_agg:
                    buyer_agg[name] = BuyerDetail(
                        name=name,
                        title=t.get("insider_title") or "",
                        total_value=0,
                        trade_count=0,
                    )
                buyer_agg[name].total_value += val
                buyer_agg[name].trade_count += 1

            num_buyers = len(buyer_agg)
            total_buy_value = sum(b.total_value for b in buyer_agg.values())
            buyers = sorted(buyer_agg.values(), key=lambda b: b.total_value, reverse=True)

            # Classify signal level
            if num_buyers >= 3:
                level = "high"
                summary = f"Insider Cluster: {num_buyers} insiders buying"
            elif num_buyers >= 2 or total_buy_value >= 500_000:
                level = "medium"
                if num_buyers >= 2:
                    summary = f"Insider Cluster: {num_buyers} insiders buying"
                else:
                    summary = f"Insider Buying: ${total_buy_value:,.0f} total"
            else:
                level = "low"
                summary = f"Insider Purchase: {buyers[0].name}" if buyers else "Insider Purchase"

            # Filter by min level
            if level_order.get(level, 2) > min_level_order:
                continue

            info = company_info[cik]
            clusters.append(InsiderClusterSignal(
                cik=cik,
                company_name=info["name"],
                ticker=pick_ticker(info.get("tickers")),
                window_start=window_start,
                window_end=latest_date,
                signal_level=level,
                signal_summary=summary,
                num_buyers=num_buyers,
                total_buy_value=total_buy_value,
                buyers=buyers,
            ))

        # Sort by level then date
        clusters.sort(key=lambda c: c.window_end, reverse=True)
        clusters.sort(key=lambda c: level_order.get(c.signal_level, 2))

        return clusters

    @staticmethod
    async def detect_clusters_excluding_8k(
        days: int = 90,
        window_days: int = 30,
        min_level: str = "medium",
    ) -> list[InsiderClusterSignal]:
        """
        Detect clusters, excluding companies that already have 8-K signals
        in the same time window (to avoid double-counting).
        """
        clusters = await InsiderClusterService.detect_clusters(days, window_days, min_level)

        if not clusters:
            return []

        # Get CIKs of companies with 8-K events in the lookback window
        since_date = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
        query = """
            MATCH (c:Company)-[:FILED_EVENT]->(e:Event)
            WHERE e.is_ma_signal = true
              AND e.filing_date >= $since_date
            RETURN DISTINCT c.cik as cik
        """
        results = await Neo4jClient.execute_query(query, {"since_date": since_date})
        ciks_with_8k = {r["cik"] for r in results}

        return [c for c in clusters if c.cik not in ciks_with_8k]

    @staticmethod
    async def get_cluster_detail(cluster_id: str) -> Optional[dict]:
        """
        Get detailed information for a cluster signal.

        Parses CLUSTER-{cik}-{YYYY-MM-DD} format, fetches all trades for
        that company, and returns a response shaped like EventDetailResponse.

        Args:
            cluster_id: e.g. "CLUSTER-0001234567-2026-02-15"

        Returns:
            Dict matching EventDetailResponse shape, or None
        """
        # Parse cluster ID: CLUSTER-{cik}-{YYYY-MM-DD}
        parts = cluster_id.split("-", 2)
        if len(parts) < 3 or parts[0] != "CLUSTER":
            return None

        # CIK might contain dashes? No, but the date does.
        # Format: CLUSTER-{cik}-{YYYY-MM-DD}
        # Split on "CLUSTER-" then split remaining on the date pattern
        remainder = cluster_id[len("CLUSTER-"):]
        # Find the date at the end (YYYY-MM-DD = 10 chars)
        if len(remainder) < 12:  # cik + "-" + date
            return None

        window_end = remainder[-10:]  # YYYY-MM-DD
        cik = remainder[:-11]  # Everything before the last "-YYYY-MM-DD"

        if not cik or not window_end:
            return None

        try:
            window_end_dt = datetime.strptime(window_end, "%Y-%m-%d")
        except ValueError:
            return None

        window_start_dt = window_end_dt - timedelta(days=30)
        window_start = window_start_dt.strftime("%Y-%m-%d")

        # Get company info
        company_query = """
            MATCH (c:Company {cik: $cik})
            RETURN c.name as name, c.tickers as tickers,
                   c.sic_description as sic_description,
                   c.state_of_incorporation as state_of_incorporation
        """
        company_result = await Neo4jClient.execute_query(company_query, {"cik": cik})
        if not company_result:
            return None

        company = company_result[0]
        company_name = company["name"]
        ticker = pick_ticker(company.get("tickers"))

        # Get all trades for this company (broader window for timeline context)
        trades_query = """
            MATCH (c:Company {cik: $cik})-[:INSIDER_TRADE_OF]->(t:InsiderTransaction)<-[:TRADED_BY]-(p:Person)
            RETURN t.transaction_date as transaction_date,
                   t.transaction_code as transaction_code,
                   t.total_value as total_value,
                   t.shares as shares,
                   t.price_per_share as price_per_share,
                   p.name as insider_name,
                   t.insider_title as insider_title,
                   t.transaction_type as transaction_type,
                   t.security_title as security_title
            ORDER BY t.transaction_date DESC
            LIMIT 100
        """
        trades = await Neo4jClient.execute_query(trades_query, {"cik": cik})

        # Classify all trades
        trade_types = classify_trades_batch(
            trades,
            name_key="insider_name",
            date_key="transaction_date",
            code_key="transaction_code",
        )

        # Aggregate buyers in the cluster window (skip $0 exercises)
        buyer_agg: dict[str, BuyerDetail] = {}
        total_buy_value = 0.0
        for t, tt in zip(trades, trade_types):
            if not is_bullish_trade(tt):
                continue
            if (t.get("total_value") or 0) <= 0:
                continue
            if not t["transaction_date"] or t["transaction_date"] < window_start or t["transaction_date"] > window_end:
                continue

            name = t["insider_name"] or "Unknown"
            val = abs(t["total_value"] or 0)
            total_buy_value += val
            if name not in buyer_agg:
                buyer_agg[name] = BuyerDetail(
                    name=name,
                    title=t.get("insider_title") or "",
                    total_value=0,
                    trade_count=0,
                )
            buyer_agg[name].total_value += val
            buyer_agg[name].trade_count += 1

        num_buyers = len(buyer_agg)
        buyers = sorted(buyer_agg.values(), key=lambda b: b.total_value, reverse=True)

        # Classify signal
        if num_buyers >= 3:
            signal_level = "high"
            signal_summary = f"Insider Cluster: {num_buyers} insiders buying"
        elif num_buyers >= 2 or total_buy_value >= 500_000:
            signal_level = "medium"
            if num_buyers >= 2:
                signal_summary = f"Insider Cluster: {num_buyers} insiders buying"
            else:
                signal_summary = f"Insider Buying: ${total_buy_value:,.0f} total"
        else:
            signal_level = "low"
            signal_summary = f"Insider Purchase: {buyers[0].name}" if buyers else "Insider Purchase"

        # Build timeline entries
        timeline = []
        for t, tt in zip(trades, trade_types):
            code = t["transaction_code"] or ""
            shares_str = f"{t['shares']:,.0f}" if t.get("shares") else "?"
            value_str = f"${t['total_value']:,.0f}" if t.get("total_value") else ""

            description = f"{t['insider_name']} - {t['transaction_type'] or code}"
            detail = f"{shares_str} shares"
            if value_str:
                detail += f" ({value_str})"
            if t.get("insider_title"):
                detail += f" - {t['insider_title']}"

            # Notable if bullish and in cluster window
            notable = False
            notable_reasons = []
            if is_bullish_trade(tt) and t.get("transaction_date", "") >= window_start and t.get("transaction_date", "") <= window_end:
                notable = True
                notable_reasons.append("Cluster buy pattern")
            elif is_bullish_trade(tt) and abs(t.get("total_value", 0)) >= 100_000:
                notable = True
                notable_reasons.append("Large purchase")
            elif is_bearish_trade(tt) and abs(t.get("total_value", 0)) >= 500_000:
                notable = True
                notable_reasons.append("Large sale")

            timeline.append({
                "date": t["transaction_date"],
                "type": "trade",
                "trade_type": tt,
                "description": description,
                "detail": detail,
                "is_current": False,
                "notable": notable,
                "notable_reasons": notable_reasons,
            })

        timeline.sort(key=lambda x: x.get("date", ""), reverse=True)

        # Build insider context
        total_sell_value = sum(
            abs(t["total_value"] or 0)
            for t, tt in zip(trades, trade_types)
            if is_bearish_trade(tt)
        )

        insider_context = {
            "net_direction": "buying",
            "total_buy_value": total_buy_value,
            "total_sell_value": total_sell_value,
            "notable_trades": [f"{b.name} bought ${b.total_value:,.0f}" for b in buyers[:5]],
            "cluster_activity": num_buyers >= 3,
            "trade_count": len(trades),
            "person_matches": [],
            "near_filing_count": sum(b.trade_count for b in buyers),
            "near_filing_direction": "buying",
        }

        # Build decision card
        if signal_level == "high":
            action = "BUY"
            conviction = "HIGH"
        elif signal_level == "medium":
            action = "WATCH"
            conviction = "MEDIUM"
        else:
            action = "PASS"
            conviction = "LOW"

        one_liner = f"{num_buyers} insiders buying ${total_buy_value:,.0f} in {(window_end_dt - window_start_dt).days}d window"

        decision_card = {
            "action": action,
            "conviction": conviction,
            "one_liner": one_liner,
            "insider_direction": "buying",
            "days_since_filing": (datetime.now() - window_end_dt).days,
        }

        # Price change since window end
        if ticker:
            try:
                price_data = StockPriceService.get_price_at_date(ticker, window_end)
                if price_data and price_data["price_at_date"] > 0:
                    decision_card["price_at_filing"] = price_data["price_at_date"]
                    decision_card["price_current"] = price_data["price_current"]
                    decision_card["price_change_pct"] = round(
                        (price_data["price_current"] - price_data["price_at_date"]) / price_data["price_at_date"] * 100, 1
                    )
            except Exception as e:
                logger.warning(f"Failed to get price data for cluster detail: {e}")

        return {
            "event": {
                "accession_number": cluster_id,
                "filing_date": window_end,
                "signal_level": signal_level,
                "signal_summary": signal_summary,
                "items": [],
                "item_numbers": [],
                "persons_mentioned": [],
            },
            "analysis": {
                "agreement_type": "Insider Cluster",
                "summary": f"{num_buyers} distinct insiders purchased shares totaling ${total_buy_value:,.0f} within a {(window_end_dt - window_start_dt).days}-day window ({window_start} to {window_end}).",
                "parties_involved": [
                    {"name": b.name, "source_quote": f"{b.title} - {b.trade_count} trades, ${b.total_value:,.0f}"}
                    for b in buyers
                ],
                "key_terms": [],
                "forward_looking": f"Multiple insiders buying simultaneously often precedes material announcements. Monitor for 8-K filings from {company_name}.",
                "forward_looking_source": "Pattern analysis",
                "market_implications": f"Insider cluster buying suggests insiders see value at current prices. {num_buyers} independent buy decisions increase confidence.",
                "market_implications_source": "Insider trading analysis",
                "cached": True,
            },
            "timeline": timeline,
            "deals": [],
            "company": {
                "cik": cik,
                "name": company_name,
                "ticker": ticker,
            },
            "combined_signal_level": signal_level,
            "insider_context": insider_context,
            "decision_card": decision_card,
            "company_context": {
                "sic_description": company.get("sic_description"),
                "state_of_incorporation": company.get("state_of_incorporation"),
                "officers": [],
                "directors": [],
                "board_connections": [],
                "subsidiaries_count": 0,
            },
            "signal_type": "insider_cluster",
            "cluster_detail": {
                "window_start": window_start,
                "window_end": window_end,
                "num_buyers": num_buyers,
                "buyers": [b.to_dict() for b in buyers],
            },
        }
