"""Explorer service — builds graph data (nodes + edges) for the interactive graph explorer.

Returns structured data suitable for Cytoscape.js rendering.
"""

from app.db.neo4j_client import Neo4jClient


class ExplorerService:

    @staticmethod
    async def get_company_graph(query: str) -> dict | None:
        """Build a graph starting from a company (by ticker or name)."""

        # Find the company — exact ticker match first, then name search
        company = await Neo4jClient.execute_query("""
            MATCH (c:Company)
            WHERE (c.tickers IS NOT NULL AND ANY(t IN c.tickers WHERE toUpper(t) = toUpper($q)))
               OR toLower(c.name) CONTAINS toLower($q)
            WITH c,
                 CASE WHEN c.tickers IS NOT NULL AND ANY(t IN c.tickers WHERE toUpper(t) = toUpper($q))
                      THEN 0 ELSE 1 END AS priority
            ORDER BY priority
            RETURN c.cik AS cik, c.name AS name, c.tickers AS tickers,
                   c.sic_description AS sic
            LIMIT 1
        """, {"q": query})

        if not company:
            return None

        c = company[0]
        cik = c["cik"]
        ticker = c["tickers"][0] if c.get("tickers") and len(c["tickers"]) > 0 else None
        company_id = f"company-{cik}"

        nodes = [{
            "id": company_id,
            "type": "company",
            "label": ticker or cik,
            "name": c["name"],
            "metadata": {
                "cik": cik,
                "ticker": ticker,
                "sic": c["sic"],
            },
        }]
        edges = []

        # Insiders — aggregate by person (open market trades, last 12 months)
        insiders = await Neo4jClient.execute_query("""
            MATCH (co:Company {cik: $cik})-[:INSIDER_TRADE_OF]->(t:InsiderTransaction)<-[:TRADED_BY]-(p:Person)
            WHERE t.transaction_code IN ['P', 'S']
              AND (t.is_derivative IS NULL OR t.is_derivative = false)
              AND (co.name IS NULL OR toLower(t.insider_name) <> toLower(co.name))
            WITH p, t.transaction_code AS code,
                 sum(t.total_value) AS total_value,
                 count(t) AS trade_count,
                 max(t.transaction_date) AS latest_date,
                 collect(DISTINCT t.insider_title)[0] AS title
            WITH p.name AS person_name, code, total_value, trade_count, latest_date, title
            RETURN person_name, title,
                   sum(CASE WHEN code = 'P' THEN total_value ELSE 0 END) AS buy_value,
                   sum(CASE WHEN code = 'S' THEN total_value ELSE 0 END) AS sell_value,
                   sum(CASE WHEN code = 'P' THEN trade_count ELSE 0 END) AS buy_count,
                   sum(CASE WHEN code = 'S' THEN trade_count ELSE 0 END) AS sell_count,
                   max(latest_date) AS latest_date
        """, {"cik": cik})

        # Check which insiders have cross-company activity and fetch their other companies
        insider_names = [r["person_name"] for r in insiders if r["person_name"]]
        cross_company = {}
        cross_company_details = {}
        if insider_names:
            cross = await Neo4jClient.execute_query("""
                UNWIND $names AS name
                MATCH (p:Person {name: name})-[:TRADED_BY]->(t:InsiderTransaction)<-[:INSIDER_TRADE_OF]-(c:Company)
                WHERE c.cik <> $cik
                  AND t.transaction_code IN ['P', 'S']
                  AND (t.is_derivative IS NULL OR t.is_derivative = false)
                  AND c.tickers IS NOT NULL AND size(c.tickers) > 0
                WITH name, c,
                     sum(CASE WHEN t.transaction_code = 'P' THEN t.total_value ELSE 0 END) AS buy_value,
                     sum(CASE WHEN t.transaction_code = 'S' THEN t.total_value ELSE 0 END) AS sell_value,
                     count(t) AS trades
                RETURN name, c.cik AS other_cik, c.tickers[0] AS other_ticker,
                       c.name AS other_company, buy_value, sell_value, trades
            """, {"names": insider_names, "cik": cik})

            for r in cross:
                person = r["name"]
                if person not in cross_company:
                    cross_company[person] = 0
                    cross_company_details[person] = []
                cross_company[person] += 1
                cross_company_details[person].append(r)

        # Add cross-company nodes and edges
        existing_node_ids = set()
        for person_name, details in cross_company_details.items():
            person_id = f"person-{person_name}"
            for d in details:
                other_company_id = f"company-{d['other_cik']}"
                if other_company_id not in existing_node_ids:
                    nodes.append({
                        "id": other_company_id,
                        "type": "company",
                        "label": d["other_ticker"] or d["other_cik"],
                        "name": d["other_company"] or "",
                        "metadata": {
                            "cik": d["other_cik"],
                            "ticker": d["other_ticker"],
                            "is_cross_company": True,
                        },
                    })
                    existing_node_ids.add(other_company_id)

                buy_val = d["buy_value"] or 0
                sell_val = d["sell_value"] or 0
                if buy_val > 0:
                    edges.append({
                        "source": person_id,
                        "target": other_company_id,
                        "type": "buy",
                        "metadata": {"total_value": round(buy_val, 2), "trade_count": d["trades"]},
                    })
                if sell_val > 0:
                    edges.append({
                        "source": person_id,
                        "target": other_company_id,
                        "type": "sell",
                        "metadata": {"total_value": round(sell_val, 2), "trade_count": d["trades"]},
                    })

        for r in insiders:
            person_id = f"person-{r['person_name']}"
            buy_val = r["buy_value"] or 0
            sell_val = r["sell_value"] or 0

            nodes.append({
                "id": person_id,
                "type": "person",
                "label": r["person_name"],
                "name": r["person_name"],
                "metadata": {
                    "title": r["title"] or "",
                    "buy_value": round(buy_val, 2),
                    "sell_value": round(sell_val, 2),
                    "buy_count": r["buy_count"] or 0,
                    "sell_count": r["sell_count"] or 0,
                    "latest_date": (r["latest_date"] or "")[:10],
                    "cross_company_count": cross_company.get(r["person_name"], 0),
                },
            })

            # Buy edge
            if buy_val > 0:
                edges.append({
                    "source": person_id,
                    "target": company_id,
                    "type": "buy",
                    "metadata": {
                        "total_value": round(buy_val, 2),
                        "trade_count": r["buy_count"] or 0,
                        "latest_date": (r["latest_date"] or "")[:10],
                    },
                })

            # Sell edge
            if sell_val > 0:
                edges.append({
                    "source": person_id,
                    "target": company_id,
                    "type": "sell",
                    "metadata": {
                        "total_value": round(sell_val, 2),
                        "trade_count": r["sell_count"] or 0,
                        "latest_date": (r["latest_date"] or "")[:10],
                    },
                })

        # Events (last 180 days)
        events = await Neo4jClient.execute_query("""
            MATCH (co:Company {cik: $cik})-[:FILED_EVENT]->(e:Event)
            RETURN DISTINCT e.accession_number AS accession,
                   e.signal_type AS type, e.filing_date AS date,
                   e.item_number AS item, e.is_ma_signal AS is_ma
            ORDER BY e.filing_date DESC
            LIMIT 15
        """, {"cik": cik})

        event_type_labels = {
            "material_agreement": "Material Agreement",
            "executive_change": "Executive Change",
            "governance_change": "Governance Change",
            "acquisition_disposition": "Acquisition",
            "control_change": "Control Change",
            "rights_modification": "Rights Modification",
        }

        for e in events:
            event_id = f"event-{e['accession']}"
            nodes.append({
                "id": event_id,
                "type": "event",
                "label": event_type_labels.get(e["type"], e["type"] or "8-K"),
                "name": event_type_labels.get(e["type"], e["type"] or "8-K"),
                "metadata": {
                    "date": (e["date"] or "")[:10],
                    "item": e["item"],
                    "accession": e["accession"],
                },
            })
            edges.append({
                "source": company_id,
                "target": event_id,
                "type": "event",
                "metadata": {"date": (e["date"] or "")[:10]},
            })

        # Activist filings
        activist = await Neo4jClient.execute_query("""
            MATCH (af:ActivistFiling)-[:TARGETS]->(co:Company {cik: $cik})
            RETURN af.filer_name AS filer, af.filing_date AS date,
                   af.percentage AS pct, af.filing_type AS form
            ORDER BY af.filing_date DESC
            LIMIT 5
        """, {"cik": cik})

        for a in activist:
            activist_id = f"activist-{a['filer']}-{a['date']}"
            pct_str = f" ({a['pct']:.1f}%)" if a.get("pct") else ""
            nodes.append({
                "id": activist_id,
                "type": "activist",
                "label": (a["filer"] or "")[:25] + pct_str,
                "name": a["filer"],
                "metadata": {
                    "filer": a["filer"],
                    "date": (a["date"] or "")[:10],
                    "percentage": round(a["pct"], 1) if a.get("pct") else None,
                    "form_type": a["form"],
                },
            })
            edges.append({
                "source": activist_id,
                "target": company_id,
                "type": "activist",
                "metadata": {
                    "date": (a["date"] or "")[:10],
                    "percentage": round(a["pct"], 1) if a.get("pct") else None,
                },
            })

        # Officers and Directors — deduplicated (one edge per person)
        existing_person_ids = {n["id"] for n in nodes if n["type"] == "person"}
        role_edge_added = set()

        try:
            roles = await Neo4jClient.execute_query("""
                MATCH (p:Person)-[r:OFFICER_OF|DIRECTOR_OF]->(co:Company {cik: $cik})
                WITH p.name AS name,
                     collect(DISTINCT CASE WHEN type(r) = 'OFFICER_OF' THEN 'officer' ELSE 'director' END) AS roles,
                     collect(DISTINCT r.title) AS titles
                RETURN name, roles,
                       [t IN titles WHERE t IS NOT NULL AND t <> ''][0] AS title
                LIMIT 20
            """, {"cik": cik})
            for r in roles:
                person_id = f"person-{r['name']}"
                role_list = r["roles"] or []
                role_label = " & ".join(sorted(set(role_list)))
                title = r["title"] or ""

                if person_id not in existing_person_ids:
                    nodes.append({
                        "id": person_id,
                        "type": "person",
                        "label": r["name"],
                        "name": r["name"],
                        "metadata": {"title": title, "role": role_label},
                    })
                    existing_person_ids.add(person_id)

                if person_id not in role_edge_added:
                    edge_type = "officer" if "officer" in role_list else "director"
                    edges.append({
                        "source": person_id,
                        "target": company_id,
                        "type": edge_type,
                        "metadata": {"title": title, "role": role_label},
                    })
                    role_edge_added.add(person_id)
        except Exception:
            pass

        # Summary
        total_buy = sum(r.get("buy_value") or 0 for r in insiders)
        total_sell = sum(r.get("sell_value") or 0 for r in insiders)
        officer_count = len([n for n in nodes if n.get("metadata", {}).get("role") == "officer"])
        director_count = len([n for n in nodes if n.get("metadata", {}).get("role") == "director"])
        summary = {
            "company": c["name"],
            "ticker": ticker,
            "cik": cik,
            "total_insiders": len(insiders),
            "total_buy_value": round(total_buy, 2),
            "total_sell_value": round(total_sell, 2),
            "event_count": len(events),
            "activist_count": len(activist),
            "cross_company_insiders": len(cross_company),
            "officer_count": officer_count,
            "director_count": director_count,
        }

        return {"nodes": nodes, "edges": edges, "summary": summary}

    @staticmethod
    async def get_person_graph(query: str) -> dict | None:
        """Build a graph starting from a person."""

        # Find the person
        person = await Neo4jClient.execute_query("""
            MATCH (p:Person)-[:TRADED_BY]->(t:InsiderTransaction)<-[:INSIDER_TRADE_OF]-(c:Company)
            WHERE p.name = $q OR toLower(p.name) CONTAINS toLower($q)
            WITH p, c, t
            LIMIT 1
            RETURN p.name AS name
        """, {"q": query})

        if not person:
            return None

        person_name = person[0]["name"]
        person_id = f"person-{person_name}"

        nodes = [{
            "id": person_id,
            "type": "person",
            "label": person_name,
            "name": person_name,
            "metadata": {},
        }]
        edges = []

        # All companies this person trades at
        companies = await Neo4jClient.execute_query("""
            MATCH (p:Person {name: $name})-[:TRADED_BY]->(t:InsiderTransaction)<-[:INSIDER_TRADE_OF]-(c:Company)
            WHERE t.transaction_code IN ['P', 'S']
              AND (t.is_derivative IS NULL OR t.is_derivative = false)
              AND c.tickers IS NOT NULL AND size(c.tickers) > 0
            WITH c,
                 sum(CASE WHEN t.transaction_code = 'P' THEN t.total_value ELSE 0 END) AS buy_value,
                 sum(CASE WHEN t.transaction_code = 'S' THEN t.total_value ELSE 0 END) AS sell_value,
                 sum(CASE WHEN t.transaction_code = 'P' THEN 1 ELSE 0 END) AS buy_count,
                 sum(CASE WHEN t.transaction_code = 'S' THEN 1 ELSE 0 END) AS sell_count,
                 max(t.transaction_date) AS latest_date,
                 collect(DISTINCT t.insider_title)[0] AS title
            RETURN c.cik AS cik, c.name AS company_name, c.tickers[0] AS ticker,
                   buy_value, sell_value, buy_count, sell_count, latest_date, title
            ORDER BY buy_value + sell_value DESC
        """, {"name": person_name})

        for c in companies:
            company_id = f"company-{c['cik']}"
            buy_val = c["buy_value"] or 0
            sell_val = c["sell_value"] or 0

            nodes.append({
                "id": company_id,
                "type": "company",
                "label": c["ticker"] or c["cik"],
                "name": c["company_name"],
                "metadata": {
                    "cik": c["cik"],
                    "ticker": c["ticker"],
                    "title": c["title"] or "",
                    "buy_value": round(buy_val, 2),
                    "sell_value": round(sell_val, 2),
                    "latest_date": (c["latest_date"] or "")[:10],
                },
            })

            if buy_val > 0:
                edges.append({
                    "source": person_id,
                    "target": company_id,
                    "type": "buy",
                    "metadata": {
                        "total_value": round(buy_val, 2),
                        "trade_count": c["buy_count"] or 0,
                    },
                })
            if sell_val > 0:
                edges.append({
                    "source": person_id,
                    "target": company_id,
                    "type": "sell",
                    "metadata": {
                        "total_value": round(sell_val, 2),
                        "trade_count": c["sell_count"] or 0,
                    },
                })

            # Events at each company
            events = await Neo4jClient.execute_query("""
                MATCH (co:Company {cik: $cik})-[:FILED_EVENT]->(e:Event)
                RETURN DISTINCT e.accession_number AS accession,
                       e.signal_type AS type, e.filing_date AS date
                ORDER BY e.filing_date DESC
                LIMIT 5
            """, {"cik": c["cik"]})

            event_labels = {
                "material_agreement": "Material Agreement",
                "executive_change": "Executive Change",
                "governance_change": "Governance Change",
                "acquisition_disposition": "Acquisition",
            }

            for e in events:
                event_id = f"event-{e['accession']}"
                nodes.append({
                    "id": event_id,
                    "type": "event",
                    "label": event_labels.get(e["type"], e["type"] or "8-K"),
                    "name": event_labels.get(e["type"], e["type"] or "8-K"),
                    "metadata": {"date": (e["date"] or "")[:10], "accession": e["accession"]},
                })
                edges.append({
                    "source": company_id,
                    "target": event_id,
                    "type": "event",
                    "metadata": {"date": (e["date"] or "")[:10]},
                })

        # Summary
        total_buy = sum(c.get("buy_value") or 0 for c in companies)
        total_sell = sum(c.get("sell_value") or 0 for c in companies)
        summary = {
            "person": person_name,
            "num_companies": len(companies),
            "total_buy_value": round(total_buy, 2),
            "total_sell_value": round(total_sell, 2),
            "net_direction": "net buyer" if total_buy > total_sell * 1.5 else "net seller" if total_sell > total_buy * 1.5 else "mixed",
        }

        return {"nodes": nodes, "edges": edges, "summary": summary}

    @staticmethod
    async def search(query: str, mode: str = "company") -> list[dict]:
        """Autocomplete search for companies or persons."""

        if len(query) < 2:
            return []

        if mode == "company":
            # Fast: try name index first (indexed), then ticker scan
            results = await Neo4jClient.execute_query("""
                CALL {
                    MATCH (c:Company)
                    WHERE c.tickers IS NOT NULL AND size(c.tickers) > 0
                      AND toLower(c.name) CONTAINS toLower($q)
                    RETURN c, 1 AS priority
                    LIMIT 10
                    UNION
                    MATCH (c:Company)
                    WHERE c.tickers IS NOT NULL AND size(c.tickers) > 0
                      AND ANY(t IN c.tickers WHERE toUpper(t) STARTS WITH toUpper($q))
                    RETURN c, 0 AS priority
                    LIMIT 10
                }
                WITH DISTINCT c, min(priority) AS p
                ORDER BY p, c.name
                RETURN c.cik AS cik, c.name AS name, c.tickers[0] AS ticker
                LIMIT 10
            """, {"q": query})
            return [
                {"id": r["cik"], "label": f"{r['ticker']} — {r['name'] or 'Unknown'}", "ticker": r["ticker"], "name": r["name"]}
                for r in results
            ]

        else:  # person
            results = await Neo4jClient.execute_query("""
                MATCH (p:Person)-[:TRADED_BY]->(t:InsiderTransaction)<-[:INSIDER_TRADE_OF]-(c:Company)
                WHERE toLower(p.name) CONTAINS toLower($q)
                  AND t.transaction_code IN ['P', 'S']
                  AND c.tickers IS NOT NULL AND size(c.tickers) > 0
                WITH p.name AS name, collect(DISTINCT c.tickers[0])[0] AS ticker,
                     count(t) AS trades
                RETURN name, ticker, trades
                ORDER BY trades DESC
                LIMIT 10
            """, {"q": query})
            return [
                {"id": r["name"], "label": f"{r['name']} — {r['ticker'] or 'Unknown'}", "name": r["name"], "ticker": r["ticker"]}
                for r in results
            ]
