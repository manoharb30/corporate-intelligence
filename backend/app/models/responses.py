"""Pydantic models for API responses."""

from typing import Any, Generic, Optional, TypeVar

from pydantic import BaseModel, Field


T = TypeVar("T")


class PaginatedResponse(BaseModel, Generic[T]):
    """Generic paginated response model."""

    items: list[T]
    total: int
    page: int = Field(..., ge=1)
    page_size: int = Field(..., ge=1, le=100)
    pages: int


class GraphNode(BaseModel):
    """Graph node for visualization."""

    id: str
    label: str
    type: str  # Company, Person, Address, etc.
    properties: dict[str, Any] = {}


class GraphEdge(BaseModel):
    """Graph edge for visualization."""

    id: str
    source: str
    target: str
    type: str  # OWNS, OFFICER_OF, etc.
    properties: dict[str, Any] = {}


class GraphResponse(BaseModel):
    """Response containing graph data for visualization."""

    nodes: list[GraphNode]
    edges: list[GraphEdge]


class OwnershipStep(BaseModel):
    """Single step in an ownership chain."""

    entity_id: str
    entity_name: str
    entity_type: str
    ownership_percentage: Optional[float] = None
    is_beneficial: bool = True


class OwnershipChain(BaseModel):
    """Complete ownership chain from ultimate owner to target."""

    target_id: str
    target_name: str
    chain: list[OwnershipStep]
    total_ownership_percentage: Optional[float] = None
    chain_length: int


class SearchResult(BaseModel):
    """Search result with relevance score."""

    id: str
    name: str
    type: str
    score: float
    highlights: dict[str, str] = {}


class CompanySearchResult(BaseModel):
    """Company search result combining graph and SEC EDGAR sources."""

    cik: str
    name: str
    ticker: Optional[str] = None
    in_graph: bool = False  # True if company already exists in our graph
    company_id: Optional[str] = None  # Graph node ID if in_graph is True


class CompanySearchResponse(BaseModel):
    """Response for company search endpoint."""

    query: str
    results: list[CompanySearchResult]
    graph_count: int  # Number of results from our graph
    edgar_count: int  # Number of results from SEC EDGAR


class PersonSummary(BaseModel):
    """Summary of a person related to a company."""

    id: str
    name: str
    title: Optional[str] = None
    is_officer: bool = False
    is_director: bool = False
    is_beneficial_owner: bool = False
    ownership_percentage: Optional[float] = None
    other_companies_count: int = 0  # Number of other companies this person is connected to
    is_sanctioned: bool = False
    is_pep: bool = False


class SubsidiarySummary(BaseModel):
    """Summary of a subsidiary company."""

    id: str
    name: str
    jurisdiction: Optional[str] = None
    ownership_percentage: Optional[float] = None


class RedFlag(BaseModel):
    """A potential red flag or concern about the company."""

    type: str  # "sanctions_match", "conflict_of_interest", "pep", "complex_structure"
    severity: str  # "high", "medium", "low"
    description: str
    entity_id: Optional[str] = None
    entity_name: Optional[str] = None


class CompanyIntelligenceResponse(BaseModel):
    """Full intelligence response for a company."""

    company_id: str
    company_name: str
    cik: Optional[str] = None
    jurisdiction: Optional[str] = None

    # People connected to this company
    officers: list[PersonSummary] = []
    directors: list[PersonSummary] = []
    beneficial_owners: list[PersonSummary] = []

    # Corporate structure
    subsidiaries: list[SubsidiarySummary] = []
    parent_company: Optional[SubsidiarySummary] = None

    # Red flags and concerns
    red_flags: list[RedFlag] = []

    # Metadata
    data_freshness: Optional[str] = None  # Date of most recent filing
    filings_count: int = 0
