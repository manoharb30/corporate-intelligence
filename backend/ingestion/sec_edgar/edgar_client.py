"""SEC EDGAR API client with rate limiting."""

import asyncio
import logging
import re
import time
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Optional

import httpx

from app.config import settings

logger = logging.getLogger(__name__)


@dataclass
class CompanyInfo:
    """Basic company information from SEC."""

    cik: str
    name: str
    tickers: list[str]
    sic: Optional[str] = None
    sic_description: Optional[str] = None
    state_of_incorporation: Optional[str] = None
    fiscal_year_end: Optional[str] = None


@dataclass
class FilingInfo:
    """Information about a single SEC filing."""

    accession_number: str
    form_type: str
    filing_date: str
    primary_document: str
    primary_doc_description: Optional[str] = None
    file_number: Optional[str] = None
    film_number: Optional[str] = None
    items: list[str] = None

    @property
    def accession_number_formatted(self) -> str:
        """Return accession number with dashes for URL construction."""
        # Remove dashes if present, then format properly
        clean = self.accession_number.replace("-", "")
        return f"{clean[:10]}-{clean[10:12]}-{clean[12:]}"

    @property
    def accession_number_nodash(self) -> str:
        """Return accession number without dashes for directory paths."""
        return self.accession_number.replace("-", "")


class RateLimiter:
    """Simple rate limiter for SEC's 10 requests/second limit."""

    def __init__(self, requests_per_second: int = 10):
        self.requests_per_second = requests_per_second
        self.min_interval = 1.0 / requests_per_second
        self.last_request_time = 0.0
        self._lock = asyncio.Lock()

    async def acquire(self) -> None:
        """Wait if necessary to respect rate limit."""
        async with self._lock:
            now = time.monotonic()
            elapsed = now - self.last_request_time
            if elapsed < self.min_interval:
                await asyncio.sleep(self.min_interval - elapsed)
            self.last_request_time = time.monotonic()


@dataclass
class CompanySearchResult:
    """Company search result from SEC EDGAR."""

    cik: str
    name: str
    ticker: Optional[str] = None
    in_graph: bool = False  # Will be set by the service layer


class SECEdgarClient:
    """Async client for SEC EDGAR API."""

    BASE_URL = "https://data.sec.gov"
    ARCHIVES_URL = "https://www.sec.gov/Archives/edgar/data"
    FULL_TEXT_SEARCH_URL = "https://efts.sec.gov/LATEST/search-index"
    COMPANY_TICKERS_URL = "https://www.sec.gov/files/company_tickers.json"

    # Filing types we're interested in
    OWNERSHIP_FORMS = ["DEF 14A", "DEFA14A", "DEF14A", "SC 13D", "SC 13D/A", "SC 13G", "SC 13G/A"]
    SUBSIDIARY_FORMS = ["10-K", "10-K/A"]
    OFFICER_FORMS = ["DEF 14A", "DEFA14A", "DEF14A"]
    EVENT_FORMS = ["8-K", "8-K/A"]  # Material events
    FORM4_FORMS = ["4", "4/A"]  # Insider trading

    def __init__(self, user_agent: Optional[str] = None):
        self.user_agent = user_agent or settings.SEC_EDGAR_USER_AGENT
        if not self.user_agent or "example" in self.user_agent.lower():
            raise ValueError(
                "SEC requires a valid User-Agent with your name and email. "
                "Set SEC_EDGAR_USER_AGENT in .env"
            )

        self.rate_limiter = RateLimiter(requests_per_second=10)
        self._client: Optional[httpx.AsyncClient] = None

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client."""
        if self._client is None:
            self._client = httpx.AsyncClient(
                headers={
                    "User-Agent": self.user_agent,
                    "Accept-Encoding": "gzip, deflate",
                },
                timeout=30.0,
                follow_redirects=True,
            )
        return self._client

    async def close(self) -> None:
        """Close HTTP client."""
        if self._client:
            await self._client.aclose()
            self._client = None

    async def _request(self, url: str) -> httpx.Response:
        """Make rate-limited request."""
        await self.rate_limiter.acquire()
        client = await self._get_client()

        logger.debug(f"Requesting: {url}")
        response = await client.get(url)
        response.raise_for_status()
        return response

    @staticmethod
    def normalize_cik(cik: str) -> str:
        """Normalize CIK to 10-digit zero-padded format."""
        # Remove any leading zeros and non-digits
        cik_clean = re.sub(r"[^\d]", "", cik)
        return cik_clean.zfill(10)

    async def get_company_info(self, cik: str) -> CompanyInfo:
        """Fetch company information by CIK."""
        cik = self.normalize_cik(cik)
        url = f"{self.BASE_URL}/submissions/CIK{cik}.json"

        response = await self._request(url)
        data = response.json()

        return CompanyInfo(
            cik=cik,
            name=data.get("name", ""),
            tickers=data.get("tickers", []),
            sic=data.get("sic"),
            sic_description=data.get("sicDescription"),
            state_of_incorporation=data.get("stateOfIncorporation"),
            fiscal_year_end=data.get("fiscalYearEnd"),
        )

    async def get_company_filings(
        self,
        cik: str,
        form_types: Optional[list[str]] = None,
        limit: int = 100,
    ) -> list[FilingInfo]:
        """Fetch company filings, optionally filtered by form type."""
        cik = self.normalize_cik(cik)
        url = f"{self.BASE_URL}/submissions/CIK{cik}.json"

        response = await self._request(url)
        data = response.json()

        filings = []
        recent = data.get("filings", {}).get("recent", {})

        if not recent:
            return filings

        # Extract filing data
        accession_numbers = recent.get("accessionNumber", [])
        forms = recent.get("form", [])
        filing_dates = recent.get("filingDate", [])
        primary_documents = recent.get("primaryDocument", [])
        primary_doc_descriptions = recent.get("primaryDocDescription", [])

        # Iterate through all filings, collecting up to `limit` matches
        for i in range(len(accession_numbers)):
            form = forms[i] if i < len(forms) else ""

            # Filter by form type if specified
            if form_types:
                if not any(ft.upper() in form.upper() for ft in form_types):
                    continue

            filings.append(FilingInfo(
                accession_number=accession_numbers[i],
                form_type=form,
                filing_date=filing_dates[i] if i < len(filing_dates) else "",
                primary_document=primary_documents[i] if i < len(primary_documents) else "",
                primary_doc_description=primary_doc_descriptions[i] if i < len(primary_doc_descriptions) else None,
            ))

            # Stop once we have enough matches
            if len(filings) >= limit:
                break

        return filings

    async def get_filing_document(self, cik: str, filing: FilingInfo) -> str:
        """Fetch the primary document content for a filing."""
        cik = self.normalize_cik(cik)
        accession_nodash = filing.accession_number_nodash

        url = f"{self.ARCHIVES_URL}/{cik}/{accession_nodash}/{filing.primary_document}"

        response = await self._request(url)
        return response.text

    async def get_filing_index(self, cik: str, filing: FilingInfo) -> dict:
        """Fetch the filing index to find all documents in a filing."""
        cik = self.normalize_cik(cik)
        accession_nodash = filing.accession_number_nodash

        url = f"{self.ARCHIVES_URL}/{cik}/{accession_nodash}/index.json"

        response = await self._request(url)
        return response.json()

    async def get_exhibit_21(self, cik: str, filing: FilingInfo) -> Optional[str]:
        """Fetch Exhibit 21 (subsidiaries) from a 10-K filing."""
        cik = self.normalize_cik(cik)
        accession_nodash = filing.accession_number_nodash

        # Get filing index to find Exhibit 21
        try:
            index = await self.get_filing_index(cik, filing)
        except httpx.HTTPStatusError:
            logger.warning(f"Could not fetch index for {filing.accession_number}")
            return None

        # Look for Exhibit 21 in the directory
        directory = index.get("directory", {})
        items = directory.get("item", [])

        exhibit_21_doc = None
        for item in items:
            name = item.get("name", "").lower()
            desc = item.get("description", "").lower() if item.get("description") else ""

            # Look for Exhibit 21 patterns
            if "ex21" in name or "ex-21" in name or "exhibit21" in name:
                exhibit_21_doc = item.get("name")
                break
            if "21" in name and ("exhibit" in desc or "subsidiaries" in desc):
                exhibit_21_doc = item.get("name")
                break

        if not exhibit_21_doc:
            logger.debug(f"No Exhibit 21 found in {filing.accession_number}")
            return None

        url = f"{self.ARCHIVES_URL}/{cik}/{accession_nodash}/{exhibit_21_doc}"
        response = await self._request(url)
        return response.text

    async def search_filings(
        self,
        query: str,
        form_types: Optional[list[str]] = None,
        date_from: Optional[str] = None,
        date_to: Optional[str] = None,
        limit: int = 100,
    ) -> list[dict]:
        """Search filings using SEC full-text search (EFTS)."""
        # Note: EFTS has different API structure
        # This is a simplified implementation
        params = {
            "q": query,
            "dateRange": "custom",
            "startdt": date_from or "2020-01-01",
            "enddt": date_to or datetime.now().strftime("%Y-%m-%d"),
        }

        if form_types:
            params["forms"] = ",".join(form_types)

        url = f"{self.FULL_TEXT_SEARCH_URL}?{httpx.QueryParams(params)}"

        try:
            response = await self._request(url)
            data = response.json()
            return data.get("hits", {}).get("hits", [])[:limit]
        except Exception as e:
            logger.warning(f"Full-text search failed: {e}")
            return []

    async def get_recent_8k_filers(self, days_back: int = 3) -> list[dict]:
        """
        Discover companies that filed 8-Ks recently using SEC EFTS.

        Uses a date range query and paginates through all results.

        Returns: [{"cik": "0001234567", "name": "COMPANY NAME"}, ...]
        """
        seen_ciks = {}  # cik -> name
        today = datetime.now()
        start_date = (today - timedelta(days=days_back)).strftime("%Y-%m-%d")
        end_date = today.strftime("%Y-%m-%d")

        from_idx = 0
        while True:
            params = {
                "forms": "8-K",
                "dateRange": "custom",
                "startdt": start_date,
                "enddt": end_date,
                "from": str(from_idx),
            }

            url = f"{self.FULL_TEXT_SEARCH_URL}?{httpx.QueryParams(params)}"

            try:
                response = await self._request(url)
                data = response.json()

                hits = data.get("hits", {}).get("hits", [])
                if not hits:
                    break

                for hit in hits:
                    source = hit.get("_source", {})
                    ciks = source.get("ciks", [])
                    display_names = source.get("display_names", [])

                    for i, cik in enumerate(ciks):
                        if cik not in seen_ciks:
                            name = ""
                            if i < len(display_names):
                                raw = display_names[i]
                                name = re.sub(r"\s*\(CIK[^)]*\)", "", raw)
                                name = re.sub(r"\s*\([A-Z0-9,\s]+\)\s*$", "", name).strip()
                            seen_ciks[cik] = name or f"CIK {cik}"

                if len(hits) >= 100:
                    from_idx += 100
                else:
                    break

            except Exception as e:
                logger.warning(f"EFTS search failed: {e}")
                break

        logger.info(f"EFTS discovery: found {len(seen_ciks)} unique 8-K filers in last {days_back} days")
        return [{"cik": cik, "name": name} for cik, name in seen_ciks.items()]

    async def get_ownership_filings(self, cik: str, limit: int = 20) -> list[FilingInfo]:
        """Get recent ownership-related filings for a company."""
        return await self.get_company_filings(
            cik=cik,
            form_types=self.OWNERSHIP_FORMS,
            limit=limit,
        )

    async def get_10k_filings(self, cik: str, limit: int = 5) -> list[FilingInfo]:
        """Get recent 10-K filings for a company."""
        return await self.get_company_filings(
            cik=cik,
            form_types=self.SUBSIDIARY_FORMS,
            limit=limit,
        )

    async def get_def14a_filings(self, cik: str, limit: int = 5) -> list[FilingInfo]:
        """Get recent DEF 14A (proxy) filings for a company."""
        return await self.get_company_filings(
            cik=cik,
            form_types=self.OFFICER_FORMS,
            limit=limit,
        )

    async def get_8k_filings(self, cik: str, limit: int = 20) -> list[FilingInfo]:
        """Get recent 8-K (material event) filings for a company."""
        return await self.get_company_filings(
            cik=cik,
            form_types=self.EVENT_FORMS,
            limit=limit,
        )

    async def get_form4_filings(self, cik: str, limit: int = 50) -> list[FilingInfo]:
        """Get recent Form 4 (insider trading) filings for a company."""
        return await self.get_company_filings(
            cik=cik,
            form_types=self.FORM4_FORMS,
            limit=limit,
        )

    async def get_form4_xml(self, cik: str, filing: FilingInfo) -> Optional[str]:
        """
        Fetch the raw XML content of a Form 4 filing.

        The primary document for Form 4s is often an XSLT-transformed HTML
        (e.g. xslF345X05/form4.xml). The actual raw XML is a separate file
        in the filing index. This method finds and fetches that raw XML.
        """
        cik = self.normalize_cik(cik)
        accession_nodash = filing.accession_number_nodash

        # Try to find the raw XML by looking at the filing index
        try:
            index = await self.get_filing_index(cik, filing)
            items = index.get("directory", {}).get("item", [])

            for item in items:
                name = item.get("name", "")
                # Look for .xml files that aren't index files
                if name.endswith(".xml") and "index" not in name.lower():
                    url = f"{self.ARCHIVES_URL}/{cik}/{accession_nodash}/{name}"
                    response = await self._request(url)
                    return response.text
        except Exception as e:
            logger.warning(f"Could not fetch Form 4 XML for {filing.accession_number}: {e}")

        return None

    async def search_companies(self, query: str, limit: int = 20) -> list[CompanySearchResult]:
        """
        Search for companies by name or ticker.

        Uses SEC's company_tickers.json which contains all SEC-registered companies.
        Performs fuzzy matching on company name and exact matching on ticker.
        """
        query_lower = query.lower().strip()
        if not query_lower:
            return []

        try:
            response = await self._request(self.COMPANY_TICKERS_URL)
            data = response.json()
        except Exception as e:
            logger.error(f"Failed to fetch company tickers: {e}")
            return []

        results = []

        # Score and collect matching companies
        scored_results = []
        for entry in data.values():
            cik = str(entry.get("cik_str", ""))
            name = entry.get("title", "")
            ticker = entry.get("ticker", "")

            name_lower = name.lower()
            ticker_lower = ticker.lower() if ticker else ""

            score = 0

            # Exact ticker match - highest priority
            if ticker_lower == query_lower:
                score = 1000
            # Ticker starts with query
            elif ticker_lower.startswith(query_lower):
                score = 500
            # Exact name match
            elif name_lower == query_lower:
                score = 400
            # Name starts with query
            elif name_lower.startswith(query_lower):
                score = 300
            # Query words at start of name words
            elif any(word.startswith(query_lower) for word in name_lower.split()):
                score = 200
            # Query contained in name
            elif query_lower in name_lower:
                score = 100
            # Query contained in ticker
            elif query_lower in ticker_lower:
                score = 50

            if score > 0:
                scored_results.append((score, CompanySearchResult(
                    cik=self.normalize_cik(cik),
                    name=name,
                    ticker=ticker if ticker else None,
                )))

        # Sort by score descending, then by name
        scored_results.sort(key=lambda x: (-x[0], x[1].name))

        # Return top results
        return [r[1] for r in scored_results[:limit]]
