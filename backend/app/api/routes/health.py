"""Health check endpoints."""

from fastapi import APIRouter, HTTPException

from app.db.neo4j_client import Neo4jClient

router = APIRouter()


@router.get("/health")
async def health_check() -> dict[str, str]:
    """Basic health check."""
    return {"status": "healthy"}


@router.get("/health/db")
async def database_health() -> dict[str, str]:
    """Check Neo4j database connectivity."""
    try:
        driver = Neo4jClient.get_driver()
        await driver.verify_connectivity()
        return {"status": "healthy", "database": "connected"}
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Database unhealthy: {str(e)}")
