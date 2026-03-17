"""Dashboard API routes."""

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from app.services.dashboard_service import DashboardService
from app.services.dashboard_precompute_service import DashboardPrecomputeService

router = APIRouter()


@router.get("/pulse")
async def get_pulse():
    """Real-time dashboard pulse: last signal, today's counts, market mood, movers."""
    return await DashboardService.get_pulse()


@router.get("/precomputed")
async def get_precomputed():
    """Get pre-computed dashboard data from Neo4j. Instant response."""
    data = await DashboardPrecomputeService.get_cached()
    if data is None:
        return JSONResponse(
            status_code=404,
            content={"error": "not_computed", "message": "Dashboard data not yet computed. Trigger /api/dashboard/compute first."},
        )
    return data


@router.post("/compute")
async def compute_dashboard():
    """Pre-compute all dashboard data and store in Neo4j.

    Run after scanner completes or on-demand. Takes 30-60 seconds.
    """
    result = await DashboardPrecomputeService.compute_and_store()
    return result
