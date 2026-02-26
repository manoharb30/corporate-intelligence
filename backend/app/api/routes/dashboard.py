"""Dashboard API routes."""

from fastapi import APIRouter

from app.services.dashboard_service import DashboardService

router = APIRouter()


@router.get("/pulse")
async def get_pulse():
    """Real-time dashboard pulse: last signal, today's counts, market mood, movers."""
    return await DashboardService.get_pulse()
