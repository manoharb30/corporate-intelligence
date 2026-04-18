"""FastAPI application entry point for Corporate Intelligence Graph."""

from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.db.neo4j_client import Neo4jClient
from app.api.routes import health, event_detail, scanner, activist, snapshot, signal_performance, explorer


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan handler for startup and shutdown."""
    # Startup
    await Neo4jClient.connect()
    # Warm the connection pool so first user request is fast
    try:
        await Neo4jClient.execute_query("RETURN 1", {})
    except Exception:
        pass
    yield
    # Shutdown
    await Neo4jClient.disconnect()


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="Beneficial ownership intelligence platform using Neo4j graph database",
    lifespan=lifespan,
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers — only routes needed by new dashboard
app.include_router(health.router, prefix="/api", tags=["Health"])
app.include_router(snapshot.router, prefix="/api/snapshot", tags=["Snapshot"])
app.include_router(event_detail.router, prefix="/api/event-detail", tags=["Event Detail"])
app.include_router(signal_performance.router, prefix="/api/signal-performance", tags=["Signal Performance"])
app.include_router(explorer.router, prefix="/api/explorer", tags=["Explorer"])
app.include_router(scanner.router, prefix="/api/scanner", tags=["Scanner"])
app.include_router(activist.router, prefix="/api/activist", tags=["Activist Filings"])


@app.get("/")
async def root() -> dict[str, str]:
    """Root endpoint."""
    return {
        "name": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "docs": "/docs",
    }
