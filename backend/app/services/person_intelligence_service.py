"""Service for assembling person-level intelligence from the graph.

Shows all companies a person trades at, their roles, transaction history,
and cross-company activity patterns.
"""

from app.db.neo4j_client import Neo4jClient


class PersonIntelligenceService:

    @staticmethod
    async def get_intelligence(person_name: str) -> dict | None:
        """Get everything we know about a person's trading activity."""

        # Find the person and all their trading activity
        trades = await Neo4jClient.execute_query("""
            MATCH (p:Person)-[:TRADED_BY]->(t:InsiderTransaction)<-[:INSIDER_TRADE_OF]-(c:Company)
            WHERE p.name = $name
              AND t.transaction_code IN ['P', 'S']
              AND (t.is_derivative IS NULL OR t.is_derivative = false)
              AND t.total_value > 0
            RETURN c.cik AS cik, c.name AS company_name, c.tickers AS tickers,
                   t.transaction_code AS code, t.transaction_date AS date,
                   t.total_value AS value, t.shares AS shares,
                   t.price_per_share AS price, t.insider_title AS title
            ORDER BY t.transaction_date DESC
        """, {"name": person_name})

        if not trades:
            # Try fuzzy match
            trades = await Neo4jClient.execute_query("""
                MATCH (p:Person)-[:TRADED_BY]->(t:InsiderTransaction)<-[:INSIDER_TRADE_OF]-(c:Company)
                WHERE toLower(p.name) = toLower($name)
                  AND t.transaction_code IN ['P', 'S']
                  AND (t.is_derivative IS NULL OR t.is_derivative = false)
                  AND t.total_value > 0
                RETURN c.cik AS cik, c.name AS company_name, c.tickers AS tickers,
                       t.transaction_code AS code, t.transaction_date AS date,
                       t.total_value AS value, t.shares AS shares,
                       t.price_per_share AS price, t.insider_title AS title
                ORDER BY t.transaction_date DESC
            """, {"name": person_name})

        if not trades:
            return None

        # Group by company
        companies: dict[str, dict] = {}
        all_transactions = []

        for t in trades:
            cik = t["cik"]
            ticker = t["tickers"][0] if t.get("tickers") and len(t["tickers"]) > 0 else None

            if cik not in companies:
                companies[cik] = {
                    "cik": cik,
                    "name": t["company_name"],
                    "ticker": ticker,
                    "title": t["title"],
                    "total_buying": 0,
                    "total_selling": 0,
                    "buy_count": 0,
                    "sell_count": 0,
                    "latest_trade": None,
                    "earliest_trade": None,
                }

            comp = companies[cik]
            if t["code"] == "P":
                comp["total_buying"] += t["value"] or 0
                comp["buy_count"] += 1
            else:
                comp["total_selling"] += t["value"] or 0
                comp["sell_count"] += 1

            trade_date = t["date"][:10] if t["date"] else None
            if trade_date:
                if not comp["latest_trade"] or trade_date > comp["latest_trade"]:
                    comp["latest_trade"] = trade_date
                if not comp["earliest_trade"] or trade_date < comp["earliest_trade"]:
                    comp["earliest_trade"] = trade_date

            # Update title if we find one
            if t["title"] and not comp["title"]:
                comp["title"] = t["title"]

            all_transactions.append({
                "cik": cik,
                "ticker": ticker,
                "company_name": t["company_name"],
                "code": "BUY" if t["code"] == "P" else "SELL",
                "date": trade_date,
                "value": round(t["value"], 2) if t["value"] else None,
                "shares": t["shares"],
                "price": round(t["price"], 2) if t["price"] else None,
            })

        # Check for roles (officer/director)
        roles = await Neo4jClient.execute_query("""
            MATCH (p:Person)
            WHERE p.name = $name OR toLower(p.name) = toLower($name)
            OPTIONAL MATCH (p)-[r:OFFICER_OF]->(c:Company)
            WITH p, collect(DISTINCT {cik: c.cik, name: c.name, ticker: c.tickers[0], role: 'officer', title: r.title}) AS officer_roles
            OPTIONAL MATCH (p)-[:DIRECTOR_OF]->(c2:Company)
            WITH p, officer_roles, collect(DISTINCT {cik: c2.cik, name: c2.name, ticker: c2.tickers[0], role: 'director'}) AS director_roles
            RETURN officer_roles + director_roles AS roles
        """, {"name": person_name})

        role_list = []
        if roles and roles[0].get("roles"):
            role_list = [r for r in roles[0]["roles"] if r.get("cik")]

        # Build company list sorted by total activity
        company_list = sorted(
            companies.values(),
            key=lambda c: c["total_buying"] + c["total_selling"],
            reverse=True,
        )

        # Determine net direction
        total_buying = sum(c["total_buying"] for c in company_list)
        total_selling = sum(c["total_selling"] for c in company_list)

        if total_buying > total_selling * 1.5:
            net_direction = "net buyer"
        elif total_selling > total_buying * 1.5:
            net_direction = "net seller"
        else:
            net_direction = "mixed"

        return {
            "person_name": person_name,
            "num_companies": len(company_list),
            "total_buying": round(total_buying, 2),
            "total_selling": round(total_selling, 2),
            "total_trades": len(all_transactions),
            "net_direction": net_direction,
            "companies": company_list,
            "transactions": all_transactions[:50],
            "roles": role_list,
        }
