"""SEC EDGAR XBRL company-facts client.

Fetches primary-source shares-outstanding time series from
`data.sec.gov/api/xbrl/companyfacts/CIK{padded}.json`.

Used by v1.4 Phase 9 to ground-truth historical market cap.
"""

import logging
from dataclasses import dataclass
from typing import Optional

import httpx

logger = logging.getLogger(__name__)


# SEC requires an identifying User-Agent on all requests.
# Matches the pattern already used in backend/fetch_form4_index.py.
DEFAULT_USER_AGENT = "LookInsight research@lookinsight.ai"
BASE_URL = "https://data.sec.gov/api/xbrl/companyfacts"
ALLOWED_FORMS = {"10-Q", "10-K", "10-Q/A", "10-K/A"}

# XBRL concepts to try for shares outstanding, in priority order.
# Different filers use different concepts; the first one with usable data wins.
SHARES_OUTSTANDING_CONCEPTS = [
    ("dei", "EntityCommonStockSharesOutstanding"),
    ("us-gaap", "CommonStockSharesOutstanding"),
    ("us-gaap", "CommonStockSharesIssued"),
    # Dual-class filers (e.g., MRVI) and some post-IPO filers don't report
    # point-in-time shares outstanding; they report weighted-average for EPS.
    # This is a close approximation (typically within 1-2% of point-in-time).
    ("us-gaap", "WeightedAverageNumberOfSharesOutstandingBasic"),
    ("us-gaap", "WeightedAverageNumberOfDilutedSharesOutstanding"),
]

# Sanity threshold: reject entries with shares below this count.
# IPO registration statements (S-1s) sometimes tag "100 shares" as a placeholder
# in companyfacts, which my client would otherwise naively pick as the earliest entry.
# No legitimate public company has fewer than 100k shares outstanding.
MIN_REASONABLE_SHARES = 100_000


@dataclass
class SharesOutstandingEntry:
    """One quarterly/annual shares-outstanding data point from SEC XBRL."""

    end_date: str       # "YYYY-MM-DD" — period end
    shares: int
    form: str           # "10-Q" | "10-K" | "10-Q/A" | "10-K/A"
    fiscal_year: int
    fiscal_period: str  # "Q1" | "Q2" | "Q3" | "FY"
    accession: str


class XBRLClient:
    """Async HTTP client for SEC EDGAR XBRL company-facts API."""

    @staticmethod
    async def get_shares_outstanding(
        cik: str, user_agent: str = DEFAULT_USER_AGENT
    ) -> list[SharesOutstandingEntry]:
        """Fetch shares-outstanding time series for a CIK.

        Tries these XBRL concepts in order (different filers use different ones):
          1. dei:EntityCommonStockSharesOutstanding
          2. us-gaap:CommonStockSharesOutstanding
          3. us-gaap:CommonStockSharesIssued  (fallback)

        Args:
            cik: CIK string (will be zero-padded to 10 digits).
            user_agent: User-Agent header (SEC requirement).

        Returns:
            Sorted-ascending list of SharesOutstandingEntry. Empty list if the
            company has no XBRL shares-outstanding facts or the companyfacts
            endpoint returns 404.

        Raises:
            httpx.HTTPStatusError on non-404 HTTP errors.
        """
        padded_cik = str(cik).lstrip("0").zfill(10)
        url = f"{BASE_URL}/CIK{padded_cik}.json"

        headers = {"User-Agent": user_agent, "Accept": "application/json"}

        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.get(url, headers=headers)

        if resp.status_code == 404:
            logger.info(f"XBRL: no companyfacts for CIK {padded_cik}")
            return []
        if resp.status_code != 200:
            snippet = resp.text[:200]
            raise httpx.HTTPStatusError(
                f"XBRL companyfacts HTTP {resp.status_code} for {padded_cik}: {snippet}",
                request=resp.request,
                response=resp,
            )

        data = resp.json()
        facts = data.get("facts", {})

        # Try concepts in priority order. If a concept has raw entries but they
        # all get removed by sanity/form filters, fall through to the next concept
        # rather than returning empty. (Case: FNKO has CommonStockSharesOutstanding
        # with only 2 very old placeholder entries — both filtered out — but has
        # 106 WeightedAverageNumberOfSharesOutstandingBasic entries that are good.)
        for taxonomy, concept in SHARES_OUTSTANDING_CONCEPTS:
            taxonomy_data = facts.get(taxonomy, {})
            concept_data = taxonomy_data.get(concept, {})
            units = concept_data.get("units", {})
            shares_list = units.get("shares", [])
            if not shares_list:
                continue

            entries: dict[tuple, SharesOutstandingEntry] = {}
            for r in shares_list:
                form = r.get("form", "")
                if form not in ALLOWED_FORMS:
                    continue
                end_date = r.get("end")
                val = r.get("val")
                if not end_date or val is None or val <= 0:
                    continue
                if val < MIN_REASONABLE_SHARES:
                    continue

                accn = r.get("accn", "")
                key = (accn, end_date)
                entries[key] = SharesOutstandingEntry(
                    end_date=end_date,
                    shares=int(val),
                    form=form,
                    fiscal_year=int(r.get("fy") or 0),
                    fiscal_period=str(r.get("fp") or ""),
                    accession=accn,
                )

            if entries:
                logger.debug(
                    f"XBRL CIK {padded_cik}: using {taxonomy}:{concept} "
                    f"({len(entries)} usable entries)"
                )
                return sorted(entries.values(), key=lambda e: e.end_date)
            # else: this concept yielded no usable entries after filtering;
            # continue to next fallback concept.

        logger.info(f"XBRL CIK {padded_cik}: no usable shares-outstanding facts found")
        return []

    @staticmethod
    def pick_shares_at_or_before(
        entries: list[SharesOutstandingEntry], signal_date: str
    ) -> Optional[SharesOutstandingEntry]:
        """Return the entry with the largest end_date <= signal_date.

        Args:
            entries: sorted-ascending list from get_shares_outstanding.
            signal_date: "YYYY-MM-DD".

        Returns:
            Latest SharesOutstandingEntry whose end_date is <= signal_date,
            or None if all entries are after signal_date (or list is empty).
        """
        sd = signal_date[:10]
        chosen: Optional[SharesOutstandingEntry] = None
        for e in entries:
            if e.end_date <= sd:
                chosen = e
            else:
                break  # entries are sorted ascending
        return chosen

    @staticmethod
    def pick_nearest_post_signal(
        entries: list[SharesOutstandingEntry],
        signal_date: str,
        max_days: int = 90,
    ) -> Optional[SharesOutstandingEntry]:
        """Fallback: return the EARLIEST entry AFTER signal_date, within max_days.

        Used when no pre-signal entry exists (e.g., late-IPO'd issuers whose
        first 10-Q XBRL filing postdates the signal). Shares outstanding changes
        slowly for most issuers — a quarter-later snapshot is usually within
        a few percent of point-in-time.

        This result should be labeled distinctly from pick_shares_at_or_before
        so downstream consumers can weight or flag it.
        """
        from datetime import datetime, timedelta

        try:
            sd = datetime.strptime(signal_date[:10], "%Y-%m-%d")
        except ValueError:
            return None
        cutoff = (sd + timedelta(days=max_days)).strftime("%Y-%m-%d")
        sd_str = sd.strftime("%Y-%m-%d")

        for e in entries:
            if sd_str < e.end_date <= cutoff:
                return e
        return None
