"""Parser for SEC Schedule 13D/13D-A filings.

Extracts structured data from the XSLT-rendered HTML that SEC serves for
Schedule 13D filings. The key extraction targets are:

- Cover page: filer name, reporting person type, shares owned, percentage
- Item 4 (Purpose of Transaction): raw text for downstream classification
- Filing metadata: amendment status, filing date
"""

import logging
import re
from dataclasses import dataclass, field
from typing import Optional

from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)


@dataclass
class Schedule13DResult:
    """Result of parsing a Schedule 13D filing."""

    # Filing metadata (from EFTS, passed in)
    accession_number: str = ""
    filing_type: str = ""  # "SCHEDULE 13D" or "SCHEDULE 13D/A"
    filing_date: str = ""

    # Filer info (from cover page)
    filer_name: str = ""
    filer_cik: str = ""
    reporting_person_type: str = ""  # Row 14: IA, IN, CO, HC, etc.
    citizenship: str = ""  # Row 6

    # Target info (from EFTS or Item 1)
    target_name: str = ""
    target_cik: str = ""

    # Stake info (from cover page)
    shares_owned: Optional[int] = None  # Row 11: aggregate amount
    percentage: Optional[float] = None  # Row 13: percent of class
    sole_voting_power: Optional[int] = None  # Row 7
    shared_voting_power: Optional[int] = None  # Row 8

    # Purpose (Item 4) — raw text
    purpose_text: str = ""

    # Amendment info
    is_amendment: bool = False
    amendment_number: Optional[int] = None

    # Filing URL
    filing_url: str = ""

    # Parse quality
    parse_errors: list[str] = field(default_factory=list)


def parse_schedule_13d(html: str, metadata: Optional[dict] = None) -> Schedule13DResult:
    """
    Parse a Schedule 13D filing from its rendered HTML.

    Args:
        html: The HTML content of the filing (from www.sec.gov XSLT render)
        metadata: Optional dict with EFTS fields (accession_number, filing_type,
                  filing_date, target_cik, target_name, filer_cik, filer_name)

    Returns:
        Schedule13DResult with extracted fields
    """
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

    text = soup.get_text(separator="\n", strip=True)

    # Extract amendment number from the header
    result.amendment_number = _extract_amendment_number(text)

    # Parse cover page rows
    _parse_cover_page(text, result)

    # Parse Item 4 (Purpose of Transaction)
    _parse_item4(text, result)

    # Parse Item 1 for target name if not from EFTS
    if not result.target_name:
        _parse_item1(text, result)

    return result


def _extract_amendment_number(text: str) -> Optional[int]:
    """Extract amendment number from '(Amendment No. X)' in the header.

    The number may be on the same line or a separate line in the rendered HTML.
    """
    match = re.search(r"\(Amendment\s+No\.?\s*\n?\s*(\d+)\s*\n?\s*\)", text, re.IGNORECASE)
    if match:
        return int(match.group(1))
    return None


def _parse_cover_page(text: str, result: Schedule13DResult) -> None:
    """Extract structured data from the numbered cover page rows."""

    # Row 1: Name of reporting person (filer)
    # Only overwrite if we didn't get it from EFTS
    if not result.filer_name:
        match = re.search(
            r"1\s*\n\s*Name of reporting person\s*\n\s*(.+)",
            text, re.IGNORECASE
        )
        if match:
            result.filer_name = match.group(1).strip()

    # Row 6: Citizenship or place of organization
    match = re.search(
        r"6\s*\n\s*Citizenship or place of organization\s*\n\s*(.+)",
        text, re.IGNORECASE
    )
    if match:
        result.citizenship = match.group(1).strip()

    # Row 11: Aggregate amount beneficially owned
    match = re.search(
        r"11\s*\n\s*Aggregate amount beneficially owned[^\n]*\n\s*([\d,\.]+)",
        text, re.IGNORECASE
    )
    if match:
        result.shares_owned = _parse_int(match.group(1))

    # Row 13: Percent of class
    match = re.search(
        r"13\s*\n\s*Percent of class[^\n]*\n\s*([\d\.]+)\s*%?",
        text, re.IGNORECASE
    )
    if match:
        try:
            result.percentage = float(match.group(1))
        except ValueError:
            result.parse_errors.append(f"Could not parse percentage: {match.group(1)}")

    # Row 14: Type of Reporting Person
    match = re.search(
        r"14\s*\n\s*Type of Reporting Person[^\n]*\n\s*([A-Z]{2})",
        text, re.IGNORECASE
    )
    if match:
        result.reporting_person_type = match.group(1).upper()

    # Row 7: Sole Voting Power
    match = re.search(
        r"7\s*\n\s*Sole Voting Power\s*\n\s*([\d,\.]+)",
        text, re.IGNORECASE
    )
    if match:
        result.sole_voting_power = _parse_int(match.group(1))

    # Row 8: Shared Voting Power
    match = re.search(
        r"8\s*\n\s*Shared Voting Power\s*\n\s*([\d,\.]+)",
        text, re.IGNORECASE
    )
    if match:
        result.shared_voting_power = _parse_int(match.group(1))


def _parse_item4(text: str, result: Schedule13DResult) -> None:
    """Extract Item 4 (Purpose of Transaction) text."""
    # Find Item 4 section
    item4_match = re.search(r"Item\s+4\.?\s*\n\s*Purpose of Transaction", text, re.IGNORECASE)
    if not item4_match:
        result.parse_errors.append("Could not find Item 4 section")
        return

    # Find where Item 5 starts (end boundary for Item 4)
    item5_match = re.search(r"Item\s+5\.?\s*\n\s*Interest in Securities", text[item4_match.end():], re.IGNORECASE)

    if item5_match:
        raw = text[item4_match.end():item4_match.end() + item5_match.start()]
    else:
        # Take up to 2000 chars if we can't find Item 5
        raw = text[item4_match.end():item4_match.end() + 2000]

    # Clean up the text
    purpose = raw.strip()
    # Remove leading section label remnants
    purpose = re.sub(r"^\s*Purpose of Transaction\s*", "", purpose, flags=re.IGNORECASE).strip()

    result.purpose_text = purpose


def _parse_item1(text: str, result: Schedule13DResult) -> None:
    """Extract target company name from Item 1 if not already set."""
    match = re.search(
        r"Item\s+1\.?\s*\n\s*Security and Issuer.*?"
        r"Name of Issuer:\s*\n?\s*(.+?)(?:\n|$)",
        text, re.IGNORECASE | re.DOTALL
    )
    if match:
        result.target_name = match.group(1).strip().rstrip(".")


def _parse_int(value: str) -> Optional[int]:
    """Parse an integer from a string, handling commas and decimals."""
    try:
        cleaned = value.replace(",", "").replace("'", "").strip()
        # Handle values like "2,872,185.00"
        if "." in cleaned:
            return int(float(cleaned))
        return int(cleaned)
    except (ValueError, TypeError):
        return None
