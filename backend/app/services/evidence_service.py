"""Service for building evidence chains to substantiate claims."""

import hashlib
from datetime import date
from typing import Optional

from app.models.evidence_models import (
    ClaimType,
    EvidenceStep,
    EvidenceChain,
    RiskFactor,
)


class EvidenceService:
    """Service for building and managing evidence chains."""

    @staticmethod
    def hash_text(text: str) -> str:
        """Create hash of source text for verification."""
        return hashlib.sha256(text.encode()).hexdigest()[:16]

    @staticmethod
    def build_direct_evidence(
        fact: str,
        source_type: str,
        raw_text: str,
        filing_url: Optional[str] = None,
        filing_type: Optional[str] = None,
        filing_accession: Optional[str] = None,
        filing_date: Optional[date] = None,
        source_section: Optional[str] = None,
        confidence: float = 0.95,
        extraction_method: Optional[str] = None,
    ) -> EvidenceChain:
        """Build evidence chain for a direct fact from a single source."""
        step = EvidenceStep(
            step=1,
            fact=fact,
            claim_type=ClaimType.DIRECT,
            source_type=source_type,
            filing_url=filing_url,
            filing_type=filing_type,
            filing_accession=filing_accession,
            filing_date=filing_date,
            source_section=source_section,
            raw_text=raw_text[:1000],
            raw_text_hash=EvidenceService.hash_text(raw_text),
            confidence=confidence,
            extraction_method=extraction_method,
        )

        return EvidenceChain(
            claim=fact,
            claim_type=ClaimType.DIRECT,
            overall_confidence=confidence,
            evidence_steps=[step],
            generated_at=date.today(),
        )

    @staticmethod
    def build_connection_evidence(
        entity_a_name: str,
        entity_b_name: str,
        path_segments: list[dict],
    ) -> EvidenceChain:
        """
        Build evidence chain for an inferred connection.

        path_segments is a list of dicts with:
        - from_name, to_name: entity names
        - rel_type: relationship type
        - fact: human-readable statement
        - raw_text, source_section, confidence, filing_*, etc.
        """
        steps = []
        path_parts = []
        min_confidence = 1.0

        for i, segment in enumerate(path_segments):
            raw_text = segment.get("raw_text") or ""
            confidence = segment.get("confidence", 0.9)

            step = EvidenceStep(
                step=i + 1,
                fact=segment["fact"],
                claim_type=ClaimType.DIRECT,
                source_type=segment.get("source_type", "SEC_EDGAR"),
                filing_url=segment.get("filing_url"),
                filing_type=segment.get("filing_type"),
                filing_accession=segment.get("filing_accession"),
                filing_date=segment.get("filing_date"),
                source_section=segment.get("source_section"),
                raw_text=raw_text[:1000],
                raw_text_hash=EvidenceService.hash_text(raw_text),
                confidence=confidence,
                extraction_method=segment.get("extraction_method"),
            )
            steps.append(step)
            min_confidence = min(min_confidence, confidence)

            # Build path string visualization
            rel_type = segment.get("rel_type", "CONNECTED")
            from_name = segment.get("from_name", "?")
            to_name = segment.get("to_name", "?")
            path_parts.append(f"{from_name} -[{rel_type}]-> {to_name}")

        claim = f"{entity_a_name} is connected to {entity_b_name}"
        graph_path = " | ".join(path_parts)

        return EvidenceChain(
            claim=claim,
            claim_type=ClaimType.INFERRED,
            overall_confidence=min_confidence,
            evidence_steps=steps,
            graph_path=graph_path,
            generated_at=date.today(),
        )

    @staticmethod
    def build_risk_score_evidence(
        entity_name: str,
        risk_score: int,
        risk_factors: list[RiskFactor],
    ) -> EvidenceChain:
        """Build evidence chain for a computed risk score."""
        steps = []

        for i, factor in enumerate(risk_factors):
            raw_text = factor.raw_text or f"Pattern detected: {factor.factor_name}"

            step = EvidenceStep(
                step=i + 1,
                fact=f"{factor.factor_name}: +{factor.weight} points",
                claim_type=ClaimType.DIRECT if factor.filing_url else ClaimType.COMPUTED,
                source_type=factor.source_type,
                filing_url=factor.filing_url,
                filing_type=factor.filing_type,
                source_section=None,
                raw_text=raw_text[:1000],
                raw_text_hash=EvidenceService.hash_text(raw_text),
                confidence=factor.confidence,
            )
            steps.append(step)

        # Overall confidence for computed values is based on factor confidence
        avg_confidence = (
            sum(f.confidence for f in risk_factors) / len(risk_factors)
            if risk_factors else 0.9
        )

        return EvidenceChain(
            claim=f"{entity_name} has risk score {risk_score}",
            claim_type=ClaimType.COMPUTED,
            overall_confidence=avg_confidence,
            evidence_steps=steps,
            generated_at=date.today(),
        )

    @staticmethod
    def relationship_to_fact(
        from_name: str,
        to_name: str,
        rel_type: str,
        rel_properties: dict,
    ) -> str:
        """Convert relationship to human-readable fact."""
        templates = {
            "OWNS": "{from_name} owns {percentage} of {to_name}",
            "OFFICER_OF": "{from_name} is {title} of {to_name}",
            "DIRECTOR_OF": "{from_name} is a director of {to_name}",
            "REGISTERED_AT": "{from_name} is registered at {to_name}",
            "INCORPORATED_IN": "{from_name} is incorporated in {to_name}",
            "SUBSIDIARY_OF": "{from_name} is a subsidiary of {to_name}",
            "FILED": "{from_name} filed {to_name}",
        }

        template = templates.get(rel_type, "{from_name} is connected to {to_name}")

        # Get percentage string
        percentage = rel_properties.get("percentage")
        if percentage is not None:
            percentage_str = f"{percentage}%"
        else:
            percentage_str = "an unknown percentage"

        # Get title
        title = rel_properties.get("title", "an officer")

        return template.format(
            from_name=from_name,
            to_name=to_name,
            percentage=percentage_str,
            title=title,
        )

    @staticmethod
    def determine_connection_type(rel_types: list[str]) -> str:
        """Determine the type of connection based on relationships in path."""
        rel_set = set(rel_types)

        if "OWNS" in rel_set:
            return "ownership"
        if "DIRECTOR_OF" in rel_set:
            return "directorship"
        if "OFFICER_OF" in rel_set:
            return "executive"
        if "REGISTERED_AT" in rel_set:
            return "address"
        if "INCORPORATED_IN" in rel_set:
            return "jurisdiction"
        return "indirect"
