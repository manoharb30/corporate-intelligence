"""Parser for officer and director information from DEF 14A."""

import logging
import re
from datetime import date
from typing import Optional

from bs4 import BeautifulSoup, Tag

from app.models.extraction_models import (
    ExtractionMethod,
    ExtractionMetadata,
    OfficerRecord,
    OfficerExtractionResult,
)
from ingestion.sec_edgar.llm_extractor import LLMExtractor
from ingestion.sec_edgar.review_queue import ReviewQueue

logger = logging.getLogger(__name__)

RULE_BASED_CONFIDENCE = 0.95
LLM_CONFIDENCE_THRESHOLD = 0.9

# Maximum length for raw text snippets
MAX_SNIPPET_LENGTH = 300
CONTEXT_LENGTH = 100


class OfficerParser:
    """Parse officer and director data from DEF 14A proxy statements."""

    # Executive titles
    EXECUTIVE_TITLES = [
        "chief executive officer", "ceo",
        "chief financial officer", "cfo",
        "chief operating officer", "coo",
        "chief technology officer", "cto",
        "chief information officer", "cio",
        "chief marketing officer", "cmo",
        "chief legal officer", "clo",
        "chief human resources officer", "chro",
        "chief strategy officer", "cso",
        "president",
        "executive vice president", "evp",
        "senior vice president", "svp",
        "general counsel",
        "treasurer",
        "controller",
        "secretary",
    ]

    # Director indicators
    DIRECTOR_INDICATORS = [
        "director",
        "board member",
        "chairman",
        "chair",
        "lead independent",
        "independent director",
        "non-executive",
    ]

    # Section headers that indicate officer/director information
    SECTION_HEADERS = [
        r"executive\s*officers?",
        r"directors?\s*and\s*executive\s*officers?",
        r"board\s*of\s*directors?",
        r"our\s*directors?",
        r"named\s*executive\s*officers?",
        r"management",
        r"directors?\s*nominees?",
        r"election\s*of\s*directors?",
        r"proposal.*election.*directors?",
        r"nominees?\s*for\s*director",
        r"director\s*nominees?",
        r"continuing\s*directors?",
        r"class\s*[iI]{1,3}\s*directors?",
        r"independent\s*directors?",
        r"non-employee\s*directors?",
        r"members?\s*of\s*the\s*board",
        r"biographical\s*information",
        r"information\s*about\s*directors?",
        r"information\s*regarding\s*directors?",
    ]

    # Specific headers for board of directors (used for targeted search)
    BOARD_SECTION_HEADERS = [
        r"board\s*of\s*directors?",
        r"election\s*of\s*directors?",
        r"proposal.*election.*directors?",
        r"nominees?\s*for\s*director",
        r"director\s*nominees?",
        r"our\s*directors?",
        r"continuing\s*directors?",
        r"class\s*[iI]{1,3}\s*directors?",
    ]

    def __init__(
        self,
        llm_extractor: Optional[LLMExtractor] = None,
        review_queue: Optional[ReviewQueue] = None,
    ):
        self.llm_extractor = llm_extractor or LLMExtractor()
        self.review_queue = review_queue or ReviewQueue()

    def extract_officers(
        self,
        filing_html: str,
        filing_accession: str,
        company_cik: str,
        company_name: Optional[str] = None,
        filing_date: Optional[date] = None,
        filing_url: Optional[str] = None,
    ) -> OfficerExtractionResult:
        """
        Extract officer and director data from DEF 14A.

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
        rule_based_records = self._parse_officers_rulebased(filing_html)

        # Check quality of rule-based extraction
        has_officers = any(r.is_officer or r.is_executive for r in rule_based_records)
        has_directors = any(r.is_director for r in rule_based_records)

        # Determine if we need LLM fallback
        needs_llm = False
        llm_reason = None

        if not rule_based_records:
            needs_llm = True
            llm_reason = "rule-based found nothing"
        elif has_officers and not has_directors:
            # Found officers but no directors - likely missed board section
            needs_llm = True
            llm_reason = "found officers but no directors"
        elif len(rule_based_records) < 3:
            # Too few records - probably incomplete
            needs_llm = True
            llm_reason = f"only {len(rule_based_records)} records found"

        if not needs_llm and rule_based_records:
            logger.info(
                f"Rule-based extraction found {len(rule_based_records)} officers/directors "
                f"({sum(1 for r in rule_based_records if r.is_officer)} officers, "
                f"{sum(1 for r in rule_based_records if r.is_director)} directors) "
                f"from {filing_accession}"
            )
            records = rule_based_records
            method = ExtractionMethod.RULE_BASED
            confidence = RULE_BASED_CONFIDENCE
        else:
            # Fallback to LLM extraction
            logger.info(f"Trying LLM extraction for {filing_accession} ({llm_reason})")
            llm_records = self._llm_extract_officers(filing_html)

            if llm_records:
                # Merge LLM records with rule-based records, avoiding duplicates
                if rule_based_records:
                    seen_names = {r.name.lower() for r in rule_based_records}
                    for llm_record in llm_records:
                        if llm_record.name.lower() not in seen_names:
                            rule_based_records.append(llm_record)
                            seen_names.add(llm_record.name.lower())
                    records = rule_based_records
                    method = ExtractionMethod.HYBRID
                    confidence = 0.90
                    warnings.append(f"Used hybrid extraction ({llm_reason})")
                else:
                    records = llm_records
                    method = ExtractionMethod.LLM
                    confidences = [r.confidence for r in llm_records if r.confidence]
                    confidence = sum(confidences) / len(confidences) if confidences else 0.8
                    warnings.append("Used LLM extraction (rule-based failed)")
            elif rule_based_records:
                # LLM failed but we have some rule-based records
                logger.warning(f"LLM extraction failed, using partial rule-based for {filing_accession}")
                records = rule_based_records
                method = ExtractionMethod.RULE_BASED
                confidence = 0.7  # Lower confidence since we know it's incomplete
                warnings.append(f"Partial extraction only ({llm_reason}, LLM failed)")
            else:
                logger.warning(f"Both extraction methods failed for {filing_accession}")
                method = ExtractionMethod.RULE_BASED
                confidence = 0.0
                warnings.append("Extraction failed - added to review queue")

                self.review_queue.add_failed_extraction(
                    filing_accession=filing_accession,
                    filing_type="DEF 14A",
                    company_cik=company_cik,
                    company_name=company_name,
                    extraction_type="officer",
                    raw_text=filing_html[:50000],
                    failure_reason="Both rule-based and LLM extraction failed",
                )

        # Check confidence threshold
        if records and confidence < LLM_CONFIDENCE_THRESHOLD:
            self.review_queue.add_low_confidence(
                filing_accession=filing_accession,
                filing_type="DEF 14A",
                company_cik=company_cik,
                company_name=company_name,
                extraction_type="officer",
                raw_text=filing_html[:50000],
                confidence=confidence,
                attempted_extraction={"records": [r.model_dump() for r in records]},
            )
            warnings.append(f"Low confidence ({confidence:.2f}) - added to review queue")

        return OfficerExtractionResult(
            records=records,
            filing_accession=filing_accession,
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

    def _parse_officers_rulebased(self, html: str) -> list[OfficerRecord]:
        """Parse officer/director tables and sections using BeautifulSoup."""
        soup = BeautifulSoup(html, "lxml")
        records = []
        seen_names = set()

        # Try table-based extraction
        table_records = self._parse_officer_table(soup)
        for record in table_records:
            if record.name.lower() not in seen_names:
                records.append(record)
                seen_names.add(record.name.lower())

        # Try section-based extraction (for narrative format)
        section_records = self._parse_officer_sections(soup)
        for record in section_records:
            if record.name.lower() not in seen_names:
                records.append(record)
                seen_names.add(record.name.lower())

        # Specifically look for board member sections if we haven't found directors
        has_directors = any(r.is_director for r in records)
        if not has_directors:
            board_records = self._parse_board_members(soup)
            for record in board_records:
                if record.name.lower() not in seen_names:
                    records.append(record)
                    seen_names.add(record.name.lower())

        return records

    def _parse_board_members(self, soup: BeautifulSoup) -> list[OfficerRecord]:
        """Specifically parse board of directors sections."""
        records = []

        # Look for board-specific sections
        for header in soup.find_all(["h1", "h2", "h3", "h4", "p", "b", "strong", "span"]):
            header_text = header.get_text().lower()

            # Check if this is a board-related section
            if not any(re.search(p, header_text) for p in self.BOARD_SECTION_HEADERS):
                continue

            section_name = header.get_text().strip()[:100]
            logger.debug(f"Found board section: {section_name}")

            # Look for director entries in following content
            # Common patterns: Name with age and brief bio
            sibling = header.find_next_sibling()
            iterations = 0
            max_iterations = 100

            while sibling and iterations < max_iterations:
                iterations += 1

                # Check if we've hit another major section
                if sibling.name in ["h1", "h2"] and iterations > 10:
                    sibling_text = sibling.get_text().lower()
                    # Break if it's a different section (not board-related)
                    if not any(re.search(p, sibling_text) for p in self.BOARD_SECTION_HEADERS):
                        break

                text = sibling.get_text().strip()
                if not text or len(text) < 10:
                    sibling = sibling.find_next_sibling()
                    continue

                raw_text_snippet = text[:MAX_SNIPPET_LENGTH]

                # Pattern: "Name, Age XX" or "Name (Age XX)" at start of paragraph
                # Often followed by title and bio
                patterns = [
                    # "John Smith, 65, has served as..."
                    r"^([A-Z][a-zA-Z]+(?:\s+[A-Z][a-zA-Z\.]+){1,3}),?\s*(?:age\s*)?(\d{2})[,\s]",
                    # "John Smith (65) has served..."
                    r"^([A-Z][a-zA-Z]+(?:\s+[A-Z][a-zA-Z\.]+){1,3})\s*\((\d{2})\)",
                    # "John Smith, Director since..."
                    r"^([A-Z][a-zA-Z]+(?:\s+[A-Z][a-zA-Z\.]+){1,3}),?\s*(Director|Chairman|Board Member)",
                ]

                for pattern in patterns:
                    match = re.match(pattern, text, re.IGNORECASE)
                    if match:
                        raw_name = match.group(1).strip()

                        # Validate and clean name
                        name, is_valid = self._validate_and_clean_name(raw_name)
                        if not is_valid:
                            continue

                        # Try to extract age
                        age = None
                        if len(match.groups()) >= 2:
                            try:
                                potential_age = int(match.group(2))
                                if 30 <= potential_age <= 95:
                                    age = potential_age
                            except (ValueError, TypeError):
                                pass

                        # Extract title from surrounding text
                        title = None
                        title_match = re.search(
                            r"(Director|Chairman|Chair|Board Member|Lead Independent|Independent Director)",
                            text[:200],
                            re.IGNORECASE
                        )
                        if title_match:
                            title = title_match.group(1)

                        # Check not already added
                        if not any(r.name.lower() == name.lower() for r in records):
                            try:
                                records.append(OfficerRecord(
                                    name=name,
                                    title=title or "Director",
                                    is_director=True,
                                    is_officer=False,
                                    is_executive=False,
                                    age=age,
                                    extraction_method=ExtractionMethod.RULE_BASED,
                                    confidence=0.85,
                                    raw_text=raw_text_snippet,
                                    source_section=section_name,
                                ))
                                logger.debug(f"Extracted board member: {name}")
                            except Exception as e:
                                logger.warning(f"Failed to create OfficerRecord for {name}: {e}")
                        break

                # Also look for bold names (common format for director bios)
                bold_elem = sibling.find(["b", "strong"])
                if bold_elem and not any(r.name.lower() == bold_elem.get_text().lower().strip() for r in records):
                    raw_name = self._clean_text(bold_elem.get_text())
                    name, is_valid = self._validate_and_clean_name(raw_name)
                    if name and is_valid:
                        # Check if this looks like a director bio
                        full_text = sibling.get_text().lower()
                        if any(kw in full_text for kw in ["director", "board", "served", "appointed", "elected"]):
                            try:
                                records.append(OfficerRecord(
                                    name=name,
                                    title="Director",
                                    is_director=True,
                                    is_officer=False,
                                    is_executive=False,
                                    extraction_method=ExtractionMethod.RULE_BASED,
                                    confidence=0.80,
                                    raw_text=raw_text_snippet,
                                    source_section=section_name,
                                ))
                                logger.debug(f"Extracted board member (bold): {name}")
                            except Exception as e:
                                logger.warning(f"Failed to create OfficerRecord for {name}: {e}")

                sibling = sibling.find_next_sibling()

        return records

    def _parse_officer_table(self, soup: BeautifulSoup) -> list[OfficerRecord]:
        """Parse officers from HTML tables."""
        records = []

        for table in soup.find_all("table"):
            # Check if this table is relevant
            table_text = table.get_text().lower()
            section_name = None
            table_name = None

            if not any(re.search(p, table_text) for p in self.SECTION_HEADERS):
                # Also check preceding text
                prev = table.find_previous(["p", "h1", "h2", "h3", "h4"])
                if prev:
                    prev_text = prev.get_text().lower()
                    if not any(re.search(p, prev_text) for p in self.SECTION_HEADERS):
                        continue
                    section_name = prev.get_text().strip()[:100]
            else:
                # Extract section name from matched pattern
                for pattern in self.SECTION_HEADERS:
                    match = re.search(pattern, table_text)
                    if match:
                        section_name = match.group(0).strip()[:100]
                        break

            # Try to get table caption or title
            caption = table.find("caption")
            if caption:
                table_name = caption.get_text().strip()[:100]

            rows = table.find_all("tr")
            if len(rows) < 2:
                continue

            # Try to identify columns
            header_row = rows[0]
            cells = header_row.find_all(["th", "td"])
            headers = [c.get_text().strip().lower() for c in cells]

            name_col = None
            title_col = None
            age_col = None

            for i, header in enumerate(headers):
                if any(w in header for w in ["name", "director", "officer"]):
                    name_col = i
                if any(w in header for w in ["title", "position", "office"]):
                    title_col = i
                if "age" in header:
                    age_col = i

            # Default columns if headers not found
            if name_col is None and len(cells) >= 2:
                name_col = 0
                title_col = 1

            if name_col is None:
                continue

            # Parse data rows
            for row in rows[1:]:
                cells = row.find_all(["th", "td"])
                if len(cells) <= name_col:
                    continue

                raw_name = self._clean_text(cells[name_col].get_text())

                # Capture raw text for citation
                row_text = row.get_text().strip()
                raw_text_snippet = row_text[:MAX_SNIPPET_LENGTH] if row_text else None

                # Try to extract name from combined name+title text
                name, extracted_title = self._extract_name_from_text(raw_name)

                # Validate and clean name
                name, is_valid = self._validate_and_clean_name(name)
                if not is_valid:
                    continue

                title = None
                if title_col is not None and title_col < len(cells):
                    title = self._clean_text(cells[title_col].get_text())
                elif extracted_title:
                    title = extracted_title

                age = None
                if age_col is not None and age_col < len(cells):
                    age_text = cells[age_col].get_text().strip()
                    age = self._parse_age(age_text)

                is_director, is_officer, is_executive = self._classify_role(title)

                # If no role from title, infer from section context
                if not (is_director or is_officer or is_executive) and section_name:
                    section_lower = section_name.lower()
                    if any(kw in section_lower for kw in ["board of director", "director nominee", "our director", "election of director"]):
                        is_director = True
                    elif any(kw in section_lower for kw in ["executive officer", "named executive", "management"]):
                        is_officer = True
                        is_executive = True

                try:
                    records.append(OfficerRecord(
                        name=name,
                        title=title,
                        is_director=is_director,
                        is_officer=is_officer,
                        is_executive=is_executive,
                        age=age,
                        extraction_method=ExtractionMethod.RULE_BASED,
                        confidence=RULE_BASED_CONFIDENCE,
                        raw_text=raw_text_snippet,
                        source_section=section_name,
                        source_table=table_name,
                    ))
                except Exception as e:
                    logger.warning(f"Failed to create OfficerRecord for {name}: {e}")

        return records

    def _parse_officer_sections(self, soup: BeautifulSoup) -> list[OfficerRecord]:
        """Parse officers from narrative sections (name followed by bio)."""
        records = []

        # Find relevant sections
        for header in soup.find_all(["h1", "h2", "h3", "h4", "p", "b", "strong"]):
            header_text = header.get_text().lower()

            if not any(re.search(p, header_text) for p in self.SECTION_HEADERS):
                continue

            # Capture section name for citation
            section_name = header.get_text().strip()[:100]

            # Found a relevant section - look for officer entries
            # Common pattern: Bold name followed by title and bio

            sibling = header.find_next_sibling()
            iterations = 0
            max_iterations = 50

            while sibling and iterations < max_iterations:
                iterations += 1

                # Check if we've hit another major section
                if sibling.name in ["h1", "h2"] and iterations > 5:
                    break

                # Look for name patterns
                text = sibling.get_text().strip()

                # Capture raw text snippet for citation
                raw_text_snippet = text[:MAX_SNIPPET_LENGTH] if text else None

                # Pattern: "Name, Age XX, Title"
                pattern1 = re.match(
                    r"([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+),?\s*(?:age\s*)?(\d{2}),?\s*(.+)",
                    text,
                    re.IGNORECASE
                )

                if pattern1:
                    raw_name = pattern1.group(1).strip()
                    raw_age = int(pattern1.group(2))
                    # Validate age range (25-100)
                    age = raw_age if 25 <= raw_age <= 100 else None
                    title = pattern1.group(3).split(".")[0].strip()

                    # Validate and clean name
                    name, is_valid = self._validate_and_clean_name(raw_name)
                    if name and len(name) >= 3 and is_valid:
                        is_director, is_officer, is_executive = self._classify_role(title)

                        # If no role from title, infer from section context
                        if not (is_director or is_officer or is_executive):
                            section_lower = section_name.lower() if section_name else ""
                            if any(kw in section_lower for kw in ["board of director", "director nominee", "our director", "election of director"]):
                                is_director = True
                            elif any(kw in section_lower for kw in ["executive officer", "named executive", "management"]):
                                is_officer = True
                                is_executive = True

                        try:
                            records.append(OfficerRecord(
                                name=name,
                                title=title,
                                is_director=is_director,
                                is_officer=is_officer,
                                is_executive=is_executive,
                                age=age,
                                extraction_method=ExtractionMethod.RULE_BASED,
                                confidence=0.85,
                                raw_text=raw_text_snippet,
                                source_section=section_name,
                            ))
                        except Exception as e:
                            logger.warning(f"Failed to create OfficerRecord for {name}: {e}")

                # Pattern: Bold name followed by title
                bold_elem = sibling.find(["b", "strong"])
                if bold_elem:
                    raw_name = self._clean_text(bold_elem.get_text())
                    name, is_valid = self._validate_and_clean_name(raw_name)
                    if name and len(name.split()) >= 2 and len(name) < 50 and is_valid:
                        # Get title from rest of text
                        full_text = sibling.get_text()
                        title_text = full_text.replace(name, "").strip()
                        title_text = re.sub(r"^[,.\s]+", "", title_text)
                        title = title_text.split(".")[0].strip()[:100]

                        if title:
                            is_director, is_officer, is_executive = self._classify_role(title)

                            # Check if not already added
                            if not any(r.name.lower() == name.lower() for r in records):
                                try:
                                    records.append(OfficerRecord(
                                        name=name,
                                        title=title,
                                        is_director=is_director,
                                        is_officer=is_officer,
                                        is_executive=is_executive,
                                        extraction_method=ExtractionMethod.RULE_BASED,
                                        confidence=0.80,
                                        raw_text=raw_text_snippet,
                                        source_section=section_name,
                                    ))
                                except Exception as e:
                                    logger.warning(f"Failed to create OfficerRecord for {name}: {e}")

                sibling = sibling.find_next_sibling()

        return records

    def _llm_extract_officers(self, html: str) -> list[OfficerRecord]:
        """Use LLM to extract officer data when rule-based fails."""
        if not self.llm_extractor.client:
            return []

        # Clean HTML and find relevant section
        soup = BeautifulSoup(html, "lxml")
        text, section_name = self._find_officer_section_with_name(soup)

        if not text:
            text = soup.get_text()[:30000]
            section_name = None

        officers_data = self.llm_extractor.extract_officers(text)

        if not officers_data:
            return []

        records = []
        for officer in officers_data:
            try:
                # Validate and clean the name from LLM
                raw_name = officer.get("name", "")
                name, is_valid = self._validate_and_clean_name(raw_name)
                if not is_valid:
                    logger.debug(f"LLM returned invalid name, skipping: {raw_name}")
                    continue

                title = officer.get("title")
                is_director = officer.get("is_director", False)
                is_officer = officer.get("is_officer", False)
                is_executive = officer.get("is_executive", False)

                # Supplement with our classification
                if title and not (is_director or is_officer or is_executive):
                    is_director, is_officer, is_executive = self._classify_role(title)

                # Get raw text from LLM response if provided
                raw_text = officer.get("source_text", officer.get("raw_text"))
                if raw_text:
                    raw_text = raw_text[:MAX_SNIPPET_LENGTH]

                records.append(OfficerRecord(
                    name=name,
                    title=title,
                    is_director=is_director or officer.get("is_director", False),
                    is_officer=is_officer or officer.get("is_officer", False),
                    is_executive=is_executive or officer.get("is_executive", False),
                    age=officer.get("age"),
                    extraction_method=ExtractionMethod.LLM,
                    confidence=officer.get("confidence", 0.85),
                    raw_text=raw_text,
                    source_section=section_name,
                ))
            except Exception as e:
                logger.warning(f"Failed to parse LLM officer record: {e}")

        return records

    def _find_officer_section(self, soup: BeautifulSoup) -> Optional[str]:
        """Try to find the specific officer/director section."""
        text, _ = self._find_officer_section_with_name(soup)
        return text

    def _find_officer_section_with_name(self, soup: BeautifulSoup) -> tuple[Optional[str], Optional[str]]:
        """Try to find the specific officer/director section and its name."""
        for header in soup.find_all(["h1", "h2", "h3", "h4", "p", "b", "strong"]):
            text = header.get_text().lower()
            if any(re.search(p, text) for p in self.SECTION_HEADERS):
                section_name = header.get_text().strip()[:100]
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

    def _classify_role(self, title: Optional[str]) -> tuple[bool, bool, bool]:
        """
        Classify a role as director, officer, and/or executive.

        Returns: (is_director, is_officer, is_executive)
        """
        if not title:
            return False, False, False

        title_lower = title.lower()

        # Use word boundary matching to avoid false positives (e.g., "cto" in "director")
        def word_match(term: str, text: str) -> bool:
            """Check if term appears as a word/phrase in text."""
            # For short abbreviations, require word boundaries
            if len(term) <= 4:
                pattern = rf"\b{re.escape(term)}\b"
                return bool(re.search(pattern, text))
            # For longer phrases, substring match is fine
            return term in text

        is_director = any(word_match(ind, title_lower) for ind in self.DIRECTOR_INDICATORS)
        is_executive = any(word_match(ind, title_lower) for ind in self.EXECUTIVE_TITLES)
        is_officer = is_executive or any(
            word_match(w, title_lower) for w in ["vice president", "vp", "officer", "counsel", "secretary", "treasurer"]
        )

        return is_director, is_officer, is_executive

    @staticmethod
    def _clean_text(text: str) -> str:
        """Clean extracted text."""
        text = re.sub(r"\s+", " ", text)
        text = re.sub(r"\(\d+\)", "", text)  # Remove footnote references like (1), (2)
        text = re.sub(r"\*+", "", text)
        # Remove role indicators in parentheses like (Chair), (Lead Independent)
        text = re.sub(r"\s*\((?:Chair|Chairman|Lead\s*Independent|Vice\s*Chair)\)", "", text, flags=re.IGNORECASE)
        return text.strip()

    @staticmethod
    def _clean_person_name(name: str) -> str:
        """Clean and normalize a person name."""
        name = OfficerParser._clean_text(name)
        # Remove trailing role indicators
        name = re.sub(r"\s+(Chair|Chairman|Director|Lead|Former)$", "", name, flags=re.IGNORECASE)
        # Remove "Former" prefix/suffix
        name = re.sub(r"^Former\s+", "", name, flags=re.IGNORECASE)
        name = re.sub(r"\s+Former$", "", name, flags=re.IGNORECASE)
        # Remove other common trailing artifacts
        name = re.sub(r"\s*\(\d+\)\s*$", "", name)  # Remove trailing (1), (2) etc.
        name = re.sub(r"\s*\*+\s*$", "", name)  # Remove trailing asterisks
        # Remove unclosed parentheses at end (like "Bruno Wu (Former")
        name = re.sub(r"\s*\([^)]*$", "", name)
        # Remove "(Former" or "(Former anything" patterns
        name = re.sub(r"\s*\(Former[^)]*\)?", "", name, flags=re.IGNORECASE)
        return name.strip()

    @classmethod
    def _validate_and_clean_name(cls, name: str) -> tuple[str | None, bool]:
        """
        Clean and validate a potential person name.
        Returns (cleaned_name, is_valid) tuple.
        """
        if not name:
            return None, False
        cleaned = cls._clean_person_name(name)
        if cls._is_valid_name(cleaned):
            return cleaned, True
        return None, False

    @staticmethod
    def _extract_name_from_text(text: str) -> tuple[str, str | None]:
        """
        Extract person name from text that might include title.
        Returns (name, title) tuple.
        """
        if not text:
            return ("", None)

        # Common title patterns to split on
        title_keywords = [
            "chief executive officer", "chief operating officer",
            "chief financial officer", "chief technology officer",
            "chief legal officer", "chief marketing officer",
            "senior vice president", "executive vice president",
            "vice president", "president", "chairman", "chair",
            "general counsel", "secretary", "treasurer", "director",
            "ceo", "coo", "cfo", "cto", "cmo", "clo", "svp", "evp", "vp",
        ]

        text_lower = text.lower()

        # Try to find where the title starts
        for title_kw in title_keywords:
            idx = text_lower.find(title_kw)
            if idx > 0:
                # Found a title keyword - split there
                name_part = text[:idx].strip().rstrip(",").strip()
                title_part = text[idx:].strip()

                # Only accept if name_part looks like a name (2-4 words)
                words = name_part.split()
                if 2 <= len(words) <= 4:
                    return (name_part, title_part)

        # No title found, return as-is
        return (text.strip(), None)

    @staticmethod
    def _is_valid_name(name: str) -> bool:
        """Check if a name is valid person name (not garbage text)."""
        if not name or len(name) < 3:
            return False

        name_lower = name.lower().strip()
        name_upper = name.upper().strip()

        # Skip if it looks like a company name (contains corporate suffixes)
        company_suffixes = [
            " inc.", " inc", " corp.", " corp", " llc", " l.l.c.",
            " l.p.", " lp", " ltd.", " ltd", " limited", " plc",
            " co.", " company", " corporation", " incorporated",
            " holdings", " enterprises", " partners", " group",
            " s.a.", " n.v.", " b.v.", " gmbh", " ag",
        ]
        if any(name_lower.endswith(suffix) for suffix in company_suffixes):
            return False

        # Skip if name is ALL CAPS (likely a company or header)
        if name == name_upper and len(name) > 10:
            return False

        # Skip if name contains a sentence pattern (word followed by period and more words)
        # This catches garbage like "INITIAL GRANTS. Each Non-Employee"
        if re.search(r'\w+\.\s+[A-Z][a-z]+', name):
            return False

        # Skip if starts with common document section words followed by more text
        section_starts = [
            "initial ", "maximum ", "other ", "stock ", "market ",
            "shareholder ", "audit ", "executive ", "compensation ",
        ]
        if any(name_lower.startswith(s) for s in section_starts):
            return False

        # Skip exact matches to header-like text
        skip_exact = [
            "name", "director", "officer", "age", "position", "title",
            "executive", "board", "committee", "n/a", "none", "—", "–",
            "see footnote", "see note", "total", "former", "current",
            "chief executive officer", "chief financial officer",
            "chief operating officer", "chief technology officer",
            "exhibit a", "exhibit b", "exhibit c", "annex a", "annex b",
            "non-employee directors", "independent directors",
            "shareholder engagement", "corporate governance",
            "board independence", "board oversight", "vote required",
            "business conduct policy", "other information", "general information",
            "executive officers", "stock awards", "market capitalization",
            "ernst & young", "ernst &\n    young",
            # SEC document sections that slip through
            "risk management", "five percent holders", "pay versus performance",
            "pay ratio", "equity compensation", "beneficial ownership",
            "security ownership", "audit committee", "accounting",
            "performance graph", "compensation discussion", "principal stockholders",
            "related party", "certain relationships", "director compensation",
            "executive compensation", "stock ownership", "delinquent section",
            # LLM hallucination patterns - product/document names mistaken as people
            "nikola badger", "nikola insider", "nikola motor", "nikola truck",
            "tesla model", "apple watch", "apple iphone",
        ]
        if any(name_lower == p or name_lower.startswith(p + " ") for p in skip_exact):
            return False

        # Skip if contains document/section patterns
        skip_contains = [
            "highlights", "transition", "compensation", "proposal",
            "table of contents", "notice of", "election of", "annual",
            "meeting", "shareholders", "guidelines", "policies",
            "prohibitions", "hedging", "pledging", "voting", "majority",
            "separation", "self-evaluation", "commitment", "summary",
            "the role of", "the following table", "named executive",
            "employment contract", "employed at will", "fiscal", "target",
            "million", "$", "ceo ", " cfo", "total target",
            "questions and answers", "proxy statement", "form 4",
            "schedule 13", "section 16", "rule 10b", "exchange act",
            "securities act", "item ", "part ", "exhibit",
            "information is based on", "filed by", "filed with",
        ]
        if any(p in name_lower for p in skip_contains):
            return False

        # Skip if starts with common document patterns
        skip_starts = [
            "proposal no", "notice of", "table of", "summary of",
            "the ", "our ", "all ", "each ", "any ", "this ",
            "20", "19",  # Years like 2024, 2025
            "on ", "in ", "at ", "by ", "for ", "to ", "as ",
            "former ", "current ", "see ", "note ", "per ",
        ]
        if any(name_lower.startswith(p) for p in skip_starts):
            return False

        # Skip if name starts with a company name pattern (LLM hallucination)
        # These are often product names mistaken as people
        company_first_words = [
            "nikola ", "tesla ", "apple ", "amazon ", "google ", "microsoft ",
            "meta ", "nvidia ", "intel ", "cisco ", "oracle ", "ibm ",
        ]
        if any(name_lower.startswith(c) for c in company_first_words):
            return False

        # Skip if it's just numbers/letters with dots (like "1a.", "1b.")
        if re.match(r"^[\d\(\)]+[a-z]?\.?$", name_lower):
            return False

        # Skip if contains year patterns like "2024" or "2025"
        if re.search(r"\b20\d{2}\b", name):
            return False

        # Skip if mostly numbers
        alpha_count = sum(1 for c in name if c.isalpha())
        digit_count = sum(1 for c in name if c.isdigit())
        if alpha_count < 3 or digit_count > alpha_count * 0.3:
            return False

        # Skip if it's too long (likely not a name)
        if len(name) > 60:
            return False

        # Skip if contains long parenthetical text (committee descriptions etc.)
        paren_match = re.search(r'\([^)]{15,}\)', name)
        if paren_match:
            return False

        # Skip if it looks like a sentence (contains common sentence words)
        sentence_words = [
            " is ", " are ", " was ", " were ", " has ", " have ", " had ",
            " based on ", " filed ", " pursuant ", " accordance ", " regarding ",
            " concerning ", " relating ", " with respect to ", " in connection ",
            " with the ", " by the ", " on the ", " of the ", " to the ",
            " filed by ", " filed with ", " sec on ", " march ", " april ",
            " january ", " february ", " may ", " june ", " july ", " august ",
            " september ", " october ", " november ", " december ",
        ]
        if any(w in name_lower for w in sentence_words):
            return False

        # Skip if too long to be a person name (more than 50 chars after cleaning)
        if len(name) > 50:
            return False

        # Name should have 2-5 words for a person
        words = name.split()
        if len(words) < 2 or len(words) > 6:
            return False

        # Detect concatenated names (multiple person names in one string)
        # Pattern: "FirstA LastA FirstB LastB" - Look for too many capitalized words
        # that don't follow typical name patterns (e.g., "Andrea Jung Alex Gorsky")
        cap_word_count = sum(1 for w in words if w and w[0].isupper() and len(w) > 1)
        if cap_word_count > 4:
            return False

        # Check for pattern: Two+ sequences of First Last (consecutive capitalized pairs)
        # e.g., "Andrea Jung Alex Gorsky" has 4 cap words with alternating structure
        if len(words) >= 4:
            # Count transitions from likely first-name to likely last-name
            # If we see multiple "First Last First Last" patterns, it's concatenated names
            first_name_patterns = 0
            for i, word in enumerate(words):
                if i > 0 and word and word[0].isupper():
                    # This word starts a new potential name if previous word was also capitalized
                    # and both words look like first/last names (not suffixes like Jr., III)
                    prev_word = words[i-1].strip(".,")
                    curr_word = word.strip(".,")
                    suffixes = ["jr", "sr", "ii", "iii", "iv", "phd", "md", "esq"]
                    if (prev_word.lower() not in suffixes and
                        curr_word.lower() not in suffixes and
                        len(prev_word) > 2 and len(curr_word) > 2 and
                        not prev_word.lower() in ["de", "van", "von", "la", "le"]):
                        first_name_patterns += 1
            # If there are 3+ transitions, likely concatenated names
            if first_name_patterns >= 3:
                return False

        # First word should start with capital letter (proper name)
        if not name[0].isupper():
            return False

        # Check if it looks like a proper name (First Last pattern)
        # Each word should be capitalized and reasonable length
        for word in words:
            clean_word = word.strip(".,;:()")
            if clean_word and len(clean_word) > 1:
                if not clean_word[0].isupper():
                    # Allow lowercase connectors like "de", "van", "von"
                    if clean_word.lower() not in ["de", "van", "von", "der", "la", "le", "du"]:
                        return False

        return True

    @staticmethod
    def _parse_age(text: str) -> Optional[int]:
        """Parse age from text."""
        if not text:
            return None

        # Look for age patterns like "age 55", "Age: 55", ", 55,"
        age_patterns = [
            r"age[:\s]+(\d{2})",  # "age 55" or "age: 55"
            r",\s*(\d{2})\s*,",   # ", 55," (age between commas)
            r"^\s*(\d{2})\s*$",   # Just a number in the cell
        ]

        for pattern in age_patterns:
            match = re.search(pattern, text.lower())
            if match:
                age = int(match.group(1))
                # More reasonable age range for executives (30-95)
                if 30 <= age <= 95:
                    return age

        # Fallback: look for any 2-digit number that could be an age
        fallback_match = re.search(r"(\d{2})", text)
        if fallback_match:
            age = int(fallback_match.group(1))
            if 35 <= age <= 90:  # Stricter range for fallback
                return age

        return None
