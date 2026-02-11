"""Pydantic models for SEC EDGAR data extraction."""

from datetime import date, datetime
from enum import Enum
from typing import Optional, TYPE_CHECKING

from pydantic import BaseModel, Field

if TYPE_CHECKING:
    from app.models.citation_models import SourceCitation


class ExtractionMethod(str, Enum):
    """Method used to extract data."""

    RULE_BASED = "rule_based"
    LLM = "llm"
    MANUAL = "manual"
    HYBRID = "hybrid"


class ExtractionMetadata(BaseModel):
    """Metadata about the extraction process."""

    method: ExtractionMethod
    confidence: float = Field(ge=0, le=1)
    extracted_at: datetime = Field(default_factory=datetime.utcnow)
    source_filing_id: Optional[str] = None
    source_url: Optional[str] = None
    section_name: Optional[str] = Field(None, description="Section where data was found")
    table_name: Optional[str] = Field(None, description="Table name if from a table")


class OwnershipRecord(BaseModel):
    """Extracted beneficial ownership record."""

    owner_name: str = Field(..., min_length=1)
    owner_type: str = Field(..., pattern="^(person|company)$")
    shares_owned: Optional[int] = Field(None, ge=0)
    percentage: Optional[float] = Field(None, ge=0, le=100)
    is_beneficial: bool = True
    is_direct: bool = True
    as_of_date: Optional[date] = None
    extraction_method: ExtractionMethod
    confidence: float = Field(ge=0, le=1)
    raw_text: Optional[str] = Field(None, description="Original text snippet for verification")

    # Citation fields
    source_section: Optional[str] = Field(None, description="Section where this was found")
    source_table: Optional[str] = Field(None, description="Table name if from a table")
    context_before: Optional[str] = Field(None, description="Text before the data")
    context_after: Optional[str] = Field(None, description="Text after the data")


class OwnershipExtractionResult(BaseModel):
    """Result of ownership extraction from a filing."""

    records: list[OwnershipRecord] = []
    filing_accession: str
    filing_type: str
    company_cik: str
    company_name: Optional[str] = None
    extraction_metadata: ExtractionMetadata
    warnings: list[str] = []

    # Filing context for citations
    filing_date: Optional[date] = Field(None, description="Date of the filing")
    filing_url: Optional[str] = Field(None, description="URL to the filing")


class SubsidiaryRecord(BaseModel):
    """Extracted subsidiary record from 10-K Exhibit 21."""

    name: str = Field(..., min_length=1)
    jurisdiction: Optional[str] = None
    state_of_incorporation: Optional[str] = None
    ownership_percentage: Optional[float] = Field(None, ge=0, le=100)
    is_wholly_owned: bool = False
    parent_name: Optional[str] = None
    extraction_method: ExtractionMethod
    confidence: float = Field(ge=0, le=1)
    raw_text: Optional[str] = None

    # Citation fields
    source_section: Optional[str] = Field(None, description="Section where this was found")
    source_table: Optional[str] = Field(None, description="Table name if from a table")
    context_before: Optional[str] = Field(None, description="Text before the data")
    context_after: Optional[str] = Field(None, description="Text after the data")


class SubsidiaryExtractionResult(BaseModel):
    """Result of subsidiary extraction from 10-K Exhibit 21."""

    records: list[SubsidiaryRecord] = []
    filing_accession: str
    company_cik: str
    company_name: Optional[str] = None
    extraction_metadata: ExtractionMetadata
    warnings: list[str] = []

    # Filing context for citations
    filing_date: Optional[date] = Field(None, description="Date of the filing")
    filing_url: Optional[str] = Field(None, description="URL to the filing")


class OfficerRecord(BaseModel):
    """Extracted officer/director record."""

    name: str = Field(..., min_length=1)
    title: Optional[str] = None
    is_director: bool = False
    is_officer: bool = False
    is_executive: bool = False
    age: Optional[int] = Field(None, ge=25, le=100)
    tenure_start: Optional[date] = None
    other_affiliations: list[str] = []
    extraction_method: ExtractionMethod
    confidence: float = Field(ge=0, le=1)
    raw_text: Optional[str] = None

    # Citation fields
    source_section: Optional[str] = Field(None, description="Section where this was found")
    source_table: Optional[str] = Field(None, description="Table name if from a table")
    context_before: Optional[str] = Field(None, description="Text before the data")
    context_after: Optional[str] = Field(None, description="Text after the data")


class OfficerExtractionResult(BaseModel):
    """Result of officer/director extraction from DEF-14A."""

    records: list[OfficerRecord] = []
    filing_accession: str
    company_cik: str
    company_name: Optional[str] = None
    extraction_metadata: ExtractionMetadata
    warnings: list[str] = []

    # Filing context for citations
    filing_date: Optional[date] = Field(None, description="Date of the filing")
    filing_url: Optional[str] = Field(None, description="URL to the filing")


class Schedule13Record(BaseModel):
    """Extracted Schedule 13D/13G record."""

    filer_name: str = Field(..., min_length=1)
    filer_type: str = Field(..., pattern="^(person|company|group)$")
    subject_company: str
    subject_cik: Optional[str] = None
    shares_owned: Optional[int] = Field(None, ge=0)
    percentage: Optional[float] = Field(None, ge=0, le=100)
    filing_date: Optional[date] = None
    event_date: Optional[date] = None
    acquisition_type: Optional[str] = None
    purpose: Optional[str] = None
    extraction_method: ExtractionMethod
    confidence: float = Field(ge=0, le=1)
    raw_text: Optional[str] = None

    # Citation fields
    source_section: Optional[str] = Field(None, description="Section where this was found")
    source_table: Optional[str] = Field(None, description="Table name if from a table")
    context_before: Optional[str] = Field(None, description="Text before the data")
    context_after: Optional[str] = Field(None, description="Text after the data")


class Schedule13ExtractionResult(BaseModel):
    """Result of Schedule 13D/13G extraction."""

    records: list[Schedule13Record] = []
    filing_accession: str
    filing_type: str  # "13D" or "13G"
    extraction_metadata: ExtractionMetadata
    warnings: list[str] = []

    # Filing context for citations
    filing_date: Optional[date] = Field(None, description="Date of the filing")
    filing_url: Optional[str] = Field(None, description="URL to the filing")
    filer_cik: Optional[str] = Field(None, description="CIK of the filer")


# LLM extraction request/response models
class LLMOwnershipRequest(BaseModel):
    """Schema for LLM ownership extraction."""

    owners: list[dict] = Field(
        ...,
        description="List of beneficial owners extracted from the text"
    )


class LLMSubsidiaryRequest(BaseModel):
    """Schema for LLM subsidiary extraction."""

    subsidiaries: list[dict] = Field(
        ...,
        description="List of subsidiaries extracted from the text"
    )


class LLMOfficerRequest(BaseModel):
    """Schema for LLM officer extraction."""

    officers: list[dict] = Field(
        ...,
        description="List of officers and directors extracted from the text"
    )
