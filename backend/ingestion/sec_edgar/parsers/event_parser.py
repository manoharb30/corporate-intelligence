"""Parser for 8-K material event filings."""

import re
import logging
from dataclasses import dataclass, field
from typing import Optional
from datetime import datetime

logger = logging.getLogger(__name__)


# 8-K Item definitions - what each item type means
ITEM_DEFINITIONS = {
    "1.01": {
        "name": "Entry into Material Agreement",
        "signal": "material_agreement",
        "description": "Company entered into a material definitive agreement",
    },
    "1.02": {
        "name": "Termination of Material Agreement",
        "signal": "agreement_terminated",
        "description": "Material definitive agreement was terminated",
    },
    "1.03": {
        "name": "Bankruptcy or Receivership",
        "signal": "bankruptcy",
        "description": "Company entered bankruptcy or receivership",
    },
    "2.01": {
        "name": "Completion of Acquisition or Disposition",
        "signal": "acquisition_disposition",
        "description": "Completed acquisition or disposition of assets",
    },
    "2.03": {
        "name": "Creation of Direct Financial Obligation",
        "signal": "new_debt",
        "description": "Created a direct financial obligation or off-balance sheet arrangement",
    },
    "2.04": {
        "name": "Triggering Events for Acceleration of Obligations",
        "signal": "debt_acceleration",
        "description": "Triggering events that accelerate or increase financial obligations",
    },
    "2.05": {
        "name": "Costs for Exit or Disposal Activities",
        "signal": "restructuring",
        "description": "Costs associated with exit or disposal activities",
    },
    "2.06": {
        "name": "Material Impairments",
        "signal": "impairment",
        "description": "Material impairments to assets",
    },
    "3.01": {
        "name": "Notice of Delisting",
        "signal": "delisting",
        "description": "Notice of delisting or failure to satisfy listing rules",
    },
    "3.02": {
        "name": "Unregistered Sales of Equity Securities",
        "signal": "equity_sale",
        "description": "Unregistered sales of equity securities",
    },
    "3.03": {
        "name": "Material Modification to Rights",
        "signal": "rights_modification",
        "description": "Material modification to rights of security holders",
    },
    "4.01": {
        "name": "Changes in Accountant",
        "signal": "auditor_change",
        "description": "Changes in registrant's certifying accountant",
    },
    "4.02": {
        "name": "Non-Reliance on Financial Statements",
        "signal": "restatement",
        "description": "Non-reliance on previously issued financial statements",
    },
    "5.01": {
        "name": "Changes in Control",
        "signal": "control_change",
        "description": "Changes in control of registrant",
    },
    "5.02": {
        "name": "Departure/Appointment of Officers/Directors",
        "signal": "executive_change",
        "description": "Departure or election of directors; appointment of principal officers",
    },
    "5.03": {
        "name": "Amendments to Articles/Bylaws",
        "signal": "governance_change",
        "description": "Amendments to articles of incorporation or bylaws",
    },
    "5.04": {
        "name": "Temporary Suspension of Trading",
        "signal": "trading_suspended",
        "description": "Temporary suspension of trading under employee benefit plans",
    },
    "5.05": {
        "name": "Amendment to Code of Ethics",
        "signal": "ethics_change",
        "description": "Amendments to, or waivers from, code of ethics",
    },
    "5.06": {
        "name": "Change in Shell Company Status",
        "signal": "shell_status_change",
        "description": "Change in shell company status",
    },
    "5.07": {
        "name": "Shareholder Vote Results",
        "signal": "vote_results",
        "description": "Submission of matters to a vote of security holders",
    },
    "5.08": {
        "name": "Shareholder Nominations",
        "signal": "nominations",
        "description": "Shareholder director nominations",
    },
    "7.01": {
        "name": "Regulation FD Disclosure",
        "signal": "reg_fd",
        "description": "Regulation FD disclosure",
    },
    "8.01": {
        "name": "Other Events",
        "signal": "other",
        "description": "Other events the company considers important",
    },
    "9.01": {
        "name": "Financial Statements and Exhibits",
        "signal": "exhibits",
        "description": "Financial statements and exhibits",
    },
}

# Items we care about for M&A signals
MA_SIGNAL_ITEMS = ["1.01", "2.01", "3.03", "5.01", "5.02", "5.03"]


@dataclass
class ExtractedEvent:
    """A single event extracted from an 8-K filing."""

    item_number: str
    item_name: str
    signal_type: str
    description: str
    raw_text: str  # Extracted text for this item
    persons_mentioned: list[str] = field(default_factory=list)
    companies_mentioned: list[str] = field(default_factory=list)
    is_ma_signal: bool = False


@dataclass
class Filing8KResult:
    """Result of parsing an 8-K filing."""

    cik: str
    company_name: str
    accession_number: str
    filing_date: str
    events: list[ExtractedEvent] = field(default_factory=list)
    has_ma_signals: bool = False
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "cik": self.cik,
            "company_name": self.company_name,
            "accession_number": self.accession_number,
            "filing_date": self.filing_date,
            "events": [
                {
                    "item_number": e.item_number,
                    "item_name": e.item_name,
                    "signal_type": e.signal_type,
                    "description": e.description,
                    "is_ma_signal": e.is_ma_signal,
                    "persons_mentioned": e.persons_mentioned,
                    "raw_text": e.raw_text[:500] if e.raw_text else "",
                }
                for e in self.events
            ],
            "has_ma_signals": self.has_ma_signals,
            "ma_signals": [e.item_number for e in self.events if e.is_ma_signal],
        }


class EventParser:
    """Parser for 8-K material event filings."""

    # Regex patterns for finding Item numbers
    ITEM_PATTERN = re.compile(
        r'Item\s*(\d+\.\d+)[.\s]*([^\n<]{0,100})',
        re.IGNORECASE
    )

    def __init__(self):
        pass

    def parse_8k(
        self,
        html_content: str,
        cik: str,
        company_name: str,
        accession_number: str,
        filing_date: str,
    ) -> Filing8KResult:
        """
        Parse an 8-K filing and extract events.

        Args:
            html_content: Raw HTML content of the 8-K filing
            cik: Company CIK
            company_name: Company name
            accession_number: Filing accession number
            filing_date: Filing date

        Returns:
            Filing8KResult with extracted events
        """
        result = Filing8KResult(
            cik=cik,
            company_name=company_name,
            accession_number=accession_number,
            filing_date=filing_date,
        )

        # Clean HTML to text
        text = self._clean_html(html_content)

        # Find all Item mentions
        items_found = self._find_items(text)

        if not items_found:
            result.warnings.append("No Item numbers found in filing")
            return result

        # Extract content for each item
        for item_number, start_pos in items_found:
            event = self._extract_item_content(text, item_number, start_pos, items_found)
            if event:
                result.events.append(event)

                if event.is_ma_signal:
                    result.has_ma_signals = True

        return result

    def _clean_html(self, html: str) -> str:
        """Remove HTML tags and clean up text."""
        # Remove style and script tags
        text = re.sub(r'<style[^>]*>.*?</style>', '', html, flags=re.DOTALL | re.IGNORECASE)
        text = re.sub(r'<script[^>]*>.*?</script>', '', text, flags=re.DOTALL | re.IGNORECASE)

        # Remove HTML tags
        text = re.sub(r'<[^>]+>', ' ', text)

        # Decode HTML entities
        text = re.sub(r'&nbsp;', ' ', text)
        text = re.sub(r'&amp;', '&', text)
        text = re.sub(r'&lt;', '<', text)
        text = re.sub(r'&gt;', '>', text)
        text = re.sub(r'&#\d+;', ' ', text)
        text = re.sub(r'&[a-z]+;', ' ', text, flags=re.IGNORECASE)

        # Normalize whitespace
        text = re.sub(r'\s+', ' ', text)

        return text

    def _find_items(self, text: str) -> list[tuple[str, int]]:
        """Find all Item numbers and their positions in the text."""
        items = []
        seen = set()

        for match in self.ITEM_PATTERN.finditer(text):
            item_number = match.group(1)

            # Normalize to X.XX format
            if '.' in item_number:
                parts = item_number.split('.')
                item_number = f"{parts[0]}.{parts[1].zfill(2)}"

            # Skip duplicates (keep first occurrence)
            if item_number not in seen:
                seen.add(item_number)
                items.append((item_number, match.start()))

        return items

    def _extract_item_content(
        self,
        text: str,
        item_number: str,
        start_pos: int,
        all_items: list[tuple[str, int]],
    ) -> Optional[ExtractedEvent]:
        """Extract content for a specific Item."""
        # Find end position (start of next item or end of text)
        end_pos = len(text)
        for other_item, other_pos in all_items:
            if other_pos > start_pos:
                end_pos = other_pos
                break

        # Extract text for this item (limit to reasonable size)
        item_text = text[start_pos:min(end_pos, start_pos + 5000)]

        # Get item definition
        item_def = ITEM_DEFINITIONS.get(item_number, {
            "name": f"Item {item_number}",
            "signal": "unknown",
            "description": "Unknown item type",
        })

        # Check if this is an M&A signal
        is_ma_signal = item_number in MA_SIGNAL_ITEMS

        # Extract persons mentioned
        persons = self._extract_persons(item_text)

        event = ExtractedEvent(
            item_number=item_number,
            item_name=item_def["name"],
            signal_type=item_def["signal"],
            description=item_def["description"],
            raw_text=item_text.strip(),
            persons_mentioned=persons,
            is_ma_signal=is_ma_signal,
        )

        return event

    def _extract_persons(self, text: str) -> list[str]:
        """Extract person names from text.

        Regex-based extraction is disabled due to high false-positive rate
        (e.g. 'Material Definitive', 'Effective Da'). Person extraction is
        handled by LLM analysis in llm_analysis_service.py instead.
        """
        return []

    def get_ma_signal_summary(self, result: Filing8KResult) -> Optional[str]:
        """Generate a summary of M&A signals in a filing."""
        if not result.has_ma_signals:
            return None

        summaries = []
        for event in result.events:
            if event.is_ma_signal:
                if event.item_number == "5.02" and event.persons_mentioned:
                    summaries.append(
                        f"Executive change: {', '.join(event.persons_mentioned[:3])}"
                    )
                elif event.item_number == "2.01":
                    summaries.append("Acquisition or disposition completed")
                elif event.item_number == "5.01":
                    summaries.append("Change in control")
                elif event.item_number == "1.01":
                    summaries.append("Material agreement entered")
                elif event.item_number == "5.03":
                    summaries.append("Governance/bylaw changes")

        if summaries:
            return f"{result.company_name}: {'; '.join(summaries)}"
        return None
