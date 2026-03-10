"""Tests for the Schedule 13D parser."""

import pytest

from ingestion.sec_edgar.parsers.schedule13_parser import (
    parse_schedule_13d,
    Schedule13DResult,
    _extract_amendment_number,
    _parse_int,
)
from app.services.activist_filing_service import classify_signal_level, build_signal_summary


# Minimal 13D HTML fixture (modeled on the real XSLT-rendered format)
SAMPLE_13D_HTML = """
<html xmlns:p="http://www.sec.gov/edgar/schedule13D">
<head><title>SCHEDULE 13D</title></head>
<body>
<div>
SECURITIES AND EXCHANGE COMMISSION
Washington, D.C. 20549
SCHEDULE 13D
Under the Securities Exchange Act of 1934
(Amendment No.
6
)
Five9, Inc.
(Name of Issuer)
COMMON STOCK
(Title of Class of Securities)
</div>
<div>
SCHEDULE 13D
CUSIP Number(s):
1
Name of reporting person
PICTET ASSET MANAGEMENT SA
2
Check the appropriate box if a member of a Group (See Instructions)
(a)
(b)
3
SEC use only
4
Source of funds (See Instructions)
WC
5
Check if disclosure of legal proceedings is required pursuant to Items 2(d) or 2(e)
6
Citizenship or place of organization
SWITZERLAND
Number of Shares Beneficially Owned by Each Reporting Person With:
7
Sole Voting Power
2,865,052.00
8
Shared Voting Power
0.00
9
Sole Dispositive Power
2,872,185.00
10
Shared Dispositive Power
0.00
11
Aggregate amount beneficially owned by each reporting person
2,872,185.00
12
Check if the aggregate amount in Row (11) excludes certain shares (See Instructions)
13
Percent of class represented by amount in Row (11)
3.8 %
14
Type of Reporting Person (See Instructions)
IA
</div>
<div>
Item 1.
Security and Issuer
(a)
Title of Class of Securities:
COMMON STOCK
(b)
Name of Issuer:
Five9, Inc.
(c)
Address of Issuer's Principal Executive Offices:
SAN RAMON, CALIFORNIA
</div>
<div>
Item 2.
Identity and Background
(a)
Pictet Asset Management SA
(b)
60 ROUTE DES ACACIAS
GENEVA 73 1211
SWITZERLAND
(c)
Investment Adviser
</div>
<div>
Item 3.
Source and Amount of Funds or Other Consideration
The Reporting Person acquired the shares using client assets.
</div>
<div>
Item 4.
Purpose of Transaction
The Reporting Person acquired shares of Five9 Inc. as part of its investment strategy. The Reporting Person does not currently have any plans or proposals that would result in a change in control of the Issuer.
</div>
<div>
Item 5.
Interest in Securities of the Issuer
(a)
Pictet Asset management SA manages 2,872,185 shares of Five9 Inc., which represents 3.75% of the total number of shares.
</div>
<div>
Item 6.
Contracts, Arrangements, Understandings or Relationships With Respect to Securities of the Issuer
None.
</div>
</body>
</html>
"""

# Activist-style 13D fixture
SAMPLE_ACTIVIST_13D_HTML = """
<html>
<head><title>SCHEDULE 13D</title></head>
<body>
<div>
SECURITIES AND EXCHANGE COMMISSION
Washington, D.C. 20549
SCHEDULE 13D
Under the Securities Exchange Act of 1934
(Amendment No.
29
)
BlackRock ESG Capital Allocation Term Trust
(Name of Issuer)
</div>
<div>
SCHEDULE 13D
1
Name of reporting person
SABA CAPITAL MANAGEMENT, L.P.
6
Citizenship or place of organization
DE
7
Sole Voting Power
23,575,057.00
8
Shared Voting Power
0.00
11
Aggregate amount beneficially owned by each reporting person
23,575,057.00
13
Percent of class represented by amount in Row (11)
23.73 %
14
Type of Reporting Person (See Instructions)
PN
</div>
<div>
Item 1.
Security and Issuer
(b)
Name of Issuer:
BlackRock ESG Capital Allocation Term Trust
</div>
<div>
Item 4.
Purpose of Transaction
Item 4 is hereby amended and supplemented as follows:

On February 25, 2026, Saba Capital Master Fund, Ltd. submitted to the Issuer a supplement to the Notice to nominate Lawrence Epstein as a Class I Nominee and Wayne Threatt and Lihong Wang as Class III Holdover Seat Nominees.
</div>
<div>
Item 5.
Interest in Securities of the Issuer
(a)
23,575,057 shares representing 23.73% of the outstanding shares.
</div>
</body>
</html>
"""

# Non-amendment (original filing)
SAMPLE_ORIGINAL_13D_HTML = """
<html>
<head><title>SCHEDULE 13D</title></head>
<body>
<div>
SECURITIES AND EXCHANGE COMMISSION
SCHEDULE 13D
Under the Securities Exchange Act of 1934
Acme Corp
(Name of Issuer)
</div>
<div>
1
Name of reporting person
ACTIVIST FUND LP
6
Citizenship or place of organization
US
11
Aggregate amount beneficially owned by each reporting person
5,000,000.00
13
Percent of class represented by amount in Row (11)
7.2 %
14
Type of Reporting Person (See Instructions)
PN
</div>
<div>
Item 4.
Purpose of Transaction
The Reporting Person acquired the shares for investment purposes and intends to engage with the board regarding capital allocation.
</div>
<div>
Item 5.
Interest in Securities of the Issuer
5,000,000 shares.
</div>
</body>
</html>
"""


class TestSchedule13DParser:
    """Tests for parse_schedule_13d()."""

    def test_parse_with_metadata(self):
        """Parser fills in EFTS metadata fields."""
        metadata = {
            "accession_number": "0001361570-26-000007",
            "filing_type": "SCHEDULE 13D/A",
            "filing_date": "2026-02-27",
            "target_cik": "0001288847",
            "target_name": "Five9, Inc.",
            "filer_cik": "0001361570",
            "filer_name": "PICTET ASSET MANAGEMENT SA",
            "filing_url": "https://example.com/filing",
        }
        result = parse_schedule_13d(SAMPLE_13D_HTML, metadata)

        assert result.accession_number == "0001361570-26-000007"
        assert result.filing_type == "SCHEDULE 13D/A"
        assert result.filing_date == "2026-02-27"
        assert result.target_cik == "0001288847"
        assert result.filer_cik == "0001361570"
        assert result.filer_name == "PICTET ASSET MANAGEMENT SA"
        assert result.is_amendment is True

    def test_parse_cover_page_percentage(self):
        """Parser extracts percentage from cover page row 13."""
        result = parse_schedule_13d(SAMPLE_13D_HTML)
        assert result.percentage == 3.8

    def test_parse_cover_page_shares(self):
        """Parser extracts shares owned from cover page row 11."""
        result = parse_schedule_13d(SAMPLE_13D_HTML)
        assert result.shares_owned == 2872185

    def test_parse_cover_page_reporting_type(self):
        """Parser extracts reporting person type from cover page row 14."""
        result = parse_schedule_13d(SAMPLE_13D_HTML)
        assert result.reporting_person_type == "IA"

    def test_parse_cover_page_citizenship(self):
        """Parser extracts citizenship from cover page row 6."""
        result = parse_schedule_13d(SAMPLE_13D_HTML)
        assert result.citizenship == "SWITZERLAND"

    def test_parse_amendment_number(self):
        """Parser extracts amendment number from header."""
        result = parse_schedule_13d(SAMPLE_13D_HTML)
        assert result.amendment_number == 6

    def test_parse_amendment_number_activist(self):
        """Parser handles large amendment numbers."""
        result = parse_schedule_13d(SAMPLE_ACTIVIST_13D_HTML)
        assert result.amendment_number == 29

    def test_parse_no_amendment(self):
        """Original filings have no amendment number."""
        result = parse_schedule_13d(SAMPLE_ORIGINAL_13D_HTML)
        assert result.amendment_number is None

    def test_parse_item4_passive(self):
        """Parser extracts passive purpose text."""
        result = parse_schedule_13d(SAMPLE_13D_HTML)
        assert "does not currently have any plans" in result.purpose_text

    def test_parse_item4_activist(self):
        """Parser extracts activist purpose text."""
        result = parse_schedule_13d(SAMPLE_ACTIVIST_13D_HTML)
        assert "nominate" in result.purpose_text.lower()

    def test_parse_item1_target_name(self):
        """Parser extracts target name from Item 1 when no metadata."""
        result = parse_schedule_13d(SAMPLE_13D_HTML)
        assert result.target_name == "Five9, Inc"

    def test_parse_filer_name_from_cover(self):
        """Parser extracts filer name from cover page when no metadata."""
        result = parse_schedule_13d(SAMPLE_ACTIVIST_13D_HTML)
        assert result.filer_name == "SABA CAPITAL MANAGEMENT, L.P."

    def test_parse_high_stake(self):
        """Activist filing with >10% stake."""
        result = parse_schedule_13d(SAMPLE_ACTIVIST_13D_HTML)
        assert result.percentage == 23.73
        assert result.shares_owned == 23575057

    def test_no_parse_errors_clean_filing(self):
        """Clean filings produce no parse errors."""
        result = parse_schedule_13d(SAMPLE_13D_HTML)
        assert result.parse_errors == []

    def test_parse_voting_power(self):
        """Parser extracts sole/shared voting power."""
        result = parse_schedule_13d(SAMPLE_13D_HTML)
        assert result.sole_voting_power == 2865052
        assert result.shared_voting_power == 0


class TestSignalClassification:
    """Tests for signal level classification."""

    def test_high_signal(self):
        """Percentage > 10% is HIGH."""
        filing = Schedule13DResult(percentage=15.0)
        assert classify_signal_level(filing) == "HIGH"

    def test_medium_signal(self):
        """Percentage 5-10% is MEDIUM."""
        filing = Schedule13DResult(percentage=7.5)
        assert classify_signal_level(filing) == "MEDIUM"

    def test_low_signal(self):
        """Percentage < 5% is LOW."""
        filing = Schedule13DResult(percentage=3.0)
        assert classify_signal_level(filing) == "LOW"

    def test_edge_case_5_percent(self):
        """Exactly 5% is MEDIUM (>= 5)."""
        filing = Schedule13DResult(percentage=5.0)
        assert classify_signal_level(filing) == "MEDIUM"

    def test_edge_case_10_percent(self):
        """Exactly 10% is MEDIUM (not > 10)."""
        filing = Schedule13DResult(percentage=10.0)
        assert classify_signal_level(filing) == "MEDIUM"

    def test_no_percentage(self):
        """Missing percentage defaults to LOW."""
        filing = Schedule13DResult()
        assert classify_signal_level(filing) == "LOW"


class TestSignalSummary:
    """Tests for signal summary generation."""

    def test_summary_new_filing(self):
        filing = Schedule13DResult(
            filer_name="Activist Fund",
            target_name="Acme Corp",
            percentage=8.5,
            is_amendment=False,
        )
        summary = build_signal_summary(filing)
        assert "Activist Fund filed 13D on Acme Corp" in summary
        assert "8.5% stake" in summary

    def test_summary_amendment(self):
        filing = Schedule13DResult(
            filer_name="Activist Fund",
            target_name="Acme Corp",
            percentage=12.0,
            is_amendment=True,
        )
        summary = build_signal_summary(filing)
        assert "updated 13D" in summary

    def test_summary_large_shares(self):
        filing = Schedule13DResult(
            filer_name="Big Fund",
            target_name="Corp",
            shares_owned=5_000_000,
        )
        summary = build_signal_summary(filing)
        assert "5.0M shares" in summary


class TestHelpers:
    """Tests for helper functions."""

    def test_parse_int_simple(self):
        assert _parse_int("1234") == 1234

    def test_parse_int_commas(self):
        assert _parse_int("2,872,185") == 2872185

    def test_parse_int_decimal(self):
        assert _parse_int("2,872,185.00") == 2872185

    def test_parse_int_apostrophes(self):
        """Swiss-style number formatting with apostrophes."""
        assert _parse_int("2'872'185") == 2872185

    def test_parse_int_invalid(self):
        assert _parse_int("not a number") is None

    def test_extract_amendment_number(self):
        assert _extract_amendment_number("(Amendment No.\n6\n)") == 6

    def test_extract_amendment_number_inline(self):
        assert _extract_amendment_number("(Amendment No. 12)") == 12

    def test_extract_no_amendment(self):
        assert _extract_amendment_number("SCHEDULE 13D original filing") is None
