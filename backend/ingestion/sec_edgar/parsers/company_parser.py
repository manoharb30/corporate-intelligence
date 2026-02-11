"""Parser for subsidiary information from 10-K Exhibit 21."""

import logging
import re
from typing import Optional

from bs4 import BeautifulSoup, Tag

from app.models.extraction_models import (
    ExtractionMethod,
    ExtractionMetadata,
    SubsidiaryRecord,
    SubsidiaryExtractionResult,
)
from ingestion.sec_edgar.llm_extractor import LLMExtractor
from ingestion.sec_edgar.review_queue import ReviewQueue

logger = logging.getLogger(__name__)

RULE_BASED_CONFIDENCE = 0.95
LLM_CONFIDENCE_THRESHOLD = 0.9
MAX_SNIPPET_LENGTH = 300


class SubsidiaryParser:
    """Parse subsidiary data from 10-K Exhibit 21."""

    # Common jurisdiction abbreviations and names
    JURISDICTIONS = {
        # US States
        "de": "Delaware", "delaware": "Delaware",
        "ca": "California", "california": "California",
        "ny": "New York", "new york": "New York",
        "tx": "Texas", "texas": "Texas",
        "nv": "Nevada", "nevada": "Nevada",
        "fl": "Florida", "florida": "Florida",
        "wa": "Washington", "washington": "Washington",
        "il": "Illinois", "illinois": "Illinois",
        "ma": "Massachusetts", "massachusetts": "Massachusetts",
        "pa": "Pennsylvania", "pennsylvania": "Pennsylvania",
        "oh": "Ohio", "ohio": "Ohio",
        "ga": "Georgia", "georgia": "Georgia",
        "nc": "North Carolina", "north carolina": "North Carolina",
        "nj": "New Jersey", "new jersey": "New Jersey",
        "va": "Virginia", "virginia": "Virginia",
        "md": "Maryland", "maryland": "Maryland",
        "co": "Colorado", "colorado": "Colorado",
        "az": "Arizona", "arizona": "Arizona",
        # International
        "ireland": "Ireland",
        "uk": "United Kingdom", "united kingdom": "United Kingdom", "england": "United Kingdom",
        "cayman": "Cayman Islands", "cayman islands": "Cayman Islands",
        "bermuda": "Bermuda",
        "netherlands": "Netherlands", "holland": "Netherlands",
        "luxembourg": "Luxembourg",
        "singapore": "Singapore",
        "hong kong": "Hong Kong",
        "japan": "Japan",
        "germany": "Germany",
        "france": "France",
        "canada": "Canada",
        "australia": "Australia",
        "switzerland": "Switzerland",
        "india": "India",
        "china": "China", "prc": "China",
        "brazil": "Brazil",
        "mexico": "Mexico",
        "israel": "Israel",
        "bvi": "British Virgin Islands", "british virgin islands": "British Virgin Islands",
    }

    def __init__(
        self,
        llm_extractor: Optional[LLMExtractor] = None,
        review_queue: Optional[ReviewQueue] = None,
    ):
        self.llm_extractor = llm_extractor or LLMExtractor()
        self.review_queue = review_queue or ReviewQueue()

    def extract_subsidiaries(
        self,
        exhibit_html: str,
        filing_accession: str,
        company_cik: str,
        company_name: Optional[str] = None,
    ) -> SubsidiaryExtractionResult:
        """
        Extract subsidiary data from 10-K Exhibit 21.

        Tries rule-based extraction first, falls back to LLM if needed.
        """
        warnings = []
        records = []

        # Try rule-based extraction first
        rule_based_records = self._parse_subsidiaries_rulebased(exhibit_html)

        if rule_based_records:
            logger.info(
                f"Rule-based extraction found {len(rule_based_records)} subsidiaries "
                f"from {filing_accession}"
            )
            records = rule_based_records
            method = ExtractionMethod.RULE_BASED
            confidence = RULE_BASED_CONFIDENCE
        else:
            # Fallback to LLM extraction
            logger.info(f"Rule-based extraction failed, trying LLM for {filing_accession}")
            llm_records = self._llm_extract_subsidiaries(exhibit_html)

            if llm_records:
                records = llm_records
                method = ExtractionMethod.LLM
                confidences = [r.confidence for r in llm_records if r.confidence]
                confidence = sum(confidences) / len(confidences) if confidences else 0.8
                warnings.append("Used LLM extraction (rule-based failed)")
            else:
                logger.warning(f"Both extraction methods failed for {filing_accession}")
                method = ExtractionMethod.RULE_BASED
                confidence = 0.0
                warnings.append("Extraction failed - added to review queue")

                self.review_queue.add_failed_extraction(
                    filing_accession=filing_accession,
                    filing_type="10-K",
                    company_cik=company_cik,
                    company_name=company_name,
                    extraction_type="subsidiary",
                    raw_text=exhibit_html[:50000],
                    failure_reason="Both rule-based and LLM extraction failed",
                )

        # Check confidence threshold
        if records and confidence < LLM_CONFIDENCE_THRESHOLD:
            self.review_queue.add_low_confidence(
                filing_accession=filing_accession,
                filing_type="10-K",
                company_cik=company_cik,
                company_name=company_name,
                extraction_type="subsidiary",
                raw_text=exhibit_html[:50000],
                confidence=confidence,
                attempted_extraction={"records": [r.model_dump() for r in records]},
            )
            warnings.append(f"Low confidence ({confidence:.2f}) - added to review queue")

        return SubsidiaryExtractionResult(
            records=records,
            filing_accession=filing_accession,
            company_cik=company_cik,
            company_name=company_name,
            extraction_metadata=ExtractionMetadata(
                method=method,
                confidence=confidence,
                source_filing_id=filing_accession,
            ),
            warnings=warnings,
        )

    def _parse_subsidiaries_rulebased(self, html: str) -> list[SubsidiaryRecord]:
        """Parse subsidiary tables/lists using BeautifulSoup."""
        soup = BeautifulSoup(html, "lxml")
        records = []

        # Try table-based extraction first
        table_records = self._parse_subsidiary_table(soup)
        if table_records:
            return table_records

        # Try text-based extraction (for simple lists)
        text_records = self._parse_subsidiary_text(soup)
        if text_records:
            return text_records

        return records

    def _parse_subsidiary_table(self, soup: BeautifulSoup) -> list[SubsidiaryRecord]:
        """Parse subsidiaries from HTML tables."""
        records = []

        for table in soup.find_all("table"):
            rows = table.find_all("tr")
            if len(rows) < 2:
                continue

            # Try to identify columns
            header_row = rows[0]
            cells = header_row.find_all(["th", "td"])
            headers = [c.get_text().strip().lower() for c in cells]

            name_col = None
            jurisdiction_col = None
            ownership_col = None

            for i, header in enumerate(headers):
                if any(w in header for w in ["name", "subsidiary", "company", "entity"]):
                    name_col = i
                if any(w in header for w in ["state", "jurisdiction", "incorporated", "country", "organization"]):
                    jurisdiction_col = i
                if any(w in header for w in ["ownership", "percent", "owned", "%"]):
                    ownership_col = i

            # If no clear headers, assume first col is name, second is jurisdiction
            if name_col is None:
                if len(cells) >= 2:
                    name_col = 0
                    jurisdiction_col = 1 if len(cells) > 1 else None
                else:
                    continue

            # Try to find table name from preceding text
            table_name = self._find_table_name(table)

            # Parse data rows
            for row in rows[1:]:
                cells = row.find_all(["th", "td"])
                if len(cells) <= name_col:
                    continue

                name = self._clean_text(cells[name_col].get_text())
                if not name or len(name) < 3:
                    continue

                # Skip header-like text
                if name.lower() in ["name", "subsidiary", "company", "entity"]:
                    continue

                jurisdiction = None
                if jurisdiction_col is not None and jurisdiction_col < len(cells):
                    jurisdiction = self._normalize_jurisdiction(
                        cells[jurisdiction_col].get_text()
                    )

                ownership = None
                is_wholly_owned = False
                if ownership_col is not None and ownership_col < len(cells):
                    ownership_text = cells[ownership_col].get_text().lower()
                    ownership = self._parse_ownership_percentage(ownership_text)
                    is_wholly_owned = ownership == 100.0 or "wholly" in ownership_text

                # Capture raw text from the row for citation
                row_text = " | ".join(c.get_text().strip() for c in cells if c.get_text().strip())
                raw_text_snippet = row_text[:MAX_SNIPPET_LENGTH] if row_text else None

                records.append(SubsidiaryRecord(
                    name=name,
                    jurisdiction=jurisdiction,
                    ownership_percentage=ownership,
                    is_wholly_owned=is_wholly_owned,
                    extraction_method=ExtractionMethod.RULE_BASED,
                    confidence=RULE_BASED_CONFIDENCE,
                    raw_text=raw_text_snippet,
                    source_section="Exhibit 21 - Subsidiaries",
                    source_table=table_name,
                ))

        return records

    def _find_table_name(self, table: Tag) -> Optional[str]:
        """Find the name/caption of a table."""
        # Check for caption
        caption = table.find("caption")
        if caption:
            return self._clean_text(caption.get_text())[:100]

        # Look for preceding heading
        for prev in table.find_all_previous(["h1", "h2", "h3", "h4", "p", "b", "strong"]):
            text = self._clean_text(prev.get_text())
            if text and len(text) > 5 and len(text) < 200:
                if any(w in text.lower() for w in ["subsidiary", "exhibit 21", "significant", "list"]):
                    return text[:100]
            break  # Only check immediate predecessor

        return None

    def _parse_subsidiary_text(self, soup: BeautifulSoup) -> list[SubsidiaryRecord]:
        """Parse subsidiaries from plain text lists."""
        records = []

        # Get all text
        text = soup.get_text()

        # Common patterns:
        # "Company Name (Delaware)"
        # "Company Name, a Delaware corporation"
        # "Company Name - Delaware"

        # Pattern 1: Name (Jurisdiction)
        pattern1 = re.compile(
            r"([A-Z][A-Za-z0-9\s,.'&-]+?)\s*\(([A-Za-z\s]+)\)",
            re.MULTILINE
        )

        for match in pattern1.finditer(text):
            name = self._clean_text(match.group(1))
            jurisdiction_raw = match.group(2).strip()
            jurisdiction = self._normalize_jurisdiction(jurisdiction_raw)

            if name and len(name) >= 3 and jurisdiction:
                # Capture surrounding context for raw_text
                start = max(0, match.start() - 20)
                end = min(len(text), match.end() + 20)
                raw_text_snippet = text[start:end].strip()[:MAX_SNIPPET_LENGTH]

                records.append(SubsidiaryRecord(
                    name=name,
                    jurisdiction=jurisdiction,
                    extraction_method=ExtractionMethod.RULE_BASED,
                    confidence=0.85,  # Lower confidence for text extraction
                    raw_text=raw_text_snippet,
                    source_section="Exhibit 21 - Subsidiaries",
                ))

        # Pattern 2: Name, a [State] corporation
        pattern2 = re.compile(
            r"([A-Z][A-Za-z0-9\s,.'&-]+?),?\s+a\s+([A-Za-z\s]+)\s+(?:corporation|company|llc|limited)",
            re.IGNORECASE | re.MULTILINE
        )

        for match in pattern2.finditer(text):
            name = self._clean_text(match.group(1))
            jurisdiction = self._normalize_jurisdiction(match.group(2))

            if name and len(name) >= 3 and jurisdiction:
                # Check if we already have this name
                if not any(r.name.lower() == name.lower() for r in records):
                    # Capture surrounding context for raw_text
                    start = max(0, match.start() - 20)
                    end = min(len(text), match.end() + 20)
                    raw_text_snippet = text[start:end].strip()[:MAX_SNIPPET_LENGTH]

                    records.append(SubsidiaryRecord(
                        name=name,
                        jurisdiction=jurisdiction,
                        extraction_method=ExtractionMethod.RULE_BASED,
                        confidence=0.80,
                        raw_text=raw_text_snippet,
                        source_section="Exhibit 21 - Subsidiaries",
                    ))

        return records

    def _llm_extract_subsidiaries(self, html: str) -> list[SubsidiaryRecord]:
        """Use LLM to extract subsidiary data when rule-based fails."""
        if not self.llm_extractor.client:
            return []

        # Clean HTML to reduce token usage
        soup = BeautifulSoup(html, "lxml")
        text = soup.get_text()[:30000]

        subsidiaries_data = self.llm_extractor.extract_subsidiaries(text)

        if not subsidiaries_data:
            return []

        records = []
        for sub in subsidiaries_data:
            try:
                jurisdiction = self._normalize_jurisdiction(sub.get("jurisdiction", ""))
                raw_text = sub.get("source_text", sub.get("raw_text"))
                if raw_text:
                    raw_text = raw_text[:MAX_SNIPPET_LENGTH]

                records.append(SubsidiaryRecord(
                    name=sub.get("name", ""),
                    jurisdiction=jurisdiction,
                    ownership_percentage=sub.get("ownership_percentage"),
                    is_wholly_owned=sub.get("is_wholly_owned", False),
                    extraction_method=ExtractionMethod.LLM,
                    confidence=sub.get("confidence", 0.85),
                    raw_text=raw_text,
                    source_section="Exhibit 21 - Subsidiaries",
                ))
            except Exception as e:
                logger.warning(f"Failed to parse LLM subsidiary record: {e}")

        return records

    def _normalize_jurisdiction(self, raw: str) -> Optional[str]:
        """Normalize jurisdiction string."""
        if not raw:
            return None

        # Clean the string
        raw = raw.strip().lower()
        raw = re.sub(r"[^a-z\s]", "", raw)
        raw = raw.strip()

        if not raw:
            return None

        # Look up in known jurisdictions
        if raw in self.JURISDICTIONS:
            return self.JURISDICTIONS[raw]

        # Try partial match
        for key, value in self.JURISDICTIONS.items():
            if key in raw or raw in key:
                return value

        # Return capitalized if no match found
        return raw.title()

    @staticmethod
    def _clean_text(text: str) -> str:
        """Clean extracted text."""
        text = re.sub(r"\s+", " ", text)
        text = re.sub(r"\(\d+\)", "", text)  # Remove footnotes
        text = re.sub(r"\*+", "", text)  # Remove asterisks
        return text.strip()

    @staticmethod
    def _parse_ownership_percentage(text: str) -> Optional[float]:
        """Parse ownership percentage from text."""
        if not text:
            return None

        text = text.lower().strip()

        # Check for wholly owned indicators
        if any(w in text for w in ["wholly", "100%", "100 %"]):
            return 100.0

        # Extract percentage
        match = re.search(r"([\d.]+)\s*%?", text)
        if match:
            try:
                value = float(match.group(1))
                if 0 <= value <= 100:
                    return value
            except ValueError:
                pass

        return None
