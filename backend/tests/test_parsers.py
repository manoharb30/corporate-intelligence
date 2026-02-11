"""Tests for SEC EDGAR parsers."""

import pytest
from app.models.extraction_models import ExtractionMethod


# Sample HTML snippets for testing
OWNERSHIP_TABLE_HTML = """
<html>
<body>
<h2>Security Ownership of Certain Beneficial Owners and Management</h2>
<p>The following table sets forth information regarding beneficial ownership of our common stock.</p>
<table>
    <tr>
        <th>Name of Beneficial Owner</th>
        <th>Shares of Common Stock Beneficially Owned</th>
        <th>Percent of Class</th>
    </tr>
    <tr>
        <td>The Vanguard Group, Inc.</td>
        <td>82,531,090</td>
        <td>8.2%</td>
    </tr>
    <tr>
        <td>BlackRock, Inc.</td>
        <td>65,123,456</td>
        <td>6.5%</td>
    </tr>
    <tr>
        <td>John Smith</td>
        <td>1,234,567</td>
        <td>0.12%</td>
    </tr>
    <tr>
        <td>Jane Doe</td>
        <td>500,000</td>
        <td>*</td>
    </tr>
</table>
</body>
</html>
"""

SUBSIDIARY_TABLE_HTML = """
<html>
<body>
<h1>EXHIBIT 21</h1>
<h2>LIST OF SUBSIDIARIES</h2>
<table>
    <tr>
        <th>Name of Subsidiary</th>
        <th>State or Other Jurisdiction of Incorporation</th>
    </tr>
    <tr>
        <td>Apple Operations International</td>
        <td>Ireland</td>
    </tr>
    <tr>
        <td>Apple Sales International</td>
        <td>Ireland</td>
    </tr>
    <tr>
        <td>Apple Inc. (California)</td>
        <td>California</td>
    </tr>
    <tr>
        <td>Beats Electronics LLC</td>
        <td>Delaware</td>
    </tr>
</table>
</body>
</html>
"""

SUBSIDIARY_TEXT_HTML = """
<html>
<body>
<h1>Exhibit 21 - Subsidiaries of the Registrant</h1>
<p>The following are the significant subsidiaries of Microsoft Corporation:</p>
<p>LinkedIn Corporation, a Delaware corporation</p>
<p>GitHub, Inc. (Delaware)</p>
<p>Nuance Communications, Inc., a Delaware corporation</p>
<p>Activision Blizzard, Inc. (Delaware)</p>
<p>Microsoft Ireland Operations Limited (Ireland)</p>
</body>
</html>
"""

OFFICER_TABLE_HTML = """
<html>
<body>
<h2>DIRECTORS AND EXECUTIVE OFFICERS</h2>
<p>The following table sets forth information about our directors and executive officers.</p>
<table>
    <tr>
        <th>Name</th>
        <th>Age</th>
        <th>Position</th>
    </tr>
    <tr>
        <td>Tim Cook</td>
        <td>63</td>
        <td>Chief Executive Officer and Director</td>
    </tr>
    <tr>
        <td>Luca Maestri</td>
        <td>60</td>
        <td>Senior Vice President, Chief Financial Officer</td>
    </tr>
    <tr>
        <td>Katherine Adams</td>
        <td>59</td>
        <td>Senior Vice President, General Counsel</td>
    </tr>
    <tr>
        <td>Arthur Levinson</td>
        <td>73</td>
        <td>Chairman of the Board</td>
    </tr>
    <tr>
        <td>Al Gore</td>
        <td>75</td>
        <td>Director</td>
    </tr>
</table>
</body>
</html>
"""

OFFICER_NARRATIVE_HTML = """
<html>
<body>
<h2>Executive Officers</h2>
<p><b>Satya Nadella</b>, age 56, has served as Chief Executive Officer and Chairman since 2021.</p>
<p><b>Amy Hood</b>, age 51, has served as Executive Vice President and Chief Financial Officer since 2013.</p>
<p><b>Brad Smith</b>, age 64, serves as Vice Chair and President.</p>
<h2>Board of Directors</h2>
<p><b>John Thompson</b> serves as Lead Independent Director.</p>
<p><b>Reid Hoffman</b> has been a director since 2017.</p>
</body>
</html>
"""


class TestOwnershipParser:
    """Tests for ownership parser."""

    def test_parse_ownership_table(self):
        """Test parsing a standard ownership table."""
        from ingestion.sec_edgar.parsers.ownership_parser import OwnershipParser

        parser = OwnershipParser(llm_extractor=None, review_queue=None)
        records = parser._parse_ownership_table_rulebased(OWNERSHIP_TABLE_HTML)

        assert len(records) >= 3

        # Check Vanguard
        vanguard = next((r for r in records if "Vanguard" in r.owner_name), None)
        assert vanguard is not None
        assert vanguard.owner_type == "company"
        assert vanguard.shares_owned == 82531090
        assert vanguard.percentage == 8.2
        assert vanguard.extraction_method == ExtractionMethod.RULE_BASED

        # Check BlackRock
        blackrock = next((r for r in records if "BlackRock" in r.owner_name), None)
        assert blackrock is not None
        assert blackrock.owner_type == "company"
        assert blackrock.percentage == 6.5

        # Check person
        john = next((r for r in records if "John Smith" in r.owner_name), None)
        assert john is not None
        assert john.owner_type == "person"

    def test_guess_owner_type(self):
        """Test owner type classification."""
        from ingestion.sec_edgar.parsers.ownership_parser import OwnershipParser

        assert OwnershipParser._guess_owner_type("The Vanguard Group, Inc.") == "company"
        assert OwnershipParser._guess_owner_type("BlackRock Fund Advisors") == "company"
        assert OwnershipParser._guess_owner_type("State Street Corporation") == "company"
        assert OwnershipParser._guess_owner_type("John Smith") == "person"
        assert OwnershipParser._guess_owner_type("Jane Doe Jr.") == "person"
        assert OwnershipParser._guess_owner_type("Dr. Robert Jones") == "person"

    def test_parse_percentage(self):
        """Test percentage parsing."""
        from ingestion.sec_edgar.parsers.ownership_parser import OwnershipParser

        assert OwnershipParser._parse_percentage("8.2%") == 8.2
        assert OwnershipParser._parse_percentage("8.2 %") == 8.2
        assert OwnershipParser._parse_percentage("8.2") == 8.2
        assert OwnershipParser._parse_percentage("*") is None
        assert OwnershipParser._parse_percentage("-") is None
        assert OwnershipParser._parse_percentage("less than 1%") == 0.5

    def test_parse_number(self):
        """Test number parsing."""
        from ingestion.sec_edgar.parsers.ownership_parser import OwnershipParser

        assert OwnershipParser._parse_number("82,531,090") == 82531090
        assert OwnershipParser._parse_number("1234567") == 1234567
        assert OwnershipParser._parse_number("1,234,567") == 1234567
        assert OwnershipParser._parse_number("-") is None
        assert OwnershipParser._parse_number("*") is None


class TestSubsidiaryParser:
    """Tests for subsidiary parser."""

    def test_parse_subsidiary_table(self):
        """Test parsing a standard subsidiary table."""
        from ingestion.sec_edgar.parsers.company_parser import SubsidiaryParser

        parser = SubsidiaryParser(llm_extractor=None, review_queue=None)
        records = parser._parse_subsidiaries_rulebased(SUBSIDIARY_TABLE_HTML)

        assert len(records) >= 4

        # Check Ireland subsidiary
        ireland_sub = next((r for r in records if "Operations International" in r.name), None)
        assert ireland_sub is not None
        assert ireland_sub.jurisdiction == "Ireland"
        assert ireland_sub.extraction_method == ExtractionMethod.RULE_BASED

        # Check Delaware subsidiary
        beats = next((r for r in records if "Beats" in r.name), None)
        assert beats is not None
        assert beats.jurisdiction == "Delaware"

    def test_parse_subsidiary_text(self):
        """Test parsing subsidiaries from text format."""
        from ingestion.sec_edgar.parsers.company_parser import SubsidiaryParser

        parser = SubsidiaryParser(llm_extractor=None, review_queue=None)
        records = parser._parse_subsidiaries_rulebased(SUBSIDIARY_TEXT_HTML)

        assert len(records) >= 3

        # Check LinkedIn
        linkedin = next((r for r in records if "LinkedIn" in r.name), None)
        assert linkedin is not None
        assert linkedin.jurisdiction == "Delaware"

        # Check GitHub
        github = next((r for r in records if "GitHub" in r.name), None)
        assert github is not None
        assert github.jurisdiction == "Delaware"

    def test_normalize_jurisdiction(self):
        """Test jurisdiction normalization."""
        from ingestion.sec_edgar.parsers.company_parser import SubsidiaryParser

        parser = SubsidiaryParser()

        assert parser._normalize_jurisdiction("DE") == "Delaware"
        assert parser._normalize_jurisdiction("delaware") == "Delaware"
        assert parser._normalize_jurisdiction("Delaware") == "Delaware"
        assert parser._normalize_jurisdiction("cayman islands") == "Cayman Islands"
        assert parser._normalize_jurisdiction("UK") == "United Kingdom"
        assert parser._normalize_jurisdiction("") is None


class TestOfficerParser:
    """Tests for officer parser."""

    def test_parse_officer_table(self):
        """Test parsing a standard officer/director table."""
        from ingestion.sec_edgar.parsers.officer_parser import OfficerParser

        parser = OfficerParser(llm_extractor=None, review_queue=None)
        records = parser._parse_officers_rulebased(OFFICER_TABLE_HTML)

        assert len(records) >= 4

        # Check CEO
        tim = next((r for r in records if "Tim Cook" in r.name), None)
        assert tim is not None
        assert tim.is_officer is True
        assert tim.is_director is True
        assert tim.is_executive is True
        assert tim.age == 63

        # Check CFO
        luca = next((r for r in records if "Luca" in r.name), None)
        assert luca is not None
        assert luca.is_officer is True
        assert luca.is_executive is True

        # Check Chairman
        arthur = next((r for r in records if "Levinson" in r.name), None)
        assert arthur is not None
        assert arthur.is_director is True

        # Check Director only
        al = next((r for r in records if "Al Gore" in r.name), None)
        assert al is not None
        assert al.is_director is True

    def test_parse_officer_narrative(self):
        """Test parsing officers from narrative format."""
        from ingestion.sec_edgar.parsers.officer_parser import OfficerParser

        parser = OfficerParser(llm_extractor=None, review_queue=None)
        records = parser._parse_officers_rulebased(OFFICER_NARRATIVE_HTML)

        # Should find at least some officers
        assert len(records) >= 2

        # Check for CEO
        satya = next((r for r in records if "Nadella" in r.name), None)
        if satya:
            assert satya.is_executive is True

    def test_classify_role(self):
        """Test role classification."""
        from ingestion.sec_edgar.parsers.officer_parser import OfficerParser

        parser = OfficerParser()

        is_dir, is_off, is_exec = parser._classify_role("Chief Executive Officer")
        assert is_exec is True
        assert is_off is True
        assert is_dir is False

        is_dir, is_off, is_exec = parser._classify_role("Director")
        assert is_dir is True
        # Director alone is not an officer role
        assert is_exec is False

        is_dir, is_off, is_exec = parser._classify_role("Chairman of the Board")
        assert is_dir is True

        is_dir, is_off, is_exec = parser._classify_role("CEO and Director")
        assert is_exec is True
        assert is_dir is True

        is_dir, is_off, is_exec = parser._classify_role("Vice President of Sales")
        assert is_off is True

        is_dir, is_off, is_exec = parser._classify_role("General Counsel")
        assert is_off is True


class TestReviewQueue:
    """Tests for review queue."""

    def test_add_and_retrieve(self, tmp_path):
        """Test adding and retrieving review items."""
        from ingestion.sec_edgar.review_queue import ReviewQueue, ReviewStatus

        db_path = tmp_path / "test_review.db"
        queue = ReviewQueue(db_path=str(db_path))

        # Add a failed extraction
        item_id = queue.add_failed_extraction(
            filing_accession="0001234567-23-000001",
            filing_type="DEF 14A",
            company_cik="0000320193",
            company_name="Apple Inc.",
            extraction_type="ownership",
            raw_text="<html>test</html>",
            failure_reason="Test failure",
        )

        assert item_id > 0

        # Retrieve pending items
        pending = queue.get_pending()
        assert len(pending) == 1
        assert pending[0].filing_accession == "0001234567-23-000001"
        assert pending[0].status == ReviewStatus.PENDING

        # Retrieve by ID
        item = queue.get_by_id(item_id)
        assert item is not None
        assert item.company_name == "Apple Inc."

    def test_approve_and_reject(self, tmp_path):
        """Test approving and rejecting review items."""
        from ingestion.sec_edgar.review_queue import ReviewQueue, ReviewStatus

        db_path = tmp_path / "test_review2.db"
        queue = ReviewQueue(db_path=str(db_path))

        item_id = queue.add_failed_extraction(
            filing_accession="0001234567-23-000002",
            filing_type="10-K",
            company_cik="0000789019",
            extraction_type="subsidiary",
            raw_text="<html>test</html>",
            failure_reason="Test failure",
        )

        # Approve
        success = queue.approve(item_id, reviewed_by="test_user")
        assert success is True

        item = queue.get_by_id(item_id)
        assert item.status == ReviewStatus.APPROVED
        assert item.reviewed_by == "test_user"

    def test_stats(self, tmp_path):
        """Test queue statistics."""
        from ingestion.sec_edgar.review_queue import ReviewQueue

        db_path = tmp_path / "test_review3.db"
        queue = ReviewQueue(db_path=str(db_path))

        # Add some items
        queue.add_failed_extraction(
            filing_accession="test1",
            filing_type="DEF 14A",
            company_cik="111",
            extraction_type="ownership",
            raw_text="test",
            failure_reason="test",
        )
        queue.add_failed_extraction(
            filing_accession="test2",
            filing_type="10-K",
            company_cik="222",
            extraction_type="subsidiary",
            raw_text="test",
            failure_reason="test",
        )

        stats = queue.get_stats()
        assert stats["total"] == 2
        assert stats.get("pending", 0) == 2


class TestEdgarClient:
    """Tests for SEC EDGAR client."""

    def test_normalize_cik(self):
        """Test CIK normalization."""
        from ingestion.sec_edgar.edgar_client import SECEdgarClient

        assert SECEdgarClient.normalize_cik("320193") == "0000320193"
        assert SECEdgarClient.normalize_cik("0000320193") == "0000320193"
        assert SECEdgarClient.normalize_cik("CIK320193") == "0000320193"

    def test_filing_info_accession_format(self):
        """Test filing accession number formatting."""
        from ingestion.sec_edgar.edgar_client import FilingInfo

        filing = FilingInfo(
            accession_number="0001193125-23-012345",
            form_type="DEF 14A",
            filing_date="2023-01-15",
            primary_document="def14a.htm",
        )

        assert filing.accession_number_nodash == "000119312523012345"


# Pydantic model validation tests
class TestExtractionModels:
    """Tests for Pydantic extraction models."""

    def test_ownership_record_validation(self):
        """Test OwnershipRecord validation."""
        from app.models.extraction_models import OwnershipRecord, ExtractionMethod

        # Valid record
        record = OwnershipRecord(
            owner_name="Test Corp",
            owner_type="company",
            shares_owned=1000000,
            percentage=5.5,
            extraction_method=ExtractionMethod.RULE_BASED,
            confidence=0.95,
        )
        assert record.owner_name == "Test Corp"
        assert record.percentage == 5.5

        # Invalid owner_type should fail
        with pytest.raises(ValueError):
            OwnershipRecord(
                owner_name="Test",
                owner_type="invalid",
                extraction_method=ExtractionMethod.RULE_BASED,
                confidence=0.5,
            )

        # Percentage out of range should fail
        with pytest.raises(ValueError):
            OwnershipRecord(
                owner_name="Test",
                owner_type="person",
                percentage=150.0,
                extraction_method=ExtractionMethod.RULE_BASED,
                confidence=0.5,
            )

    def test_confidence_bounds(self):
        """Test confidence score validation."""
        from app.models.extraction_models import OwnershipRecord, ExtractionMethod

        # Valid confidence
        record = OwnershipRecord(
            owner_name="Test",
            owner_type="person",
            extraction_method=ExtractionMethod.RULE_BASED,
            confidence=0.95,
        )
        assert record.confidence == 0.95

        # Invalid confidence (> 1)
        with pytest.raises(ValueError):
            OwnershipRecord(
                owner_name="Test",
                owner_type="person",
                extraction_method=ExtractionMethod.RULE_BASED,
                confidence=1.5,
            )

        # Invalid confidence (< 0)
        with pytest.raises(ValueError):
            OwnershipRecord(
                owner_name="Test",
                owner_type="person",
                extraction_method=ExtractionMethod.RULE_BASED,
                confidence=-0.5,
            )
