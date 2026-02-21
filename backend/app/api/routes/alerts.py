"""Alert API routes for real-time scanner alerts."""

from typing import Optional

from fastapi import APIRouter, Query

from app.services.alert_service import AlertService

router = APIRouter()


@router.get("")
async def get_alerts(
    days: int = Query(7, ge=1, le=90),
    severity: Optional[str] = Query(None),
    acknowledged: Optional[bool] = Query(None),
    limit: int = Query(50, ge=1, le=200),
):
    """Get alerts with optional filters."""
    alerts = await AlertService.get_alerts(
        days=days,
        severity=severity,
        acknowledged=acknowledged,
        limit=limit,
    )
    return {
        "total": len(alerts),
        "alerts": [a.to_dict() for a in alerts],
    }


@router.get("/stats")
async def get_alert_stats():
    """Get alert stats for bell badge (unread count)."""
    return await AlertService.get_alert_stats()


@router.post("/{alert_id}/acknowledge")
async def acknowledge_alert(alert_id: str):
    """Mark an alert as acknowledged."""
    success = await AlertService.acknowledge_alert(alert_id)
    if not success:
        return {"status": "not_found", "message": f"Alert {alert_id} not found"}
    return {"status": "acknowledged", "alert_id": alert_id}
