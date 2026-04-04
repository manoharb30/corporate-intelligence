"""Service for assembling comprehensive company intelligence from the graph."""

from app.db.neo4j_client import Neo4jClient
from app.services.insider_cluster_service import InsiderClusterService
from app.services.signal_context_service import SignalContextService


class CompanyIntelligenceService:

    @staticmethod
    async def get_intelligence(cik: str) -> dict:
        """Get everything we know about a company."""

        # Company info
        company_result = await Neo4jClient.execute_query("""
            MATCH (c:Company {cik: $cik})
            RETURN c.name AS name, c.tickers AS tickers,
                   c.sic_description AS sic_description,
                   c.state_of_incorporation AS state
        """, {"cik": cik})

        if not company_result:
            return None

        c = company_result[0]
        ticker = c["tickers"][0] if c.get("tickers") and len(c["tickers"]) > 0 else None

        company = {
            "name": c["name"],
            "ticker": ticker,
            "cik": cik,
            "sic_description": c["sic_description"],
            "state": c["state"],
        }

        # Cluster signals for this company (with market cap filter)
        try:
            clusters_raw = await InsiderClusterService.detect_clusters_for_company(cik, days=90)
            clusters = InsiderClusterService.apply_market_cap_filter(clusters_raw, min_pct=0.01)
            cluster_list = []
            for cl in clusters:
                cluster_list.append({
                    "direction": cl.direction,
                    "signal_level": cl.signal_level,
                    "signal_summary": cl.signal_summary,
                    "num_insiders": cl.num_buyers,
                    "total_value": cl.total_buy_value,
                    "window_start": cl.window_start,
                    "window_end": cl.window_end,
                    "conviction_tier": cl.conviction_tier,
                    "accession_number": cl.accession_number,
                    "buyers": [
                        {
                            "name": b.name,
                            "title": b.title,
                            "total_value": b.total_value,
                            "trade_count": b.trade_count,
                            "total_shares": b.total_shares,
                            "trade_dates": b.trade_dates,
                            "form4_url": b.form4_url,
                            "role": b.role,
                        }
                        for b in cl.buyers
                    ],
                })
        except Exception:
            cluster_list = []

        # 8-K Events (last 180 days)
        try:
            events = await Neo4jClient.execute_query("""
                MATCH (c:Company {cik: $cik})-[:FILED_EVENT]->(e:Event)
                WHERE date(substring(e.filing_date, 0, 10)) >= date() - duration({days: 180})
                RETURN e.filing_date AS date, e.signal_type AS type,
                       e.item_number AS item, e.is_ma_signal AS is_ma,
                       e.accession_number AS accession
                ORDER BY e.filing_date DESC
                LIMIT 20
            """, {"cik": cik})
            event_list = [
                {
                    "date": e["date"][:10] if e["date"] else None,
                    "type": e["type"],
                    "item": e["item"],
                    "is_ma": e["is_ma"],
                    "accession": e["accession"],
                }
                for e in events
            ]
        except Exception:
            event_list = []

        # 13D Activist filings
        try:
            activist = await Neo4jClient.execute_query("""
                MATCH (af:ActivistFiling)-[:TARGETS]->(c:Company {cik: $cik})
                RETURN af.filer_name AS filer, af.filing_date AS date,
                       af.percentage AS pct, af.filing_type AS form
                ORDER BY af.filing_date DESC
                LIMIT 10
            """, {"cik": cik})
            activist_list = [
                {
                    "filer": a["filer"],
                    "date": a["date"][:10] if a["date"] else None,
                    "percentage": round(a["pct"], 1) if a["pct"] else None,
                    "form_type": a["form"],
                }
                for a in activist
            ]
        except Exception:
            activist_list = []

        # Recent insider transactions (last 90 days, open market only)
        try:
            transactions = await Neo4jClient.execute_query("""
                MATCH (c:Company {cik: $cik})-[:INSIDER_TRADE_OF]->(t:InsiderTransaction)
                WHERE t.transaction_code IN ['P', 'S']
                  AND (t.is_derivative IS NULL OR t.is_derivative = false)
                  AND toLower(t.insider_name) <> toLower(c.name)
                RETURN t.insider_name AS name, t.insider_title AS title,
                       t.transaction_code AS code, t.transaction_date AS date,
                       t.total_value AS value, t.shares AS shares,
                       t.accession_number AS accession
                ORDER BY t.transaction_date DESC
                LIMIT 30
            """, {"cik": cik})
            txn_list = [
                {
                    "name": t["name"],
                    "title": t["title"],
                    "code": "BUY" if t["code"] == "P" else "SELL",
                    "date": t["date"][:10] if t["date"] else None,
                    "value": round(t["value"], 2) if t["value"] else None,
                    "shares": t["shares"],
                    "accession": t["accession"],
                }
                for t in transactions
            ]
        except Exception:
            txn_list = []

        # Cross-company insider check: which insiders also trade at other companies?
        cross_company_insiders: dict[str, list[dict]] = {}
        try:
            # Collect all insider names from transactions and clusters
            all_insider_names = list(set(
                [t["name"] for t in transactions if t.get("name")]
                + [b.name for cl in (clusters_raw if 'clusters_raw' in dir() else []) for b in cl.buyers]
            ))
            if not all_insider_names:
                all_insider_names = list(set(t["name"] for t in transactions if t.get("name")))

            if all_insider_names:
                cross = await Neo4jClient.execute_query("""
                    UNWIND $names AS insider_name
                    MATCH (p:Person {name: insider_name})-[:TRADED_BY]->(t:InsiderTransaction)<-[:INSIDER_TRADE_OF]-(c:Company)
                    WHERE c.cik <> $cik
                      AND t.transaction_code IN ['P', 'S']
                      AND (t.is_derivative IS NULL OR t.is_derivative = false)
                      AND t.total_value > 0
                      AND c.tickers IS NOT NULL AND size(c.tickers) > 0
                    WITH insider_name, c,
                         sum(t.total_value) AS total_value,
                         count(t) AS trade_count,
                         max(t.transaction_date) AS latest_trade,
                         collect(DISTINCT t.transaction_code) AS codes
                    RETURN insider_name,
                           c.cik AS other_cik,
                           c.name AS other_company,
                           c.tickers[0] AS other_ticker,
                           total_value, trade_count, latest_trade, codes
                    ORDER BY insider_name, total_value DESC
                """, {"names": all_insider_names, "cik": cik})

                for r in cross:
                    name = r["insider_name"]
                    if name not in cross_company_insiders:
                        cross_company_insiders[name] = []
                    direction = "buying" if "P" in (r["codes"] or []) else "selling"
                    if "P" in (r["codes"] or []) and "S" in (r["codes"] or []):
                        direction = "both"
                    cross_company_insiders[name].append({
                        "cik": r["other_cik"],
                        "company": r["other_company"],
                        "ticker": r["other_ticker"],
                        "total_value": round(r["total_value"], 2),
                        "trade_count": r["trade_count"],
                        "latest_trade": r["latest_trade"][:10] if r["latest_trade"] else None,
                        "direction": direction,
                    })
        except Exception:
            pass

        # Add cross-company flag to transactions
        for t in txn_list:
            t["has_cross_company"] = t["name"] in cross_company_insiders

        # Alerts history
        try:
            alerts = await Neo4jClient.execute_query("""
                MATCH (a:Alert {company_cik: $cik})
                RETURN a.alert_type AS type, a.severity AS severity,
                       substring(a.created_at, 0, 10) AS date,
                       a.title AS title, a.signal_id AS signal_id
                ORDER BY a.created_at DESC
                LIMIT 10
            """, {"cik": cik})
            alert_list = [
                {
                    "type": a["type"],
                    "severity": a["severity"],
                    "date": a["date"],
                    "title": a["title"],
                    "signal_id": a["signal_id"],
                }
                for a in alerts
            ]
        except Exception:
            alert_list = []

        # 12-month volume summary
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
            vol = volume[0] if volume else {}
            volume_data = {
                "total_txns": vol.get("total_txns") or 0,
                "total_buying": round(vol.get("total_buying") or 0, 2),
                "total_selling": round(vol.get("total_selling") or 0, 2),
                "distinct_insiders": vol.get("distinct_insiders") or 0,
            }
        except Exception:
            volume_data = None

        # Officers and Directors
        try:
            officers = await Neo4jClient.execute_query("""
                MATCH (p:Person)-[:OFFICER_OF]->(c:Company {cik: $cik})
                RETURN p.name AS name, p.title AS title
                LIMIT 10
            """, {"cik": cik})
            directors = await Neo4jClient.execute_query("""
                MATCH (p:Person)-[:DIRECTOR_OF]->(c:Company {cik: $cik})
                RETURN p.name AS name
                LIMIT 10
            """, {"cik": cik})
            officer_list = [{"name": o["name"], "title": o.get("title")} for o in officers]
            director_list = [{"name": d["name"]} for d in directors]
        except Exception:
            officer_list = []
            director_list = []

        return {
            "company": company,
            "clusters": cluster_list,
            "events": event_list,
            "activist_filings": activist_list,
            "transactions": txn_list,
            "alerts": alert_list,
            "volume": volume_data,
            "officers": officer_list,
            "directors": director_list,
            "cross_company_insiders": cross_company_insiders,
        }
