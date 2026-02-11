"""API endpoints for connections with evidence chains."""

from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from app.services.connection_service import ConnectionService
from app.services.risk_service import RiskService
from app.models.evidence_models import (
    ConnectionClaim,
    SharedConnectionsResult,
    RiskAssessment,
)

router = APIRouter()


@router.get("/multi-layer")
async def find_multi_layer_connections(
    company_a: str = Query(..., description="Name of first company"),
    company_b: str = Query(..., description="Name of second company"),
):
    """
    Find all multi-layer connections between two companies.

    Analyzes multiple connection types:
    - Board interlocks (shared directors)
    - Executive overlaps (people working at both)
    - Shared subsidiaries (companies owned by both)
    - Ownership paths (direct/indirect ownership chains)

    Returns connection strength: none, weak, moderate, or strong

    Example:
        GET /connections/multi-layer?company_a=Apple%20Inc.&company_b=Johnson%20%26%20Johnson
        GET /connections/multi-layer?company_a=Nikola%20Corp&company_b=Romeo%20Power%2C%20Inc.
    """
    result = await ConnectionService.find_multi_layer_connections(
        company_a_name=company_a,
        company_b_name=company_b,
    )

    return result.to_dict()


@router.get("/find", response_model=ConnectionClaim)
async def find_connection(
    entity_a: str = Query(..., description="ID or name of first entity"),
    entity_b: str = Query(..., description="ID or name of second entity"),
    max_hops: int = Query(4, ge=1, le=10, description="Maximum path length"),
    by_name: bool = Query(False, description="Search by name instead of ID"),
):
    """
    Find connection between two entities with full evidence chain.

    Returns:
    - claim: Human-readable connection claim
    - claim_type: "inferred" (based on graph traversal)
    - evidence_chain: Array of evidence steps, each with source citation
    - graph_path: Visual representation of the path

    Example:
        GET /connections/find?entity_a=tim-cook-id&entity_b=vanguard-id
        GET /connections/find?entity_a=Tim%20Cook&entity_b=Vanguard&by_name=true
    """
    if by_name:
        result = await ConnectionService.find_connection_by_name(
            entity_a_name=entity_a,
            entity_b_name=entity_b,
            max_hops=max_hops,
        )
    else:
        result = await ConnectionService.find_connection_with_evidence(
            entity_a_id=entity_a,
            entity_b_id=entity_b,
            max_hops=max_hops,
        )

    if not result:
        raise HTTPException(
            status_code=404,
            detail=f"No connection found between '{entity_a}' and '{entity_b}' within {max_hops} hops"
        )

    return result


@router.get("/shared", response_model=SharedConnectionsResult)
async def find_shared_connections(
    entity_a: str = Query(..., description="ID of first entity"),
    entity_b: str = Query(..., description="ID of second entity"),
    limit: int = Query(20, ge=1, le=100, description="Maximum results"),
):
    """
    Find shared connections between two entities (common owners, directors, etc.)

    Returns list of shared connections, each with evidence for both relationships.

    Example:
        GET /connections/shared?entity_a=apple-id&entity_b=microsoft-id
    """
    result = await ConnectionService.find_shared_connections(
        entity_a_id=entity_a,
        entity_b_id=entity_b,
        limit=limit,
    )

    return result


@router.get("/risk/{entity_id}", response_model=RiskAssessment)
async def get_risk_assessment(
    entity_id: str,
):
    """
    Get risk assessment for an entity with evidence for each factor.

    Risk levels:
    - LOW: 0-20 points
    - MEDIUM: 21-50 points
    - HIGH: 51-75 points
    - CRITICAL: 76+ points

    Risk factors checked:
    - Secrecy jurisdiction incorporation
    - Mass registration address
    - Circular ownership patterns
    - Long ownership chains (>4 levels)
    - Nominee directors (person on 10+ boards)
    - PEP connections
    - Sanctioned entity connections

    Returns:
    - risk_score: Numeric score (0-100+)
    - risk_level: LOW | MEDIUM | HIGH | CRITICAL
    - risk_factors: List of contributing factors with evidence
    - evidence_chain: Full evidence trail for the score

    Example:
        GET /connections/risk/ff00993a-6122-47d9-806f-f714c3e7e847
    """
    result = await RiskService.calculate_risk_with_evidence(entity_id)
    return result


@router.get("/risk/{entity_id}/summary")
async def get_risk_summary(
    entity_id: str,
):
    """
    Get a simple risk summary without full evidence (for list views).

    Example:
        GET /connections/risk/ff00993a-6122-47d9-806f-f714c3e7e847/summary
    """
    result = await RiskService.get_risk_summary(entity_id)
    return result


@router.get("/entity/{entity_id}")
async def get_entity_connections(
    entity_id: str,
    limit: int = Query(50, ge=1, le=200, description="Maximum results"),
):
    """
    Get all direct connections for an entity with citations.

    Returns connections grouped by type with full citation data for each.

    Example:
        GET /connections/entity/ff00993a-6122-47d9-806f-f714c3e7e847
    """
    connections = await ConnectionService.get_entity_connections_with_evidence(
        entity_id=entity_id,
        limit=limit,
    )

    # Group by relationship type
    by_type: dict[str, list] = {}
    for conn in connections:
        rel_type = conn["relationship"]
        if rel_type not in by_type:
            by_type[rel_type] = []
        by_type[rel_type].append(conn)

    return {
        "entity_id": entity_id,
        "total_connections": len(connections),
        "connections_by_type": by_type,
        "connections": connections,
    }


@router.get("/verify/{entity_id}")
async def verify_entity_claims(
    entity_id: str,
    limit: int = Query(50, ge=1, le=200),
):
    """
    Verify all claims about an entity by checking citation quality.

    Returns verification status for each relationship:
    - verified: High confidence (>=0.9) with raw text
    - partial: High confidence but no raw text
    - unverified: Low confidence or missing source

    Example:
        GET /connections/verify/ff00993a-6122-47d9-806f-f714c3e7e847
    """
    connections = await ConnectionService.get_entity_connections_with_evidence(
        entity_id=entity_id,
        limit=limit,
    )

    verified = []
    partial = []
    unverified = []

    for conn in connections:
        citation = conn.get("citation", {})
        confidence = citation.get("confidence") or 0
        has_raw_text = bool(citation.get("raw_text"))

        verification_status = {
            "connected_entity": conn["connected_entity"]["name"],
            "relationship": conn["relationship"],
            "confidence": confidence,
            "has_raw_text": has_raw_text,
            "filing_accession": citation.get("filing_accession"),
        }

        if confidence >= 0.9 and has_raw_text:
            verification_status["status"] = "verified"
            verified.append(verification_status)
        elif confidence >= 0.9:
            verification_status["status"] = "partial"
            partial.append(verification_status)
        else:
            verification_status["status"] = "unverified"
            unverified.append(verification_status)

    total = len(connections)
    return {
        "entity_id": entity_id,
        "total_claims": total,
        "verified_count": len(verified),
        "partial_count": len(partial),
        "unverified_count": len(unverified),
        "verification_rate": len(verified) / total if total > 0 else 0,
        "verified": verified,
        "partial": partial,
        "unverified": unverified,
    }
