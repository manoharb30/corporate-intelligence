"""Citation models for tracking data provenance."""

from datetime import date, datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class FactType(str, Enum):
    """Types of facts that can be cited."""
    OFFICER_ROLE = "officer_role"
    DIRECTOR_ROLE = "director_role"
    OWNERSHIP_PERCENTAGE = "ownership_percentage"
    SHARES_OWNED = "shares_owned"
    SUBSIDIARY_RELATIONSHIP = "subsidiary_relationship"
    COMPANY_JURISDICTION = "company_jurisdiction"
    COMPANY_ADDRESS = "company_address"
    PERSON_AGE = "person_age"
    COMPENSATION = "compensation"
    FILING_DATE = "filing_date"
    OTHER = "other"


class SourceCitation(BaseModel):
    """Citation pointing to exact source of extracted data."""

    # Filing identification
    filing_accession: str = Field(..., description="SEC EDGAR accession number")
    filing_type: str = Field(..., description="Form type (DEF 14A, 10-K, etc.)")
    filing_date: Optional[date] = Field(None, description="Date filing was submitted")
    filing_url: Optional[str] = Field(None, description="Direct URL to filing on SEC EDGAR")

    # Location within document
    page_number: Optional[int] = Field(None, description="Page number if determinable")
    section_name: Optional[str] = Field(None, description="Section name (e.g., 'Security Ownership')")
    table_name: Optional[str] = Field(None, description="Table name if extracted from table")

    # Source text
    raw_text_snippet: str = Field(..., description="Exact text snippet from source (50-500 chars)")
    context_before: Optional[str] = Field(None, description="Text before the snippet for context")
    context_after: Optional[str] = Field(None, description="Text after the snippet for context")

    # Extraction metadata
    confidence: float = Field(
        default=0.95,
        ge=0.0,
        le=1.0,
        description="Confidence score for this citation"
    )
    extraction_method: str = Field(
        default="rule_based",
        description="Method used to extract (rule_based, llm, hybrid)"
    )
    extracted_at: datetime = Field(
        default_factory=datetime.utcnow,
        description="When this data was extracted"
    )

    def to_neo4j_props(self) -> dict:
        """Convert to Neo4j property dictionary."""
        return {
            "filing_accession": self.filing_accession,
            "filing_type": self.filing_type,
            "filing_date": self.filing_date.isoformat() if self.filing_date else None,
            "filing_url": self.filing_url,
            "page_number": self.page_number,
            "section_name": self.section_name,
            "table_name": self.table_name,
            "raw_text_snippet": self.raw_text_snippet[:500],  # Limit size
            "confidence": self.confidence,
            "extraction_method": self.extraction_method,
            "extracted_at": self.extracted_at.isoformat(),
        }


class CitedFact(BaseModel):
    """A single fact with its citation."""

    fact_type: FactType = Field(..., description="Type of fact being cited")
    fact_value: str = Field(..., description="The extracted value")
    citation: SourceCitation = Field(..., description="Source citation for this fact")

    # Optional additional context
    entity_name: Optional[str] = Field(None, description="Name of entity this fact is about")
    related_entity: Optional[str] = Field(None, description="Related entity if applicable")


class CitationSummary(BaseModel):
    """Summary of citations for an entity or relationship."""

    total_citations: int = Field(default=0, description="Total number of citations")
    filing_types: list[str] = Field(default_factory=list, description="Types of filings cited")
    date_range: Optional[tuple[date, date]] = Field(None, description="Date range of citations")
    avg_confidence: float = Field(default=0.0, description="Average confidence score")
    extraction_methods: list[str] = Field(
        default_factory=list,
        description="Methods used for extraction"
    )


class CitationQuery(BaseModel):
    """Query parameters for citation lookup."""

    entity_id: Optional[str] = Field(None, description="Entity ID to get citations for")
    entity_name: Optional[str] = Field(None, description="Entity name to search")
    fact_type: Optional[FactType] = Field(None, description="Filter by fact type")
    filing_type: Optional[str] = Field(None, description="Filter by filing type")
    min_confidence: float = Field(default=0.0, description="Minimum confidence threshold")
    limit: int = Field(default=50, le=200, description="Maximum results to return")
