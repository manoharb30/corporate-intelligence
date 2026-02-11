"""Neo4j database client for the Corporate Intelligence Graph."""

from contextlib import asynccontextmanager
from typing import Any, AsyncGenerator

from neo4j import AsyncGraphDatabase, AsyncDriver, AsyncSession
from neo4j.exceptions import ServiceUnavailable, AuthError

from app.config import settings


class Neo4jClient:
    """Async Neo4j database client."""

    _driver: AsyncDriver | None = None

    @classmethod
    async def connect(cls) -> None:
        """Initialize the Neo4j driver connection."""
        if cls._driver is not None:
            return

        cls._driver = AsyncGraphDatabase.driver(
            settings.NEO4J_URI,
            auth=(settings.NEO4J_USER, settings.NEO4J_PASSWORD),
            max_connection_lifetime=3600,
            max_connection_pool_size=50,
            connection_acquisition_timeout=60,
        )

        # Verify connectivity
        try:
            await cls._driver.verify_connectivity()
        except ServiceUnavailable as e:
            raise ConnectionError(f"Failed to connect to Neo4j: {e}")
        except AuthError as e:
            raise ConnectionError(f"Neo4j authentication failed: {e}")

    @classmethod
    async def disconnect(cls) -> None:
        """Close the Neo4j driver connection."""
        if cls._driver is not None:
            await cls._driver.close()
            cls._driver = None

    @classmethod
    def get_driver(cls) -> AsyncDriver:
        """Get the Neo4j driver instance."""
        if cls._driver is None:
            raise RuntimeError("Neo4j client not initialized. Call connect() first.")
        return cls._driver

    @classmethod
    @asynccontextmanager
    async def get_session(cls) -> AsyncGenerator[AsyncSession, None]:
        """Get a Neo4j session as an async context manager."""
        driver = cls.get_driver()
        session = driver.session()
        try:
            yield session
        finally:
            await session.close()

    @classmethod
    async def execute_query(
        cls,
        query: str,
        parameters: dict[str, Any] | None = None,
        database: str | None = None,
    ) -> list[dict[str, Any]]:
        """Execute a Cypher query and return results as a list of dicts."""
        async with cls.get_session() as session:
            result = await session.run(query, parameters or {})
            records = await result.data()
            return records

    @classmethod
    async def execute_write(
        cls,
        query: str,
        parameters: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Execute a write transaction and return summary info."""
        async with cls.get_session() as session:
            result = await session.run(query, parameters or {})
            summary = await result.consume()
            return {
                "nodes_created": summary.counters.nodes_created,
                "nodes_deleted": summary.counters.nodes_deleted,
                "relationships_created": summary.counters.relationships_created,
                "relationships_deleted": summary.counters.relationships_deleted,
                "properties_set": summary.counters.properties_set,
            }


# Dependency for FastAPI
async def get_neo4j_session() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency for Neo4j session."""
    async with Neo4jClient.get_session() as session:
        yield session
