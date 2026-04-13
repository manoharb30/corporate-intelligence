"""Parser for SEC Schedule 13D/13D-A filings.

Parses the XSLT-rendered HTML using BeautifulSoup table structure (not regex).
The 13D rendered HTML uses semantic IDs:
  - <table id="reportingPersonDetails"> — one per reporting person
  - Row 1: Name of reporting person
  - Row 6: Citizenship
  - Row 7: Sole voting power
  - Row 8: Shared voting power
  - Row 11: Aggregate amount beneficially owned
  - Row 13: Percent of class
  - Row 14: Type of reporting person
"""

import logging
import re
from dataclasses import dataclass, field
from typing import Optional

from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

# Quality flag thresholds
SHARES_LIKELY_ERROR = 1_000_000_000  # >1B shares is suspicious


@dataclass
class ReportingPerson:
    """Single reporting person within a 13D filing."""

    name: str = ""
    citizenship: str = ""
    sole_voting_power: Optional[int] = None
    shared_voting_power: Optional[int] = None
    shares_owned: Optional[int] = None
    percentage: Optional[float] = None
    reporting_person_type: str = ""


@dataclass
class Schedule13DResult:
    """Result of parsing a Schedule 13D filing."""

    # Filing metadata (from EFTS, passed in)
    accession_number: str = ""
    filing_type: str = ""  # "SCHEDULE 13D" or "SCHEDULE 13D/A"
    filing_date: str = ""

    # Filer info — from the FIRST reporting person, or EFTS metadata
    filer_name: str = ""
    filer_cik: str = ""
    reporting_person_type: str = ""  # Row 14: IA, IN, CO, HC, etc.
    citizenship: str = ""  # Row 6

    # Target info (from EFTS or Item 1)
    target_name: str = ""
    target_cik: str = ""

    # Stake info — from the FIRST reporting person
    shares_owned: Optional[int] = None
    percentage: Optional[float] = None
    sole_voting_power: Optional[int] = None
    shared_voting_power: Optional[int] = None

    # All reporting persons (multi-filer support)
    all_reporting_persons: list[ReportingPerson] = field(default_factory=list)

    # Purpose (Item 4) — raw text
    purpose_text: str = ""

    # Amendment info
    is_amendment: bool = False
    amendment_number: Optional[int] = None

    # Filing URL
    filing_url: str = ""

    # Parse quality
    parse_errors: list[str] = field(default_factory=list)
    quality_flag: Optional[str] = None  # set if data looks suspicious


def parse_schedule_13d(html: str, metadata: Optional[dict] = None) -> Schedule13DResult:
    """Parse a Schedule 13D filing from its rendered HTML."""
    result = Schedule13DResult()

    # Pre-fill from EFTS metadata if provided
    if metadata:
        result.accession_number = metadata.get("accession_number", "")
        result.filing_type = metadata.get("filing_type", "")
        result.filing_date = metadata.get("filing_date", "")
        result.target_cik = metadata.get("target_cik", "")
        result.target_name = metadata.get("target_name", "")
        result.filer_cik = metadata.get("filer_cik", "")
        result.filer_name = metadata.get("filer_name", "")
        result.filing_url = metadata.get("filing_url", "")

    # Detect amendment from filing type
    result.is_amendment = "/A" in result.filing_type

    soup = BeautifulSoup(html, "html.parser")

    # Remove style and script tags
    for tag in soup(["style", "script"]):
        tag.decompose()

    # Parse all reporting persons from the table structures
    _parse_reporting_persons(soup, result)

    # Use the first reporting person as the primary filer info
    if result.all_reporting_persons:
        primary = result.all_reporting_persons[0]
        if not result.filer_name:
            result.filer_name = primary.name
        result.citizenship = primary.citizenship
        result.shares_owned = primary.shares_owned
        result.percentage = primary.percentage
        result.sole_voting_power = primary.sole_voting_power
        result.shared_voting_power = primary.shared_voting_power
        result.reporting_person_type = primary.reporting_person_type

    # Get plain text for amendment number, item 1, item 4
    text = soup.get_text(separator="\n", strip=True)

    result.amendment_number = _extract_amendment_number(text)
    _parse_item4(text, result)
    if not result.target_name:
        _parse_item1(text, result)

    # Auto-flag suspicious data
    _set_quality_flag(result)

    return result


def _parse_reporting_persons(soup: BeautifulSoup, result: Schedule13DResult) -> None:
    """Extract data from each reportingPersonDetails table.

    Each filing has one or more <table id="reportingPersonDetails"> tables.
    Each table has rows 1-14 of the cover page.
    """
    tables = soup.find_all("table", id="reportingPersonDetails")
    if not tables:
        # Fallback: try to find tables that look like reporting person tables
        # by looking for cells containing "Name of reporting person"
        all_tables = soup.find_all("table")
        tables = [
            t for t in all_tables
            if t.find(string=re.compile(r"Name of reporting person", re.IGNORECASE))
        ]

    for table in tables:
        person = _parse_one_reporting_person(table)
        if person and person.name:
            result.all_reporting_persons.append(person)

    # If no tables found OR no person extracted, fall back to text-based parsing
    # (handles legacy fixtures and unstructured HTML)
    if not result.all_reporting_persons:
        text = soup.get_text(separator="\n", strip=True)
        person = _parse_text_fallback(text)
        if person and person.name:
            result.all_reporting_persons.append(person)
        else:
            result.parse_errors.append("Could not extract reporting person data")


def _parse_one_reporting_person(table) -> Optional[ReportingPerson]:
    """Extract fields from a single reportingPersonDetails table.

    The table is structured as <tr><td row_num</td><td label and value</td></tr>.
    The value is typically inside a <div class="text"> tag.
    """
    person = ReportingPerson()
    rows = table.find_all("tr")

    for row in rows:
        cells = row.find_all("td")
        if len(cells) < 2:
            continue

        # First cell is the row number (1-14)
        row_num_text = cells[0].get_text(strip=True)
        try:
            row_num = int(row_num_text)
        except (ValueError, TypeError):
            continue

        # Second cell contains the label and value
        value_cell = cells[1]
        # The value is typically in a <div class="text"> child
        text_div = value_cell.find("div", class_="text")
        if text_div:
            value = text_div.get_text(strip=True)
        else:
            # Fallback: get all text from the cell, strip the label
            full_text = value_cell.get_text(separator=" ", strip=True)
            value = full_text  # may include label

        if row_num == 1:
            person.name = value
        elif row_num == 6:
            person.citizenship = value
        elif row_num == 7:
            person.sole_voting_power = _parse_int(value)
        elif row_num == 8:
            person.shared_voting_power = _parse_int(value)
        elif row_num == 11:
            person.shares_owned = _parse_int(value)
        elif row_num == 13:
            person.percentage = _parse_percent(value)
        elif row_num == 14:
            # Type of reporting person — typically 2-letter code
            m = re.search(r"\b([A-Z]{2})\b", value)
            if m:
                person.reporting_person_type = m.group(1)

    return person if person.name else None


def _parse_text_fallback(text: str) -> Optional[ReportingPerson]:
    """Fallback parser for unstructured HTML — uses text patterns.

    Used when the rendered HTML doesn't have <table id="reportingPersonDetails">
    structure (e.g., test fixtures or older filings).
    """
    person = ReportingPerson()

    # Row 1: Name
    m = re.search(r"1\s*\n\s*Name of reporting person\s*\n\s*(.+)", text, re.IGNORECASE)
    if m:
        person.name = m.group(1).strip()

    # Row 6: Citizenship
    m = re.search(r"6\s*\n\s*Citizenship or place of organization\s*\n\s*(.+)", text, re.IGNORECASE)
    if m:
        person.citizenship = m.group(1).strip()

    # Row 7: Sole Voting Power
    m = re.search(r"7\s*\n\s*Sole Voting Power\s*\n\s*([\d,\.]+)", text, re.IGNORECASE)
    if m:
        person.sole_voting_power = _parse_int(m.group(1))

    # Row 8: Shared Voting Power
    m = re.search(r"8\s*\n\s*Shared Voting Power\s*\n\s*([\d,\.]+)", text, re.IGNORECASE)
    if m:
        person.shared_voting_power = _parse_int(m.group(1))

    # Row 11: Aggregate amount
    m = re.search(r"11\s*\n\s*Aggregate amount beneficially owned[^\n]*\n\s*([\d,\.]+)", text, re.IGNORECASE)
    if m:
        person.shares_owned = _parse_int(m.group(1))

    # Row 13: Percent
    m = re.search(r"13\s*\n\s*Percent of class[^\n]*\n\s*([\d\.]+)\s*%?", text, re.IGNORECASE)
    if m:
        person.percentage = _parse_percent(m.group(1))

    # Row 14: Type of Reporting Person
    m = re.search(r"14\s*\n\s*Type of Reporting Person[^\n]*\n\s*([A-Z]{2})", text, re.IGNORECASE)
    if m:
        person.reporting_person_type = m.group(1).upper()

    return person if person.name else None


def _extract_amendment_number(text: str) -> Optional[int]:
    """Extract amendment number from '(Amendment No. X)' in the header."""
    match = re.search(r"\(Amendment\s+No\.?\s*\n?\s*(\d+)\s*\n?\s*\)", text, re.IGNORECASE)
    if match:
        return int(match.group(1))
    return None


def _parse_item4(text: str, result: Schedule13DResult) -> None:
    """Extract Item 4 (Purpose of Transaction) text."""
    item4_match = re.search(r"Item\s+4\.?\s*\n\s*Purpose of Transaction", text, re.IGNORECASE)
    if not item4_match:
        result.parse_errors.append("Could not find Item 4 section")
        return

    item5_match = re.search(r"Item\s+5\.?\s*\n\s*Interest in Securities", text[item4_match.end():], re.IGNORECASE)

    if item5_match:
        raw = text[item4_match.end():item4_match.end() + item5_match.start()]
    else:
        raw = text[item4_match.end():item4_match.end() + 2000]

    purpose = raw.strip()
    purpose = re.sub(r"^\s*Purpose of Transaction\s*", "", purpose, flags=re.IGNORECASE).strip()
    result.purpose_text = purpose


def _parse_item1(text: str, result: Schedule13DResult) -> None:
    """Extract target company name from Item 1."""
    match = re.search(
        r"Item\s+1\.?\s*\n\s*Security and Issuer.*?"
        r"Name of Issuer:\s*\n?\s*(.+?)(?:\n|$)",
        text, re.IGNORECASE | re.DOTALL
    )
    if match:
        result.target_name = match.group(1).strip().rstrip(".")


def _parse_int(value: str) -> Optional[int]:
    """Parse an integer from a string, handling commas and decimals."""
    if not value:
        return None
    try:
        cleaned = value.replace(",", "").replace("'", "").strip()
        # Strip non-numeric trailing chars
        cleaned = re.sub(r"[^\d.\-]+", "", cleaned)
        if not cleaned or cleaned == "-":
            return None
        if "." in cleaned:
            return int(float(cleaned))
        return int(cleaned)
    except (ValueError, TypeError):
        return None


def _parse_percent(value: str) -> Optional[float]:
    """Parse a percentage like '8.7 %' or '100' or '5.85%'."""
    if not value:
        return None
    try:
        # Strip % sign and whitespace
        cleaned = value.replace("%", "").replace(",", "").strip()
        # Strip any non-numeric trailing chars
        m = re.search(r"^[\-+]?[\d.]+", cleaned)
        if m:
            return float(m.group(0))
    except (ValueError, TypeError):
        pass
    return None


def _set_quality_flag(result: Schedule13DResult) -> None:
    """Auto-set quality_flag if data looks suspicious."""
    # Multi-filer with first entry at 100% — likely parent ownership
    if (result.percentage is not None and result.percentage >= 100
            and len(result.all_reporting_persons) > 1):
        result.quality_flag = "pct_100_likely_multi_filer"
        return

    # Suspicious share count (likely SEC filing error or non-equity unit)
    if result.shares_owned is not None and result.shares_owned > SHARES_LIKELY_ERROR:
        result.quality_flag = "shares_over_1b_review"
        return

    # Original filing with 0% — parser may have grabbed wrong row
    if (result.percentage == 0 and not result.is_amendment):
        result.quality_flag = "zero_pct_original_review"
        return

    # Inconsistent: has percentage but no shares
    if (result.percentage and result.percentage > 0
            and (not result.shares_owned or result.shares_owned == 0)):
        result.quality_flag = "shares_zero_inconsistent"
        return
