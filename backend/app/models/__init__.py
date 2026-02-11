"""Pydantic models for the Corporate Intelligence Graph."""

from app.models.nodes import (
    Company,
    CompanyCreate,
    CompanyUpdate,
    Person,
    PersonCreate,
    PersonUpdate,
    Address,
    AddressCreate,
    Filing,
    FilingCreate,
    Jurisdiction,
    JurisdictionCreate,
)
from app.models.relationships import (
    Ownership,
    OwnershipCreate,
    OfficerRelation,
    DirectorRelation,
    SameAsRelation,
)
from app.models.responses import (
    PaginatedResponse,
    GraphResponse,
    GraphNode,
    GraphEdge,
    OwnershipChain,
    CompanySearchResult,
    CompanySearchResponse,
    PersonSummary,
    SubsidiarySummary,
    RedFlag,
    CompanyIntelligenceResponse,
)
from app.models.extraction_models import (
    ExtractionMethod,
    ExtractionMetadata,
    OwnershipRecord,
    OwnershipExtractionResult,
    SubsidiaryRecord,
    SubsidiaryExtractionResult,
    OfficerRecord,
    OfficerExtractionResult,
    Schedule13Record,
    Schedule13ExtractionResult,
)
from app.models.citation_models import (
    FactType,
    SourceCitation,
    CitedFact,
    CitationSummary,
    CitationQuery,
)
from app.models.filing_metadata import (
    FilingContext,
    DocumentSection,
    TableContext,
    ExtractionContext,
)

__all__ = [
    # Nodes
    "Company",
    "CompanyCreate",
    "CompanyUpdate",
    "Person",
    "PersonCreate",
    "PersonUpdate",
    "Address",
    "AddressCreate",
    "Filing",
    "FilingCreate",
    "Jurisdiction",
    "JurisdictionCreate",
    # Relationships
    "Ownership",
    "OwnershipCreate",
    "OfficerRelation",
    "DirectorRelation",
    "SameAsRelation",
    # Responses
    "PaginatedResponse",
    "GraphResponse",
    "GraphNode",
    "GraphEdge",
    "OwnershipChain",
    "CompanySearchResult",
    "CompanySearchResponse",
    "PersonSummary",
    "SubsidiarySummary",
    "RedFlag",
    "CompanyIntelligenceResponse",
    # Extraction
    "ExtractionMethod",
    "ExtractionMetadata",
    "OwnershipRecord",
    "OwnershipExtractionResult",
    "SubsidiaryRecord",
    "SubsidiaryExtractionResult",
    "OfficerRecord",
    "OfficerExtractionResult",
    "Schedule13Record",
    "Schedule13ExtractionResult",
    # Citations
    "FactType",
    "SourceCitation",
    "CitedFact",
    "CitationSummary",
    "CitationQuery",
    # Filing Metadata
    "FilingContext",
    "DocumentSection",
    "TableContext",
    "ExtractionContext",
]
