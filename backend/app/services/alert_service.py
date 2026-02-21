"""Service for real-time alerts from Form 4 scanner and cluster detection."""

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Optional

from app.db.neo4j_client import Neo4jClient

logger = logging.getLogger(__name__)


@dataclass
class AlertItem:
    """A single alert for display."""

    id: str
    alert_type: str  # insider_cluster, large_purchase
    severity: str  # high, medium, low
    company_cik: str
    company_name: str
    ticker: Optional[str]
    title: str
    description: str
    created_at: str
    acknowledged: bool
    acknowledged_at: Optional[str] = None
    dedup_key: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "alert_type": self.alert_type,
            "severity": self.severity,
            "company_cik": self.company_cik,
            "company_name": self.company_name,
            "ticker": self.ticker,
            "title": self.title,
            "description": self.description,
            "created_at": self.created_at,
            "acknowledged": self.acknowledged,
            "acknowledged_at": self.acknowledged_at,
        }


class AlertService:
    """CRUD service for scanner alerts."""

    @staticmethod
    async def create_alert(
        alert_type: str,
        severity: str,
        cik: str,
        name: str,
        ticker: Optional[str],
        title: str,
        description: str,
    ) -> Optional[str]:
        """
        Create or deduplicate an alert.

        Dedup key: {cik}_{type}_{YYYY-MM-DD} — one alert per company per type per day.
        Uses MERGE so re-processing is safe.

        Returns the alert id if created/matched, None on error.
        """
        today = datetime.utcnow().strftime("%Y-%m-%d")
        dedup_key = f"{cik}_{alert_type}_{today}"
        now = datetime.utcnow().isoformat()

        query = """
            MERGE (a:Alert {dedup_key: $dedup_key})
            ON CREATE SET
                a.id = randomUUID(),
                a.alert_type = $alert_type,
                a.severity = $severity,
                a.company_cik = $cik,
                a.company_name = $name,
                a.ticker = $ticker,
                a.title = $title,
                a.description = $description,
                a.created_at = $now,
                a.acknowledged = false
            WITH a
            OPTIONAL MATCH (c:Company {cik: $cik})
            FOREACH (_ IN CASE WHEN c IS NOT NULL THEN [1] ELSE [] END |
                MERGE (a)-[:ALERT_FOR]->(c)
            )
            RETURN a.id as id
        """

        try:
            results = await Neo4jClient.execute_query(query, {
                "dedup_key": dedup_key,
                "alert_type": alert_type,
                "severity": severity,
                "cik": cik,
                "name": name,
                "ticker": ticker,
                "title": title,
                "description": description,
                "now": now,
            })
            if results:
                return results[0]["id"]
            return None
        except Exception as e:
            logger.error(f"Failed to create alert: {e}")
            return None

    @staticmethod
    async def get_alerts(
        days: int = 7,
        severity: Optional[str] = None,
        acknowledged: Optional[bool] = None,
        limit: int = 50,
    ) -> list[AlertItem]:
        """Get alerts with optional filters."""
        since = (datetime.utcnow() - timedelta(days=days)).isoformat()

        conditions = ["a.created_at >= $since"]
        params: dict = {"since": since, "limit": limit}

        if severity:
            conditions.append("a.severity = $severity")
            params["severity"] = severity

        if acknowledged is not None:
            conditions.append("a.acknowledged = $acknowledged")
            params["acknowledged"] = acknowledged

        where_clause = " AND ".join(conditions)

        query = f"""
            MATCH (a:Alert)
            WHERE {where_clause}
            RETURN a.id as id,
                   a.alert_type as alert_type,
                   a.severity as severity,
                   a.company_cik as company_cik,
                   a.company_name as company_name,
                   a.ticker as ticker,
                   a.title as title,
                   a.description as description,
                   a.created_at as created_at,
                   a.acknowledged as acknowledged,
                   a.acknowledged_at as acknowledged_at,
                   a.dedup_key as dedup_key
            ORDER BY a.created_at DESC
            LIMIT $limit
        """

        results = await Neo4jClient.execute_query(query, params)

        return [
            AlertItem(
                id=r["id"],
                alert_type=r["alert_type"] or "",
                severity=r["severity"] or "low",
                company_cik=r["company_cik"] or "",
                company_name=r["company_name"] or "",
                ticker=r.get("ticker"),
                title=r["title"] or "",
                description=r["description"] or "",
                created_at=r["created_at"] or "",
                acknowledged=r["acknowledged"] if r["acknowledged"] is not None else False,
                acknowledged_at=r.get("acknowledged_at"),
                dedup_key=r.get("dedup_key"),
            )
            for r in results
        ]

    @staticmethod
    async def get_alert_stats() -> dict:
        """Get alert stats for the bell badge."""
        query = """
            MATCH (a:Alert)
            WHERE a.acknowledged = false
            RETURN count(a) as total,
                   sum(CASE WHEN a.severity = 'high' THEN 1 ELSE 0 END) as high,
                   sum(CASE WHEN a.severity = 'medium' THEN 1 ELSE 0 END) as medium,
                   sum(CASE WHEN a.severity = 'low' THEN 1 ELSE 0 END) as low
        """
        results = await Neo4jClient.execute_query(query)

        if results:
            r = results[0]
            return {
                "total": r["total"] or 0,
                "unread": r["total"] or 0,
                "by_severity": {
                    "high": r["high"] or 0,
                    "medium": r["medium"] or 0,
                    "low": r["low"] or 0,
                },
            }

        return {"total": 0, "unread": 0, "by_severity": {"high": 0, "medium": 0, "low": 0}}

    @staticmethod
    async def acknowledge_alert(alert_id: str) -> bool:
        """Mark an alert as acknowledged."""
        now = datetime.utcnow().isoformat()

        query = """
            MATCH (a:Alert {id: $alert_id})
            SET a.acknowledged = true,
                a.acknowledged_at = $now
            RETURN a.id as id
        """

        results = await Neo4jClient.execute_query(query, {
            "alert_id": alert_id,
            "now": now,
        })

        return len(results) > 0
