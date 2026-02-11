"""Tests for the Form 4 (insider trading) parser."""

import pytest

from ingestion.sec_edgar.parsers.form4_parser import Form4Parser, TRANSACTION_CODES
from app.services.insider_trading_service import InsiderTradingService


SAMPLE_FORM4_XML = """<?xml version="1.0"?>
<ownershipDocument>
    <schemaVersion>X0306</schemaVersion>
    <documentType>4</documentType>
    <periodOfReport>2023-09-15</periodOfReport>
    <issuer>
        <issuerCik>0000789019</issuerCik>
        <issuerName>SPLUNK INC</issuerName>
        <issuerTradingSymbol>SPLK</issuerTradingSymbol>
    </issuer>
    <reportingOwner>
        <reportingOwnerId>
            <rptOwnerCik>0001234567</rptOwnerCik>
            <rptOwnerName>DOE JOHN A</rptOwnerName>
        </reportingOwnerId>
        <reportingOwnerAddress>
            <rptOwnerStreet1>123 MAIN ST</rptOwnerStreet1>
            <rptOwnerCity>SAN FRANCISCO</rptOwnerCity>
            <rptOwnerState>CA</rptOwnerState>
            <rptOwnerZipCode>94105</rptOwnerZipCode>
        </reportingOwnerAddress>
        <reportingOwnerRelationship>
            <isDirector>1</isDirector>
            <isOfficer>1</isOfficer>
            <isTenPercentOwner>0</isTenPercentOwner>
            <isOther>0</isOther>
            <officerTitle>Chief Executive Officer</officerTitle>
        </reportingOwnerRelationship>
    </reportingOwner>
    <nonDerivativeTable>
        <nonDerivativeTransaction>
            <securityTitle>
                <value>Common Stock</value>
            </securityTitle>
            <transactionDate>
                <value>2023-09-15</value>
            </transactionDate>
            <transactionCoding>
                <transactionFormType>4</transactionFormType>
                <transactionCode>P</transactionCode>
                <equitySwapInvolved>0</equitySwapInvolved>
            </transactionCoding>
            <transactionAmounts>
                <transactionShares>
                    <value>5000</value>
                </transactionShares>
                <transactionPricePerShare>
                    <value>150.00</value>
                </transactionPricePerShare>
                <transactionAcquiredDisposedCode>
                    <value>A</value>
                </transactionAcquiredDisposedCode>
            </transactionAmounts>
            <postTransactionAmounts>
                <sharesOwnedFollowingTransaction>
                    <value>25000</value>
                </sharesOwnedFollowingTransaction>
            </postTransactionAmounts>
            <ownershipNature>
                <directOrIndirectOwnership>
                    <value>D</value>
                </directOrIndirectOwnership>
            </ownershipNature>
        </nonDerivativeTransaction>
        <nonDerivativeTransaction>
            <securityTitle>
                <value>Common Stock</value>
            </securityTitle>
            <transactionDate>
                <value>2023-09-14</value>
            </transactionDate>
            <transactionCoding>
                <transactionFormType>4</transactionFormType>
                <transactionCode>S</transactionCode>
                <equitySwapInvolved>0</equitySwapInvolved>
            </transactionCoding>
            <transactionAmounts>
                <transactionShares>
                    <value>2000</value>
                </transactionShares>
                <transactionPricePerShare>
                    <value>148.50</value>
                </transactionPricePerShare>
                <transactionAcquiredDisposedCode>
                    <value>D</value>
                </transactionAcquiredDisposedCode>
            </transactionAmounts>
            <postTransactionAmounts>
                <sharesOwnedFollowingTransaction>
                    <value>20000</value>
                </sharesOwnedFollowingTransaction>
            </postTransactionAmounts>
            <ownershipNature>
                <directOrIndirectOwnership>
                    <value>D</value>
                </directOrIndirectOwnership>
            </ownershipNature>
        </nonDerivativeTransaction>
    </nonDerivativeTable>
    <derivativeTable>
        <derivativeTransaction>
            <securityTitle>
                <value>Stock Option (Right to Buy)</value>
            </securityTitle>
            <transactionDate>
                <value>2023-09-15</value>
            </transactionDate>
            <transactionCoding>
                <transactionFormType>4</transactionFormType>
                <transactionCode>M</transactionCode>
                <equitySwapInvolved>0</equitySwapInvolved>
            </transactionCoding>
            <transactionAmounts>
                <transactionShares>
                    <value>1000</value>
                </transactionShares>
                <transactionPricePerShare>
                    <value>100.00</value>
                </transactionPricePerShare>
                <transactionAcquiredDisposedCode>
                    <value>D</value>
                </transactionAcquiredDisposedCode>
            </transactionAmounts>
            <postTransactionAmounts>
                <sharesOwnedFollowingTransaction>
                    <value>9000</value>
                </sharesOwnedFollowingTransaction>
            </postTransactionAmounts>
            <ownershipNature>
                <directOrIndirectOwnership>
                    <value>D</value>
                </directOrIndirectOwnership>
            </ownershipNature>
        </derivativeTransaction>
    </derivativeTable>
</ownershipDocument>
"""

SAMPLE_HTML_FORM4 = """<html>
<head><title>Form 4</title></head>
<body>
<h1>FORM 4 - STATEMENT OF CHANGES IN BENEFICIAL OWNERSHIP</h1>
<p>This is an old HTML-based Form 4 that cannot be parsed as XML.</p>
</body>
</html>"""


class TestForm4Parser:
    """Tests for Form4Parser."""

    def setup_method(self):
        self.parser = Form4Parser()

    def test_parse_valid_xml(self):
        """Test parsing a valid Form 4 XML."""
        result = self.parser.parse_form4(
            xml_content=SAMPLE_FORM4_XML,
            accession_number="0001234567-23-000001",
            filing_date="2023-09-16",
        )

        assert result is not None
        assert result.issuer_cik == "0000789019"
        assert result.issuer_name == "SPLUNK INC"
        assert result.accession_number == "0001234567-23-000001"
        assert result.filing_date == "2023-09-16"

    def test_parse_insider_info(self):
        """Test insider information extraction."""
        result = self.parser.parse_form4(
            xml_content=SAMPLE_FORM4_XML,
            accession_number="0001234567-23-000001",
            filing_date="2023-09-16",
        )

        assert result.insider.name == "DOE JOHN A"
        assert result.insider.cik == "0001234567"
        assert result.insider.title == "Chief Executive Officer"
        assert result.insider.is_officer is True
        assert result.insider.is_director is True
        assert result.insider.is_ten_percent_owner is False

    def test_parse_transactions(self):
        """Test transaction extraction."""
        result = self.parser.parse_form4(
            xml_content=SAMPLE_FORM4_XML,
            accession_number="0001234567-23-000001",
            filing_date="2023-09-16",
        )

        # Should have 3 transactions: 2 non-derivative + 1 derivative
        assert len(result.transactions) == 3

        # First transaction: Purchase
        purchase = result.transactions[0]
        assert purchase.transaction_code == "P"
        assert purchase.transaction_type == "Purchase"
        assert purchase.shares == 5000
        assert purchase.price_per_share == 150.00
        assert purchase.total_value == 750000.00
        assert purchase.shares_after_transaction == 25000
        assert purchase.ownership_type == "D"
        assert purchase.is_derivative is False
        assert purchase.security_title == "Common Stock"

        # Second transaction: Sale
        sale = result.transactions[1]
        assert sale.transaction_code == "S"
        assert sale.transaction_type == "Sale"
        assert sale.shares == 2000
        assert sale.price_per_share == 148.50
        assert sale.total_value == 297000.00
        assert sale.is_derivative is False

        # Third transaction: Derivative exercise
        exercise = result.transactions[2]
        assert exercise.transaction_code == "M"
        assert exercise.transaction_type == "Exercise"
        assert exercise.is_derivative is True

    def test_net_shares(self):
        """Test net shares calculation."""
        result = self.parser.parse_form4(
            xml_content=SAMPLE_FORM4_XML,
            accession_number="0001234567-23-000001",
            filing_date="2023-09-16",
        )

        # P: +5000, S: -2000, M: +1000 = +4000
        assert result.net_shares == 4000

    def test_has_purchases_and_sales(self):
        """Test purchase/sale detection."""
        result = self.parser.parse_form4(
            xml_content=SAMPLE_FORM4_XML,
            accession_number="0001234567-23-000001",
            filing_date="2023-09-16",
        )

        assert result.has_purchases is True
        assert result.has_sales is True
        assert result.total_purchase_value == 750000.00

    def test_skip_non_xml(self):
        """Test that non-XML filings are gracefully skipped."""
        result = self.parser.parse_form4(
            xml_content=SAMPLE_HTML_FORM4,
            accession_number="0001234567-23-000002",
            filing_date="2023-09-16",
        )

        assert result is None

    def test_skip_invalid_xml(self):
        """Test that invalid XML is handled gracefully."""
        result = self.parser.parse_form4(
            xml_content="<?xml version='1.0'?><broken><unclosed>",
            accession_number="0001234567-23-000003",
            filing_date="2023-09-16",
        )

        assert result is None


class TestInsiderSignalClassification:
    """Tests for insider trading signal classification."""

    def test_cluster_buy_high_signal(self):
        """3+ insiders buying = HIGH signal."""
        from datetime import datetime
        today = datetime.now().strftime("%Y-%m-%d")

        trades = [
            {"insider_name": "Alice", "code": "P", "total_value": 100000, "txn_date": today},
            {"insider_name": "Bob", "code": "P", "total_value": 200000, "txn_date": today},
            {"insider_name": "Charlie", "code": "P", "total_value": 150000, "txn_date": today},
        ]

        level, summary = InsiderTradingService.classify_insider_signal(trades, days=30)
        assert level == "high"
        assert "Cluster Buy" in summary

    def test_two_buyers_medium_signal(self):
        """2 insiders buying = MEDIUM signal."""
        from datetime import datetime
        today = datetime.now().strftime("%Y-%m-%d")

        trades = [
            {"insider_name": "Alice", "code": "P", "total_value": 100000, "txn_date": today},
            {"insider_name": "Bob", "code": "P", "total_value": 200000, "txn_date": today},
        ]

        level, _ = InsiderTradingService.classify_insider_signal(trades, days=30)
        assert level == "medium"

    def test_large_purchase_medium_signal(self):
        """Single purchase >$500K = MEDIUM signal."""
        from datetime import datetime
        today = datetime.now().strftime("%Y-%m-%d")

        trades = [
            {"insider_name": "Alice", "code": "P", "total_value": 600000, "txn_date": today},
        ]

        level, summary = InsiderTradingService.classify_insider_signal(trades, days=30)
        assert level == "medium"
        assert "Large purchase" in summary

    def test_single_purchase_low_signal(self):
        """Single small purchase = LOW signal."""
        from datetime import datetime
        today = datetime.now().strftime("%Y-%m-%d")

        trades = [
            {"insider_name": "Alice", "code": "P", "total_value": 50000, "txn_date": today},
        ]

        level, _ = InsiderTradingService.classify_insider_signal(trades, days=30)
        assert level == "low"

    def test_no_purchases_none_signal(self):
        """No purchases = NONE signal."""
        from datetime import datetime
        today = datetime.now().strftime("%Y-%m-%d")

        trades = [
            {"insider_name": "Alice", "code": "S", "total_value": 500000, "txn_date": today},
            {"insider_name": "Bob", "code": "A", "total_value": 0, "txn_date": today},
        ]

        level, _ = InsiderTradingService.classify_insider_signal(trades, days=30)
        assert level == "none"

    def test_old_trades_ignored(self):
        """Trades older than the window are not counted."""
        trades = [
            {"insider_name": "Alice", "code": "P", "total_value": 600000, "txn_date": "2020-01-01"},
            {"insider_name": "Bob", "code": "P", "total_value": 600000, "txn_date": "2020-01-01"},
            {"insider_name": "Charlie", "code": "P", "total_value": 600000, "txn_date": "2020-01-01"},
        ]

        level, _ = InsiderTradingService.classify_insider_signal(trades, days=30)
        assert level == "none"


class TestTransactionCodes:
    """Test that all transaction codes are defined."""

    def test_all_codes_have_names(self):
        """All transaction codes should have human-readable names."""
        expected_codes = ["P", "S", "A", "M", "F", "G", "D", "C", "W", "J", "K", "U", "I"]
        for code in expected_codes:
            assert code in TRANSACTION_CODES
            assert len(TRANSACTION_CODES[code]) > 0
