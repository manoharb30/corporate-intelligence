"""Parser for SEC Form 4 (insider trading) filings."""

import logging
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from typing import Optional

logger = logging.getLogger(__name__)

# Transaction code definitions
TRANSACTION_CODES = {
    "P": "Purchase",
    "S": "Sale",
    "A": "Award",
    "M": "Exercise",
    "F": "Tax",
    "G": "Gift",
    "D": "Disposition",
    "C": "Conversion",
    "W": "Acquisition Due to Will/Inheritance",
    "J": "Other",
    "K": "Equity Swap",
    "U": "Tender of Shares",
    "I": "Discretionary Transaction",
}


@dataclass
class InsiderInfo:
    """Information about the reporting insider."""

    name: str
    cik: str
    title: str = ""
    is_officer: bool = False
    is_director: bool = False
    is_ten_percent_owner: bool = False


@dataclass
class InsiderTransaction:
    """A single insider transaction from a Form 4."""

    security_title: str
    transaction_date: str
    transaction_code: str
    transaction_type: str  # Human-readable from TRANSACTION_CODES
    shares: float
    price_per_share: float
    total_value: float
    shares_after_transaction: float
    ownership_type: str  # "D" = Direct, "I" = Indirect
    is_derivative: bool = False


@dataclass
class Form4Result:
    """Result of parsing a Form 4 filing."""

    issuer_cik: str
    issuer_name: str
    insider: InsiderInfo
    accession_number: str
    filing_date: str
    transactions: list[InsiderTransaction] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def net_shares(self) -> float:
        """Net shares change (positive = net buying)."""
        total = 0.0
        for t in self.transactions:
            if t.transaction_code in ("P", "A", "M", "C", "W"):
                total += t.shares
            elif t.transaction_code in ("S", "F", "G", "D"):
                total -= t.shares
        return total

    @property
    def has_purchases(self) -> bool:
        return any(t.transaction_code == "P" for t in self.transactions)

    @property
    def has_sales(self) -> bool:
        return any(t.transaction_code == "S" for t in self.transactions)

    @property
    def total_purchase_value(self) -> float:
        return sum(t.total_value for t in self.transactions if t.transaction_code == "P")


class Form4Parser:
    """Parser for SEC Form 4 XML filings."""

    def parse_form4(
        self,
        xml_content: str,
        accession_number: str,
        filing_date: str,
    ) -> Optional[Form4Result]:
        """
        Parse a Form 4 XML filing.

        Args:
            xml_content: Raw XML content of the Form 4 filing
            accession_number: Filing accession number
            filing_date: Filing date

        Returns:
            Form4Result with parsed data, or None if not valid XML
        """
        # Skip non-XML filings (pre-2005 HTML Form 4s)
        stripped = xml_content.strip()
        if not stripped.startswith("<?xml") and not stripped.startswith("<ownershipDocument"):
            logger.warning(f"Skipping non-XML Form 4: {accession_number}")
            return None

        try:
            root = ET.fromstring(xml_content)
        except ET.ParseError as e:
            logger.warning(f"Failed to parse Form 4 XML {accession_number}: {e}")
            return None

        # Extract issuer info
        issuer = root.find(".//issuer")
        issuer_cik = self._get_text(issuer, "issuerCik", "")
        issuer_name = self._get_text(issuer, "issuerName", "")

        # Extract reporting owner info
        insider = self._parse_owner(root)
        if not insider:
            return None

        result = Form4Result(
            issuer_cik=issuer_cik,
            issuer_name=issuer_name,
            insider=insider,
            accession_number=accession_number,
            filing_date=filing_date,
        )

        # Parse non-derivative transactions
        for txn_elem in root.findall(".//nonDerivativeTransaction"):
            txn = self._parse_transaction(txn_elem, is_derivative=False)
            if txn:
                result.transactions.append(txn)

        # Parse derivative transactions
        for txn_elem in root.findall(".//derivativeTransaction"):
            txn = self._parse_transaction(txn_elem, is_derivative=True)
            if txn:
                result.transactions.append(txn)

        return result

    def _parse_owner(self, root: ET.Element) -> Optional[InsiderInfo]:
        """Parse reporting owner information."""
        owner = root.find(".//reportingOwner")
        if owner is None:
            return None

        owner_id = owner.find("reportingOwnerId")
        name = self._get_text(owner_id, "rptOwnerName", "")
        cik = self._get_text(owner_id, "rptOwnerCik", "")

        if not name:
            return None

        rel = owner.find("reportingOwnerRelationship")
        is_officer = self._get_text(rel, "isOfficer", "0") == "1"
        is_director = self._get_text(rel, "isDirector", "0") == "1"
        is_ten_percent = self._get_text(rel, "isTenPercentOwner", "0") == "1"
        title = self._get_text(rel, "officerTitle", "")

        return InsiderInfo(
            name=name,
            cik=cik,
            title=title,
            is_officer=is_officer,
            is_director=is_director,
            is_ten_percent_owner=is_ten_percent,
        )

    def _parse_transaction(
        self, elem: ET.Element, is_derivative: bool
    ) -> Optional[InsiderTransaction]:
        """Parse a single transaction element."""
        security_title = self._get_text(
            elem.find("securityTitle"), "value", "Unknown"
        )

        # Transaction date
        txn_date = self._get_text(
            elem.find("transactionDate"), "value", ""
        )

        # Transaction coding
        coding = elem.find("transactionCoding")
        txn_code = self._get_text(coding, "transactionCode", "")
        if not txn_code:
            return None

        txn_type = TRANSACTION_CODES.get(txn_code, "Unknown")

        # Transaction amounts
        amounts = elem.find("transactionAmounts")
        shares = self._get_float(amounts, "transactionShares/value", 0.0)
        price = self._get_float(amounts, "transactionPricePerShare/value", 0.0)
        total_value = shares * price

        # Post-transaction holdings
        post_holdings = elem.find("postTransactionAmounts")
        shares_after = self._get_float(
            post_holdings, "sharesOwnedFollowingTransaction/value", 0.0
        )

        # Ownership type
        ownership_elem = elem.find("ownershipNature")
        ownership_type = self._get_text(
            ownership_elem, "directOrIndirectOwnership/value", "D"
        )

        return InsiderTransaction(
            security_title=security_title,
            transaction_date=txn_date,
            transaction_code=txn_code,
            transaction_type=txn_type,
            shares=shares,
            price_per_share=price,
            total_value=total_value,
            shares_after_transaction=shares_after,
            ownership_type=ownership_type,
            is_derivative=is_derivative,
        )

    @staticmethod
    def _get_text(
        parent: Optional[ET.Element], path: str, default: str
    ) -> str:
        """Safely get text from an XML element."""
        if parent is None:
            return default
        elem = parent.find(path)
        if elem is None or elem.text is None:
            return default
        return elem.text.strip()

    @staticmethod
    def _get_float(
        parent: Optional[ET.Element], path: str, default: float
    ) -> float:
        """Safely get a float value from an XML element."""
        if parent is None:
            return default
        elem = parent.find(path)
        if elem is None or elem.text is None:
            return default
        try:
            return float(elem.text.strip())
        except (ValueError, TypeError):
            return default
