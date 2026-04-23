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
from app.services.feed_service import pick_ticker, resolve_ticker, FeedService, InsiderContext
from app.services.trade_classifier import (
    classify_trades_batch,
    is_bullish_trade,
    is_bearish_trade,
)
from app.services.stock_price_service import StockPriceService

logger = logging.getLogger(__name__)


def classify_insider_role(title: str) -> str:
    """Classify insider title into role category for signal weighting.

    Officers (CEO/CFO/etc.) have the most information asymmetry,
    followed by directors, then 10%+ institutional holders.

    Returns: 'officer', 'director', 'owner_10pct', or 'other'
    """
    if not title:
        return "other"
    t = title.lower()
    # Check 10%/beneficial owner first — most specific
    if "10%" in t or "10 percent" in t or "beneficial owner" in t:
        return "owner_10pct"
    # Check for director before officer acronyms (since "cto" is a
    # substring of "director", we need to handle this first)
    if "director" in t:
        # But "Director and CEO" should still be officer — check for
        # officer keywords in the same title
        officer_long = [
            "chief", "president", "treasurer", "controller",
            "general counsel", "secretary",
        ]
        if any(kw in t for kw in officer_long):
            return "officer"
        # Check C-suite acronyms as whole words
        words = set(t.replace(",", " ").replace(";", " ").split())
        csuite = {"ceo", "cfo", "coo", "cto", "cio", "cmo", "cso", "evp", "svp", "vp"}
        if words & csuite:
            return "officer"
        return "director"
    # Officer keywords — longer strings safe for substring matching
    officer_long = [
        "chief", "president", "treasurer", "controller",
        "general counsel", "secretary",
    ]
    if any(kw in t for kw in officer_long):
        return "officer"
    # C-suite acronyms — must be whole words to avoid "cto" in "director"
    words = set(t.replace(",", " ").replace(";", " ").split())
    csuite = {"ceo", "cfo", "coo", "cto", "cio", "cmo", "cso", "evp", "svp", "vp"}
    if words & csuite:
        return "officer"
    if "vice president" in t:
        return "officer"
    return "other"


@dataclass
class BuyerDetail:
    """Detail about a single insider buyer in a cluster."""

    name: str
    title: str
    total_value: float
    trade_count: int
    total_shares: float = 0.0
    trade_dates: list = field(default_factory=list)
    insider_cik: str = ""
    filing_accession: str = ""
    primary_document: str = ""
    form4_url: str = ""
    role: str = "other"  # officer, director, owner_10pct, other

    @property
    def avg_price_per_share(self) -> Optional[float]:
        if self.total_shares > 0:
            return round(self.total_value / self.total_shares, 2)
        return None

    def to_dict(self) -> dict:
        d = {
            "name": self.name,
            "title": self.title,
            "total_value": self.total_value,
            "trade_count": self.trade_count,
            "total_shares": self.total_shares,
            "avg_price_per_share": self.avg_price_per_share,
            "trade_dates": sorted(set(self.trade_dates)),
            "form4_url": self.form4_url,
            "role": self.role,
        }
        return d


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
    direction: str = "buy"  # "buy" or "sell"
    conviction_tier: str = "watch"  # strong_buy, buy, watch

    @property
    def accession_number(self) -> str:
        if self.direction == "sell":
            return f"SELL-CLUSTER-{self.cik}-{self.window_end}"
        return f"CLUSTER-{self.cik}-{self.window_end}"

    def to_signal_dict(self) -> dict:
        """Shape output to match SignalItem.to_dict() for unified feed."""
        is_sell = self.direction == "sell"
        verb = "sold" if is_sell else "bought"
        net_dir = "selling" if is_sell else "buying"
        sig_type = "insider_sell_cluster" if is_sell else "insider_cluster"

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
                "net_direction": net_dir,
                "total_buy_value": 0 if is_sell else self.total_buy_value,
                "total_sell_value": self.total_buy_value if is_sell else 0,
                "notable_trades": [
                    f"{b.name} {verb} ${b.total_value:,.0f}"
                    for b in self.buyers[:5]
                ],
                "cluster_activity": True,
                "trade_count": sum(b.trade_count for b in self.buyers),
                "person_matches": [],
                "near_filing_count": sum(b.trade_count for b in self.buyers),
                "near_filing_direction": net_dir,
            },
            "signal_type": sig_type,
            "conviction_tier": self.conviction_tier,
            "cluster_detail": {
                "window_start": self.window_start,
                "window_end": self.window_end,
                "num_buyers": self.num_buyers,
                "buyers": [b.to_dict() for b in self.buyers],
                "direction": self.direction,
                "conviction_tier": self.conviction_tier,
            },
        }


class InsiderClusterService:
    """Detects insider buying clusters as standalone signals."""

    @staticmethod
    async def detect_clusters(
        days: int = 90,
        window_days: int = 30,
        min_level: str = "medium",
        direction: str = "buy",
    ) -> list[InsiderClusterSignal]:
        """
        Detect insider buying or selling clusters from Form 4 data.

        1. Query open-market trades (P for buy, S for sell) in the last `days` days
        2. Group by company CIK
        3. Use a 30-day sliding window from the latest trade backward
        4. Count distinct traders -> classify based on direction thresholds

        Buy thresholds:  3+ = HIGH, 2+ or >$500K = MEDIUM, 1 = LOW
        Sell thresholds: 4+ & $100K+ = HIGH, 3 & $100K+ = MEDIUM, else skip

        Args:
            days: Look back this many days for trades
            window_days: Sliding window size for cluster detection
            min_level: Minimum signal level to include
            direction: "buy" for purchase clusters, "sell" for selling clusters

        Returns:
            List of InsiderClusterSignal sorted by level then date
        """
        since_date = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
        tx_code = "S" if direction == "sell" else "P"

        # Filter to companies with tickers to exclude funds/persons/entities
        # that got Company nodes from EFTS multi-CIK Form 4 results
        query = """
            MATCH (c:Company)-[:INSIDER_TRADE_OF]->(t:InsiderTransaction)<-[:TRADED_BY]-(p:Person)
            WHERE t.transaction_date >= $since_date
              AND t.transaction_code = $tx_code
              AND t.classification = 'GENUINE'
              AND (t.is_derivative IS NULL OR t.is_derivative = false)
              AND c.tickers IS NOT NULL AND size(c.tickers) > 0
            RETURN c.cik as cik,
                   c.name as company_name,
                   c.tickers as tickers,
                   t.transaction_date as transaction_date,
                   t.transaction_code as transaction_code,
                   t.total_value as total_value,
                   t.shares as shares,
                   p.name as insider_name,
                   t.insider_title as insider_title,
                   t.insider_cik as insider_cik,
                   t.accession_number as accession_number,
                   t.is_10b5_1 as is_10b5_1,
                   t.primary_document as primary_document
            ORDER BY t.transaction_date DESC
        """
        results = await Neo4jClient.execute_query(query, {"since_date": since_date, "tx_code": tx_code})

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

            # Filter to only target transaction code with actual dollar value
            # For sell clusters, exclude pre-planned 10b5-1 sales
            if direction == "sell":
                target_trades = [
                    (t, tt) for t, tt in zip(trades, trade_types)
                    if t.get("transaction_code") == tx_code
                    and (t.get("total_value") or 0) > 0
                    and not t.get("is_10b5_1", False)
                ]
            else:
                target_trades = [
                    (t, tt) for t, tt in zip(trades, trade_types)
                    if t.get("transaction_code") == tx_code
                    and (t.get("total_value") or 0) > 0
                    and not t.get("is_10b5_1", False)
                ]

            if not target_trades:
                continue

            # Find the latest trade date as the window end
            latest_date = max(
                t["transaction_date"] for t, _ in target_trades
                if t["transaction_date"]
            )

            try:
                window_end_dt = datetime.strptime(latest_date, "%Y-%m-%d")
            except (ValueError, TypeError):
                continue

            window_start_dt = window_end_dt - timedelta(days=window_days)
            window_start = window_start_dt.strftime("%Y-%m-%d")

            # Collect trades within the window
            window_trades = [
                (t, tt) for t, tt in target_trades
                if t["transaction_date"] and t["transaction_date"] >= window_start
            ]

            if not window_trades:
                continue

            # Dedup: same date + same shares + same price = same transaction
            # reported by multiple legal entities in a fund structure.
            # Keep only the first filing per (date, shares, price) group.
            seen_trades: set[tuple] = set()
            deduped_trades = []
            for t, tt in window_trades:
                key = (
                    t.get("transaction_date", ""),
                    str(int(t.get("shares") or 0)),
                    str(round(t.get("price_per_share") or 0, 2)),
                )
                if key in seen_trades:
                    continue
                seen_trades.add(key)
                deduped_trades.append((t, tt))
            window_trades = deduped_trades

            # Aggregate by trader
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
                        insider_cik=t.get("insider_cik") or "",
                        filing_accession=t.get("accession_number") or "",
                        primary_document=t.get("primary_document") or "",
                        role=classify_insider_role(t.get("insider_title") or ""),
                    )
                buyer_agg[name].total_value += val
                buyer_agg[name].trade_count += 1
                buyer_agg[name].total_shares += abs(t.get("shares") or 0)
                if t.get("transaction_date"):
                    buyer_agg[name].trade_dates.append(t["transaction_date"])

            num_buyers = len(buyer_agg)
            total_buy_value = sum(b.total_value for b in buyer_agg.values())
            buyers = sorted(buyer_agg.values(), key=lambda b: b.total_value, reverse=True)

            # Compute Form 4 SEC EDGAR URLs (direct link to rendered filing)
            for buyer in buyers:
                if buyer.filing_accession:
                    acc_no_dashes = buyer.filing_accession.replace("-", "")
                    if buyer.primary_document:
                        buyer.form4_url = f"https://www.sec.gov/Archives/edgar/data/{cik}/{acc_no_dashes}/{buyer.primary_document}"
                    else:
                        buyer.form4_url = f"https://www.sec.gov/Archives/edgar/data/{cik}/{acc_no_dashes}/{buyer.filing_accession}-index.htm"

            # Compute actual trade date range from the trades themselves
            all_trade_dates = [d for b in buyers for d in b.trade_dates if d]
            first_trade = min(all_trade_dates) if all_trade_dates else window_start
            last_trade = max(all_trade_dates) if all_trade_dates else latest_date

            # Format as "Mar 10 - Mar 19" for the summary
            def _fmt_date(d: str) -> str:
                try:
                    from datetime import datetime as dt
                    return dt.strptime(d[:10], "%Y-%m-%d").strftime("%b %d").replace(" 0", " ")
                except (ValueError, TypeError):
                    return d[:10]

            date_range = _fmt_date(first_trade) if first_trade == last_trade else f"{_fmt_date(first_trade)} - {_fmt_date(last_trade)}"

            # Classify signal level (different thresholds for buy vs sell)
            if direction == "sell":
                # Sell: higher thresholds since selling is noisier
                # Minimum $100K total to filter out trivial sells
                if total_buy_value < 100_000:
                    continue
                if num_buyers >= 4:
                    level = "high"
                    summary = f"{num_buyers} insiders selling between {date_range}"
                elif num_buyers >= 3:
                    level = "medium"
                    summary = f"{num_buyers} insiders selling between {date_range}"
                else:
                    continue  # <3 sellers = skip entirely
            else:
                # Buy: cluster thresholds — require multiple buyers
                # Count officer buyers for role-based weighting
                officer_count = sum(1 for b in buyers if b.role == "officer")

                if num_buyers >= 3:
                    level = "high"
                    summary = f"{num_buyers} insiders buying between {date_range}"
                elif num_buyers >= 2 and officer_count >= 2 and total_buy_value >= 200_000:
                    # Two officers buying is highly informational — promote to HIGH
                    level = "high"
                    summary = f"{num_buyers} officers buying between {date_range}"
                elif num_buyers >= 2:
                    level = "medium"
                    summary = f"{num_buyers} insiders buying between {date_range}"
                else:
                    level = "low"
                    summary = f"Insider Purchase: {buyers[0].name}" if buyers else "Insider Purchase"

            # Evidence-based conviction tiers
            # Based on tested findings: $300M-$5B midcap + $100K+ value = 75% hit rate
            # Upper cap aligned with signal_performance_service.compute_conviction_tier
            # (tightened from $10B → $5B on 2026-04-17: $5B-$10B bucket had 38.1% HR
            # vs 67.4% for <$5B, p=0.018, CIs don't overlap).
            info = company_info[cik]
            ticker = pick_ticker(info.get("tickers"))
            conviction_tier = "watch"  # default

            if direction == "buy" and level in ("high", "medium") and ticker:
                try:
                    mcap = StockPriceService.get_market_cap(ticker)
                    if mcap and mcap > 0:
                        in_sweet_spot = 300_000_000 <= mcap <= 5_000_000_000
                        high_value = total_buy_value >= 100_000

                        if in_sweet_spot and high_value:
                            conviction_tier = "strong_buy"  # 75% hit rate
                        elif in_sweet_spot or high_value:
                            conviction_tier = "buy"  # 68-70% hit rate
                        else:
                            conviction_tier = "watch"  # <60% hit rate
                    else:
                        # No market cap data — fall back to value only
                        if total_buy_value >= 100_000:
                            conviction_tier = "buy"
                        else:
                            conviction_tier = "watch"
                except Exception as e:
                    logger.warning(
                        f"StockPriceService.get_market_cap failed for {ticker}: "
                        f"{type(e).__name__}: {str(e)[:120]}"
                    )
                    if total_buy_value >= 100_000:
                        conviction_tier = "buy"
                    else:
                        conviction_tier = "watch"
            elif direction == "sell":
                conviction_tier = "watch"  # sell signals don't use conviction tiers

            # Filter by min level
            if level_order.get(level, 2) > min_level_order:
                continue

            clusters.append(InsiderClusterSignal(
                cik=cik,
                company_name=info["name"],
                ticker=ticker,
                window_start=window_start,
                window_end=latest_date,
                signal_level=level,
                signal_summary=summary,
                num_buyers=num_buyers,
                total_buy_value=total_buy_value,
                buyers=buyers,
                direction=direction,
                conviction_tier=conviction_tier,
            ))

        # Sort by level then date
        clusters.sort(key=lambda c: c.window_end, reverse=True)
        clusters.sort(key=lambda c: level_order.get(c.signal_level, 2))

        return clusters

    @staticmethod
    async def detect_clusters_for_company(
        cik: str,
        days: int = 90,
        window_days: int = 30,
    ) -> list[InsiderClusterSignal]:
        """Detect buy and sell clusters for a single company.

        Returns both buy and sell clusters combined, sorted by date.
        """
        buy_clusters = await InsiderClusterService.detect_clusters(
            days=days, window_days=window_days, min_level="low", direction="buy"
        )
        sell_clusters = await InsiderClusterService.detect_clusters(
            days=days, window_days=window_days, min_level="low", direction="sell"
        )
        # Filter to just this CIK
        company_clusters = [c for c in buy_clusters + sell_clusters if c.cik == cik]
        company_clusters.sort(key=lambda c: c.window_end, reverse=True)
        return company_clusters

    @staticmethod
    async def detect_clusters_excluding_8k(
        days: int = 90,
        window_days: int = 30,
        min_level: str = "medium",
        direction: str = "buy",
    ) -> list[InsiderClusterSignal]:
        """
        Detect clusters, excluding companies that already have 8-K signals
        in the same time window (to avoid double-counting).
        """
        clusters = await InsiderClusterService.detect_clusters(days, window_days, min_level, direction=direction)

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
    async def detect_sell_clusters(
        days: int = 90,
        window_days: int = 30,
        min_level: str = "medium",
    ) -> list[InsiderClusterSignal]:
        """Detect insider selling clusters (S-code open market sales)."""
        return await InsiderClusterService.detect_clusters(days, window_days, min_level, direction="sell")

    @staticmethod
    async def detect_sell_clusters_excluding_8k(
        days: int = 90,
        window_days: int = 30,
        min_level: str = "medium",
    ) -> list[InsiderClusterSignal]:
        """Detect sell clusters, excluding companies with recent 8-K signals."""
        return await InsiderClusterService.detect_clusters_excluding_8k(days, window_days, min_level, direction="sell")

    @staticmethod
    def apply_market_cap_filter(
        clusters: list[InsiderClusterSignal],
        min_pct: float = 0.01,
    ) -> list[InsiderClusterSignal]:
        """Remove clusters where purchase value is insignificant relative to market cap.

        A $1M purchase at a $100B company (0.001%) is noise.
        A $100K purchase at a $100M company (0.1%) is meaningful.

        Args:
            clusters: list of detected clusters
            min_pct: minimum purchase-as-%-of-market-cap to keep (default 0.01%)

        Returns:
            Filtered list of clusters
        """
        if not clusters:
            return clusters

        filtered = []
        for c in clusters:
            if not c.ticker:
                filtered.append(c)
                continue
            try:
                market_cap = StockPriceService.get_market_cap(c.ticker)
                if market_cap and market_cap > 0:
                    pct_of_cap = (c.total_buy_value / market_cap) * 100
                    if pct_of_cap < min_pct:
                        logger.debug(
                            f"Market cap filter: {c.ticker} purchase ${c.total_buy_value:,.0f} "
                            f"is {pct_of_cap:.4f}% of ${market_cap:,.0f} mkt cap — skipping"
                        )
                        continue
                filtered.append(c)
            except Exception:
                filtered.append(c)  # Keep on error
        return filtered

    @staticmethod
    async def get_cluster_detail(cluster_id: str, confidence_stats: Optional[dict] = None) -> Optional[dict]:
        """
        Get detailed information for a cluster signal.

        Parses CLUSTER-{cik}-{YYYY-MM-DD} or SELL-CLUSTER-{cik}-{YYYY-MM-DD}
        format, fetches all trades for that company, and returns a response
        shaped like EventDetailResponse.

        Args:
            cluster_id: e.g. "CLUSTER-0001234567-2026-02-15" or "SELL-CLUSTER-..."

        Returns:
            Dict matching EventDetailResponse shape, or None
        """
        # Parse cluster ID — detect direction from prefix
        if cluster_id.startswith("SELL-CLUSTER-"):
            direction = "sell"
            remainder = cluster_id[len("SELL-CLUSTER-"):]
        elif cluster_id.startswith("CLUSTER-"):
            direction = "buy"
            remainder = cluster_id[len("CLUSTER-"):]
        else:
            return None

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
        ticker = await resolve_ticker(cik, company.get("tickers"))

        is_sell = direction == "sell"
        tx_code = "S" if is_sell else "P"

        # Find when this cluster was first detected (earliest alert)
        alert_type = "insider_sell_cluster" if is_sell else "insider_cluster"
        first_detected_query = """
            MATCH (a:Alert)
            WHERE a.company_cik = $cik
              AND a.alert_type = $alert_type
            RETURN a.created_at AS created_at
            ORDER BY a.created_at ASC
            LIMIT 1
        """
        first_detected_result = await Neo4jClient.execute_query(
            first_detected_query, {"cik": cik, "alert_type": alert_type}
        )
        first_detected = None
        if first_detected_result:
            raw = first_detected_result[0].get("created_at", "")
            if raw:
                first_detected = raw[:10]  # YYYY-MM-DD

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
                   t.security_title as security_title,
                   t.accession_number as accession_number,
                   t.insider_cik as insider_cik,
                   t.is_10b5_1 as is_10b5_1,
                   t.primary_document as primary_document
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

        # Aggregate traders in the cluster window (open-market trades only)
        buyer_agg: dict[str, BuyerDetail] = {}
        total_trade_value = 0.0
        earliest_trade_date: Optional[str] = None
        latest_trade_date: Optional[str] = None
        for t, tt in zip(trades, trade_types):
            if t.get("transaction_code") != tx_code:
                continue
            if (t.get("total_value") or 0) <= 0:
                continue
            if t.get("is_derivative", False):
                continue
            if not t["transaction_date"] or t["transaction_date"] < window_start or t["transaction_date"] > window_end:
                continue
            # Exclude pre-planned 10b5-1 sales from sell cluster aggregation
            if is_sell and t.get("is_10b5_1", False):
                continue

            name = t["insider_name"] or "Unknown"
            val = abs(t["total_value"] or 0)
            total_trade_value += val
            if name not in buyer_agg:
                buyer_agg[name] = BuyerDetail(
                    name=name,
                    title=t.get("insider_title") or "",
                    total_value=0,
                    trade_count=0,
                    insider_cik=t.get("insider_cik") or "",
                    filing_accession=t.get("accession_number") or "",
                    primary_document=t.get("primary_document") or "",
                    role=classify_insider_role(t.get("insider_title") or ""),
                )
            buyer_agg[name].total_value += val
            buyer_agg[name].trade_count += 1
            buyer_agg[name].total_shares += abs(t.get("shares") or 0)
            if t.get("transaction_date"):
                buyer_agg[name].trade_dates.append(t["transaction_date"])

            # Track earliest actual trade date for price measurement
            if earliest_trade_date is None or t["transaction_date"] < earliest_trade_date:
                earliest_trade_date = t["transaction_date"]
            if latest_trade_date is None or t["transaction_date"] > latest_trade_date:
                latest_trade_date = t["transaction_date"]

        num_traders = len(buyer_agg)
        buyers = sorted(buyer_agg.values(), key=lambda b: b.total_value, reverse=True)

        # Compute Form 4 SEC EDGAR URLs (direct link to rendered filing)
        for buyer in buyers:
            if buyer.filing_accession:
                acc_no_dashes = buyer.filing_accession.replace("-", "")
                if buyer.primary_document:
                    buyer.form4_url = f"https://www.sec.gov/Archives/edgar/data/{cik}/{acc_no_dashes}/{buyer.primary_document}"
                else:
                    buyer.form4_url = f"https://www.sec.gov/Archives/edgar/data/{cik}/{acc_no_dashes}/{buyer.filing_accession}-index.htm"

        # Classify signal (direction-aware)
        if is_sell:
            if num_traders >= 4:
                signal_level = "high"
                signal_summary = f"Insider Sell Cluster: {num_traders} insiders selling"
            elif num_traders >= 3:
                signal_level = "medium"
                signal_summary = f"Insider Sell Cluster: {num_traders} insiders selling"
            else:
                signal_level = "low"
                signal_summary = f"Insider Selling: {buyers[0].name}" if buyers else "Insider Selling"
        else:
            officer_count = sum(1 for b in buyers if b.role == "officer")
            if num_traders >= 3:
                signal_level = "high"
                signal_summary = f"Open Market Cluster: {num_traders} insiders buying"
            elif num_traders >= 2 and officer_count >= 2 and total_trade_value >= 200_000:
                signal_level = "high"
                signal_summary = f"Officer Cluster: {num_traders} insiders buying (inc. {officer_count} officers)"
            elif num_traders >= 2:
                signal_level = "medium"
                signal_summary = f"Open Market Cluster: {num_traders} insiders buying"
            else:
                signal_level = "low"
                signal_summary = f"Insider Purchase: {buyers[0].name}" if buyers else "Insider Purchase"

        # Conviction tiers (buy direction only)
        if direction == "buy" and signal_level in ("high", "medium"):
            if num_traders >= 3 and officer_count >= 2:
                conviction_tier = "strong_buy"
            elif num_traders >= 3 or (num_traders >= 2 and officer_count >= 1):
                conviction_tier = "buy"
            else:
                conviction_tier = "watch"
        else:
            officer_count = 0
            conviction_tier = "watch"

        # Build timeline entries — only open market buys (P) and sells (S)
        timeline = []
        for t, tt in zip(trades, trade_types):
            if t.get("transaction_code") not in ("P", "S"):
                continue
            # Exclude 10b5-1 planned sales from sell cluster timelines
            if is_sell and t.get("is_10b5_1", False):
                continue
            code = t["transaction_code"] or ""
            shares_str = f"{t['shares']:,.0f}" if t.get("shares") else "?"
            value_str = f"${t['total_value']:,.0f}" if t.get("total_value") else ""

            price_str = f"@ ${t['price_per_share']:,.2f}" if t.get("price_per_share") else ""

            description = f"{t['insider_name']} - {t['transaction_type'] or code}"
            detail = f"{shares_str} shares"
            if price_str:
                detail += f" {price_str}"
            if value_str:
                detail += f" ({value_str})"
            if t.get("insider_title"):
                detail += f" - {t['insider_title']}"

            # Notable: direction-aware cluster pattern detection
            notable = False
            notable_reasons = []
            in_window = t.get("transaction_date", "") >= window_start and t.get("transaction_date", "") <= window_end
            if is_sell:
                if is_bearish_trade(tt) and in_window:
                    notable = True
                    notable_reasons.append("Cluster sell pattern")
                elif is_bearish_trade(tt) and abs(t.get("total_value", 0)) >= 500_000:
                    notable = True
                    notable_reasons.append("Large sale")
                elif is_bullish_trade(tt) and abs(t.get("total_value", 0)) >= 100_000:
                    notable = True
                    notable_reasons.append("Large purchase")
            else:
                if is_bullish_trade(tt) and in_window:
                    notable = True
                    notable_reasons.append("Cluster buy pattern")
                elif is_bullish_trade(tt) and abs(t.get("total_value", 0)) >= 100_000:
                    notable = True
                    notable_reasons.append("Large purchase")
                elif is_bearish_trade(tt) and abs(t.get("total_value", 0)) >= 500_000:
                    notable = True
                    notable_reasons.append("Large sale")

            # Build direct Form 4 URL for citation
            acc = t.get("accession_number") or ""
            primary_doc = t.get("primary_document") or ""
            if acc:
                acc_nd = acc.replace("-", "")
                if primary_doc:
                    form4_url = f"https://www.sec.gov/Archives/edgar/data/{cik}/{acc_nd}/{primary_doc}"
                else:
                    form4_url = f"https://www.sec.gov/Archives/edgar/data/{cik}/{acc_nd}/{acc}-index.htm"
            else:
                form4_url = ""

            timeline.append({
                "date": t["transaction_date"],
                "type": "trade",
                "trade_type": tt,
                "description": description,
                "detail": detail,
                "is_current": False,
                "notable": notable,
                "notable_reasons": notable_reasons,
                "form4_url": form4_url,
            })

        timeline.sort(key=lambda x: x.get("date", ""), reverse=True)

        # Build insider context (direction-aware)
        total_buy_value_all = sum(
            abs(t["total_value"] or 0)
            for t, tt in zip(trades, trade_types)
            if is_bullish_trade(tt)
        )
        total_sell_value_all = sum(
            abs(t["total_value"] or 0)
            for t, tt in zip(trades, trade_types)
            if is_bearish_trade(tt)
        )

        verb = "sold" if is_sell else "bought"
        net_dir = "selling" if is_sell else "buying"

        insider_context = {
            "net_direction": net_dir,
            "total_buy_value": total_buy_value_all,
            "total_sell_value": total_sell_value_all,
            "notable_trades": [f"{b.name} {verb} ${b.total_value:,.0f}" for b in buyers[:5]],
            "cluster_activity": num_traders >= 3,
            "trade_count": len(trades),
            "person_matches": [],
            "near_filing_count": sum(b.trade_count for b in buyers),
            "near_filing_direction": net_dir,
        }

        # Build decision card (direction-aware)
        if is_sell:
            if signal_level == "high":
                action = "PASS"
                conviction = "HIGH"
            elif signal_level == "medium":
                action = "WATCH"
                conviction = "MEDIUM"
            else:
                action = "WATCH"
                conviction = "LOW"
        else:
            if signal_level == "high":
                action = "BUY"
                conviction = "HIGH"
            elif signal_level == "medium":
                action = "WATCH"
                conviction = "MEDIUM"
            else:
                action = "PASS"
                conviction = "LOW"

        action_verb = "selling" if is_sell else "buying"

        # Format actual trade date range for display
        _first = earliest_trade_date or window_start
        _last = latest_trade_date or window_end
        def _fmt_dt(d: str) -> str:
            try:
                return datetime.strptime(d[:10], "%Y-%m-%d").strftime("%b %d").replace(" 0", " ")
            except (ValueError, TypeError):
                return d[:10]
        first_trade_fmt = _fmt_dt(_first)
        last_trade_fmt = _fmt_dt(_last)

        one_liner = f"{num_traders} insiders {action_verb} on open market — ${total_trade_value:,.0f} between {first_trade_fmt} and {last_trade_fmt}"

        # Use earliest actual trade date for price & timing (not arbitrary window_start)
        first_trade_date = earliest_trade_date or window_start
        first_trade_dt = datetime.strptime(first_trade_date, "%Y-%m-%d")

        # Use first_detected (alert date) for "days ago" if available,
        # otherwise fall back to first trade date
        if first_detected:
            try:
                detected_dt = datetime.strptime(first_detected, "%Y-%m-%d")
                days_since = (datetime.now() - detected_dt).days
            except ValueError:
                days_since = (datetime.now() - first_trade_dt).days
        else:
            days_since = (datetime.now() - first_trade_dt).days

        decision_card = {
            "action": action,
            "conviction": conviction,
            "one_liner": one_liner,
            "insider_direction": net_dir,
            "insider_buy_type": "open_market",
            "days_since_filing": days_since,
        }

        # Price change since detection date (when our system flagged it)
        # This shows the return a user could actually capture after our alert
        price_date = first_detected or first_trade_date
        if ticker:
            try:
                price_data = StockPriceService.get_price_at_date(ticker, price_date)
                if price_data and price_data["price_at_date"] > 0:
                    decision_card["price_at_filing"] = price_data["price_at_date"]
                    decision_card["price_current"] = price_data["price_current"]
                    pct = round(
                        (price_data["price_current"] - price_data["price_at_date"]) / price_data["price_at_date"] * 100, 1
                    )
                    decision_card["price_change_pct"] = pct

                    # Add context label for price measurement
                    if is_sell:
                        decision_card["price_label"] = "since detected"
                        if pct > 5:
                            decision_card["price_context"] = f"Insiders selling into +{pct}% rally"
                        elif pct < -5:
                            decision_card["price_context"] = f"Stock already down {abs(pct)}% — insiders heading for the exits"
                    else:
                        decision_card["price_label"] = "since detected"
                        if pct < -10:
                            decision_card["price_context"] = f"Insiders buying into a {abs(pct)}% dip — contrarian signal"
            except Exception as e:
                logger.warning(f"Failed to get price data for cluster detail: {e}")

        # Check hostile activist flag from transactions
        hostile_query = """
            MATCH (c:Company {cik: $cik})-[:INSIDER_TRADE_OF]->(t:InsiderTransaction)
            WHERE t.has_hostile_activist = true AND t.classification = 'GENUINE'
            RETURN count(t) as cnt
        """
        hostile_result = await Neo4jClient.execute_query(hostile_query, {"cik": cik})
        has_hostile = (hostile_result[0]["cnt"] or 0) > 0 if hostile_result else False

        # Get hostile keywords if flagged
        hostile_keywords = []
        if has_hostile:
            kw_query = """
                MATCH (af:ActivistFiling)-[:TARGETS]->(c:Company {cik: $cik})
                WHERE af.purpose_text IS NOT NULL
                RETURN af.purpose_text as text
                LIMIT 5
            """
            kw_result = await Neo4jClient.execute_query(kw_query, {"cik": cik})
            keyword_list = ["proxy", "remove", "replace", "strategic alternative", "inadequate",
                            "underperform", "oppose", "withhold", "hostile", "unsolicited"]
            for row in kw_result:
                text_lower = (row["text"] or "").lower()
                for kw in keyword_list:
                    if kw in text_lower and kw not in hostile_keywords:
                        hostile_keywords.append(kw)

        signal_type = "insider_sell_cluster" if is_sell else "insider_cluster"
        agreement_type = "Insider Sell Cluster" if is_sell else "Insider Cluster"
        trade_verb = "sales" if is_sell else "purchases"

        return {
            "event": {
                "accession_number": cluster_id,
                "filing_date": window_end,
                "first_detected": first_detected,
                "signal_level": signal_level,
                "signal_summary": signal_summary,
                "items": [],
                "item_numbers": [],
                "persons_mentioned": [],
            },
            "analysis": {
                "agreement_type": agreement_type,
                "summary": f"{num_traders} insiders made open market {trade_verb} totaling ${total_trade_value:,.0f} between {first_trade_fmt} and {last_trade_fmt}.",
                "parties_involved": [
                    {"name": b.name, "source_quote": f"{b.title} - {b.trade_count} trades, ${b.total_value:,.0f}"}
                    for b in buyers
                ],
                "key_terms": [],
                "forward_looking": f"Multiple insiders {'selling' if is_sell else 'buying'} simultaneously {'may indicate upcoming negative catalysts or insider concern about valuation' if is_sell else 'often precedes material announcements'}. Monitor for 8-K filings from {company_name}.",
                "forward_looking_source": "Pattern analysis",
                "market_implications": f"Insider cluster {'selling suggests insiders may see limited upside or upcoming headwinds' if is_sell else 'buying suggests insiders see value at current prices'}. {num_traders} independent {'sell' if is_sell else 'buy'} decisions {'increase concern' if is_sell else 'increase confidence'}.",
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
            "signal_type": signal_type,
            "conviction_tier": conviction_tier,
            "cluster_detail": {
                "window_start": window_start,
                "window_end": window_end,
                "num_buyers": num_traders,
                "buyers": [b.to_dict() for b in buyers],
                "direction": direction,
                "conviction_tier": conviction_tier,
            },
            "has_hostile_activist": has_hostile,
            "hostile_keywords": hostile_keywords,
        }
