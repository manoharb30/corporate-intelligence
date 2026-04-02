"""Service for pulling signal context from the Neo4j graph.

Runs 6 queries to gather surrounding context for a signal:
recent events, activist filings, insider track record, opposing activity,
prior alerts, and 12-month volume summary.
"""

from app.db.neo4j_client import Neo4jClient


class SignalContextService:

    @staticmethod
    async def get_context(
        cik: str,
        signal_date: str,
        insider_names: list[str] | None = None,
        direction: str = "buy",
    ) -> dict:
        """Pull all context for a signal from the graph."""
        result = {}

        # 1. Recent 8-K events (last 90 days)
        try:
            events = await Neo4jClient.execute_query("""
                MATCH (c:Company {cik: $cik})-[:FILED_EVENT]->(e:Event)
                WHERE date(substring(e.filing_date, 0, 10)) >= date() - duration({days: 90})
                RETURN e.signal_type AS type, e.filing_date AS date,
                       e.item_number AS item, e.is_ma_signal AS is_ma
                ORDER BY e.filing_date DESC
                LIMIT 10
            """, {"cik": cik})
            result["recent_events"] = [
                {
                    "type": _format_event_type(e["type"]),
                    "date": e["date"][:10] if e["date"] else None,
                    "item": e["item"],
                    "is_ma": e["is_ma"],
                }
                for e in events
            ]
        except Exception:
            result["recent_events"] = []

        # 2. Activist filings (last 180 days)
        try:
            activist = await Neo4jClient.execute_query("""
                MATCH (af:ActivistFiling)-[:TARGETS]->(c:Company {cik: $cik})
                WHERE date(substring(af.filing_date, 0, 10)) >= date() - duration({days: 180})
                RETURN af.filer_name AS filer, af.filing_date AS date,
                       af.percentage AS pct, af.filing_type AS form
                ORDER BY af.filing_date DESC
                LIMIT 5
            """, {"cik": cik})
            result["activist_filings"] = [
                {
                    "filer": a["filer"],
                    "date": a["date"][:10] if a["date"] else None,
                    "percentage": round(a["pct"], 1) if a["pct"] else None,
                    "form_type": a["form"],
                }
                for a in activist
            ]
        except Exception:
            result["activist_filings"] = []

        # 3. Insider track record at this company
        try:
            if insider_names:
                history = await Neo4jClient.execute_query("""
                    UNWIND $names AS insider_name
                    MATCH (c:Company {cik: $cik})-[:INSIDER_TRADE_OF]->(t:InsiderTransaction)
                    WHERE t.insider_name = insider_name
                      AND t.transaction_date < $signal_date
                      AND t.transaction_code IN ['P', 'S']
                      AND (t.is_derivative IS NULL OR t.is_derivative = false)
                    WITH insider_name,
                         count(t) AS prior_trades,
                         sum(CASE WHEN t.transaction_code = 'P' THEN 1 ELSE 0 END) AS buys,
                         sum(CASE WHEN t.transaction_code = 'S' THEN 1 ELSE 0 END) AS sells
                    RETURN insider_name AS name, prior_trades, buys, sells
                """, {"cik": cik, "names": insider_names, "signal_date": signal_date})
                result["insider_history"] = [
                    {
                        "name": h["name"],
                        "prior_trades": h["prior_trades"],
                        "buys": h["buys"],
                        "sells": h["sells"],
                    }
                    for h in history
                ]
            else:
                result["insider_history"] = []
        except Exception:
            result["insider_history"] = []

        # 4. Opposing activity (last 30 days)
        try:
            opp_code = "S" if direction == "buy" else "P"
            opposing = await Neo4jClient.execute_query("""
                MATCH (c:Company {cik: $cik})-[:INSIDER_TRADE_OF]->(t:InsiderTransaction)
                WHERE t.transaction_code = $opp_code
                  AND date(substring(t.transaction_date, 0, 10)) >= date() - duration({days: 30})
                  AND (t.is_derivative IS NULL OR t.is_derivative = false)
                  AND toLower(t.insider_name) <> toLower(c.name)
                RETURN t.insider_name AS name, t.insider_title AS title,
                       t.transaction_date AS date, t.total_value AS value
                ORDER BY t.total_value DESC
                LIMIT 5
            """, {"cik": cik, "opp_code": opp_code})
            result["opposing_activity"] = [
                {
                    "name": o["name"],
                    "title": o["title"],
                    "date": o["date"][:10] if o["date"] else None,
                    "value": round(o["value"], 2) if o["value"] else None,
                }
                for o in opposing
            ]
        except Exception:
            result["opposing_activity"] = []

        # 5. Previous alerts for this company
        try:
            alerts = await Neo4jClient.execute_query("""
                MATCH (a:Alert {company_cik: $cik})
                WHERE a.created_at < $signal_date
                RETURN a.alert_type AS type, a.severity AS severity,
                       substring(a.created_at, 0, 10) AS date, a.title AS title
                ORDER BY a.created_at DESC
                LIMIT 5
            """, {"cik": cik, "signal_date": signal_date})
            result["prior_alerts"] = [
                {
                    "type": a["type"],
                    "severity": a["severity"],
                    "date": a["date"],
                    "title": a["title"],
                }
                for a in alerts
            ]
        except Exception:
            result["prior_alerts"] = []

        # 6. Insider activity volume (last 12 months)
        try:
            volume = await Neo4jClient.execute_query("""
                MATCH (c:Company {cik: $cik})-[:INSIDER_TRADE_OF]->(t:InsiderTransaction)
                WHERE date(substring(t.transaction_date, 0, 10)) >= date() - duration({months: 12})
                  AND t.transaction_code IN ['P', 'S']
                  AND (t.is_derivative IS NULL OR t.is_derivative = false)
                  AND toLower(t.insider_name) <> toLower(c.name)
                RETURN count(t) AS total_txns,
                       sum(CASE WHEN t.transaction_code = 'P' THEN t.total_value ELSE 0 END) AS total_buying,
                       sum(CASE WHEN t.transaction_code = 'S' THEN t.total_value ELSE 0 END) AS total_selling,
                       count(DISTINCT t.insider_name) AS distinct_insiders
            """, {"cik": cik})
            if volume:
                v = volume[0]
                result["volume"] = {
                    "total_txns": v["total_txns"] or 0,
                    "total_buying": round(v["total_buying"] or 0, 2),
                    "total_selling": round(v["total_selling"] or 0, 2),
                    "distinct_insiders": v["distinct_insiders"] or 0,
                }
            else:
                result["volume"] = None
        except Exception:
            result["volume"] = None

        return result


def _format_event_type(signal_type: str | None) -> str:
    """Convert signal_type to readable label."""
    mapping = {
        "material_agreement": "Material Agreement",
        "executive_change": "Executive Change",
        "governance_change": "Governance Change",
        "acquisition_disposition": "Acquisition / Disposition",
        "control_change": "Control Change",
        "rights_modification": "Rights Modification",
    }
    return mapping.get(signal_type or "", signal_type or "Unknown")
