"""Neo4j database client for the Corporate Intelligence Graph."""

import logging
from contextlib import asynccontextmanager
from typing import Any, AsyncGenerator

from neo4j import AsyncGraphDatabase, AsyncDriver, AsyncSession
from neo4j.exceptions import ServiceUnavailable, AuthError, SessionExpired

logger = logging.getLogger(__name__)

from app.config import settings


class Neo4jClient:
    """Async Neo4j database client."""

    _driver: AsyncDriver | None = None

    @classmethod
    async def connect(cls, max_retries: int = 3) -> None:
        """Initialize the Neo4j driver connection with retry on failure."""
        if cls._driver is not None:
            return

        cls._driver = AsyncGraphDatabase.driver(
            settings.NEO4J_URI,
            auth=(settings.NEO4J_USER, settings.NEO4J_PASSWORD),
            max_connection_lifetime=300,
            max_connection_pool_size=50,
            connection_acquisition_timeout=60,
            keep_alive=True,
        )

        # Verify connectivity with retries
        import asyncio as _asyncio
        for attempt in range(max_retries + 1):
            try:
                await cls._driver.verify_connectivity()
                return
            except AuthError as e:
                raise ConnectionError(f"Neo4j authentication failed: {e}")
            except Exception as e:
                if attempt < max_retries:
                    wait = 5 * (attempt + 1)
                    logger.warning(f"Neo4j connect attempt {attempt + 1}/{max_retries + 1} failed, retrying in {wait}s: {e}")
                    await _asyncio.sleep(wait)
                    # Reset driver for fresh attempt
                    try:
                        await cls._driver.close()
                    except Exception:
                        pass
                    cls._driver = AsyncGraphDatabase.driver(
                        settings.NEO4J_URI,
                        auth=(settings.NEO4J_USER, settings.NEO4J_PASSWORD),
                        max_connection_lifetime=300,
                        max_connection_pool_size=50,
                        connection_acquisition_timeout=60,
                        keep_alive=True,
                    )
                else:
                    raise ConnectionError(f"Failed to connect to Neo4j after {max_retries + 1} attempts: {e}")

    @classmethod
    async def reconnect(cls) -> None:
        """Force-close and re-establish the Neo4j driver connection."""
        await cls.disconnect()
        await cls.connect()

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
    async def _is_connection_error(cls, exc: Exception) -> bool:
        """Check if an exception is a stale/dropped connection error."""
        msg = str(exc).lower()
        return isinstance(exc, (ServiceUnavailable, SessionExpired, OSError)) or \
            "timed out" in msg or "defunct connection" in msg or \
            "routing" in msg or "failed to read" in msg

    @classmethod
    async def execute_query(
        cls,
        query: str,
        parameters: dict[str, Any] | None = None,
        database: str | None = None,
    ) -> list[dict[str, Any]]:
        """Execute a Cypher query and return results as a list of dicts.
        Auto-retries once on stale connection errors (Aura load balancer drops).
        """
        try:
            async with cls.get_session() as session:
                result = await session.run(query, parameters or {})
                records = await result.data()
                return records
        except Exception as e:
            if await cls._is_connection_error(e):
                logger.warning(f"Neo4j connection error, reconnecting and retrying: {e}")
                await cls.reconnect()
                async with cls.get_session() as session:
                    result = await session.run(query, parameters or {})
                    records = await result.data()
                    return records
            raise

    @classmethod
    async def execute_write(
        cls,
        query: str,
        parameters: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Execute a write transaction and return summary info.
        Auto-retries once on stale connection errors (Aura load balancer drops).
        """
        try:
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
        except Exception as e:
            if await cls._is_connection_error(e):
                logger.warning(f"Neo4j connection error, reconnecting and retrying: {e}")
                await cls.reconnect()
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
            raise


# Dependency for FastAPI
async def get_neo4j_session() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency for Neo4j session."""
    async with Neo4jClient.get_session() as session:
        yield session
