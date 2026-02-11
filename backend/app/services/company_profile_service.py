"""Service for generating company profiles."""

from dataclasses import dataclass, field
from typing import Optional

from app.db.neo4j_client import Neo4jClient


@dataclass
class CompanyProfile:
    """Complete company profile for the detail view."""

    # Basic info
    cik: str
    name: str
    ticker: Optional[str] = None
    sic: Optional[str] = None
    sic_description: Optional[str] = None
    state_of_incorporation: Optional[str] = None

    # Counts
    subsidiary_count: int = 0
    officer_count: int = 0
    director_count: int = 0
    connection_count: int = 0  # Board interlocks with other companies

    # Related data
    signals: list[dict] = field(default_factory=list)
    connections: list[dict] = field(default_factory=list)
    recent_subsidiaries: list[dict] = field(default_factory=list)
    officers: list[dict] = field(default_factory=list)
    directors: list[dict] = field(default_factory=list)
    insider_trades: list[dict] = field(default_factory=list)
    insider_trade_summary: Optional[dict] = None

    def to_dict(self) -> dict:
        return {
            "basic_info": {
                "cik": self.cik,
                "name": self.name,
                "ticker": self.ticker,
                "sic": self.sic,
                "sic_description": self.sic_description,
                "state_of_incorporation": self.state_of_incorporation,
            },
            "counts": {
                "subsidiaries": self.subsidiary_count,
                "officers": self.officer_count,
                "directors": self.director_count,
                "board_connections": self.connection_count,
                "insider_trades": len(self.insider_trades),
            },
            "signals": self.signals,
            "connections": self.connections,
            "officers": self.officers,
            "directors": self.directors,
            "recent_subsidiaries": self.recent_subsidiaries,
            "insider_trades": self.insider_trades,
            "insider_trade_summary": self.insider_trade_summary,
        }


class CompanyProfileService:
    """Service for building company profiles."""

    @staticmethod
    async def get_profile(cik: str) -> Optional[CompanyProfile]:
        """
        Get complete company profile by CIK.
        """
        # Get basic company info
        company_query = """
            MATCH (c:Company {cik: $cik})
            OPTIONAL MATCH (c)-[:OWNS]->(sub:Company)
            OPTIONAL MATCH (p1:Person)-[:OFFICER_OF]->(c)
            OPTIONAL MATCH (p2:Person)-[:DIRECTOR_OF]->(c)
            WITH c,
                 count(DISTINCT sub) as sub_count,
                 count(DISTINCT p1) as officer_count,
                 count(DISTINCT p2) as director_count
            RETURN c.cik as cik,
                   c.name as name,
                   c.tickers as tickers,
                   c.sic as sic,
                   c.sic_description as sic_description,
                   c.state_of_incorporation as state,
                   sub_count,
                   officer_count,
                   director_count
        """

        result = await Neo4jClient.execute_query(company_query, {"cik": cik})

        if not result:
            return None

        r = result[0]
        profile = CompanyProfile(
            cik=r["cik"],
            name=r["name"],
            ticker=r["tickers"][0] if r["tickers"] else None,
            sic=r["sic"],
            sic_description=r["sic_description"],
            state_of_incorporation=r["state"],
            subsidiary_count=r["sub_count"],
            officer_count=r["officer_count"],
            director_count=r["director_count"],
        )

        # Get signals
        profile.signals = await CompanyProfileService._get_signals(cik)

        # Get board connections
        connections_result = await CompanyProfileService._get_connections(cik)
        profile.connections = connections_result["connections"]
        profile.connection_count = connections_result["count"]

        # Get officers
        profile.officers = await CompanyProfileService._get_officers(cik)

        # Get directors
        profile.directors = await CompanyProfileService._get_directors(cik)

        # Get recent subsidiaries
        profile.recent_subsidiaries = await CompanyProfileService._get_subsidiaries(cik)

        # Get insider trades
        insider_result = await CompanyProfileService._get_insider_trades(cik)
        profile.insider_trades = insider_result["trades"]
        profile.insider_trade_summary = insider_result["summary"]

        return profile

    @staticmethod
    async def _get_signals(cik: str, limit: int = 20) -> list[dict]:
        """Get signal timeline for company."""
        query = """
            MATCH (c:Company {cik: $cik})-[:FILED_EVENT]->(e:Event)
            RETURN e.filing_date as filing_date,
                   e.item_number as item_number,
                   e.item_name as item_name,
                   e.signal_type as signal_type,
                   e.persons_mentioned as persons_mentioned,
                   e.accession_number as accession_number
            ORDER BY e.filing_date DESC
            LIMIT $limit
        """

        results = await Neo4jClient.execute_query(query, {"cik": cik, "limit": limit})

        return [
            {
                "filing_date": r["filing_date"],
                "item_number": r["item_number"],
                "item_name": r["item_name"],
                "signal_type": r["signal_type"],
                "persons_mentioned": r["persons_mentioned"] or [],
                "accession_number": r["accession_number"],
            }
            for r in results
        ]

    @staticmethod
    async def _get_connections(cik: str) -> dict:
        """Get board connections to other companies."""
        query = """
            MATCH (c:Company {cik: $cik})<-[:DIRECTOR_OF]-(p:Person)-[:DIRECTOR_OF]->(other:Company)
            WHERE c <> other
            RETURN p.name as person,
                   other.name as connected_company,
                   other.cik as connected_cik
            ORDER BY other.name
        """

        results = await Neo4jClient.execute_query(query, {"cik": cik})

        # Group by connected company
        connections = {}
        for r in results:
            key = r["connected_cik"]
            if key not in connections:
                connections[key] = {
                    "company_name": r["connected_company"],
                    "cik": r["connected_cik"],
                    "shared_directors": [],
                }
            connections[key]["shared_directors"].append(r["person"])

        return {
            "count": len(connections),
            "connections": list(connections.values()),
        }

    @staticmethod
    async def _get_officers(cik: str, limit: int = 10) -> list[dict]:
        """Get officers of the company."""
        query = """
            MATCH (p:Person)-[r:OFFICER_OF]->(c:Company {cik: $cik})
            RETURN p.name as name,
                   r.title as title
            ORDER BY p.name
            LIMIT $limit
        """

        results = await Neo4jClient.execute_query(query, {"cik": cik, "limit": limit})

        return [
            {
                "name": r["name"],
                "title": r["title"],
            }
            for r in results
        ]

    @staticmethod
    async def _get_directors(cik: str, limit: int = 15) -> list[dict]:
        """Get directors of the company."""
        query = """
            MATCH (p:Person)-[:DIRECTOR_OF]->(c:Company {cik: $cik})
            OPTIONAL MATCH (p)-[:DIRECTOR_OF]->(other:Company)
            WHERE other <> c
            WITH p, collect(DISTINCT other.name) as other_boards
            RETURN p.name as name,
                   other_boards
            ORDER BY size(other_boards) DESC, p.name
            LIMIT $limit
        """

        results = await Neo4jClient.execute_query(query, {"cik": cik, "limit": limit})

        return [
            {
                "name": r["name"],
                "other_boards": r["other_boards"],
            }
            for r in results
        ]

    @staticmethod
    async def _get_subsidiaries(cik: str, limit: int = 20) -> list[dict]:
        """Get subsidiaries of the company."""
        query = """
            MATCH (c:Company {cik: $cik})-[:OWNS]->(sub:Company)
            OPTIONAL MATCH (sub)-[:INCORPORATED_IN]->(j:Jurisdiction)
            RETURN sub.name as name,
                   j.name as jurisdiction
            ORDER BY sub.name
            LIMIT $limit
        """

        results = await Neo4jClient.execute_query(query, {"cik": cik, "limit": limit})

        return [
            {
                "name": r["name"],
                "jurisdiction": r["jurisdiction"],
            }
            for r in results
        ]

    @staticmethod
    async def _get_insider_trades(cik: str, limit: int = 20) -> dict:
        """Get recent insider trades and summary for company."""
        query = """
            MATCH (c:Company {cik: $cik})-[:INSIDER_TRADE_OF]->(t:InsiderTransaction)
            RETURN t.insider_name as insider_name,
                   t.insider_title as insider_title,
                   t.transaction_date as transaction_date,
                   t.transaction_code as transaction_code,
                   t.transaction_type as transaction_type,
                   t.security_title as security_title,
                   t.shares as shares,
                   t.price_per_share as price_per_share,
                   t.total_value as total_value,
                   t.filing_date as filing_date,
                   t.accession_number as accession_number
            ORDER BY t.transaction_date DESC
            LIMIT $limit
        """

        results = await Neo4jClient.execute_query(query, {"cik": cik, "limit": limit})

        trades = [
            {
                "insider_name": r["insider_name"],
                "insider_title": r["insider_title"],
                "transaction_date": r["transaction_date"],
                "transaction_code": r["transaction_code"],
                "transaction_type": r["transaction_type"],
                "security_title": r["security_title"],
                "shares": r["shares"],
                "price_per_share": r["price_per_share"],
                "total_value": r["total_value"],
                "filing_date": r["filing_date"],
                "accession_number": r["accession_number"],
            }
            for r in results
        ]

        # Build summary
        unique_insiders = set()
        purchases = 0
        sales = 0
        for r in results:
            unique_insiders.add(r["insider_name"])
            if r["transaction_code"] == "P":
                purchases += 1
            elif r["transaction_code"] == "S":
                sales += 1

        summary = {
            "total": len(results),
            "unique_insiders": len(unique_insiders),
            "purchases": purchases,
            "sales": sales,
        }

        return {"trades": trades, "summary": summary}

    @staticmethod
    async def search_companies(query: str, limit: int = 20) -> list[dict]:
        """Search for companies by name or ticker."""
        # Only return companies with CIKs (public filers, not subsidiaries)
        search_query = """
            MATCH (c:Company)
            WHERE c.cik IS NOT NULL AND c.cik <> ''
            AND (
                toLower(c.name) CONTAINS toLower($query)
                OR any(t IN coalesce(c.tickers, []) WHERE t CONTAINS $query_upper)
            )
            OPTIONAL MATCH (c)-[:FILED_EVENT]->(e:Event)
            WITH c, count(e) as signal_count
            RETURN c.cik as cik,
                   c.name as name,
                   c.tickers as tickers,
                   signal_count
            ORDER BY signal_count DESC, c.name
            LIMIT $limit
        """

        results = await Neo4jClient.execute_query(
            search_query,
            {"query": query, "query_upper": query.upper(), "limit": limit}
        )

        return [
            {
                "cik": r["cik"],
                "name": r["name"],
                "ticker": r["tickers"][0] if r.get("tickers") else None,
                "signal_count": r["signal_count"],
            }
            for r in results
        ]
