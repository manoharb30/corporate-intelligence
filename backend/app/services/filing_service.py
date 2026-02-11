"""Filing-related business logic."""

from typing import Optional

from app.models import Filing, FilingCreate, PaginatedResponse
from app.db.neo4j_client import Neo4jClient


class FilingService:
    """Service for SEC filing operations."""

    @staticmethod
    async def list_filings(
        page: int,
        page_size: int,
        form_type: Optional[str] = None,
    ) -> PaginatedResponse[Filing]:
        """List filings with pagination and filtering."""
        skip = (page - 1) * page_size

        where_clauses = []
        params = {"skip": skip, "limit": page_size}

        if form_type:
            where_clauses.append("f.form_type = $form_type")
            params["form_type"] = form_type

        where_str = f"WHERE {' AND '.join(where_clauses)}" if where_clauses else ""

        count_query = f"MATCH (f:Filing) {where_str} RETURN count(f) as total"
        count_result = await Neo4jClient.execute_query(count_query, params)
        total = count_result[0]["total"] if count_result else 0

        data_query = f"""
            MATCH (f:Filing) {where_str}
            RETURN f
            ORDER BY f.filing_date DESC
            SKIP $skip LIMIT $limit
        """
        records = await Neo4jClient.execute_query(data_query, params)

        filings = [Filing(**record["f"]) for record in records]
        pages = (total + page_size - 1) // page_size

        return PaginatedResponse(
            items=filings,
            total=total,
            page=page,
            page_size=page_size,
            pages=pages,
        )

    @staticmethod
    async def get_form_type_counts() -> list[dict[str, int]]:
        """Get count of filings by form type."""
        cypher = """
            MATCH (f:Filing)
            RETURN f.form_type as form_type, count(*) as count
            ORDER BY count DESC
        """
        records = await Neo4jClient.execute_query(cypher)
        return [{"form_type": r["form_type"], "count": r["count"]} for r in records]

    @staticmethod
    async def get_by_id(filing_id: str) -> Optional[Filing]:
        """Get filing by ID."""
        cypher = "MATCH (f:Filing {id: $id}) RETURN f"
        records = await Neo4jClient.execute_query(cypher, {"id": filing_id})
        return Filing(**records[0]["f"]) if records else None

    @staticmethod
    async def get_by_accession_number(accession_number: str) -> Optional[Filing]:
        """Get filing by SEC accession number."""
        cypher = "MATCH (f:Filing {accession_number: $accession_number}) RETURN f"
        records = await Neo4jClient.execute_query(cypher, {"accession_number": accession_number})
        return Filing(**records[0]["f"]) if records else None

    @staticmethod
    async def get_mentioned_entities(filing_id: str) -> dict:
        """Get all entities mentioned in a filing."""
        cypher = """
            MATCH (f:Filing {id: $id})
            OPTIONAL MATCH (c:Company)-[:FILED]->(f)
            OPTIONAL MATCH (e)-[:MENTIONED_IN]->(f)
            RETURN
                collect(DISTINCT c) as filers,
                collect(DISTINCT e) as mentioned
        """
        records = await Neo4jClient.execute_query(cypher, {"id": filing_id})

        if not records:
            return {"filers": [], "mentioned": []}

        return {
            "filers": records[0]["filers"],
            "mentioned": records[0]["mentioned"],
        }

    @staticmethod
    async def create(filing: FilingCreate) -> Filing:
        """Create a new filing record."""
        import uuid

        filing_id = str(uuid.uuid4())

        cypher = """
            CREATE (f:Filing {
                id: $id,
                accession_number: $accession_number,
                form_type: $form_type,
                filing_date: $filing_date,
                source_url: $source_url
            })
            RETURN f
        """
        params = {
            "id": filing_id,
            "accession_number": filing.accession_number,
            "form_type": filing.form_type,
            "filing_date": str(filing.filing_date),
            "source_url": filing.source_url,
        }

        records = await Neo4jClient.execute_query(cypher, params)
        return Filing(**records[0]["f"])

    @staticmethod
    async def delete(filing_id: str) -> bool:
        """Delete a filing and its relationships."""
        cypher = """
            MATCH (f:Filing {id: $id})
            DETACH DELETE f
            RETURN count(*) as deleted
        """
        result = await Neo4jClient.execute_write(cypher, {"id": filing_id})
        return result["nodes_deleted"] > 0
