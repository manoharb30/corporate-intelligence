"""Signal filter — earnings exclusion rule + hostile activist flag.

Earnings rule: Exclude strong_buy signals where next earnings >60 days away.
Hostile flag: Informational tag when activist filing has hostile keywords (not a filter).

Research backing:
  - Earnings: p=0.003 significance (earnings-sector-patterns.md)
  - Hostile activist: 88% of losers-with-activist had hostile keywords vs 33% winners
    Aligned with Brav 2008, Klein & Zur 2009, Greenwood & Schor 2009.
"""

import json
import os
import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

import yfinance as yf


EARNINGS_THRESHOLD_DAYS = 60
_EARNINGS_CACHE_PATH = "/tmp/lookinsight_earnings_cache.json"
_HOSTILE_CACHE_PATH = "/tmp/lookinsight_hostile_cache.json"
_CACHE_FILE_TTL = 24 * 60 * 60  # 24 hours

HOSTILE_KEYWORDS = [
    "proxy", "remove", "replace", "strategic alternative", "inadequate",
    "underperform", "oppose", "withhold", "hostile", "unsolicited",
]


@dataclass
class FilterResult:
    """Result of applying the signal filter."""
    passed: bool
    earnings_distance: Optional[int]
    reason: str


@dataclass
class HostileCheckResult:
    """Result of hostile activist check. Informational only — not a filter."""
    has_hostile: bool
    keywords: list[str] = field(default_factory=list)


def _load_json_cache(path: str) -> dict:
    """Load cache from JSON file if it exists and is <24h old."""
    if not os.path.exists(path):
        return {}
    try:
        if time.time() - os.path.getmtime(path) > _CACHE_FILE_TTL:
            return {}
        with open(path) as f:
            return json.load(f)
    except (ValueError, OSError):
        return {}


def _save_json_cache(path: str, data: dict) -> None:
    """Save cache to JSON file."""
    try:
        with open(path, "w") as f:
            json.dump(data, f)
    except OSError:
        pass


class SignalFilter:
    """Earnings proximity filter + hostile activist flag."""

    _earnings_cache: dict[str, list[str]] = {}
    _hostile_cache: dict[str, HostileCheckResult] = {}
    _caches_loaded: bool = False

    @classmethod
    def _load_persistent_caches(cls):
        """Load caches from disk on first use. Persists across subprocess invocations."""
        if cls._caches_loaded:
            return
        earnings_data = _load_json_cache(_EARNINGS_CACHE_PATH)
        if earnings_data:
            cls._earnings_cache.update(earnings_data)
        hostile_data = _load_json_cache(_HOSTILE_CACHE_PATH)
        if hostile_data:
            cls._hostile_cache.update({
                k: HostileCheckResult(has_hostile=v["has_hostile"], keywords=v["keywords"])
                for k, v in hostile_data.items()
            })
        cls._caches_loaded = True

    @classmethod
    def _save_persistent_caches(cls):
        """Save caches to disk."""
        _save_json_cache(_EARNINGS_CACHE_PATH, cls._earnings_cache)
        hostile_serializable = {
            k: {"has_hostile": v.has_hostile, "keywords": v.keywords}
            for k, v in cls._hostile_cache.items()
        }
        _save_json_cache(_HOSTILE_CACHE_PATH, hostile_serializable)

    @staticmethod
    def apply_filter(ticker: str, signal_date: str) -> FilterResult:
        """Apply earnings proximity rule to a signal.

        Args:
            ticker: Stock ticker symbol
            signal_date: Signal date in YYYY-MM-DD format

        Returns:
            FilterResult with pass/fail, distance, and reason
        """
        try:
            earnings_dates = SignalFilter._get_earnings_dates(ticker)
        except Exception:
            return FilterResult(
                passed=True,
                earnings_distance=None,
                reason="Warning: error fetching earnings data — signal passed by default"
            )

        if not earnings_dates:
            return FilterResult(
                passed=True,
                earnings_distance=None,
                reason="Warning: no earnings data available — signal passed by default"
            )

        sig_dt = datetime.strptime(signal_date, "%Y-%m-%d")
        next_earnings_dist = None

        for d in earnings_dates:
            try:
                e_dt = datetime.strptime(d, "%Y-%m-%d")
                if e_dt >= sig_dt:
                    next_earnings_dist = (e_dt - sig_dt).days
                    break
            except (ValueError, TypeError):
                continue

        if next_earnings_dist is None:
            return FilterResult(
                passed=True,
                earnings_distance=None,
                reason="Warning: no future earnings date found from signal date — signal passed by default"
            )

        if next_earnings_dist <= EARNINGS_THRESHOLD_DAYS:
            return FilterResult(
                passed=True,
                earnings_distance=next_earnings_dist,
                reason=f"Earnings in {next_earnings_dist}d — within {EARNINGS_THRESHOLD_DAYS}d window (mid-quarter conviction)"
            )
        else:
            return FilterResult(
                passed=False,
                earnings_distance=next_earnings_dist,
                reason=f"Earnings in {next_earnings_dist}d — beyond {EARNINGS_THRESHOLD_DAYS}d threshold (post-earnings, no informational edge)"
            )

    @staticmethod
    def _get_earnings_dates(ticker: str) -> list[str]:
        """Get sorted list of historical + future earnings dates. Cached per ticker, persisted to disk."""
        SignalFilter._load_persistent_caches()
        if ticker in SignalFilter._earnings_cache:
            return SignalFilter._earnings_cache[ticker]

        dates = SignalFilter._fetch_earnings_dates(ticker)
        SignalFilter._earnings_cache[ticker] = dates
        SignalFilter._save_persistent_caches()
        return dates

    @staticmethod
    def _fetch_earnings_dates(ticker: str) -> list[str]:
        """Fetch earnings dates from yfinance (limit=20 for historical coverage)."""
        ed = yf.Ticker(ticker).get_earnings_dates(limit=20)
        if ed is not None and len(ed) > 0:
            return sorted([d.strftime("%Y-%m-%d") for d in ed.index])
        return []

    # --- Hostile activist flag (informational, not a filter) ---

    @staticmethod
    def check_hostile_activist(cik: str) -> HostileCheckResult:
        """Check if company has activist filings with hostile keywords.

        Informational only — does NOT affect signal classification.
        88% of losers-with-activist had hostile keywords vs 33% of winners.
        """
        SignalFilter._load_persistent_caches()
        if cik in SignalFilter._hostile_cache:
            return SignalFilter._hostile_cache[cik]

        try:
            purpose_texts = SignalFilter._get_activist_purpose_texts(cik)
        except Exception:
            result = HostileCheckResult(has_hostile=False, keywords=[])
            SignalFilter._hostile_cache[cik] = result
            return result

        matched = []
        for text in purpose_texts:
            text_lower = text.lower()
            for kw in HOSTILE_KEYWORDS:
                if kw in text_lower and kw not in matched:
                    matched.append(kw)

        result = HostileCheckResult(has_hostile=len(matched) > 0, keywords=matched)
        SignalFilter._hostile_cache[cik] = result
        SignalFilter._save_persistent_caches()
        return result

    @staticmethod
    def _get_activist_purpose_texts(cik: str) -> list[str]:
        """Fetch purpose_text from ActivistFiling nodes for a CIK. Override in tests."""
        import asyncio
        from app.db.neo4j_client import Neo4jClient

        async def _fetch():
            await Neo4jClient.connect()
            r = await Neo4jClient.execute_query("""
                MATCH (af:ActivistFiling)
                WHERE af.target_cik = $cik AND af.purpose_text IS NOT NULL AND af.purpose_text <> ''
                RETURN af.purpose_text AS text
            """, {"cik": cik})
            await Neo4jClient.disconnect()
            return [row["text"] for row in r]

        return asyncio.run(_fetch())
