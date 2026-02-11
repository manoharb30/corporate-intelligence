"""Neo4j loader for SEC EDGAR extracted data."""

import logging
import re
import uuid
from datetime import date, datetime
from typing import Optional

from app.db.neo4j_client import Neo4jClient

# Blocklist of known invalid person names (exact matches, case-insensitive)
INVALID_NAME_EXACT = {
    # Table headers
    "insider trading policy",
    "former executive",
    "former officer",
    "former director",
    "name age title",
    "name",
    "age",
    "title",
    "n/a",
    "none",
    "unknown",
    "vacant",
    "tbd",
    "to be determined",
    # Document sections incorrectly parsed as names
    "shareholder engagement",
    "corporate governance",
    "board independence",
    "board oversight",
    "business conduct policy",
    "vote required",
    "other information",
    "general information",
    "annex a",
    "annex b",
    "annex c",
    "exhibit a",
    "exhibit b",
    "exhibit c",
    "exhibit d",
    # Role titles
    "chief executive officer",
    "chief financial officer",
    "chief operating officer",
    "chief technology officer",
    "chief legal officer",
    "chief marketing officer",
    "non-employee directors",
    "independent directors",
    # Common parsing errors
    "questions and answers",
    "proxy statement",
    "table of contents",
}

# Patterns that indicate invalid names (regex)
INVALID_NAME_PATTERNS = [
    r"^\s*$",                          # Empty or whitespace only
    r"^name\s*\n",                     # Starts with "Name" followed by newline
    r"^\d+$",                          # Numbers only
    r"^[^a-zA-Z]*$",                   # No letters at all
    r"^.{1,2}$",                       # Too short (1-2 chars)
    r"^\s*age\s*\n",                   # Table header "Age"
    r"^\s*title\s*\n",                 # Table header "Title"
    r"^(mr|mrs|ms|dr|prof)\.?\s*$",    # Title only, no name
    r"^\(\d+\)$",                      # Just a number in parentheses like "(1)"
    r".*\s+(inc\.?|corp\.?|llc|l\.?l\.?c\.?|l\.?p\.?|ltd\.?|limited|plc)\s*$",  # Company suffixes
    r"^(the|our|all|each|any|this)\s+",  # Starts with articles
    r".*\b(20\d{2})\b.*",              # Contains year (2020-2029)
    r"^(proposal|notice|table|summary|item|part|section)\s",  # Document structure
    r".*\b(form\s*4|schedule\s*13|section\s*16)\b.*",  # SEC form references
    r"^information\s+(is\s+)?based\s+on",  # Common footnote pattern
]

# Company name suffixes to detect (checked separately for efficiency)
COMPANY_SUFFIXES = [
    " inc.", " inc", " corp.", " corp", " llc", " l.l.c.",
    " l.p.", " lp", " ltd.", " ltd", " limited", " plc",
    " co.", " company", " corporation", " incorporated",
    " holdings", " enterprises", " partners", " group",
    " s.a.", " n.v.", " b.v.", " gmbh", " ag",
]

# Compiled patterns for efficiency
_INVALID_PATTERNS_COMPILED = [re.compile(p, re.IGNORECASE) for p in INVALID_NAME_PATTERNS]


def is_valid_person_name(name: str) -> bool:
    """
    Validate if a string is a valid person name.

    Returns False for:
    - Empty or whitespace-only strings
    - Known invalid names (table headers, placeholders)
    - Strings without letters
    - Very short strings (< 3 chars)
    - Company names (containing Inc., Corp., LLC, etc.)
    """
    if not name:
        return False

    name_stripped = name.strip()
    name_lower = name_stripped.lower()

    # Check exact blocklist
    if name_lower in INVALID_NAME_EXACT:
        return False

    # Check if it looks like a company name
    for suffix in COMPANY_SUFFIXES:
        if name_lower.endswith(suffix):
            return False

    # Check if ALL CAPS (likely company or header)
    if name_stripped == name_stripped.upper() and len(name_stripped) > 10:
        return False

    # Check regex patterns
    for pattern in _INVALID_PATTERNS_COMPILED:
        if pattern.match(name_stripped):
            return False

    # Must have at least 3 characters
    if len(name_stripped) < 3:
        return False

    # Must contain at least 2 letters
    letter_count = sum(1 for c in name_stripped if c.isalpha())
    if letter_count < 2:
        return False

    # Should not be mostly whitespace/newlines
    if name_stripped.count('\n') > 2:
        return False

    # Name should be 2-6 words (typical for person names)
    words = name_stripped.split()
    if len(words) < 2 or len(words) > 6:
        return False

    # Should not be too long
    if len(name_stripped) > 60:
        return False

    return True
from app.models.extraction_models import (
    ExtractionMethod,
    OwnershipRecord,
    OwnershipExtractionResult,
    SubsidiaryRecord,
    SubsidiaryExtractionResult,
    OfficerRecord,
    OfficerExtractionResult,
)

logger = logging.getLogger(__name__)


class SECDataLoader:
    """Load extracted SEC data into Neo4j."""

    def __init__(self):
        pass

    async def load_ownership_data(
        self,
        result: OwnershipExtractionResult,
    ) -> dict:
        """
        Load ownership data into Neo4j.

        Creates/updates:
        - Company node (subject company)
        - Person/Company nodes (owners)
        - OWNS relationships
        - Filing node
        - MENTIONED_IN relationships
        """
        stats = {
            "companies_created": 0,
            "persons_created": 0,
            "ownership_relationships": 0,
            "filings_created": 0,
        }

        # Create or update the subject company
        company_id = await self._ensure_company(
            cik=result.company_cik,
            name=result.company_name,
        )
        stats["companies_created"] += 1

        # Create the filing node
        filing_id = await self._ensure_filing(
            accession_number=result.filing_accession,
            form_type=result.filing_type,
            company_id=company_id,
            extraction_method=result.extraction_metadata.method,
            filing_date=result.filing_date,
            filing_url=result.filing_url,
        )
        stats["filings_created"] += 1

        # Process each ownership record
        for record in result.records:
            owner_id = await self._ensure_entity(
                name=record.owner_name,
                entity_type=record.owner_type,
            )

            if record.owner_type == "company":
                stats["companies_created"] += 1
            else:
                stats["persons_created"] += 1

            # Create OWNS relationship
            await self._create_ownership_relationship(
                owner_id=owner_id,
                owned_id=company_id,
                record=record,
                filing_id=filing_id,
            )
            stats["ownership_relationships"] += 1

        logger.info(f"Loaded ownership data for {result.company_cik}: {stats}")
        return stats

    async def load_subsidiary_data(
        self,
        result: SubsidiaryExtractionResult,
    ) -> dict:
        """
        Load subsidiary data into Neo4j.

        Creates/updates:
        - Company node (parent company)
        - Company nodes (subsidiaries)
        - OWNS relationships
        - INCORPORATED_IN relationships
        - Filing node
        """
        stats = {
            "companies_created": 0,
            "subsidiaries_created": 0,
            "ownership_relationships": 0,
            "jurisdiction_relationships": 0,
            "filings_created": 0,
        }

        # Create or update the parent company
        parent_id = await self._ensure_company(
            cik=result.company_cik,
            name=result.company_name,
        )
        stats["companies_created"] += 1

        # Create the filing node
        filing_id = await self._ensure_filing(
            accession_number=result.filing_accession,
            form_type="10-K",
            company_id=parent_id,
            extraction_method=result.extraction_metadata.method,
            filing_date=result.filing_date,
            filing_url=result.filing_url,
        )
        stats["filings_created"] += 1

        # Process each subsidiary
        for record in result.records:
            subsidiary_id = await self._ensure_company(
                name=record.name,
                jurisdiction=record.jurisdiction,
            )
            stats["subsidiaries_created"] += 1

            # Create OWNS relationship from parent to subsidiary
            await self._create_subsidiary_relationship(
                parent_id=parent_id,
                subsidiary_id=subsidiary_id,
                record=record,
                filing_id=filing_id,
            )
            stats["ownership_relationships"] += 1

            # Create jurisdiction relationship if we have jurisdiction
            if record.jurisdiction:
                await self._create_jurisdiction_relationship(
                    company_id=subsidiary_id,
                    jurisdiction=record.jurisdiction,
                )
                stats["jurisdiction_relationships"] += 1

        logger.info(f"Loaded subsidiary data for {result.company_cik}: {stats}")
        return stats

    async def load_officer_data(
        self,
        result: OfficerExtractionResult,
    ) -> dict:
        """
        Load officer/director data into Neo4j.

        Creates/updates:
        - Company node
        - Person nodes (officers/directors)
        - OFFICER_OF relationships
        - DIRECTOR_OF relationships
        - Filing node
        """
        stats = {
            "companies_created": 0,
            "persons_created": 0,
            "officer_relationships": 0,
            "director_relationships": 0,
            "filings_created": 0,
        }

        # Create or update the company
        company_id = await self._ensure_company(
            cik=result.company_cik,
            name=result.company_name,
        )
        stats["companies_created"] += 1

        # Create the filing node
        filing_id = await self._ensure_filing(
            accession_number=result.filing_accession,
            form_type="DEF 14A",
            company_id=company_id,
            extraction_method=result.extraction_metadata.method,
            filing_date=result.filing_date,
            filing_url=result.filing_url,
        )
        stats["filings_created"] += 1

        # Process each officer/director
        skipped_invalid = 0
        for record in result.records:
            # Validate person name before creating node
            if not is_valid_person_name(record.name):
                logger.debug(f"Skipping invalid person name: {record.name!r}")
                skipped_invalid += 1
                continue

            person_id = await self._ensure_person(
                name=record.name,
            )
            stats["persons_created"] += 1

            # Create relationships based on role
            if record.is_officer or record.is_executive:
                await self._create_officer_relationship(
                    person_id=person_id,
                    company_id=company_id,
                    record=record,
                    filing_id=filing_id,
                )
                stats["officer_relationships"] += 1

            if record.is_director:
                await self._create_director_relationship(
                    person_id=person_id,
                    company_id=company_id,
                    record=record,
                    filing_id=filing_id,
                )
                stats["director_relationships"] += 1

        if skipped_invalid > 0:
            logger.info(f"Skipped {skipped_invalid} invalid person names for {result.company_cik}")
        logger.info(f"Loaded officer data for {result.company_cik}: {stats}")
        return stats

    async def _ensure_company(
        self,
        cik: Optional[str] = None,
        name: Optional[str] = None,
        jurisdiction: Optional[str] = None,
    ) -> str:
        """Create or update a company node, return its ID."""
        if cik:
            # MERGE by CIK if available
            cypher = """
                MERGE (c:Company {cik: $cik})
                ON CREATE SET
                    c.id = $id,
                    c.name = $name,
                    c.normalized_name = $normalized_name,
                    c.jurisdiction = $jurisdiction,
                    c.created_at = datetime(),
                    c.source = 'sec_edgar'
                ON MATCH SET
                    c.id = COALESCE(c.id, $id),
                    c.name = COALESCE($name, c.name),
                    c.jurisdiction = COALESCE($jurisdiction, c.jurisdiction),
                    c.updated_at = datetime()
                RETURN c.id as id
            """
        else:
            # MERGE by normalized name if no CIK
            cypher = """
                MERGE (c:Company {normalized_name: $normalized_name})
                ON CREATE SET
                    c.id = $id,
                    c.name = $name,
                    c.jurisdiction = $jurisdiction,
                    c.created_at = datetime(),
                    c.source = 'sec_edgar'
                ON MATCH SET
                    c.id = COALESCE(c.id, $id),
                    c.name = COALESCE($name, c.name),
                    c.jurisdiction = COALESCE($jurisdiction, c.jurisdiction),
                    c.updated_at = datetime()
                RETURN c.id as id
            """

        company_id = str(uuid.uuid4())
        normalized_name = name.upper().strip() if name else None

        params = {
            "id": company_id,
            "cik": cik,
            "name": name,
            "normalized_name": normalized_name,
            "jurisdiction": jurisdiction,
        }

        result = await Neo4jClient.execute_query(cypher, params)
        return result[0]["id"] if result else company_id

    async def _ensure_person(self, name: str) -> str:
        """Create or update a person node, return its ID."""
        normalized_name = name.upper().strip()

        cypher = """
            MERGE (p:Person {normalized_name: $normalized_name})
            ON CREATE SET
                p.id = $id,
                p.name = $name,
                p.created_at = datetime(),
                p.source = 'sec_edgar'
            ON MATCH SET
                p.updated_at = datetime()
            RETURN p.id as id
        """

        person_id = str(uuid.uuid4())
        params = {
            "id": person_id,
            "name": name,
            "normalized_name": normalized_name,
        }

        result = await Neo4jClient.execute_query(cypher, params)
        return result[0]["id"] if result else person_id

    async def _ensure_entity(self, name: str, entity_type: str) -> str:
        """Create or update an entity (person or company), return its ID."""
        if entity_type == "company":
            return await self._ensure_company(name=name)
        else:
            return await self._ensure_person(name=name)

    async def _ensure_filing(
        self,
        accession_number: str,
        form_type: str,
        company_id: str,
        extraction_method: ExtractionMethod,
        filing_date: Optional[date] = None,
        filing_url: Optional[str] = None,
    ) -> str:
        """Create or update a filing node, return its ID."""
        cypher = """
            MERGE (f:Filing {accession_number: $accession_number})
            ON CREATE SET
                f.id = $id,
                f.form_type = $form_type,
                f.extraction_method = $extraction_method,
                f.filing_date = $filing_date,
                f.filing_url = $filing_url,
                f.extracted_at = datetime(),
                f.created_at = datetime()
            ON MATCH SET
                f.filing_date = COALESCE($filing_date, f.filing_date),
                f.filing_url = COALESCE($filing_url, f.filing_url),
                f.updated_at = datetime()
            WITH f
            MATCH (c:Company {id: $company_id})
            MERGE (c)-[:FILED]->(f)
            RETURN f.id as id
        """

        filing_id = str(uuid.uuid4())
        params = {
            "id": filing_id,
            "accession_number": accession_number,
            "form_type": form_type,
            "company_id": company_id,
            "extraction_method": extraction_method.value,
            "filing_date": filing_date.isoformat() if filing_date else None,
            "filing_url": filing_url,
        }

        result = await Neo4jClient.execute_query(cypher, params)
        return result[0]["id"] if result else filing_id

    async def _create_ownership_relationship(
        self,
        owner_id: str,
        owned_id: str,
        record: OwnershipRecord,
        filing_id: str,
    ) -> None:
        """Create OWNS relationship between owner and owned entity."""
        cypher = """
            MATCH (owner {id: $owner_id})
            MATCH (owned:Company {id: $owned_id})
            MATCH (f:Filing {id: $filing_id})
            MERGE (owner)-[r:OWNS]->(owned)
            SET r.percentage = $percentage,
                r.shares = $shares,
                r.is_beneficial = $is_beneficial,
                r.is_direct = $is_direct,
                r.extraction_method = $extraction_method,
                r.confidence = $confidence,
                r.source_filing = $filing_id,
                r.raw_text = $raw_text,
                r.source_section = $source_section,
                r.source_table = $source_table,
                r.updated_at = datetime()
            MERGE (owner)-[:MENTIONED_IN]->(f)
        """

        params = {
            "owner_id": owner_id,
            "owned_id": owned_id,
            "filing_id": filing_id,
            "percentage": record.percentage,
            "shares": record.shares_owned,
            "is_beneficial": record.is_beneficial,
            "is_direct": record.is_direct,
            "extraction_method": record.extraction_method.value,
            "confidence": record.confidence,
            "raw_text": record.raw_text,
            "source_section": record.source_section,
            "source_table": record.source_table,
        }

        await Neo4jClient.execute_query(cypher, params)

    async def _create_subsidiary_relationship(
        self,
        parent_id: str,
        subsidiary_id: str,
        record: SubsidiaryRecord,
        filing_id: str,
    ) -> None:
        """Create OWNS relationship from parent to subsidiary."""
        cypher = """
            MATCH (parent:Company {id: $parent_id})
            MATCH (sub:Company {id: $subsidiary_id})
            MATCH (f:Filing {id: $filing_id})
            MERGE (parent)-[r:OWNS]->(sub)
            SET r.percentage = $percentage,
                r.is_wholly_owned = $is_wholly_owned,
                r.extraction_method = $extraction_method,
                r.confidence = $confidence,
                r.source_filing = $filing_id,
                r.raw_text = $raw_text,
                r.source_section = $source_section,
                r.source_table = $source_table,
                r.updated_at = datetime()
            MERGE (sub)-[:MENTIONED_IN]->(f)
        """

        params = {
            "parent_id": parent_id,
            "subsidiary_id": subsidiary_id,
            "filing_id": filing_id,
            "percentage": record.ownership_percentage or (100.0 if record.is_wholly_owned else None),
            "is_wholly_owned": record.is_wholly_owned,
            "extraction_method": record.extraction_method.value,
            "confidence": record.confidence,
            "raw_text": record.raw_text,
            "source_section": record.source_section,
            "source_table": record.source_table,
        }

        await Neo4jClient.execute_query(cypher, params)

    async def _create_jurisdiction_relationship(
        self,
        company_id: str,
        jurisdiction: str,
    ) -> None:
        """Create INCORPORATED_IN relationship to jurisdiction."""
        # First ensure jurisdiction exists
        cypher = """
            MERGE (j:Jurisdiction {code: $code})
            ON CREATE SET
                j.name = $name,
                j.country = $country
            WITH j
            MATCH (c:Company {id: $company_id})
            MERGE (c)-[:INCORPORATED_IN]->(j)
        """

        # Determine if it's a US state or country
        us_states = ["Delaware", "California", "New York", "Texas", "Nevada", "Florida"]
        country = "USA" if jurisdiction in us_states else jurisdiction

        params = {
            "code": jurisdiction[:10].upper().replace(" ", "_"),
            "name": jurisdiction,
            "country": country,
            "company_id": company_id,
        }

        await Neo4jClient.execute_query(cypher, params)

    async def _create_officer_relationship(
        self,
        person_id: str,
        company_id: str,
        record: OfficerRecord,
        filing_id: str,
    ) -> None:
        """Create OFFICER_OF relationship."""
        cypher = """
            MATCH (p:Person {id: $person_id})
            MATCH (c:Company {id: $company_id})
            MATCH (f:Filing {id: $filing_id})
            MERGE (p)-[r:OFFICER_OF]->(c)
            SET r.title = $title,
                r.is_executive = $is_executive,
                r.extraction_method = $extraction_method,
                r.confidence = $confidence,
                r.source_filing = $filing_id,
                r.raw_text = $raw_text,
                r.source_section = $source_section,
                r.source_table = $source_table,
                r.updated_at = datetime()
            MERGE (p)-[:MENTIONED_IN]->(f)
        """

        params = {
            "person_id": person_id,
            "company_id": company_id,
            "filing_id": filing_id,
            "title": record.title,
            "is_executive": record.is_executive,
            "extraction_method": record.extraction_method.value,
            "confidence": record.confidence,
            "raw_text": record.raw_text,
            "source_section": record.source_section,
            "source_table": record.source_table,
        }

        await Neo4jClient.execute_query(cypher, params)

    async def _create_director_relationship(
        self,
        person_id: str,
        company_id: str,
        record: OfficerRecord,
        filing_id: str,
    ) -> None:
        """Create DIRECTOR_OF relationship."""
        cypher = """
            MATCH (p:Person {id: $person_id})
            MATCH (c:Company {id: $company_id})
            MATCH (f:Filing {id: $filing_id})
            MERGE (p)-[r:DIRECTOR_OF]->(c)
            SET r.extraction_method = $extraction_method,
                r.confidence = $confidence,
                r.source_filing = $filing_id,
                r.raw_text = $raw_text,
                r.source_section = $source_section,
                r.source_table = $source_table,
                r.updated_at = datetime()
            MERGE (p)-[:MENTIONED_IN]->(f)
        """

        params = {
            "person_id": person_id,
            "company_id": company_id,
            "filing_id": filing_id,
            "extraction_method": record.extraction_method.value,
            "confidence": record.confidence,
            "raw_text": record.raw_text,
            "source_section": record.source_section,
            "source_table": record.source_table,
        }

        await Neo4jClient.execute_query(cypher, params)
