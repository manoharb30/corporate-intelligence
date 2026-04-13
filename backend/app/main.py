"""FastAPI application entry point for Corporate Intelligence Graph."""

from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.db.neo4j_client import Neo4jClient
from app.api.routes import companies, persons, health, citations, events, feed, profile, insider_trades, event_detail, stock_price, officers, alerts, scanner, accuracy, dashboard, activist, anomalies, snapshot, signal_performance, signal_context, company_intelligence, person_intelligence, explorer, signal_returns


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

# Include routers
app.include_router(health.router, prefix="/api", tags=["Health"])
app.include_router(companies.router, prefix="/api/companies", tags=["Companies"])
app.include_router(persons.router, prefix="/api/persons", tags=["Persons"])
app.include_router(citations.router, prefix="/api/citations", tags=["Citations"])
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
app.include_router(dashboard.router, prefix="/api/dashboard", tags=["Dashboard"])
app.include_router(activist.router, prefix="/api/activist", tags=["Activist Filings"])
app.include_router(anomalies.router, prefix="/api/anomalies", tags=["Anomalies"])
app.include_router(snapshot.router, prefix="/api/snapshot", tags=["Snapshot"])
app.include_router(signal_performance.router, prefix="/api/signal-performance", tags=["Signal Performance"])
app.include_router(signal_context.router, prefix="/api/signal-context", tags=["Signal Context"])
app.include_router(company_intelligence.router, prefix="/api/company-intelligence", tags=["Company Intelligence"])
app.include_router(person_intelligence.router, prefix="/api/person-intelligence", tags=["Person Intelligence"])
app.include_router(explorer.router, prefix="/api/explorer", tags=["Explorer"])
app.include_router(signal_returns.router, prefix="/api/signal-returns", tags=["Signal Returns"])


@app.get("/")
async def root() -> dict[str, str]:
    """Root endpoint."""
    return {
        "name": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "docs": "/docs",
    }
