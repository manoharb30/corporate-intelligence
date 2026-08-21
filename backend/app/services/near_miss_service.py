"""Research Queue — genuine insider clusters dropped solely on earnings timing.

These are NOT signals. Every row here was classified GENUINE by the LLM and then
rewritten by merge_classifications.py to classification='FILTERED' with
classification_rule='EARNINGS_FILTER' — real open-market buys rejected on the
earnings-proximity gate alone. Historically this bucket returns 55.6% HR /
+0.97pp alpha vs 65.3% / +7.3pp for accepted signals, which is why the filter
stays; the page exists so a good company is not silently lost.

Computed live on every request — one aggregation over a few dozen rows. No
precomputed blob: that is what caused the snapshot-vs-detail divergence and the
GSHD 5-buyers bug.

Gates are imported from insider_cluster_service, never redeclared here.
"""

import logging
from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta

from app.db.neo4j_client import Neo4jClient
from app.services.insider_cluster_service import (
    EXCLUDED_CIKS,
    MIN_CLUSTER_INSIDERS,
    MIN_CLUSTER_VALUE_USD,
    MIN_MARKET_CAP_USD,
    MAX_MARKET_CAP_USD,
    CLUSTER_WINDOW_DAYS,
    classify_insider_role,
)
from app.services.research_note_service import ResearchNoteService

logger = logging.getLogger(__name__)

FILTER_RULE = "EARNINGS_FILTER"

# The caveat the page must carry. Kept beside the data so it cannot drift away
# from it — see docs/near-miss framing.
CAVEAT = (
    "Filtered on earnings timing. This bucket historically returns 55.6% hit rate "
    "and +0.97pp alpha, versus 65.3% and +7.3pp for accepted signals. "
    "Research queue, not a signal list."
)


def _pad(cik: str) -> str:
    return (cik or "").strip().zfill(10)


def _date_only(value: str) -> str:
    """Transaction dates may carry a TZ suffix ('2026-08-13-05:00'). Keep the date."""
    return (value or "")[:10]


def _parse(value: str) -> datetime | None:
    try:
        return datetime.strptime(_date_only(value), "%Y-%m-%d")
    except ValueError:
        return None


@dataclass
class NearMissBuyer:
    insider_name: str
    insider_title: str
    role: str
    transaction_date: str
    value: float
    form4_url: str | None = None


@dataclass
class NearMiss:
    cik: str
    ticker: str
    company_name: str
    window_start: str
    window_end: str
    insider_count: int
    total_value: float
    market_cap: float
    pct_of_mcap: float
    buyers: list[NearMissBuyer] = field(default_factory=list)
    research_notes: list[dict] = field(default_factory=list)
    verdict: str | None = None
    filter_reason: str | None = None

    def to_dict(self) -> dict:
        return asdict(self)


class NearMissService:
    @staticmethod
    def build_near_misses(rows: list[dict], notes_by_cik: dict | None = None) -> list[NearMiss]:
        """Pure aggregation: earnings-filtered transactions -> ranked near misses.

        Applies exactly the strong_buy gates (2+ distinct insiders, $100K+,
        $300M-$5B mcap, 30-day window frozen at the latest trade, blocklist),
        then ranks by insider commitment as a share of market cap — the ordering
        that separates a trivial $200K on $4B from $8M on $800M.
        """
        notes_by_cik = notes_by_cik or {}
        by_cik: dict[str, list[dict]] = {}
        for row in rows:
            if row.get("classification") != "FILTERED":
                continue
            if row.get("classification_rule") != FILTER_RULE:
                continue
            cik = _pad(row.get("cik"))
            if cik in EXCLUDED_CIKS:
                continue
            by_cik.setdefault(cik, []).append(row)

        out: list[NearMiss] = []
        for cik, company_rows in by_cik.items():
            near_miss = NearMissService._build_one(cik, company_rows, notes_by_cik.get(cik, []))
            if near_miss:
                out.append(near_miss)

        out.sort(key=lambda n: n.pct_of_mcap, reverse=True)
        return out

    @staticmethod
    def _build_one(cik: str, rows: list[dict], notes: list[dict]) -> NearMiss | None:
        mcap = rows[0].get("market_cap")
        try:
            mcap = float(mcap) if mcap else 0.0
        except (TypeError, ValueError):
            return None
        if not (MIN_MARKET_CAP_USD <= mcap <= MAX_MARKET_CAP_USD):
            return None

        dated = [(dt, r) for r in rows if (dt := _parse(r.get("transaction_date"))) is not None]
        if not dated:
            return None

        # 30-day window measured back from the latest trade, inclusive — the same
        # sliding window detect_clusters() uses, frozen at formation.
        window_end_dt = max(dt for dt, _ in dated)
        window_start_dt = window_end_dt - timedelta(days=CLUSTER_WINDOW_DAYS)
        in_window = [(dt, r) for dt, r in dated if dt >= window_start_dt]

        buyers: dict[str, NearMissBuyer] = {}
        total_value = 0.0
        for dt, row in in_window:
            value = float(row.get("total_value") or 0)
            total_value += value
            name = row.get("insider_name") or ""
            existing = buyers.get(name)
            if existing is None:
                buyers[name] = NearMissBuyer(
                    insider_name=name,
                    insider_title=row.get("insider_title") or "",
                    role=classify_insider_role(row.get("insider_title") or ""),
                    transaction_date=_date_only(row.get("transaction_date")),
                    value=value,
                    form4_url=row.get("form4_url"),
                )
            else:
                existing.value += value
                existing.transaction_date = max(
                    existing.transaction_date, _date_only(row.get("transaction_date"))
                )

        if len(buyers) < MIN_CLUSTER_INSIDERS:
            return None
        if total_value < MIN_CLUSTER_VALUE_USD:
            return None

        first = rows[0]
        ticker = first.get("ticker") or (first.get("tickers") or [""])[0]
        return NearMiss(
            cik=cik,
            ticker=ticker,
            company_name=first.get("company_name") or "",
            window_start=min(dt for dt, _ in in_window).strftime("%Y-%m-%d"),
            window_end=window_end_dt.strftime("%Y-%m-%d"),
            insider_count=len(buyers),
            total_value=total_value,
            market_cap=mcap,
            pct_of_mcap=round(total_value / mcap * 100, 4),
            buyers=sorted(buyers.values(), key=lambda b: b.value, reverse=True),
            research_notes=notes,
            verdict=notes[0].get("verdict") if notes else None,
            filter_reason=first.get("classification_reason"),
        )

    @staticmethod
    async def get_near_misses(since_date: str) -> list[dict]:
        """Live compute: earnings-filtered transactions since `since_date`, ranked."""
        query = """
            MATCH (c:Company)-[:INSIDER_TRADE_OF]->(t:InsiderTransaction)<-[:TRADED_BY]-(p:Person)
            WHERE t.transaction_date >= $since_date
              AND t.transaction_code = 'P'
              AND t.classification = 'FILTERED'
              AND t.classification_rule = $filter_rule
              AND (t.is_derivative IS NULL OR t.is_derivative = false)
              AND c.tickers IS NOT NULL AND size(c.tickers) > 0
              AND NOT c.cik IN $excluded_ciks
            RETURN c.cik as cik,
                   c.name as company_name,
                   head(c.tickers) as ticker,
                   c.market_cap as market_cap,
                   t.transaction_date as transaction_date,
                   t.total_value as total_value,
                   t.shares as shares,
                   p.name as insider_name,
                   t.insider_title as insider_title,
                   t.classification as classification,
                   t.classification_rule as classification_rule,
                   t.classification_reason as classification_reason,
                   t.filing_date as filing_date,
                   t.primary_document as form4_url
            ORDER BY t.transaction_date DESC
        """
        rows = await Neo4jClient.execute_query(
            query,
            {
                "since_date": since_date,
                "filter_rule": FILTER_RULE,
                "excluded_ciks": list(EXCLUDED_CIKS),
            },
        )

        near_misses = NearMissService.build_near_misses(rows or [])
        if not near_misses:
            return []

        notes_by_cik = await ResearchNoteService.get_notes_for_ciks([n.cik for n in near_misses])
        for near_miss in near_misses:
            notes = notes_by_cik.get(near_miss.cik, [])
            near_miss.research_notes = notes
            near_miss.verdict = notes[0].get("verdict") if notes else None

        logger.info("near-miss: %d companies since %s", len(near_misses), since_date)
        return [n.to_dict() for n in near_misses]
