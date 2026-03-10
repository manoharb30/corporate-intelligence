"""Snapshot page service — manual weekly snapshot for demo purposes.

Queries Neo4j directly for a specific week's signals:
  - Insider clusters (buy/sell) from that week
  - Pre-event insider anomalies (8-K events with front-loaded selling)
"""

import logging
from app.db.neo4j_client import Neo4jClient

logger = logging.getLogger(__name__)

CLUSTER_QUERY = """
MATCH (c:Company)-[:INSIDER_TRADE_OF]->(t:InsiderTransaction)<-[:TRADED_BY]-(p:Person)
WHERE t.transaction_date >= $start_date
  AND t.transaction_date <= $end_date
  AND t.transaction_code IN ['P', 'S']
  AND c.tickers IS NOT NULL AND size(c.tickers) > 0
  AND toLower(t.insider_name) <> toLower(c.name)
WITH c, t.transaction_code AS tx_code,
     collect(DISTINCT p.name) AS people,
     collect(DISTINCT t.insider_title) AS titles,
     sum(coalesce(t.total_value, 0)) AS total_value,
     count(t) AS trade_count,
     min(t.transaction_date) AS first_date,
     max(t.transaction_date) AS last_date
WHERE size(people) >= 2
RETURN c.cik AS cik,
       c.name AS company_name,
       c.tickers AS tickers,
       tx_code,
       people,
       titles,
       total_value,
       trade_count,
       first_date,
       last_date
ORDER BY total_value DESC
"""

ANOMALY_QUERY = """
MATCH (c:Company)-[:FILED_EVENT]->(e:Event)
WHERE e.filing_date >= $start_date
  AND e.filing_date <= $end_date
  AND c.tickers IS NOT NULL AND size(c.tickers) > 0
WITH c, e
MATCH (c)-[:INSIDER_TRADE_OF]->(t:InsiderTransaction)
WHERE t.transaction_code = 'S'
  AND toLower(t.insider_name) <> toLower(c.name)
WITH c, e,
     date(substring(e.filing_date, 0, 10)) AS event_dt,
     date(substring(t.transaction_date, 0, 10)) AS txn_dt,
     t
WHERE txn_dt >= event_dt - duration({days: 30})
  AND txn_dt < event_dt
WITH c, e,
     sum(coalesce(t.total_value, 0)) AS pre_sell_value,
     count(DISTINCT t.insider_name) AS num_insiders,
     collect(DISTINCT t.insider_name + ' (' + coalesce(t.insider_title, '') + ')')[..5] AS insider_list,
     avg(duration.between(date(substring(t.transaction_date, 0, 10)), date(substring(e.filing_date, 0, 10))).days) AS avg_days_before
WHERE pre_sell_value >= 100000
  AND num_insiders >= 1
RETURN c.cik AS cik,
       c.name AS company_name,
       c.tickers AS tickers,
       e.signal_type AS event_type,
       e.filing_date AS event_date,
       e.accession_number AS accession_number,
       pre_sell_value,
       num_insiders,
       insider_list,
       avg_days_before
ORDER BY pre_sell_value DESC
LIMIT 20
"""


class SnapshotPageService:
    """One-time snapshot page data for a specific week."""

    @staticmethod
    async def get_week_snapshot(
        start_date: str = "2026-03-03",
        end_date: str = "2026-03-07",
    ) -> dict:
        # 1. Insider clusters from that week
        cluster_records = await Neo4jClient.execute_query(
            CLUSTER_QUERY,
            {"start_date": start_date, "end_date": end_date},
        )

        clusters = []
        for r in cluster_records:
            tickers = r["tickers"]
            ticker = tickers[0] if tickers else None
            tx_code = r["tx_code"]
            direction = "buy" if tx_code == "P" else "sell"
            people = r["people"]
            total_value = r["total_value"] or 0

            # Signal level
            if direction == "buy":
                if len(people) >= 3:
                    level = "high"
                elif len(people) >= 2 or total_value >= 500_000:
                    level = "medium"
                else:
                    continue
            else:
                if len(people) >= 4 and total_value >= 100_000:
                    level = "high"
                elif len(people) >= 3 and total_value >= 100_000:
                    level = "medium"
                else:
                    continue

            cik = r["cik"]
            signal_date = r["last_date"]
            acc = (
                f"SELL-CLUSTER-{cik}-{signal_date}"
                if direction == "sell"
                else f"CLUSTER-{cik}-{signal_date}"
            )

            clusters.append({
                "cik": cik,
                "company_name": r["company_name"],
                "ticker": ticker,
                "direction": direction,
                "signal_level": level,
                "signal_date": signal_date,
                "num_insiders": len(people),
                "total_value": total_value,
                "trade_count": r["trade_count"],
                "insiders": people[:5],
                "accession_number": acc,
                "description": _cluster_description(direction, people, total_value),
            })

        # Sort: high first, then by value
        level_order = {"high": 0, "medium": 1, "low": 2}
        clusters.sort(
            key=lambda x: (level_order.get(x["signal_level"], 9), -x["total_value"])
        )

        # 2. Pre-event anomalies from that week
        anomaly_records = await Neo4jClient.execute_query(
            ANOMALY_QUERY,
            {"start_date": start_date, "end_date": end_date},
        )

        anomalies = []
        for r in anomaly_records:
            tickers = r["tickers"]
            ticker = tickers[0] if tickers else None
            event_type = r["event_type"] or "unknown"
            pre_sell = r["pre_sell_value"] or 0
            num_ins = r["num_insiders"]
            avg_days = r["avg_days_before"]

            anomalies.append({
                "cik": r["cik"],
                "company_name": r["company_name"],
                "ticker": ticker,
                "event_type": event_type,
                "event_date": r["event_date"],
                "accession_number": r["accession_number"],
                "pre_sell_value": pre_sell,
                "num_insiders": num_ins,
                "insider_list": r["insider_list"] or [],
                "avg_days_before": round(avg_days) if avg_days else None,
                "description": _anomaly_description(
                    num_ins, pre_sell, event_type, avg_days
                ),
            })

        return {
            "week_start": start_date,
            "week_end": end_date,
            "clusters": clusters[:15],
            "anomalies": anomalies[:15],
        }


def _format_value(v: float) -> str:
    if v >= 1_000_000_000:
        return f"${v / 1_000_000_000:.1f}B"
    if v >= 1_000_000:
        return f"${v / 1_000_000:.1f}M"
    if v >= 1_000:
        return f"${v / 1_000:.0f}K"
    return f"${v:.0f}"


def _cluster_description(
    direction: str, people: list[str], total_value: float
) -> str:
    n = len(people)
    val = _format_value(total_value)
    verb = "bought" if direction == "buy" else "sold"
    return f"{n} insiders {verb} {val}"


def _event_label(event_type: str) -> str:
    labels = {
        "material_agreement": "material agreement",
        "executive_change": "executive change",
        "governance_change": "governance change",
        "acquisition_disposition": "acquisition/disposition",
        "rights_modification": "rights modification",
    }
    return labels.get(event_type, event_type)


def _anomaly_description(
    num_insiders: int, pre_sell: float, event_type: str, avg_days: float | None
) -> str:
    val = _format_value(pre_sell)
    label = _event_label(event_type)
    days_part = f" ~{round(avg_days)}d before" if avg_days else ""
    return f"{num_insiders} insider{'s' if num_insiders != 1 else ''} sold {val}{days_part} {label}"
