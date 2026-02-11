"""API endpoints for auto-discovered insights."""

from fastapi import APIRouter, Query

from app.services.insights_service import InsightsService

router = APIRouter()


@router.get("")
async def get_insights(
    category: str = Query(None, description="Filter by category: board_interlock, large_structure, bridge_person, hub_company"),
    limit: int = Query(50, ge=1, le=200, description="Maximum insights to return"),
):
    """
    Get auto-discovered insights from the corporate intelligence graph.

    Returns patterns that the system has automatically identified as interesting:
    - board_interlock: Companies sharing board members
    - large_structure: Companies with many subsidiaries
    - bridge_person: People serving on multiple boards
    - hub_company: Companies with many board connections

    Insights are sorted by importance (high, medium, low).

    Example:
        GET /insights
        GET /insights?category=board_interlock
        GET /insights?limit=10
    """
    all_insights = await InsightsService.discover_all()

    # Filter by category if specified
    if category:
        all_insights = [i for i in all_insights if i.category == category]

    # Apply limit
    all_insights = all_insights[:limit]

    return {
        "total": len(all_insights),
        "insights": [i.to_dict() for i in all_insights],
    }


@router.get("/summary")
async def get_insights_summary():
    """
    Get a summary of all discovered insights by category.

    Example:
        GET /insights/summary
    """
    all_insights = await InsightsService.discover_all()

    # Count by category
    by_category = {}
    for insight in all_insights:
        cat = insight.category
        if cat not in by_category:
            by_category[cat] = {"count": 0, "high_importance": 0}
        by_category[cat]["count"] += 1
        if insight.importance == "high":
            by_category[cat]["high_importance"] += 1

    return {
        "total_insights": len(all_insights),
        "by_category": by_category,
        "top_insights": [i.to_dict() for i in all_insights[:5]],
    }
