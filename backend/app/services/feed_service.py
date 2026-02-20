"""Service for generating the signal feed."""

import logging
import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Optional

from app.db.neo4j_client import Neo4jClient
from app.services.trade_classifier import (
    classify_trades_batch,
    is_bullish_trade,
    is_bearish_trade,
)
from app.services.insider_trading_service import InsiderTradingService
from app.services.officer_scan_service import OfficerScanService
from ingestion.sec_edgar.edgar_client import SECEdgarClient
from ingestion.sec_edgar.parsers.event_parser import EventParser, Filing8KResult

logger = logging.getLogger(__name__)

# Suffixes that indicate non-common-stock tickers (warrants, units, rights)
_NON_COMMON_SUFFIXES = ("W", "WS", "U", "R")


def pick_ticker(tickers: list[str] | None) -> str | None:
    """Pick the best ticker from a list, preferring common stock over warrants/units/rights."""
    if not tickers:
        return None
    for t in tickers:
        if not any(t.endswith(s) for s in _NON_COMMON_SUFFIXES):
            return t
    # All tickers are non-common; return the first one as fallback
    return tickers[0]


def _name_keywords(name: str) -> set[str]:
    """Extract significant keywords from a name for matching.

    Handles both "First Last" and SEC "LAST FIRST MIDDLE" formats.
    Returns set of uppercase words with length >= 4 (to avoid matching initials/particles).
    """
    n = name.upper().strip()
    # Remove suffixes, initials, punctuation
    n = re.sub(r'\b(JR\.?|SR\.?|III|IV|II|ESQ\.?|PH\.?D\.?|MD|L\.?P\.?)\b', '', n)
    n = re.sub(r'[.,\'"()]', '', n)
    n = re.sub(r'\s+', ' ', n).strip()
    # Return words with 4+ letters (avoids matching on "S", "C.", "OF", etc.)
    return {w for w in n.split() if len(w) >= 4 and w.isalpha()}


def _match_persons(persons_mentioned: list[str], trader_names: dict[str, list[dict]]) -> list[str]:
    """
    Match persons mentioned in an 8-K filing with insider traders.

    Uses keyword overlap: if a significant name word (4+ chars) from the filing
    matches a significant name word from an insider trader, it's a match.
    Handles SEC "LAST FIRST" format and 8-K "First Last" format.

    Returns list of match descriptions like:
    "RUSCKOWSKI STEPHEN H mentioned in filing — sold $1,234,567"
    """
    if not persons_mentioned or not trader_names:
        return []

    matches = []
    # Build keyword → trader mapping
    keyword_to_trader: dict[str, tuple[str, list[dict]]] = {}
    for name, trades in trader_names.items():
        keywords = _name_keywords(name)
        for kw in keywords:
            if kw not in keyword_to_trader:
                keyword_to_trader[kw] = (name, trades)

    seen = set()
    for person in persons_mentioned:
        person_keywords = _name_keywords(person)
        if not person_keywords:
            continue

        for kw in person_keywords:
            matched = keyword_to_trader.get(kw)
            if matched and matched[0] not in seen:
                seen.add(matched[0])
                original_name, trades = matched
                # Summarize their trading
                buys = [t for t in trades if t.get("direction") == "buy"]
                sells = [t for t in trades if t.get("direction") == "sell"]
                title = trades[0].get("title", "") if trades else ""
                title_str = f" ({title})" if title else ""

                if buys:
                    total = sum(t.get("value", 0) for t in buys)
                    matches.append(
                        f"{original_name}{title_str} mentioned in filing — bought ${total:,.0f}"
                    )
                elif sells:
                    total = sum(t.get("value", 0) for t in sells)
                    matches.append(
                        f"{original_name}{title_str} mentioned in filing — sold ${total:,.0f}"
                    )
                else:
                    matches.append(
                        f"{original_name}{title_str} mentioned in filing — also traded stock"
                    )
                break  # Only match once per person mentioned

    return matches


@dataclass
class InsiderContext:
    """Insider trading context for a signal."""

    net_direction: str  # "buying", "selling", "mixed", "none"
    total_buy_value: float
    total_sell_value: float
    notable_trades: list[str]  # e.g., ["CFO bought $51K 3mo before filing"]
    cluster_activity: bool  # 3+ insiders same direction within window
    trade_count: int
    person_matches: list[str] = field(default_factory=list)  # persons in both filing AND trades
    near_filing_count: int = 0  # trades within ±90d of filing
    near_filing_direction: str = "none"  # direction from near-filing trades only

    def to_dict(self) -> dict:
        return {
            "net_direction": self.net_direction,
            "total_buy_value": self.total_buy_value,
            "total_sell_value": self.total_sell_value,
            "notable_trades": self.notable_trades[:5],
            "cluster_activity": self.cluster_activity,
            "trade_count": self.trade_count,
            "person_matches": self.person_matches[:5],
            "near_filing_count": self.near_filing_count,
            "near_filing_direction": self.near_filing_direction,
        }


@dataclass
class SignalItem:
    """A single signal item for the feed."""

    company_name: str
    cik: str
    ticker: Optional[str]
    filing_date: str
    signal_level: str  # high, medium, low
    signal_summary: str
    items: list[str]  # e.g., ["1.01", "5.03"]
    item_names: list[str]  # e.g., ["Material Agreement", "Governance Change"]
    persons_mentioned: list[str]
    accession_number: str
    combined_signal_level: Optional[str] = None  # critical, high_bearish, high, medium, low
    insider_context: Optional[InsiderContext] = None
    signal_type: str = "8k"  # "8k" or "insider_cluster"
    cluster_detail: Optional[dict] = None  # Only for insider_cluster signals

    def to_dict(self) -> dict:
        result = {
            "company_name": self.company_name,
            "cik": self.cik,
            "ticker": self.ticker,
            "filing_date": self.filing_date,
            "signal_level": self.signal_level,
            "signal_summary": self.signal_summary,
            "items": self.items,
            "item_names": self.item_names,
            "persons_mentioned": self.persons_mentioned[:5],  # Limit to 5
            "accession_number": self.accession_number,
            "combined_signal_level": self.combined_signal_level or self.signal_level,
            "insider_context": self.insider_context.to_dict() if self.insider_context else None,
            "signal_type": self.signal_type,
        }
        if self.cluster_detail:
            result["cluster_detail"] = self.cluster_detail
        return result


@dataclass
class MarketScanResult:
    """Result of a full market scan."""

    status: str = "idle"  # idle, in_progress, completed, error
    companies_discovered: int = 0
    companies_scanned: int = 0
    events_stored: int = 0
    insider_transactions_stored: int = 0
    errors: list = field(default_factory=list)
    message: str = ""

    def to_dict(self) -> dict:
        return {
            "status": self.status,
            "companies_discovered": self.companies_discovered,
            "companies_scanned": self.companies_scanned,
            "events_stored": self.events_stored,
            "insider_transactions_stored": self.insider_transactions_stored,
            "errors_count": len(self.errors),
            "message": self.message,
        }


class FeedService:
    """Service for generating and ranking signal feeds."""

    # Keywords that indicate an IPO/SPAC/offering filing, NOT an M&A signal
    IPO_KEYWORDS = [
        "underwriting agreement",
        "initial public offering",
        "ipo",
        "prospectus supplement",
        "public offering price",
        "shares of common stock registered",
        "business combination agreement",  # SPAC merger
    ]

    # Item name mapping
    ITEM_NAMES = {
        "1.01": "Material Agreement",
        "1.02": "Agreement Terminated",
        "2.01": "Acquisition/Disposition",
        "2.03": "New Debt",
        "5.01": "Control Change",
        "5.02": "Executive Change",
        "5.03": "Governance Change",
        "7.01": "Regulation FD",
        "8.01": "Other Events",
        "9.01": "Exhibits",
    }

    @staticmethod
    def is_ipo_filing(raw_texts: list[str]) -> bool:
        """Check if raw_text content indicates an IPO/SPAC/offering filing."""
        combined = " ".join(t.lower() for t in raw_texts if t)
        return any(kw in combined for kw in FeedService.IPO_KEYWORDS)

    @staticmethod
    def classify_signal_level(items: list[str], raw_texts: list[str] | None = None) -> tuple[str, str]:
        """
        Classify signal level based on PREDICTIVE value for M&A detection.

        Key insight: 2.01 (Acquisition Complete) means deal is DONE - too late.
        The predictive signal is 1.01 (Material Agreement) BEFORE 2.01 appears.
        IPO/SPAC/offering filings are downgraded since they are not M&A signals.

        Returns: (level, summary)
        """
        items_set = set(items)

        # Check if deal is already closed (2.01 present)
        deal_closed = "2.01" in items_set or "5.01" in items_set
        has_material_agreement = "1.01" in items_set
        has_exec_changes = "5.02" in items_set
        has_governance_changes = "5.03" in items_set

        # HIGH: Material Agreement + Governance/Exec changes (NO 2.01)
        # This is the PREDICTIVE signal - deal announced but not closed
        if has_material_agreement and not deal_closed:
            if has_exec_changes or has_governance_changes:
                # Check for IPO/offering false positive
                if raw_texts and FeedService.is_ipo_filing(raw_texts):
                    return "low", "IPO/Offering Filing - Not M&A"
                return "high", "Deal in Progress - Material Agreement + Leadership Changes"
            # Material agreement alone - also check for IPO/offering
            if raw_texts and FeedService.is_ipo_filing(raw_texts):
                return "low", "IPO/Offering Filing - Not M&A"
            return "medium", "Material Agreement Filed - Potential Deal"

        # MEDIUM: Multiple exec/governance changes together (potential integration)
        if has_exec_changes and has_governance_changes and not deal_closed:
            return "medium", "Multiple Leadership/Governance Changes"

        # LOW: Deal already closed - too late to act
        if deal_closed:
            if has_material_agreement:
                return "low", "Acquisition Completed"
            return "low", "Control Change Completed"

        # LOW: Single executive or governance change (routine)
        if has_exec_changes:
            return "low", "Executive Change"

        if has_governance_changes:
            return "low", "Governance Change"

        # LOW: Everything else
        return "low", "SEC Filing"

    @staticmethod
    def compute_combined_signal(signal_level: str, insider_ctx: Optional[InsiderContext]) -> str:
        """
        Layer insider trade data on top of 8-K signal level.

        Returns combined signal level: critical, high_bearish, high, medium, low
        """
        if not insider_ctx or insider_ctx.trade_count == 0:
            return signal_level

        # Only upgrade/downgrade based on near-filing trades (±90d)
        # All-trades direction is informational context only
        if insider_ctx.near_filing_count == 0:
            return signal_level

        if signal_level == "high":
            if insider_ctx.near_filing_direction == "buying":
                return "critical"
            if insider_ctx.near_filing_direction == "selling":
                return "high_bearish"
        elif signal_level == "medium":
            if insider_ctx.near_filing_direction == "buying":
                return "high"
        return signal_level

    @staticmethod
    async def get_db_stats() -> dict:
        """Get database node/relationship counts for the overview page."""
        query = """
            CALL {
                MATCH (c:Company) WHERE c.cik IS NOT NULL RETURN 'companies' as label, count(c) as cnt
                UNION ALL
                MATCH (e:Event) RETURN 'events' as label, count(e) as cnt
                UNION ALL
                MATCH (p:Person) RETURN 'persons' as label, count(p) as cnt
                UNION ALL
                MATCH (t:InsiderTransaction) RETURN 'insider_transactions' as label, count(t) as cnt
                UNION ALL
                MATCH (j:Jurisdiction) RETURN 'jurisdictions' as label, count(j) as cnt
            }
            RETURN label, cnt
        """
        results = await Neo4jClient.execute_query(query)
        counts = {r["label"]: r["cnt"] for r in results}

        # Get relationship count
        rel_query = """
            MATCH ()-[r]->() RETURN count(r) as total_relationships
        """
        rel_results = await Neo4jClient.execute_query(rel_query)
        total_rels = rel_results[0]["total_relationships"] if rel_results else 0

        # Get total nodes
        total_nodes = sum(counts.values())

        return {
            "companies": counts.get("companies", 0),
            "events": counts.get("events", 0),
            "persons": counts.get("persons", 0),
            "insider_transactions": counts.get("insider_transactions", 0),
            "jurisdictions": counts.get("jurisdictions", 0),
            "total_nodes": total_nodes,
            "total_relationships": total_rels,
        }

    @staticmethod
    async def get_insider_context_batch(signals: list['SignalItem']) -> dict[str, InsiderContext]:
        """
        Batch-fetch insider trade context for a list of signals.

        Two-tier approach:
        - ALL trades for overall context (net_direction, trade_count, buy/sell values)
        - Near-filing trades (±90d) for signal enrichment (near_filing_direction, cluster_activity, notable_trades)

        Returns dict keyed by (cik, filing_date, accession_number) string.
        """
        if not signals:
            return {}

        # Collect unique CIKs
        ciks = list(set(s.cik for s in signals))

        # Batch query: get all insider transactions for these CIKs
        query = """
            MATCH (c:Company)-[:INSIDER_TRADE_OF]->(t:InsiderTransaction)<-[:TRADED_BY]-(p:Person)
            WHERE c.cik IN $ciks
            RETURN c.cik as cik,
                   t.transaction_date as transaction_date,
                   t.transaction_code as transaction_code,
                   t.transaction_type as transaction_type,
                   t.total_value as total_value,
                   t.shares as shares,
                   p.name as insider_name,
                   t.insider_title as insider_title
            ORDER BY t.transaction_date DESC
        """
        results = await Neo4jClient.execute_query(query, {"ciks": ciks})

        # Index trades by CIK
        trades_by_cik: dict[str, list] = {}
        for r in results:
            cik = r["cik"]
            if cik not in trades_by_cik:
                trades_by_cik[cik] = []
            trades_by_cik[cik].append(r)

        # Build InsiderContext for each signal
        contexts = {}
        for signal in signals:
            key = f"{signal.cik}|{signal.filing_date}|{signal.accession_number}"
            trades = trades_by_cik.get(signal.cik, [])

            if not trades:
                contexts[key] = InsiderContext(
                    net_direction="none", total_buy_value=0, total_sell_value=0,
                    notable_trades=[], cluster_activity=False, trade_count=0,
                )
                continue

            # Parse filing date
            try:
                filing_dt = datetime.strptime(signal.filing_date, "%Y-%m-%d")
            except (ValueError, TypeError):
                contexts[key] = InsiderContext(
                    net_direction="none", total_buy_value=0, total_sell_value=0,
                    notable_trades=[], cluster_activity=False, trade_count=0,
                )
                continue

            # === TIER 1: ALL trades for this company ===
            total_buy = 0.0
            total_sell = 0.0
            buyers = set()
            sellers = set()
            trades_by_person: dict[str, list[dict]] = {}

            all_trade_types = classify_trades_batch(
                trades,
                name_key="insider_name",
                date_key="transaction_date",
                code_key="transaction_code",
            )

            for t, trade_type in zip(trades, all_trade_types):
                val = abs(t["total_value"] or 0)
                name = t["insider_name"] or "Unknown"
                title = t["insider_title"] or ""

                if is_bullish_trade(trade_type):
                    total_buy += val
                    buyers.add(name)
                    trades_by_person.setdefault(name, []).append(
                        {"direction": "buy", "value": val, "title": title}
                    )
                elif is_bearish_trade(trade_type):
                    total_sell += val
                    sellers.add(name)
                    trades_by_person.setdefault(name, []).append(
                        {"direction": "sell", "value": val, "title": title}
                    )

            # Overall direction from ALL trades
            if total_buy > total_sell * 1.5:
                direction = "buying"
            elif total_sell > total_buy * 1.5:
                direction = "selling"
            elif total_buy > 0 or total_sell > 0:
                direction = "mixed"
            else:
                direction = "none"

            # Person-level matching from ALL trades
            person_matches = _match_persons(signal.persons_mentioned, trades_by_person)

            # === TIER 2: Near-filing window (±90 days) ===
            window_start = (filing_dt - timedelta(days=90)).strftime("%Y-%m-%d")
            window_end = (filing_dt + timedelta(days=90)).strftime("%Y-%m-%d")

            window_trades = [
                t for t in trades
                if t["transaction_date"] and window_start <= t["transaction_date"] <= window_end
            ]

            notable = []
            near_buy = 0.0
            near_sell = 0.0
            near_buyers = set()
            near_sellers = set()

            if window_trades:
                window_trade_types = classify_trades_batch(
                    window_trades,
                    name_key="insider_name",
                    date_key="transaction_date",
                    code_key="transaction_code",
                )

                for t, trade_type in zip(window_trades, window_trade_types):
                    val = abs(t["total_value"] or 0)
                    name = t["insider_name"] or "Unknown"
                    title = t["insider_title"] or ""

                    if is_bullish_trade(trade_type):
                        near_buy += val
                        near_buyers.add(name)
                        # Days relative to filing (only meaningful for near-filing)
                        try:
                            trade_dt = datetime.strptime(t["transaction_date"], "%Y-%m-%d")
                            days_diff = (filing_dt - trade_dt).days
                            if days_diff > 0:
                                time_desc = f"{days_diff}d before filing"
                            elif days_diff < 0:
                                time_desc = f"{abs(days_diff)}d after filing"
                            else:
                                time_desc = "same day as filing"
                        except (ValueError, TypeError):
                            time_desc = ""

                        label = title.split(",")[0].strip() if title else name.split()[-1]
                        if val >= 10000:
                            notable.append(f"{label} bought ${val:,.0f} {time_desc}")
                    elif is_bearish_trade(trade_type):
                        near_sell += val
                        near_sellers.add(name)

            # Near-filing direction
            if near_buy > near_sell * 1.5:
                near_direction = "buying"
            elif near_sell > near_buy * 1.5:
                near_direction = "selling"
            elif near_buy > 0 or near_sell > 0:
                near_direction = "mixed"
            else:
                near_direction = "none"

            # Cluster activity only meaningful within near-filing window
            cluster = len(near_buyers) >= 3 or len(near_sellers) >= 3

            contexts[key] = InsiderContext(
                net_direction=direction,
                total_buy_value=total_buy,
                total_sell_value=total_sell,
                notable_trades=notable[:5],
                cluster_activity=cluster,
                trade_count=len(trades),
                person_matches=person_matches,
                near_filing_count=len(window_trades),
                near_filing_direction=near_direction,
            )

        return contexts

    @staticmethod
    async def get_feed(
        days: int = 7,
        limit: int = 50,
        min_level: str = "low",
        cik: Optional[str] = None,
    ) -> tuple[list['SignalItem'], Optional[dict]]:
        """
        Get signal feed from stored events.

        Args:
            days: Look back this many days
            limit: Maximum signals to return
            min_level: Minimum signal level (low, medium, high)
            cik: Optional CIK to filter to a single company

        Returns:
            Tuple of (list of SignalItem sorted by date and importance, company_filter dict or None)
        """
        # Query stored events
        cik_clause = "AND c.cik = $cik" if cik else ""
        query = f"""
            MATCH (c:Company)-[:FILED_EVENT]->(e:Event)
            WHERE e.is_ma_signal = true
            AND e.filing_date >= $since_date
            {cik_clause}
            RETURN c.name as company_name,
                   c.cik as cik,
                   c.tickers as tickers,
                   e.filing_date as filing_date,
                   e.item_number as item_number,
                   e.item_name as item_name,
                   e.signal_type as signal_type,
                   e.persons_mentioned as persons_mentioned,
                   e.accession_number as accession_number,
                   e.raw_text as raw_text
            ORDER BY e.filing_date DESC
        """

        since_date = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
        params: dict = {"since_date": since_date}
        if cik:
            params["cik"] = cik

        results = await Neo4jClient.execute_query(query, params)

        # Group by company + filing date + accession number
        grouped = {}
        for r in results:
            key = (r["cik"], r["filing_date"], r["accession_number"])
            if key not in grouped:
                grouped[key] = {
                    "company_name": r["company_name"],
                    "cik": r["cik"],
                    "ticker": pick_ticker(r["tickers"]),
                    "filing_date": r["filing_date"],
                    "items": [],
                    "item_names": [],
                    "persons_mentioned": [],
                    "accession_number": r["accession_number"],
                    "raw_texts": [],
                }
            grouped[key]["items"].append(r["item_number"])
            if r["item_name"]:
                grouped[key]["item_names"].append(r["item_name"])
            if r["persons_mentioned"]:
                grouped[key]["persons_mentioned"].extend(r["persons_mentioned"])
            if r.get("raw_text"):
                grouped[key]["raw_texts"].append(r["raw_text"])

        # Convert to SignalItems with classification
        signals = []
        level_order = {"high": 0, "medium": 1, "low": 2}
        min_level_order = level_order.get(min_level, 2)

        for data in grouped.values():
            level, summary = FeedService.classify_signal_level(data["items"], data.get("raw_texts"))

            # Filter by minimum level
            if level_order.get(level, 2) > min_level_order:
                continue

            signals.append(SignalItem(
                company_name=data["company_name"],
                cik=data["cik"],
                ticker=data["ticker"],
                filing_date=data["filing_date"],
                signal_level=level,
                signal_summary=summary,
                items=list(set(data["items"])),
                item_names=list(set(data["item_names"])),
                persons_mentioned=list(set(data["persons_mentioned"])),
                accession_number=data["accession_number"],
            ))

        # Enrich with insider context
        try:
            insider_contexts = await FeedService.get_insider_context_batch(signals)
            for s in signals:
                key = f"{s.cik}|{s.filing_date}|{s.accession_number}"
                ctx = insider_contexts.get(key)
                if ctx:
                    s.insider_context = ctx
                    s.combined_signal_level = FeedService.compute_combined_signal(s.signal_level, ctx)
                else:
                    s.combined_signal_level = s.signal_level
        except Exception as e:
            logger.warning(f"Failed to enrich signals with insider context: {e}")
            for s in signals:
                s.combined_signal_level = s.signal_level

        # Merge standalone insider cluster signals (no 8-K required)
        if not cik:
            try:
                from app.services.insider_cluster_service import InsiderClusterService
                cluster_signals = await InsiderClusterService.detect_clusters_excluding_8k(
                    days=days, window_days=30, min_level=min_level,
                )
                for cs in cluster_signals:
                    d = cs.to_signal_dict()
                    signals.append(SignalItem(
                        company_name=d["company_name"],
                        cik=d["cik"],
                        ticker=d["ticker"],
                        filing_date=d["filing_date"],
                        signal_level=d["signal_level"],
                        signal_summary=d["signal_summary"],
                        items=d["items"],
                        item_names=d["item_names"],
                        persons_mentioned=d["persons_mentioned"],
                        accession_number=d["accession_number"],
                        combined_signal_level=d["combined_signal_level"],
                        insider_context=InsiderContext(
                            net_direction="buying",
                            total_buy_value=cs.total_buy_value,
                            total_sell_value=0,
                            notable_trades=[f"{b.name} bought ${b.total_value:,.0f}" for b in cs.buyers[:5]],
                            cluster_activity=cs.num_buyers >= 3,
                            trade_count=sum(b.trade_count for b in cs.buyers),
                        ),
                        signal_type="insider_cluster",
                        cluster_detail=d.get("cluster_detail"),
                    ))
            except Exception as e:
                logger.warning(f"Failed to merge insider cluster signals: {e}")

        # Sort by combined level then by date
        combined_order = {"critical": 0, "high_bearish": 1, "high": 2, "medium": 3, "low": 4}
        signals.sort(key=lambda x: (x.filing_date,), reverse=True)
        signals.sort(key=lambda x: combined_order.get(x.combined_signal_level or x.signal_level, 4))

        # Build company_filter when CIK is specified
        company_filter = None
        if cik and signals:
            company_filter = {
                "cik": cik,
                "name": signals[0].company_name,
                "ticker": signals[0].ticker,
            }
        elif cik and not signals:
            # Query company name even if no signals
            company_query = """
                MATCH (c:Company {cik: $cik})
                RETURN c.name as name, c.tickers as tickers
            """
            company_result = await Neo4jClient.execute_query(company_query, {"cik": cik})
            if company_result:
                r = company_result[0]
                company_filter = {
                    "cik": cik,
                    "name": r["name"],
                    "ticker": pick_ticker(r.get("tickers")),
                }

        return signals[:limit], company_filter

    @staticmethod
    async def get_feed_summary() -> dict:
        """Get summary statistics for the feed."""
        query = """
            MATCH (c:Company)-[:FILED_EVENT]->(e:Event)
            WHERE e.is_ma_signal = true
            WITH e.filing_date as date, count(*) as count
            ORDER BY date DESC
            LIMIT 30
            RETURN collect({date: date, count: count}) as daily_counts
        """

        results = await Neo4jClient.execute_query(query)
        daily_counts = results[0]["daily_counts"] if results else []

        # Count by level for recent events
        recent_query = """
            MATCH (c:Company)-[:FILED_EVENT]->(e:Event)
            WHERE e.is_ma_signal = true
            RETURN e.item_number as item, count(*) as count
        """

        item_results = await Neo4jClient.execute_query(recent_query)
        item_counts = {r["item"]: r["count"] for r in item_results}

        return {
            "daily_counts": daily_counts,
            "item_counts": item_counts,
            "total_events": sum(item_counts.values()),
        }

    @staticmethod
    async def get_top_insider_activity(days: int = 30, limit: int = 10) -> list[dict]:
        """
        Get companies with the most insider trading activity.

        Returns top companies by trade count with net buy/sell values.
        """
        since_date = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")

        query = """
            MATCH (c:Company)-[:INSIDER_TRADE_OF]->(t:InsiderTransaction)<-[:TRADED_BY]-(p:Person)
            WHERE t.transaction_date >= $since_date
            WITH c, t, p,
                 CASE WHEN t.transaction_code = 'P' THEN t.total_value ELSE 0 END as buy_val,
                 CASE WHEN t.transaction_code = 'S' THEN t.total_value ELSE 0 END as sell_val
            WITH c.cik as cik, c.name as company_name, c.tickers as tickers,
                 count(t) as trade_count,
                 count(DISTINCT p) as unique_insiders,
                 sum(buy_val) as total_buy_value,
                 sum(sell_val) as total_sell_value
            ORDER BY trade_count DESC
            LIMIT $limit
            RETURN cik, company_name, tickers, trade_count, unique_insiders,
                   total_buy_value, total_sell_value
        """

        results = await Neo4jClient.execute_query(query, {
            "since_date": since_date,
            "limit": limit,
        })

        return [
            {
                "cik": r["cik"],
                "company_name": r["company_name"],
                "ticker": pick_ticker(r.get("tickers")),
                "trade_count": r["trade_count"],
                "unique_insiders": r["unique_insiders"],
                "total_buy_value": r["total_buy_value"] or 0,
                "total_sell_value": r["total_sell_value"] or 0,
                "net_direction": "buying" if (r["total_buy_value"] or 0) > (r["total_sell_value"] or 0) * 1.5
                    else "selling" if (r["total_sell_value"] or 0) > (r["total_buy_value"] or 0) * 1.5
                    else "mixed",
            }
            for r in results
        ]

    @staticmethod
    async def scan_and_store_company(
        cik: str,
        company_name: str,
        limit: int = 20,
    ) -> dict:
        """
        Scan a company's 8-K filings and store the events.

        Returns summary of what was found and stored.
        """
        client = SECEdgarClient()
        parser = EventParser()

        try:
            # Fetch company info for tickers and other metadata
            try:
                company_info = await client.get_company_info(cik)
                tickers = company_info.tickers
                sic = company_info.sic
                sic_description = company_info.sic_description
                state = company_info.state_of_incorporation
                # Use SEC name if available
                if company_info.name:
                    company_name = company_info.name
            except Exception as e:
                logger.warning(f"Could not fetch company info for {cik}: {e}")
                tickers = []
                sic = None
                sic_description = None
                state = None

            # Update company node with full metadata
            update_query = """
                MERGE (c:Company {cik: $cik})
                SET c.name = $name,
                    c.tickers = $tickers,
                    c.sic = $sic,
                    c.sic_description = $sic_description,
                    c.state_of_incorporation = $state
                RETURN c
            """
            await Neo4jClient.execute_query(update_query, {
                "cik": cik,
                "name": company_name,
                "tickers": tickers,
                "sic": sic,
                "sic_description": sic_description,
                "state": state,
            })

            filings = await client.get_8k_filings(cik, limit=limit)

            results = []
            for filing in filings:
                try:
                    content = await client.get_filing_document(cik, filing)
                    result = parser.parse_8k(
                        html_content=content,
                        cik=cik,
                        company_name=company_name,
                        accession_number=filing.accession_number,
                        filing_date=filing.filing_date,
                    )
                    results.append(result)
                except Exception as e:
                    logger.error(f"Error parsing {filing.accession_number}: {e}")

            # Store events
            count = 0
            for result in results:
                for event in result.events:
                    if not event.is_ma_signal:
                        continue

                    query = """
                        MERGE (c:Company {cik: $cik})
                        ON CREATE SET c.name = $company_name
                        MERGE (e:Event {
                            accession_number: $accession_number,
                            item_number: $item_number
                        })
                        SET e.company_name = $company_name,
                            e.filing_date = $filing_date,
                            e.item_name = $item_name,
                            e.signal_type = $signal_type,
                            e.is_ma_signal = $is_ma_signal,
                            e.persons_mentioned = $persons_mentioned,
                            e.raw_text = $raw_text
                        MERGE (c)-[:FILED_EVENT]->(e)
                        RETURN e
                    """

                    await Neo4jClient.execute_query(query, {
                        "cik": cik,
                        "company_name": company_name,
                        "accession_number": result.accession_number,
                        "item_number": event.item_number,
                        "filing_date": result.filing_date,
                        "item_name": event.item_name,
                        "signal_type": event.signal_type,
                        "is_ma_signal": event.is_ma_signal,
                        "persons_mentioned": event.persons_mentioned,
                        "raw_text": event.raw_text[:1000] if event.raw_text else "",
                    })
                    count += 1

            ma_filings = sum(1 for r in results if r.has_ma_signals)

            return {
                "cik": cik,
                "company_name": company_name,
                "filings_scanned": len(filings),
                "filings_with_signals": ma_filings,
                "events_stored": count,
            }

        finally:
            await client.close()

    @staticmethod
    async def scan_multiple_companies(
        companies: list[dict],
        filings_per_company: int = 10,
    ) -> dict:
        """
        Scan multiple companies and store their events.

        Args:
            companies: List of {"cik": "...", "name": "..."}
            filings_per_company: How many 8-K filings to scan per company

        Returns:
            Summary of scan results
        """
        total_scanned = 0
        total_events = 0
        errors = []

        for company in companies:
            try:
                result = await FeedService.scan_and_store_company(
                    cik=company["cik"],
                    company_name=company["name"],
                    limit=filings_per_company,
                )
                total_scanned += 1
                total_events += result["events_stored"]
                logger.info(f"Scanned {company['name']}: {result['events_stored']} events")
            except Exception as e:
                errors.append({"company": company["name"], "error": str(e)})
                logger.error(f"Error scanning {company['name']}: {e}")

        return {
            "companies_scanned": total_scanned,
            "total_events_stored": total_events,
            "errors": errors,
        }

    @staticmethod
    async def market_scan(days_back: int = 3, scan_result: Optional['MarketScanResult'] = None) -> MarketScanResult:
        """
        Scan the entire market for recent 8-K filings.

        Discovers all companies that filed 8-Ks in the last `days_back` days
        via SEC EFTS, then scans each using the existing pipeline.

        Args:
            days_back: How many days back to look (1-7)
            scan_result: Shared MarketScanResult for progress tracking

        Returns:
            MarketScanResult with summary
        """
        if scan_result is None:
            scan_result = MarketScanResult()

        scan_result.status = "in_progress"
        scan_result.message = "Discovering recent 8-K filers..."

        client = SECEdgarClient()
        try:
            # Step 1: Discover filers
            filers = await client.get_recent_8k_filers(days_back=days_back)
            scan_result.companies_discovered = len(filers)
            scan_result.message = f"Found {len(filers)} companies, starting scan..."
            logger.info(f"Market scan: discovered {len(filers)} unique 8-K filers")
        except Exception as e:
            scan_result.status = "error"
            scan_result.message = f"Discovery failed: {e}"
            logger.error(f"Market scan discovery failed: {e}")
            return scan_result
        finally:
            await client.close()

        # Step 2: Scan each company
        for i, filer in enumerate(filers):
            try:
                result = await FeedService.scan_and_store_company(
                    cik=filer["cik"],
                    company_name=filer["name"],
                    limit=5,
                )
                scan_result.companies_scanned += 1
                scan_result.events_stored += result["events_stored"]
                scan_result.message = f"Scanning... {scan_result.companies_scanned}/{scan_result.companies_discovered} companies"
                logger.info(
                    f"Market scan [{scan_result.companies_scanned}/{scan_result.companies_discovered}] "
                    f"{filer['name']}: {result['events_stored']} events"
                )

                # Also scan for officer/director data (latest DEF 14A only)
                try:
                    await OfficerScanService.scan_and_store_company(
                        cik=filer["cik"],
                        company_name=filer["name"],
                        limit=1,
                    )
                except Exception as officer_err:
                    logger.warning(f"Officer scan failed for {filer['name']}: {officer_err}")

                # Also scan for insider trades (Form 4)
                try:
                    insider_result = await InsiderTradingService.scan_and_store_company(
                        cik=filer["cik"],
                        company_name=filer["name"],
                        limit=10,
                    )
                    scan_result.insider_transactions_stored += insider_result.get("transactions_stored", 0)
                except Exception as insider_err:
                    logger.warning(f"Insider trade scan failed for {filer['name']}: {insider_err}")
            except Exception as e:
                scan_result.errors.append({"company": filer["name"], "error": str(e)})
                logger.error(f"Market scan error for {filer['name']}: {e}")

        scan_result.status = "completed"
        scan_result.message = (
            f"Market scan complete - {scan_result.companies_scanned} companies scanned, "
            f"{scan_result.events_stored} events found"
        )
        logger.info(scan_result.message)
        return scan_result
