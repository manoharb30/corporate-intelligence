"""Graph exploration and visualization endpoints."""

from typing import Optional

from fastapi import APIRouter, Query

from app.models import GraphResponse
from app.services.graph_service import GraphService

router = APIRouter()


@router.get("/entity/{entity_id}", response_model=GraphResponse)
async def get_entity_graph(
    entity_id: str,
    depth: int = Query(2, ge=1, le=5),
    include_filings: bool = Query(False),
) -> GraphResponse:
    """Get graph neighborhood around an entity."""
    return await GraphService.get_entity_neighborhood(
        entity_id=entity_id,
        depth=depth,
        include_filings=include_filings,
    )


@router.get("/ownership/{entity_id}", response_model=GraphResponse)
async def get_ownership_graph(
    entity_id: str,
    direction: str = Query("both", pattern="^(up|down|both)$"),
    max_depth: int = Query(5, ge=1, le=10),
) -> GraphResponse:
    """Get ownership structure graph for an entity.

    direction:
        - up: Get parent owners (who owns this entity)
        - down: Get subsidiaries (what this entity owns)
        - both: Get full ownership structure
    """
    return await GraphService.get_ownership_graph(
        entity_id=entity_id,
        direction=direction,
        max_depth=max_depth,
    )


@router.get("/path")
async def find_path(
    source_id: str,
    target_id: str,
    max_depth: int = Query(6, ge=1, le=10),
) -> GraphResponse:
    """Find shortest path between two entities."""
    return await GraphService.find_shortest_path(
        source_id=source_id,
        target_id=target_id,
        max_depth=max_depth,
    )


@router.get("/address-clusters")
async def get_address_clusters(
    min_entities: int = Query(5, ge=2),
    limit: int = Query(20, ge=1, le=100),
) -> list[dict]:
    """Find addresses with multiple entities registered (potential shell company indicators)."""
    return await GraphService.get_address_clusters(min_entities, limit)


@router.get("/secrecy-jurisdictions")
async def get_secrecy_jurisdiction_entities(
    min_secrecy_score: float = Query(60.0, ge=0, le=100),
    limit: int = Query(50, ge=1, le=200),
) -> list[dict]:
    """Find entities incorporated in secrecy jurisdictions."""
    return await GraphService.get_secrecy_jurisdiction_entities(
        min_secrecy_score=min_secrecy_score,
        limit=limit,
    )


@router.get("/risk-indicators/{entity_id}")
async def get_risk_indicators(entity_id: str) -> dict:
    """Analyze risk indicators for an entity.

    Checks for:
    - Ownership complexity (long chains, circular ownership)
    - Secrecy jurisdiction involvement
    - PEP/sanctioned connections
    - Address clustering
    """
    return await GraphService.analyze_risk_indicators(entity_id)
