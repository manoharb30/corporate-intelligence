"""
Test company definitions for pipeline validation.

These companies were chosen to stress-test the ingestion pipeline
with complex ownership structures, sparse filings, and known issues.
"""

from dataclasses import dataclass, field
from enum import Enum


class TestChallenge(str, Enum):
    """Types of challenges a test company may present."""

    COMPLEX_OWNERSHIP = "complex_ownership"  # Many layers of ownership
    SPARSE_FILINGS = "sparse_filings"  # Limited SEC filings available
    NAME_CHANGES = "name_changes"  # Company has changed names
    FOREIGN_ENTITY = "foreign_entity"  # Non-US operations, foreign subsidiaries
    KNOWN_FRAUD = "known_fraud"  # SEC investigations or fraud convictions
    UNUSUAL_STRUCTURE = "unusual_structure"  # Non-standard corporate structure
    MANY_SUBSIDIARIES = "many_subsidiaries"  # 50+ subsidiaries
    SHELL_INDICATORS = "shell_indicators"  # Potential shell company markers
    SPAC = "spac"  # SPAC or reverse merger history


@dataclass
class TestCompany:
    """A company for testing the pipeline."""

    cik: str
    ticker: str
    name: str
    challenges: list[TestChallenge]
    notes: str
    expected_officers_min: int = 3  # Minimum expected officers
    expected_subsidiaries_min: int = 0  # Minimum expected subsidiaries
    expected_owners_min: int = 0  # Minimum expected beneficial owners


TEST_COMPANIES = [
    TestCompany(
        cik="0000813762",
        ticker="IEP",
        name="Icahn Enterprises L.P.",
        challenges=[TestChallenge.COMPLEX_OWNERSHIP, TestChallenge.MANY_SUBSIDIARIES],
        notes="Carl Icahn's holding company - expect 50+ subsidiaries, complex ownership structure",
        expected_officers_min=5,
        expected_subsidiaries_min=30,
    ),
    TestCompany(
        cik="0001345126",
        ticker="CODI",
        name="Compass Diversified Holdings",
        challenges=[TestChallenge.COMPLEX_OWNERSHIP, TestChallenge.MANY_SUBSIDIARIES],
        notes="Diversified holding company with many unrelated subsidiaries",
        expected_officers_min=5,
        expected_subsidiaries_min=10,
    ),
    TestCompany(
        cik="0000837852",
        ticker="IDEX",
        name="Ideanomics, Inc.",
        challenges=[TestChallenge.NAME_CHANGES, TestChallenge.FOREIGN_ENTITY],
        notes="Multiple acquisitions, formerly Seven Stars Cloud Group, Chinese operations",
        expected_officers_min=3,
    ),
    TestCompany(
        cik="0001731289",
        ticker="NKLA",
        name="Nikola Corporation",
        challenges=[TestChallenge.KNOWN_FRAUD, TestChallenge.SPAC],
        notes="Founder Trevor Milton fraud conviction, SPAC merger",
        expected_officers_min=3,
    ),
    TestCompany(
        cik="0001759546",
        ticker="RIDE",
        name="Lordstown Motors Corp.",
        challenges=[TestChallenge.KNOWN_FRAUD, TestChallenge.SPAC],
        notes="SEC investigation, SPAC issues, bankruptcy",
        expected_officers_min=3,
    ),
    TestCompany(
        cik="0001173420",
        ticker="HYMC",
        name="Hycroft Mining Holding Corporation",
        challenges=[TestChallenge.UNUSUAL_STRUCTURE],
        notes="AMC Entertainment took unusual stake, meme stock target",
        expected_officers_min=3,
    ),
    TestCompany(
        cik="0001595248",
        ticker="GRNQ",
        name="Greenpro Capital Corp.",
        challenges=[TestChallenge.FOREIGN_ENTITY, TestChallenge.SPARSE_FILINGS],
        notes="Small company, Asian operations, limited SEC disclosure",
        expected_officers_min=2,
    ),
    TestCompany(
        cik="0001346610",
        ticker="SOS",
        name="SOS Limited",
        challenges=[
            TestChallenge.FOREIGN_ENTITY,
            TestChallenge.KNOWN_FRAUD,
            TestChallenge.SHELL_INDICATORS,
        ],
        notes="Chinese company, alleged fraud, short seller target",
        expected_officers_min=2,
    ),
    TestCompany(
        cik="0000744825",
        ticker="AMS",
        name="American Shared Hospital Services",
        challenges=[TestChallenge.SPARSE_FILINGS],
        notes="Small, old company with limited filings",
        expected_officers_min=3,
    ),
    TestCompany(
        cik="0001820875",
        ticker="BTBT",
        name="Bit Digital, Inc.",
        challenges=[TestChallenge.FOREIGN_ENTITY, TestChallenge.SPARSE_FILINGS],
        notes="Chinese crypto company, minimal disclosures",
        expected_officers_min=2,
    ),
]


# Quick lookup by CIK
TEST_COMPANIES_BY_CIK = {c.cik: c for c in TEST_COMPANIES}


def get_test_company(cik: str) -> TestCompany | None:
    """Get a test company by CIK."""
    return TEST_COMPANIES_BY_CIK.get(cik)


def get_companies_by_challenge(challenge: TestChallenge) -> list[TestCompany]:
    """Get all test companies with a specific challenge."""
    return [c for c in TEST_COMPANIES if challenge in c.challenges]
