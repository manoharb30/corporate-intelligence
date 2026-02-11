"""Models for evidence chain tracking to substantiate claims."""

import hashlib
from datetime import date
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class ClaimType(str, Enum):
    """Type of claim being made."""
    DIRECT = "direct"           # Fact directly quoted from source
    COMPUTED = "computed"       # Value we calculated (e.g., risk score)
    INFERRED = "inferred"       # Conclusion from graph traversal


class EvidenceStep(BaseModel):
    """Single piece of evidence in a chain."""
    step: int
    fact: str                                           # Human-readable statement
    claim_type: ClaimType
    source_type: str                                    # "SEC_EDGAR", "OPENCORPORATES", etc.
    filing_url: Optional[str] = None                    # Direct link to source
    filing_type: Optional[str] = None                   # "DEF-14A", "10-K", etc.
    filing_accession: Optional[str] = None              # SEC accession number
    filing_date: Optional[date] = None
    source_section: Optional[str] = None                # Section within document
    raw_text: str                                       # Exact text from source (up to 1000 chars)
    raw_text_hash: str                                  # SHA256 hash for verification
    confidence: float = Field(ge=0, le=1)
    extraction_method: Optional[str] = None             # "rule_based" or "llm"

    @classmethod
    def from_relationship_data(
        cls,
        step: int,
        fact: str,
        claim_type: ClaimType,
        rel_data: dict,
        source_type: str = "SEC_EDGAR",
    ) -> "EvidenceStep":
        """Create an EvidenceStep from Neo4j relationship data."""
        raw_text = rel_data.get("raw_text") or ""
        return cls(
            step=step,
            fact=fact,
            claim_type=claim_type,
            source_type=source_type,
            filing_url=rel_data.get("filing_url"),
            filing_type=rel_data.get("filing_type"),
            filing_accession=rel_data.get("filing_accession"),
            filing_date=rel_data.get("filing_date"),
            source_section=rel_data.get("source_section"),
            raw_text=raw_text[:1000],
            raw_text_hash=hashlib.sha256(raw_text.encode()).hexdigest()[:16],
            confidence=rel_data.get("confidence", 0.9),
            extraction_method=rel_data.get("extraction_method"),
        )


class EvidenceChain(BaseModel):
    """Complete evidence chain for any claim."""
    claim: str                                          # The claim being made
    claim_type: ClaimType
    overall_confidence: float = Field(ge=0, le=1)
    evidence_steps: list[EvidenceStep]
    graph_path: Optional[str] = None                    # For inferred: "A -[REL]-> B -[REL]-> C"
    generated_at: date = Field(default_factory=date.today)

    @property
    def step_count(self) -> int:
        return len(self.evidence_steps)

    @property
    def has_source_text(self) -> bool:
        return any(step.raw_text for step in self.evidence_steps)


class ConnectionClaim(BaseModel):
    """A claimed connection between two entities."""
    entity_a_id: str
    entity_a_name: str
    entity_b_id: str
    entity_b_name: str
    connection_type: str                                # "ownership", "directorship", "shared_owner", etc.
    claim: str                                          # Human-readable claim
    claim_type: ClaimType
    evidence_chain: EvidenceChain
    path_length: int                                    # Number of hops


class RiskFactor(BaseModel):
    """Individual risk factor with evidence."""
    factor_name: str
    factor_description: str
    weight: int                                         # Points added to risk score
    source_type: str
    filing_url: Optional[str] = None
    filing_type: Optional[str] = None
    raw_text: Optional[str] = None
    confidence: float = Field(ge=0, le=1)


class RiskAssessment(BaseModel):
    """Risk assessment with full evidence chain."""
    entity_id: str
    entity_name: Optional[str] = None
    risk_score: int = Field(ge=0)
    risk_level: str                                     # LOW, MEDIUM, HIGH, CRITICAL
    factor_count: int
    risk_factors: list[RiskFactor]
    evidence_chain: EvidenceChain
    assessed_at: date = Field(default_factory=date.today)


class SharedConnection(BaseModel):
    """A shared connection between two entities."""
    shared_entity_id: str
    shared_entity_name: str
    shared_entity_type: str                             # "Person", "Company", "Address"
    connection_to_a: str                                # Relationship type
    connection_to_b: str                                # Relationship type
    evidence_a: EvidenceStep
    evidence_b: EvidenceStep


class SharedConnectionsResult(BaseModel):
    """Result of finding shared connections."""
    entity_a_id: str
    entity_a_name: str
    entity_b_id: str
    entity_b_name: str
    shared_connections: list[SharedConnection]
    total_count: int
