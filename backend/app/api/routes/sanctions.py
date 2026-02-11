"""API endpoints for OFAC sanctions checking."""

from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from app.services.sanctions_service import (
    SanctionsService,
    SanctionsExposure,
    SanctionConnection,
)

router = APIRouter()


@router.get("/check/{entity_id}")
async def check_sanctions(entity_id: str):
    """
    Check if an entity is sanctioned or linked to sanctioned entities.

    Returns:
    - is_sanctioned: Whether entity is directly sanctioned or linked
    - sanction_type: 'direct' (OFAC entry) or 'linked' (matched to OFAC entry)
    - programs: List of sanctions programs (SDGT, IRAN, etc.)
    - ofac_uid: OFAC unique identifier

    Example:
        GET /sanctions/check/ff00993a-6122-47d9-806f-f714c3e7e847
    """
    result = await SanctionsService.check_entity_sanctions(entity_id)

    if not result.get("found"):
        raise HTTPException(status_code=404, detail=f"Entity {entity_id} not found")

    return result


@router.get("/check/by-name/{entity_name:path}")
async def check_sanctions_by_name(entity_name: str):
    """
    Check if an entity is sanctioned by name search.

    This endpoint searches for the entity by name first, then checks sanctions.

    Example:
        GET /sanctions/check/by-name/Apple%20Inc.
    """
    # First find the entity
    from app.db.neo4j_client import Neo4jClient

    query = """
        MATCH (e)
        WHERE e:Person OR e:Company
        AND toLower(e.name) = toLower($name)
        RETURN e.id as id, e.name as name
        LIMIT 1
    """
    results = await Neo4jClient.execute_query(query, {"name": entity_name})

    if not results:
        # Try partial match
        query = """
            MATCH (e)
            WHERE (e:Person OR e:Company)
            AND toLower(e.name) CONTAINS toLower($name)
            RETURN e.id as id, e.name as name
            LIMIT 1
        """
        results = await Neo4jClient.execute_query(query, {"name": entity_name})

    if not results:
        raise HTTPException(
            status_code=404,
            detail=f"No entity found matching '{entity_name}'"
        )

    entity_id = results[0]["id"]
    result = await SanctionsService.check_entity_sanctions(entity_id)
    result["searched_name"] = entity_name
    result["matched_name"] = results[0]["name"]

    return result


@router.get("/exposure/{entity_id}", response_model=SanctionsExposure)
async def get_sanctions_exposure(
    entity_id: str,
    max_hops: int = Query(3, ge=1, le=6, description="Maximum hops to search"),
):
    """
    Get full sanctions exposure report for an entity.

    Checks for:
    - Direct sanctions (entity itself on SDN list)
    - Ownership by sanctioned entities
    - Sanctioned directors/officers
    - Indirect connections within N hops

    Returns risk level:
    - NONE: No sanctions exposure
    - LOW: Indirect connection (3+ hops away)
    - MEDIUM: Indirect connection (2 hops away)
    - HIGH: Direct sanction or 1-hop connection

    Example:
        GET /sanctions/exposure/ff00993a-6122-47d9-806f-f714c3e7e847
    """
    exposure = await SanctionsService.get_sanctions_exposure(entity_id, max_hops)

    if exposure.entity_name == "Unknown":
        raise HTTPException(status_code=404, detail=f"Entity {entity_id} not found")

    return exposure


@router.get("/connections/{entity_id}", response_model=list[SanctionConnection])
async def get_sanction_connections(
    entity_id: str,
    max_hops: int = Query(3, ge=1, le=6, description="Maximum hops to search"),
):
    """
    Find all paths from an entity to sanctioned entities.

    Returns list of connections with:
    - sanctioned_entity: Name of the sanctioned party
    - ofac_uid: OFAC identifier
    - programs: Sanctions programs
    - hops: Number of relationship hops
    - path: Human-readable path description

    Example:
        GET /sanctions/connections/ff00993a-6122-47d9-806f-f714c3e7e847
    """
    connections = await SanctionsService.check_connection_to_sanctioned(
        entity_id, max_hops
    )

    return connections


@router.get("/list/stats")
async def get_sdn_stats():
    """
    Get statistics about loaded SDN data.

    Returns:
    - total_sanctioned: Total number of SDN entries loaded
    - sanctioned_persons: Number of individuals
    - sanctioned_companies: Number of entities
    - last_update: Date of last SDN list update

    Example:
        GET /sanctions/list/stats
    """
    return await SanctionsService.get_sdn_stats()


@router.get("/list/search")
async def search_sdn_list(
    q: str = Query(..., min_length=2, description="Search query"),
    entity_type: Optional[str] = Query(
        None, regex="^(person|company)$", description="Filter by type"
    ),
    limit: int = Query(20, ge=1, le=100, description="Maximum results"),
):
    """
    Search the SDN list by name or alias.

    Args:
        q: Search string (searches name and aliases)
        entity_type: 'person' or 'company' (optional filter)
        limit: Maximum results to return

    Example:
        GET /sanctions/list/search?q=bank&entity_type=company
    """
    results = await SanctionsService.search_sanctioned_entities(
        query_str=q,
        entity_type=entity_type,
        limit=limit,
    )

    return {
        "query": q,
        "entity_type": entity_type,
        "count": len(results),
        "results": results,
    }


@router.get("/list/programs")
async def get_sanction_programs():
    """
    Get list of all sanctions programs in the loaded SDN data.

    Example:
        GET /sanctions/list/programs
    """
    from app.db.neo4j_client import Neo4jClient

    query = """
        MATCH (n:SanctionedEntity)
        WHERE n.source = 'ofac' AND n.sanction_programs IS NOT NULL
        UNWIND n.sanction_programs as program
        RETURN program, count(*) as count
        ORDER BY count DESC
    """

    results = await Neo4jClient.execute_query(query)

    return {
        "programs": [
            {"name": r["program"], "count": r["count"]}
            for r in results
        ]
    }
