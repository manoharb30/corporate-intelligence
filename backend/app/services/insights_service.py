"""Service for auto-discovering interesting patterns in corporate data."""

from dataclasses import dataclass, field
from typing import Optional
from app.db.neo4j_client import Neo4jClient


@dataclass
class Insight:
    """A single discovered insight."""

    category: str  # board_interlock, large_structure, cross_sector, ownership
    headline: str  # Short summary
    description: str  # Detailed explanation
    entities: list[dict] = field(default_factory=list)  # Companies/people involved
    importance: str = "medium"  # low, medium, high

    def to_dict(self) -> dict:
        return {
            "category": self.category,
            "headline": self.headline,
            "description": self.description,
            "entities": self.entities,
            "importance": self.importance,
        }


class InsightsService:
    """Service for auto-discovering patterns."""

    @staticmethod
    async def discover_all() -> list[Insight]:
        """Run all pattern detectors and return insights."""
        insights = []

        insights.extend(await InsightsService._find_board_interlocks())
        insights.extend(await InsightsService._find_large_structures())
        insights.extend(await InsightsService._find_bridge_people())
        insights.extend(await InsightsService._find_connected_companies())

        # Sort by importance
        importance_order = {"high": 0, "medium": 1, "low": 2}
        insights.sort(key=lambda x: importance_order.get(x.importance, 1))

        return insights

    @staticmethod
    async def _find_board_interlocks() -> list[Insight]:
        """Find companies that share board members."""
        insights = []

        query = """
            MATCH (c1:Company)<-[:DIRECTOR_OF]-(p:Person)-[:DIRECTOR_OF]->(c2:Company)
            WHERE c1 <> c2 AND c1.cik IS NOT NULL AND c2.cik IS NOT NULL
            WITH c1, c2, collect(p.name) as shared_directors
            WHERE c1.name < c2.name  // Avoid duplicates
            RETURN c1.name as company_a, c2.name as company_b, shared_directors
            ORDER BY size(shared_directors) DESC
        """

        results = await Neo4jClient.execute_query(query)

        for r in results:
            directors = r["shared_directors"]
            company_a = r["company_a"]
            company_b = r["company_b"]

            importance = "high" if len(directors) > 1 else "medium"

            insights.append(Insight(
                category="board_interlock",
                headline=f"{company_a} and {company_b} share board member(s)",
                description=f"{', '.join(directors)} serve(s) on the boards of both {company_a} and {company_b}. This creates a direct governance link between these companies.",
                entities=[
                    {"type": "company", "name": company_a},
                    {"type": "company", "name": company_b},
                    *[{"type": "person", "name": d} for d in directors]
                ],
                importance=importance,
            ))

        return insights

    @staticmethod
    async def _find_large_structures() -> list[Insight]:
        """Find companies with unusually large subsidiary structures."""
        insights = []

        query = """
            MATCH (parent:Company)-[:OWNS]->(sub:Company)
            WHERE parent.cik IS NOT NULL
            WITH parent, count(sub) as sub_count
            WHERE sub_count >= 100
            RETURN parent.name as company, sub_count
            ORDER BY sub_count DESC
            LIMIT 10
        """

        results = await Neo4jClient.execute_query(query)

        for r in results:
            company = r["company"]
            count = r["sub_count"]

            importance = "high" if count > 500 else "medium"

            insights.append(Insight(
                category="large_structure",
                headline=f"{company} has {count} subsidiaries",
                description=f"{company} operates a complex corporate structure with {count} subsidiary entities. Large subsidiary counts can indicate global operations, tax optimization strategies, or acquisition history.",
                entities=[{"type": "company", "name": company}],
                importance=importance,
            ))

        return insights

    @staticmethod
    async def _find_bridge_people() -> list[Insight]:
        """Find people who serve on multiple boards."""
        insights = []

        query = """
            MATCH (p:Person)-[:DIRECTOR_OF]->(c:Company)
            WHERE c.cik IS NOT NULL
            WITH p, collect(c.name) as companies, count(c) as board_count
            WHERE board_count >= 2
            RETURN p.name as person, companies, board_count
            ORDER BY board_count DESC
        """

        results = await Neo4jClient.execute_query(query)

        for r in results:
            person = r["person"]
            companies = r["companies"]
            count = r["board_count"]

            importance = "high" if count > 2 else "medium"

            insights.append(Insight(
                category="bridge_person",
                headline=f"{person} serves on {count} S&P 500 boards",
                description=f"{person} is a director at {', '.join(companies)}. This individual connects these companies through shared governance oversight.",
                entities=[
                    {"type": "person", "name": person},
                    *[{"type": "company", "name": c} for c in companies]
                ],
                importance=importance,
            ))

        return insights

    @staticmethod
    async def _find_connected_companies() -> list[Insight]:
        """Find companies with multiple board connections to other companies."""
        insights = []

        query = """
            MATCH (c1:Company)<-[:DIRECTOR_OF]-(p:Person)-[:DIRECTOR_OF]->(c2:Company)
            WHERE c1 <> c2 AND c1.cik IS NOT NULL
            WITH c1, count(DISTINCT c2) as connected_count, collect(DISTINCT c2.name) as connections
            WHERE connected_count >= 2
            RETURN c1.name as company, connected_count, connections
            ORDER BY connected_count DESC
            LIMIT 5
        """

        results = await Neo4jClient.execute_query(query)

        for r in results:
            company = r["company"]
            count = r["connected_count"]
            connections = r["connections"]

            insights.append(Insight(
                category="hub_company",
                headline=f"{company} has board ties to {count} other S&P 500 companies",
                description=f"{company} shares board members with {', '.join(connections)}. This makes it a hub in the corporate governance network.",
                entities=[
                    {"type": "company", "name": company},
                    *[{"type": "company", "name": c} for c in connections]
                ],
                importance="high",
            ))

        return insights
