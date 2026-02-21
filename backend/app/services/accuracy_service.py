"""Service for tracking signal accuracy — retroactively measures how insider
cluster signals performed in terms of subsequent price action and 8-K events.

Answers: "when we detected a cluster, what actually happened?"
"""

import logging
import math
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Optional

from app.db.neo4j_client import Neo4jClient
from app.services.insider_cluster_service import InsiderClusterService
from app.services.stock_price_service import StockPriceService

logger = logging.getLogger(__name__)

# In-memory cache: key -> (timestamp, data)
_accuracy_cache: dict[str, tuple[float, dict]] = {}
_CACHE_TTL = 4 * 3600  # 4 hours


@dataclass
class SignalOutcome:
    """Per-signal accuracy result."""

    cik: str
    company_name: str
    ticker: Optional[str]
    signal_level: str
    signal_date: str  # YYYY-MM-DD (window_end)
    num_buyers: int
    total_buy_value: float
    signal_age_days: int

    # Price outcomes (None if too recent or no data)
    price_at_signal: Optional[float] = None
    price_change_30d: Optional[float] = None
    price_change_60d: Optional[float] = None
    price_change_90d: Optional[float] = None

    # Event outcomes
    followed_by_8k: bool = False
    followed_by_deal_close: bool = False
    days_to_first_8k: Optional[int] = None
    first_8k_items: list[str] = field(default_factory=list)

    # Insider continuation
    insider_buying_continued: bool = False
    insider_selling_after: bool = False

    # Verdict: hit, partial_hit, miss, pending, no_data
    verdict: str = "no_data"

    def to_dict(self) -> dict:
        return {
            "cik": self.cik,
            "company_name": self.company_name,
            "ticker": self.ticker,
            "signal_level": self.signal_level,
            "signal_date": self.signal_date,
            "num_buyers": self.num_buyers,
            "total_buy_value": self.total_buy_value,
            "signal_age_days": self.signal_age_days,
            "price_at_signal": self.price_at_signal,
            "price_change_30d": self.price_change_30d,
            "price_change_60d": self.price_change_60d,
            "price_change_90d": self.price_change_90d,
            "followed_by_8k": self.followed_by_8k,
            "followed_by_deal_close": self.followed_by_deal_close,
            "days_to_first_8k": self.days_to_first_8k,
            "first_8k_items": self.first_8k_items,
            "insider_buying_continued": self.insider_buying_continued,
            "insider_selling_after": self.insider_selling_after,
            "verdict": self.verdict,
        }


@dataclass
class LevelStats:
    """Aggregate stats for a single signal level."""

    level: str
    count: int = 0
    scoreable: int = 0  # signals old enough to score
    hits: int = 0
    partial_hits: int = 0
    misses: int = 0
    hit_rate: Optional[float] = None
    avg_return_30d: Optional[float] = None
    avg_return_60d: Optional[float] = None
    avg_return_90d: Optional[float] = None
    eight_k_follow_rate: Optional[float] = None

    def to_dict(self) -> dict:
        return {
            "level": self.level,
            "count": self.count,
            "scoreable": self.scoreable,
            "hits": self.hits,
            "partial_hits": self.partial_hits,
            "misses": self.misses,
            "hit_rate": self.hit_rate,
            "avg_return_30d": self.avg_return_30d,
            "avg_return_60d": self.avg_return_60d,
            "avg_return_90d": self.avg_return_90d,
            "eight_k_follow_rate": self.eight_k_follow_rate,
        }


@dataclass
class AccuracySummary:
    """Aggregate accuracy stats across all signal levels."""

    total_signals: int = 0
    scoreable_signals: int = 0
    overall_hit_rate: Optional[float] = None
    overall_avg_return_90d: Optional[float] = None
    overall_8k_follow_rate: Optional[float] = None
    by_level: dict[str, LevelStats] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "total_signals": self.total_signals,
            "scoreable_signals": self.scoreable_signals,
            "overall_hit_rate": self.overall_hit_rate,
            "overall_avg_return_90d": self.overall_avg_return_90d,
            "overall_8k_follow_rate": self.overall_8k_follow_rate,
            "by_level": {k: v.to_dict() for k, v in self.by_level.items()},
        }


def compute_price_outcomes(
    price_history: list[dict],
    signal_date: str,
) -> dict:
    """Pure function: find price at signal date, compute +30/60/90d changes.

    Args:
        price_history: list of {date, close, ...} dicts sorted by date
        signal_date: YYYY-MM-DD string

    Returns:
        dict with price_at_signal, price_change_30d/60d/90d (percentage or None)
    """
    if not price_history:
        return {
            "price_at_signal": None,
            "price_change_30d": None,
            "price_change_60d": None,
            "price_change_90d": None,
        }

    try:
        signal_dt = datetime.strptime(signal_date, "%Y-%m-%d")
    except (ValueError, TypeError):
        return {
            "price_at_signal": None,
            "price_change_30d": None,
            "price_change_60d": None,
            "price_change_90d": None,
        }

    # Build date->close lookup
    date_prices: list[tuple[datetime, float]] = []
    for point in price_history:
        try:
            d = datetime.strptime(point["date"], "%Y-%m-%d")
            date_prices.append((d, point["close"]))
        except (ValueError, KeyError, TypeError):
            continue

    if not date_prices:
        return {
            "price_at_signal": None,
            "price_change_30d": None,
            "price_change_60d": None,
            "price_change_90d": None,
        }

    def find_closest_price(target_dt: datetime) -> Optional[float]:
        """Find price closest to target date, within 5 trading days."""
        best = None
        best_diff = None
        for d, price in date_prices:
            diff = abs((d - target_dt).days)
            if best_diff is None or diff < best_diff:
                best = price
                best_diff = diff
        if best_diff is not None and best_diff <= 7:
            return best
        return None

    signal_price = find_closest_price(signal_dt)
    if signal_price is None or signal_price <= 0:
        return {
            "price_at_signal": None,
            "price_change_30d": None,
            "price_change_60d": None,
            "price_change_90d": None,
        }

    result: dict = {"price_at_signal": round(signal_price, 2)}

    for label, offset_days in [("30d", 30), ("60d", 60), ("90d", 90)]:
        target_dt = signal_dt + timedelta(days=offset_days)
        future_price = find_closest_price(target_dt)
        if future_price is not None:
            pct = round((future_price - signal_price) / signal_price * 100, 2)
            result[f"price_change_{label}"] = pct
        else:
            result[f"price_change_{label}"] = None

    return result


def classify_verdict(
    signal_age_days: int,
    price_change_90d: Optional[float],
    price_change_60d: Optional[float],
    price_change_30d: Optional[float],
    followed_by_8k: bool,
    min_signal_age_days: int = 30,
) -> str:
    """Classify a signal outcome as hit/partial_hit/miss/pending/no_data.

    hit: 10%+ return at best available horizon OR followed by 8-K
    partial_hit: 0-10% return at best available horizon
    miss: negative return at best available horizon
    pending: signal too recent to score
    no_data: no price data available
    """
    if signal_age_days < min_signal_age_days:
        return "pending"

    # Use the longest available horizon
    best_return = price_change_90d if price_change_90d is not None else (
        price_change_60d if price_change_60d is not None else price_change_30d
    )

    if best_return is None and not followed_by_8k:
        return "no_data"

    # 8-K follow = automatic hit
    if followed_by_8k:
        return "hit"

    if best_return is not None:
        if best_return >= 10:
            return "hit"
        elif best_return >= 0:
            return "partial_hit"
        else:
            return "miss"

    return "no_data"


def compute_level_stats(outcomes: list[SignalOutcome], level: str) -> LevelStats:
    """Compute aggregate stats for a set of outcomes at a given level."""
    filtered = [o for o in outcomes if o.signal_level == level]
    stats = LevelStats(level=level, count=len(filtered))

    scoreable = [o for o in filtered if o.verdict not in ("pending", "no_data")]
    stats.scoreable = len(scoreable)
    stats.hits = sum(1 for o in scoreable if o.verdict == "hit")
    stats.partial_hits = sum(1 for o in scoreable if o.verdict == "partial_hit")
    stats.misses = sum(1 for o in scoreable if o.verdict == "miss")

    if stats.scoreable > 0:
        stats.hit_rate = round(stats.hits / stats.scoreable * 100, 1)

    # Average returns (only where data exists)
    for attr, field_name in [
        ("avg_return_30d", "price_change_30d"),
        ("avg_return_60d", "price_change_60d"),
        ("avg_return_90d", "price_change_90d"),
    ]:
        values = [getattr(o, field_name) for o in filtered if getattr(o, field_name) is not None]
        if values:
            setattr(stats, attr, round(sum(values) / len(values), 2))

    # 8-K follow rate
    with_8k = sum(1 for o in filtered if o.followed_by_8k)
    if stats.count > 0:
        stats.eight_k_follow_rate = round(with_8k / stats.count * 100, 1)

    return stats


def proof_score(outcome: SignalOutcome) -> float:
    """Score a hit for marketing impact on the proof wall.

    Weights: 40% return, 25% buy value (log scale), 15% buyer count,
    10% 8-K confirmation, 10% signal level.
    """
    # Best available return (prefer longest horizon)
    best_return = outcome.price_change_90d or outcome.price_change_60d or outcome.price_change_30d or 0.0
    return_score = min(best_return / 150.0, 1.0)  # cap at 150%

    # Buy value via log scale (e.g. $1M → ~0.6, $10M → ~0.8)
    buy_val = max(outcome.total_buy_value, 1)
    value_score = min(math.log10(buy_val) / 8.0, 1.0)  # $100M → 1.0

    # Buyer count (3 → 0.6, 5+ → 1.0)
    buyer_score = min(outcome.num_buyers / 5.0, 1.0)

    # 8-K confirmation
    eight_k_score = 1.0 if outcome.followed_by_8k else 0.0

    # Signal level
    level_map = {"high": 1.0, "medium": 0.5, "low": 0.2}
    level_score = level_map.get(outcome.signal_level, 0.0)

    return (
        0.40 * return_score
        + 0.25 * value_score
        + 0.15 * buyer_score
        + 0.10 * eight_k_score
        + 0.10 * level_score
    )


def _to_proof_dict(outcome: SignalOutcome) -> dict:
    """Slim payload for the proof wall frontend."""
    best_change = None
    best_horizon = None
    for horizon, attr in [("90d", "price_change_90d"), ("60d", "price_change_60d"), ("30d", "price_change_30d")]:
        val = getattr(outcome, attr)
        if val is not None:
            best_change = val
            best_horizon = horizon
            break

    return {
        "company_name": outcome.company_name,
        "ticker": outcome.ticker,
        "cik": outcome.cik,
        "signal_date": outcome.signal_date,
        "signal_level": outcome.signal_level,
        "num_buyers": outcome.num_buyers,
        "total_buy_value": outcome.total_buy_value,
        "best_price_change": best_change,
        "best_horizon": best_horizon,
        "followed_by_8k": outcome.followed_by_8k,
        "days_to_first_8k": outcome.days_to_first_8k,
    }


class AccuracyService:
    """Computes signal accuracy by checking what happened after cluster detections."""

    @staticmethod
    async def get_accuracy(
        lookback_days: int = 365,
        min_signal_age_days: int = 30,
        min_level: str = "medium",
    ) -> dict:
        """Full accuracy report: summary + individual signal outcomes.

        Returns:
            {"summary": AccuracySummary.to_dict(), "signals": [SignalOutcome.to_dict(), ...]}
        """
        cache_key = f"{lookback_days}_{min_signal_age_days}_{min_level}"
        if cache_key in _accuracy_cache:
            ts, data = _accuracy_cache[cache_key]
            if time.time() - ts < _CACHE_TTL:
                return data

        # 1. Detect historical clusters
        clusters = await InsiderClusterService.detect_clusters(
            days=lookback_days,
            min_level=min_level,
        )

        if not clusters:
            empty = {"summary": AccuracySummary().to_dict(), "signals": []}
            _accuracy_cache[cache_key] = (time.time(), empty)
            return empty

        now = datetime.now()

        # 2. Batch-fetch subsequent 8-K events
        ciks = list({c.cik for c in clusters})
        events_by_cik = await AccuracyService._batch_check_subsequent_events(ciks)

        # 3. Batch-fetch insider continuation
        continuation_by_cik = await AccuracyService._batch_check_insider_continuation(ciks)

        # 4. Fetch price data per unique ticker (batch via yfinance cache)
        ticker_prices: dict[str, list[dict]] = {}
        unique_tickers = {c.ticker for c in clusters if c.ticker}
        for ticker in unique_tickers:
            try:
                ticker_prices[ticker] = StockPriceService.get_price_data(ticker, "2y")
            except Exception as e:
                logger.warning(f"Failed to fetch prices for {ticker}: {e}")
                ticker_prices[ticker] = []

        # 5. Build outcomes
        outcomes: list[SignalOutcome] = []
        for cluster in clusters:
            signal_date = cluster.window_end
            try:
                signal_dt = datetime.strptime(signal_date, "%Y-%m-%d")
                age_days = (now - signal_dt).days
            except (ValueError, TypeError):
                age_days = 0

            outcome = SignalOutcome(
                cik=cluster.cik,
                company_name=cluster.company_name,
                ticker=cluster.ticker,
                signal_level=cluster.signal_level,
                signal_date=signal_date,
                num_buyers=cluster.num_buyers,
                total_buy_value=cluster.total_buy_value,
                signal_age_days=age_days,
            )

            # Price outcomes
            if cluster.ticker and cluster.ticker in ticker_prices:
                price_result = compute_price_outcomes(
                    ticker_prices[cluster.ticker], signal_date
                )
                outcome.price_at_signal = price_result["price_at_signal"]
                outcome.price_change_30d = price_result["price_change_30d"]
                outcome.price_change_60d = price_result["price_change_60d"]
                outcome.price_change_90d = price_result["price_change_90d"]

            # Event outcomes — find 8-Ks filed AFTER the signal date
            cik_events = events_by_cik.get(cluster.cik, [])
            subsequent = [
                e for e in cik_events
                if e["filing_date"] and e["filing_date"] > signal_date
            ]
            if subsequent:
                outcome.followed_by_8k = True
                first = subsequent[0]
                try:
                    first_dt = datetime.strptime(first["filing_date"], "%Y-%m-%d")
                    outcome.days_to_first_8k = (first_dt - signal_dt).days
                except (ValueError, TypeError):
                    pass
                outcome.first_8k_items = [
                    e.get("item_number", "") for e in subsequent[:3]
                ]
                # Check for deal close (item 2.01)
                outcome.followed_by_deal_close = any(
                    "2.01" in (e.get("item_number") or "") for e in subsequent
                )

            # Insider continuation
            cont = continuation_by_cik.get(cluster.cik, {})
            outcome.insider_buying_continued = cont.get("buying_after", False)
            outcome.insider_selling_after = cont.get("selling_after", False)

            # Verdict
            outcome.verdict = classify_verdict(
                signal_age_days=age_days,
                price_change_90d=outcome.price_change_90d,
                price_change_60d=outcome.price_change_60d,
                price_change_30d=outcome.price_change_30d,
                followed_by_8k=outcome.followed_by_8k,
                min_signal_age_days=min_signal_age_days,
            )

            outcomes.append(outcome)

        # 6. Compute summary
        summary = AccuracySummary(total_signals=len(outcomes))
        scoreable = [o for o in outcomes if o.verdict not in ("pending", "no_data")]
        summary.scoreable_signals = len(scoreable)

        if scoreable:
            hits = sum(1 for o in scoreable if o.verdict == "hit")
            summary.overall_hit_rate = round(hits / len(scoreable) * 100, 1)

        returns_90d = [o.price_change_90d for o in outcomes if o.price_change_90d is not None]
        if returns_90d:
            summary.overall_avg_return_90d = round(sum(returns_90d) / len(returns_90d), 2)

        with_8k = sum(1 for o in outcomes if o.followed_by_8k)
        if outcomes:
            summary.overall_8k_follow_rate = round(with_8k / len(outcomes) * 100, 1)

        for level in ("high", "medium", "low"):
            summary.by_level[level] = compute_level_stats(outcomes, level)

        result = {
            "summary": summary.to_dict(),
            "signals": [o.to_dict() for o in outcomes],
        }

        _accuracy_cache[cache_key] = (time.time(), result)
        return result

    @staticmethod
    async def get_top_hits(limit: int = 3) -> list[dict]:
        """Return the top N hits sorted by proof_score for the proof wall.

        Reuses the cached get_accuracy() call (4h TTL).
        """
        data = await AccuracyService.get_accuracy()
        outcomes: list[SignalOutcome] = []
        for s in data["signals"]:
            o = SignalOutcome(**{k: v for k, v in s.items() if k in SignalOutcome.__dataclass_fields__})
            outcomes.append(o)

        # Filter: verdict=hit, has ticker, positive best return
        hits = []
        for o in outcomes:
            if o.verdict != "hit" or not o.ticker:
                continue
            best = o.price_change_90d or o.price_change_60d or o.price_change_30d
            if best is not None and best > 0:
                hits.append(o)

        hits.sort(key=proof_score, reverse=True)
        return [_to_proof_dict(h) for h in hits[:limit]]

    @staticmethod
    async def get_accuracy_summary(
        lookback_days: int = 365,
        min_signal_age_days: int = 30,
        min_level: str = "medium",
    ) -> dict:
        """Just the aggregate stats (no individual signals)."""
        full = await AccuracyService.get_accuracy(
            lookback_days=lookback_days,
            min_signal_age_days=min_signal_age_days,
            min_level=min_level,
        )
        return full["summary"]

    @staticmethod
    async def _batch_check_subsequent_events(ciks: list[str]) -> dict[str, list[dict]]:
        """Single Cypher query to get MA-signal events for given CIKs.

        Returns: {cik: [{filing_date, item_number, accession_number}, ...]}
        sorted by filing_date per CIK.
        """
        if not ciks:
            return {}

        query = """
            MATCH (c:Company)-[:FILED_EVENT]->(e:Event)
            WHERE c.cik IN $ciks AND e.is_ma_signal = true
            RETURN c.cik as cik, e.filing_date as filing_date,
                   e.item_number as item_number, e.accession_number as accession_number
            ORDER BY c.cik, e.filing_date
        """
        results = await Neo4jClient.execute_query(query, {"ciks": ciks})

        events_by_cik: dict[str, list[dict]] = {}
        for r in results:
            cik = r["cik"]
            if cik not in events_by_cik:
                events_by_cik[cik] = []
            events_by_cik[cik].append({
                "filing_date": r["filing_date"],
                "item_number": r["item_number"],
                "accession_number": r["accession_number"],
            })

        return events_by_cik

    @staticmethod
    async def _batch_check_insider_continuation(ciks: list[str]) -> dict[str, dict]:
        """Check if insiders continued buying or started selling after the cluster window.

        Returns: {cik: {buying_after: bool, selling_after: bool}}
        """
        if not ciks:
            return {}

        # Look for trades in the last 30 days
        since_date = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")

        query = """
            MATCH (c:Company)-[:INSIDER_TRADE_OF]->(t:InsiderTransaction)
            WHERE c.cik IN $ciks AND t.transaction_date >= $since_date
            RETURN c.cik as cik,
                   t.transaction_code as transaction_code,
                   t.total_value as total_value
        """
        results = await Neo4jClient.execute_query(query, {
            "ciks": ciks,
            "since_date": since_date,
        })

        cont: dict[str, dict] = {}
        for r in results:
            cik = r["cik"]
            if cik not in cont:
                cont[cik] = {"buying_after": False, "selling_after": False}

            code = r.get("transaction_code") or ""
            value = abs(r.get("total_value") or 0)

            if code == "P" and value > 0:
                cont[cik]["buying_after"] = True
            elif code == "S" and value > 0:
                cont[cik]["selling_after"] = True

        return cont
