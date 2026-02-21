"""FastAPI application entry point for Corporate Intelligence Graph."""

from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.db.neo4j_client import Neo4jClient
from app.api.routes import companies, persons, filings, graph, health, citations, connections, sanctions, insights, events, feed, profile, insider_trades, event_detail, stock_price, officers, alerts, scanner, accuracy


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan handler for startup and shutdown."""
    # Startup
    await Neo4jClient.connect()
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

# Include routers
app.include_router(health.router, prefix="/api", tags=["Health"])
app.include_router(companies.router, prefix="/api/companies", tags=["Companies"])
app.include_router(persons.router, prefix="/api/persons", tags=["Persons"])
app.include_router(filings.router, prefix="/api/filings", tags=["Filings"])
app.include_router(graph.router, prefix="/api/graph", tags=["Graph"])
app.include_router(citations.router, prefix="/api/citations", tags=["Citations"])
app.include_router(connections.router, prefix="/api/connections", tags=["Connections"])
app.include_router(sanctions.router, prefix="/api/sanctions", tags=["Sanctions"])
app.include_router(insights.router, prefix="/api/insights", tags=["Insights"])
app.include_router(events.router, prefix="/api/events", tags=["Events"])
app.include_router(feed.router, prefix="/api/feed", tags=["Feed"])
app.include_router(profile.router, prefix="/api/profile", tags=["Profile"])
app.include_router(insider_trades.router, prefix="/api/insider-trades", tags=["Insider Trades"])
app.include_router(event_detail.router, prefix="/api/event-detail", tags=["Event Detail"])
app.include_router(stock_price.router, prefix="/api/stock-price", tags=["Stock Price"])
app.include_router(officers.router, prefix="/api/officers", tags=["Officers"])
app.include_router(alerts.router, prefix="/api/alerts", tags=["Alerts"])
app.include_router(scanner.router, prefix="/api/scanner", tags=["Scanner"])
app.include_router(accuracy.router, prefix="/api/accuracy", tags=["Accuracy"])


@app.get("/")
async def root() -> dict[str, str]:
    """Root endpoint."""
    return {
        "name": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "docs": "/docs",
    }
