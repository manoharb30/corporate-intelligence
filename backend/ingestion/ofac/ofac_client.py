"""OFAC SDN List download client with caching."""

import hashlib
import logging
from datetime import date, datetime
from pathlib import Path
from typing import Optional

import httpx

logger = logging.getLogger(__name__)


class OFACClient:
    """Client for downloading OFAC SDN list with local caching."""

    # Primary URL (redirects to S3)
    SDN_XML_URL = "https://www.treasury.gov/ofac/downloads/sdn.xml"
    SDN_CSV_URL = "https://www.treasury.gov/ofac/downloads/sdn.csv"

    # Cache directory
    DEFAULT_CACHE_DIR = Path("data/ofac_cache")

    def __init__(self, cache_dir: Optional[Path] = None):
        self.cache_dir = cache_dir or self.DEFAULT_CACHE_DIR
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self._client: Optional[httpx.AsyncClient] = None

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client."""
        if self._client is None:
            self._client = httpx.AsyncClient(
                timeout=120.0,  # Large file, allow longer timeout
                follow_redirects=True,
                headers={
                    "User-Agent": "CorporateIntelligenceGraph/1.0 (Sanctions Compliance)",
                    "Accept": "application/xml, text/xml, */*",
                },
            )
        return self._client

    async def close(self) -> None:
        """Close HTTP client."""
        if self._client:
            await self._client.aclose()
            self._client = None

    def _get_cache_path(self, date_stamp: date) -> Path:
        """Get cache file path for a specific date."""
        return self.cache_dir / f"sdn_{date_stamp.isoformat()}.xml"

    def _get_latest_cache(self) -> Optional[Path]:
        """Find the most recent cached file."""
        xml_files = list(self.cache_dir.glob("sdn_*.xml"))
        if not xml_files:
            return None
        # Sort by filename (date) descending
        xml_files.sort(reverse=True)
        return xml_files[0]

    def get_cache_date(self, cache_path: Path) -> Optional[date]:
        """Extract date from cache filename."""
        try:
            # Filename format: sdn_YYYY-MM-DD.xml
            date_str = cache_path.stem.replace("sdn_", "")
            return date.fromisoformat(date_str)
        except (ValueError, AttributeError):
            return None

    async def download_sdn_xml(
        self,
        force_refresh: bool = False,
    ) -> tuple[str, date]:
        """
        Download SDN XML list, using cache if available and recent.

        Args:
            force_refresh: If True, always download fresh copy

        Returns:
            Tuple of (xml_content, download_date)
        """
        today = date.today()

        # Check cache first (unless force refresh)
        if not force_refresh:
            latest_cache = self._get_latest_cache()
            if latest_cache and latest_cache.exists():
                cache_date = self.get_cache_date(latest_cache)
                if cache_date and (today - cache_date).days < 7:
                    logger.info(f"Using cached SDN list from {cache_date}")
                    content = latest_cache.read_text(encoding="utf-8")
                    return content, cache_date

        # Download fresh copy
        logger.info(f"Downloading SDN list from {self.SDN_XML_URL}")
        client = await self._get_client()

        try:
            response = await client.get(self.SDN_XML_URL)
            response.raise_for_status()
            content = response.text

            # Save to cache
            cache_path = self._get_cache_path(today)
            cache_path.write_text(content, encoding="utf-8")
            logger.info(f"Cached SDN list to {cache_path}")

            return content, today

        except httpx.HTTPError as e:
            logger.error(f"Failed to download SDN list: {e}")
            # Fall back to cache if available
            latest_cache = self._get_latest_cache()
            if latest_cache and latest_cache.exists():
                logger.warning(f"Using stale cache from {latest_cache}")
                content = latest_cache.read_text(encoding="utf-8")
                cache_date = self.get_cache_date(latest_cache) or today
                return content, cache_date
            raise

    async def download_sdn_csv(self) -> tuple[str, date]:
        """
        Download SDN CSV list (alternative format).

        Returns:
            Tuple of (csv_content, download_date)
        """
        logger.info(f"Downloading SDN CSV from {self.SDN_CSV_URL}")
        client = await self._get_client()

        response = await client.get(self.SDN_CSV_URL)
        response.raise_for_status()

        return response.text, date.today()

    def compute_content_hash(self, content: str) -> str:
        """Compute SHA-256 hash of content for change detection."""
        return hashlib.sha256(content.encode("utf-8")).hexdigest()

    async def check_for_updates(self) -> bool:
        """
        Check if SDN list has been updated since last download.

        Returns:
            True if update is available, False otherwise
        """
        latest_cache = self._get_latest_cache()
        if not latest_cache or not latest_cache.exists():
            return True

        # Download fresh and compare hashes
        try:
            new_content, _ = await self.download_sdn_xml(force_refresh=True)
            new_hash = self.compute_content_hash(new_content)

            old_content = latest_cache.read_text(encoding="utf-8")
            old_hash = self.compute_content_hash(old_content)

            return new_hash != old_hash
        except Exception as e:
            logger.warning(f"Could not check for updates: {e}")
            return False

    def get_cache_info(self) -> dict:
        """Get information about cached files."""
        xml_files = list(self.cache_dir.glob("sdn_*.xml"))
        return {
            "cache_dir": str(self.cache_dir),
            "cached_files": len(xml_files),
            "latest_cache": str(self._get_latest_cache()) if xml_files else None,
            "latest_date": str(self.get_cache_date(self._get_latest_cache()))
            if xml_files
            else None,
        }
