"""Parser for beneficial ownership data from SEC filings."""

import logging
import re
from datetime import date, datetime
from typing import Optional

from bs4 import BeautifulSoup, Tag

from app.models.extraction_models import (
    ExtractionMethod,
    ExtractionMetadata,
    OwnershipRecord,
    OwnershipExtractionResult,
)
from ingestion.sec_edgar.llm_extractor import LLMExtractor
from ingestion.sec_edgar.review_queue import ReviewQueue

logger = logging.getLogger(__name__)

# Confidence thresholds
RULE_BASED_CONFIDENCE = 0.95
LLM_CONFIDENCE_THRESHOLD = 0.9

# Maximum length for raw text snippets
MAX_SNIPPET_LENGTH = 300


class OwnershipParser:
    """Parse beneficial ownership data from DEF 14A, 13D, and 13G filings."""

    # Common table header patterns for ownership tables
    OWNERSHIP_TABLE_HEADERS = [
        r"beneficial\s*own",
        r"shares\s*(of\s*common\s*stock)?\s*beneficially\s*owned",
        r"security\s*ownership",
        r"principal\s*(stock)?holders",
        r"percent\s*(of\s*)?(class|outstanding)",
    ]

    # Column header patterns
    NAME_HEADERS = [r"name", r"beneficial\s*owner", r"holder", r"stockholder", r"shareholder"]
    SHARES_HEADERS = [r"shares", r"number\s*of\s*shares", r"amount", r"shares\s*owned"]
    PERCENT_HEADERS = [r"percent", r"%", r"percentage", r"percent\s*(of\s*class)?"]

    def __init__(
        self,
        llm_extractor: Optional[LLMExtractor] = None,
        review_queue: Optional[ReviewQueue] = None,
    ):
        self.llm_extractor = llm_extractor or LLMExtractor()
        self.review_queue = review_queue or ReviewQueue()

    def extract_ownership(
        self,
        filing_html: str,
        filing_accession: str,
        filing_type: str,
        company_cik: str,
        company_name: Optional[str] = None,
        filing_date: Optional[date] = None,
        filing_url: Optional[str] = None,
    ) -> OwnershipExtractionResult:
        """
        Extract beneficial ownership data from a filing.

        Tries rule-based extraction first, falls back to LLM if needed.
        """
        warnings = []
        records = []

        # Build filing URL if not provided
        if not filing_url:
            clean_accession = filing_accession.replace("-", "")
            filing_url = (
                f"https://www.sec.gov/Archives/edgar/data/"
                f"{company_cik.lstrip('0')}/{clean_accession}/"
            )

        # Try rule-based extraction first
        rule_based_records = self._parse_ownership_table_rulebased(filing_html)

        if rule_based_records:
            logger.info(
                f"Rule-based extraction found {len(rule_based_records)} owners "
                f"from {filing_accession}"
            )
            records = rule_based_records
            method = ExtractionMethod.RULE_BASED
            confidence = RULE_BASED_CONFIDENCE
        else:
            # Fallback to LLM extraction
            logger.info(f"Rule-based extraction failed, trying LLM for {filing_accession}")
            llm_records = self._llm_extract_ownership(filing_html)

            if llm_records:
                records = llm_records
                method = ExtractionMethod.LLM
                # Get average confidence from LLM records
                confidences = [r.confidence for r in llm_records if r.confidence]
                confidence = sum(confidences) / len(confidences) if confidences else 0.8
                warnings.append("Used LLM extraction (rule-based failed)")
            else:
                # Both methods failed - add to review queue
                logger.warning(f"Both extraction methods failed for {filing_accession}")
                method = ExtractionMethod.RULE_BASED
                confidence = 0.0
                warnings.append("Extraction failed - added to review queue")

                self.review_queue.add_failed_extraction(
                    filing_accession=filing_accession,
                    filing_type=filing_type,
                    company_cik=company_cik,
                    company_name=company_name,
                    extraction_type="ownership",
                    raw_text=filing_html[:50000],
                    failure_reason="Both rule-based and LLM extraction failed",
                )

        # Check if confidence is below threshold - add to review queue
        if records and confidence < LLM_CONFIDENCE_THRESHOLD:
            self.review_queue.add_low_confidence(
                filing_accession=filing_accession,
                filing_type=filing_type,
                company_cik=company_cik,
                company_name=company_name,
                extraction_type="ownership",
                raw_text=filing_html[:50000],
                confidence=confidence,
                attempted_extraction={"records": [r.model_dump() for r in records]},
            )
            warnings.append(f"Low confidence ({confidence:.2f}) - added to review queue")

        return OwnershipExtractionResult(
            records=records,
            filing_accession=filing_accession,
            filing_type=filing_type,
            company_cik=company_cik,
            company_name=company_name,
            extraction_metadata=ExtractionMetadata(
                method=method,
                confidence=confidence,
                source_filing_id=filing_accession,
                source_url=filing_url,
            ),
            warnings=warnings,
            filing_date=filing_date,
            filing_url=filing_url,
        )

    def _parse_ownership_table_rulebased(
        self, html: str
    ) -> list[OwnershipRecord]:
        """
        Parse ownership tables using BeautifulSoup and regex.

        Looks for common beneficial ownership table patterns in SEC filings.
        """
        soup = BeautifulSoup(html, "lxml")
        records = []

        # Find potential ownership tables
        tables = self._find_ownership_tables(soup)

        for table, section_name in tables:
            table_records = self._parse_single_table(table, section_name)
            records.extend(table_records)

        # Deduplicate by owner name
        seen_names = set()
        unique_records = []
        for record in records:
            name_key = record.owner_name.lower().strip()
            if name_key not in seen_names:
                seen_names.add(name_key)
                unique_records.append(record)

        return unique_records

    def _find_ownership_tables(self, soup: BeautifulSoup) -> list[tuple[Tag, Optional[str]]]:
        """Find tables that likely contain beneficial ownership data.

        Returns list of (table, section_name) tuples.
        """
        tables = []

        for table in soup.find_all("table"):
            # Check if table or surrounding text mentions ownership
            table_text = table.get_text().lower()
            preceding_text = ""
            section_name = None

            # Get text from preceding siblings/parents
            prev = table.find_previous(["p", "div", "h1", "h2", "h3", "h4", "span"])
            if prev:
                preceding_text = prev.get_text().lower()
                section_name = prev.get_text().strip()[:100]

            combined_text = preceding_text + " " + table_text[:500]

            # Check for ownership-related patterns
            for pattern in self.OWNERSHIP_TABLE_HEADERS:
                if re.search(pattern, combined_text, re.IGNORECASE):
                    tables.append((table, section_name))
                    break

        return tables

    def _parse_single_table(
        self, table: Tag, section_name: Optional[str] = None
    ) -> list[OwnershipRecord]:
        """Parse a single HTML table for ownership data."""
        records = []

        # Try to get table caption or title for citation
        table_name = None
        caption = table.find("caption")
        if caption:
            table_name = caption.get_text().strip()[:100]

        # Extract rows
        rows = table.find_all("tr")
        if len(rows) < 2:
            return records

        # Find header row and column indices
        header_row = None
        name_col = None
        shares_col = None
        percent_col = None

        for i, row in enumerate(rows[:5]):  # Check first 5 rows for headers
            cells = row.find_all(["th", "td"])
            cell_texts = [c.get_text().strip().lower() for c in cells]

            # Look for header patterns
            for j, text in enumerate(cell_texts):
                if any(re.search(p, text) for p in self.NAME_HEADERS):
                    name_col = j
                    header_row = i
                if any(re.search(p, text) for p in self.SHARES_HEADERS):
                    shares_col = j
                if any(re.search(p, text) for p in self.PERCENT_HEADERS):
                    percent_col = j

            if name_col is not None:
                break

        if name_col is None:
            return records

        # Parse data rows
        for row in rows[header_row + 1 if header_row else 1:]:
            cells = row.find_all(["th", "td"])
            if len(cells) <= name_col:
                continue

            # Extract owner name
            name_cell = cells[name_col]
            owner_name = self._clean_text(name_cell.get_text())

            if not owner_name or len(owner_name) < 2:
                continue

            # Skip header-like rows and garbage text
            if not self._is_valid_name(owner_name):
                continue

            # Capture raw text for citation
            row_text = row.get_text().strip()
            raw_text_snippet = row_text[:MAX_SNIPPET_LENGTH] if row_text else None

            # Extract shares
            shares = None
            if shares_col is not None and shares_col < len(cells):
                shares_text = cells[shares_col].get_text()
                shares = self._parse_number(shares_text)

            # Extract percentage
            percentage = None
            if percent_col is not None and percent_col < len(cells):
                percent_text = cells[percent_col].get_text()
                percentage = self._parse_percentage(percent_text)

            # Determine owner type (heuristic)
            owner_type = self._guess_owner_type(owner_name)

            # Skip if we have neither shares nor percentage
            if shares is None and percentage is None:
                continue

            records.append(OwnershipRecord(
                owner_name=owner_name,
                owner_type=owner_type,
                shares_owned=shares,
                percentage=percentage,
                is_beneficial=True,
                is_direct=True,
                extraction_method=ExtractionMethod.RULE_BASED,
                confidence=RULE_BASED_CONFIDENCE,
                raw_text=raw_text_snippet,
                source_section=section_name,
                source_table=table_name,
            ))

        return records

    def _llm_extract_ownership(self, html: str) -> list[OwnershipRecord]:
        """Use LLM to extract ownership data when rule-based fails."""
        if not self.llm_extractor.client:
            return []

        # Clean HTML to reduce token usage
        soup = BeautifulSoup(html, "lxml")

        # Try to find the relevant section
        ownership_section, section_name = self._find_ownership_section_with_name(soup)
        text_to_parse = ownership_section if ownership_section else soup.get_text()[:30000]

        owners_data = self.llm_extractor.extract_ownership(text_to_parse)

        if not owners_data:
            return []

        records = []
        for owner in owners_data:
            try:
                # Get raw text from LLM response if provided
                raw_text = owner.get("source_text", owner.get("raw_text"))
                if raw_text:
                    raw_text = raw_text[:MAX_SNIPPET_LENGTH]

                records.append(OwnershipRecord(
                    owner_name=owner.get("owner_name", ""),
                    owner_type=owner.get("owner_type", "person"),
                    shares_owned=owner.get("shares_owned"),
                    percentage=owner.get("percentage"),
                    is_beneficial=owner.get("is_beneficial", True),
                    is_direct=owner.get("is_direct", True),
                    extraction_method=ExtractionMethod.LLM,
                    confidence=owner.get("confidence", 0.85),
                    raw_text=raw_text,
                    source_section=section_name,
                ))
            except Exception as e:
                logger.warning(f"Failed to parse LLM owner record: {e}")

        return records

    def _find_ownership_section(self, soup: BeautifulSoup) -> Optional[str]:
        """Try to find the specific ownership section in the document."""
        text, _ = self._find_ownership_section_with_name(soup)
        return text

    def _find_ownership_section_with_name(
        self, soup: BeautifulSoup
    ) -> tuple[Optional[str], Optional[str]]:
        """Try to find the specific ownership section and its name."""
        # Look for section headers
        for header in soup.find_all(["h1", "h2", "h3", "h4", "p", "div", "b", "strong"]):
            text = header.get_text().lower()
            if "beneficial ownership" in text or "security ownership" in text:
                section_name = header.get_text().strip()[:100]
                # Get the next several siblings
                content = [header.get_text()]
                sibling = header.find_next_sibling()
                char_count = 0
                while sibling and char_count < 20000:
                    text = sibling.get_text()
                    content.append(text)
                    char_count += len(text)
                    sibling = sibling.find_next_sibling()
                return "\n".join(content), section_name
        return None, None

    @staticmethod
    def _clean_text(text: str) -> str:
        """Clean extracted text."""
        # Remove extra whitespace
        text = re.sub(r"\s+", " ", text)
        # Remove footnote markers
        text = re.sub(r"\(\d+\)", "", text)
        text = re.sub(r"\[\d+\]", "", text)
        # Remove asterisks
        text = re.sub(r"\*+", "", text)
        return text.strip()

    @staticmethod
    def _is_valid_name(name: str) -> bool:
        """Check if a name is valid (not garbage text)."""
        name_lower = name.lower().strip()

        # Skip header-like text
        skip_patterns = [
            "name", "beneficial owner", "total", "shares", "percent",
            "class", "amount", "nature", "sole", "shared", "voting",
            "see footnote", "see note", "n/a", "none", "—", "–",
        ]
        if any(p in name_lower for p in skip_patterns):
            return False

        # Skip if it's just numbers/letters with dots (like "1a.", "1b.", "(1)")
        if re.match(r"^[\d\(\)]+[a-z]?\.?$", name_lower):
            return False

        # Skip if too short
        if len(name) < 3:
            return False

        # Skip if mostly numbers
        alpha_count = sum(1 for c in name if c.isalpha())
        if alpha_count < 3:
            return False

        # Skip if it's a very long description (likely not a name)
        if len(name) > 200:
            return False

        # Skip common non-name patterns, but allow company names like "The Vanguard Group"
        company_indicators = ["inc", "corp", "llc", "llp", "ltd", "lp", "co.", "group", "fund", "trust"]
        has_company_indicator = any(ind in name_lower for ind in company_indicators)

        if not has_company_indicator:
            if name_lower.startswith(("a change", "the ", "all ", "each ", "any ")):
                return False

        return True

    @staticmethod
    def _parse_number(text: str) -> Optional[int]:
        """Parse a number from text (handles commas, dashes, etc.)."""
        if not text:
            return None

        # Remove commas and whitespace
        text = text.replace(",", "").replace(" ", "").strip()

        # Handle dash or asterisk (means zero or N/A)
        if text in ["-", "—", "*", "–", "N/A", "n/a", ""]:
            return None

        # Extract number
        match = re.search(r"([\d,]+)", text.replace(",", ""))
        if match:
            try:
                return int(match.group(1))
            except ValueError:
                return None
        return None

    @staticmethod
    def _parse_percentage(text: str) -> Optional[float]:
        """Parse a percentage from text."""
        if not text:
            return None

        text = text.strip()

        # Handle dash or asterisk (means less than 1% or not applicable)
        if text in ["-", "—", "*", "–", "N/A", "n/a", "", "—%", "*%"]:
            return None

        # Handle "less than X%" type expressions
        less_than_match = re.search(r"less\s+than\s+([\d.]+)\s*%?", text.lower())
        if less_than_match:
            try:
                return float(less_than_match.group(1)) / 2  # Approximate as half
            except ValueError:
                return 0.5

        # Handle asterisk with text like "* Less than 1%"
        if "*" in text and "1" in text:
            return 0.5

        # Try multiple patterns to extract percentage
        patterns = [
            r"([\d,]+\.?\d*)\s*%",  # "5.5%" or "5%" or "5,000%"
            r"([\d,]+\.?\d*)\s*percent",  # "5.5 percent"
            r"^([\d,]+\.?\d*)$",  # Just a number (might be percentage without %)
        ]

        for pattern in patterns:
            match = re.search(pattern, text.lower().replace(",", ""))
            if match:
                try:
                    value = float(match.group(1))
                    # Sanity check - percentage should be 0-100
                    if 0 <= value <= 100:
                        return value
                    # If value > 100, it might be shares, not percentage
                except ValueError:
                    continue

        return None

    @staticmethod
    def _guess_owner_type(name: str) -> str:
        """Guess whether owner is a person or company."""
        name_lower = name.lower()

        # Known institutional investors (explicit match)
        known_institutions = [
            "vanguard", "blackrock", "state street", "fidelity", "berkshire",
            "jpmorgan", "morgan stanley", "goldman sachs", "bank of america",
            "wells fargo", "citadel", "bridgewater", "capital group",
            "t. rowe price", "invesco", "schwab", "northern trust",
            "geode capital", "norges bank", "calpers", "tiaa",
        ]
        for inst in known_institutions:
            if inst in name_lower:
                return "company"

        # Company indicators
        company_indicators = [
            "inc", "inc.", "corp", "corp.", "llc", "llp", "ltd", "ltd.",
            "l.p.", "lp", "company", "co.", "n.a.", "n.v.", "s.a.",
            "fund", "funds", "partners", "partnership", "holdings",
            "trust", "investment", "investments", "investors",
            "capital", "management", "asset", "assets",
            "group", "advisors", "advisers", "associates", "association",
            "bank", "financial", "securities", "services",
            "international", "global", "worldwide",
            "pension", "retirement", "endowment",
        ]

        for indicator in company_indicators:
            if indicator in name_lower:
                return "company"

        # Person indicators (titles)
        person_indicators = ["mr.", "mrs.", "ms.", "dr.", "jr.", "sr.", "iii", "ii", "iv"]
        for indicator in person_indicators:
            if indicator in name_lower:
                return "person"

        # Default heuristic: if name has 2-4 words and no company indicators, likely a person
        words = name.split()
        if 2 <= len(words) <= 4:
            return "person"

        return "company"
