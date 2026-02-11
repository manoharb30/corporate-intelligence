"""Person-related business logic."""

from typing import Optional

from app.models import Person, PersonCreate, PersonUpdate, PaginatedResponse, Company
from app.db.neo4j_client import Neo4jClient


class PersonService:
    """Service for person operations."""

    @staticmethod
    async def list_persons(
        page: int,
        page_size: int,
        is_pep: Optional[bool] = None,
        is_sanctioned: Optional[bool] = None,
    ) -> PaginatedResponse[Person]:
        """List persons with pagination and filtering."""
        skip = (page - 1) * page_size

        where_clauses = []
        params = {"skip": skip, "limit": page_size}

        if is_pep is not None:
            where_clauses.append("p.is_pep = $is_pep")
            params["is_pep"] = is_pep
        if is_sanctioned is not None:
            where_clauses.append("p.is_sanctioned = $is_sanctioned")
            params["is_sanctioned"] = is_sanctioned

        where_str = f"WHERE {' AND '.join(where_clauses)}" if where_clauses else ""

        count_query = f"MATCH (p:Person) {where_str} RETURN count(p) as total"
        count_result = await Neo4jClient.execute_query(count_query, params)
        total = count_result[0]["total"] if count_result else 0

        data_query = f"""
            MATCH (p:Person) {where_str}
            RETURN p
            ORDER BY p.name
            SKIP $skip LIMIT $limit
        """
        records = await Neo4jClient.execute_query(data_query, params)

        persons = [Person(**record["p"]) for record in records]
        pages = (total + page_size - 1) // page_size

        return PaginatedResponse(
            items=persons,
            total=total,
            page=page,
            page_size=page_size,
            pages=pages,
        )

    @staticmethod
    async def search_by_name(query: str, limit: int) -> list[Person]:
        """Search persons by name using full-text search."""
        cypher = """
            CALL db.index.fulltext.queryNodes('person_name_fulltext_idx', $query)
            YIELD node, score
            RETURN node as p
            ORDER BY score DESC
            LIMIT $limit
        """
        records = await Neo4jClient.execute_query(cypher, {"query": query, "limit": limit})
        return [Person(**record["p"]) for record in records]

    @staticmethod
    async def list_peps(limit: int) -> list[Person]:
        """List Politically Exposed Persons."""
        cypher = """
            MATCH (p:Person {is_pep: true})
            RETURN p
            ORDER BY p.name
            LIMIT $limit
        """
        records = await Neo4jClient.execute_query(cypher, {"limit": limit})
        return [Person(**record["p"]) for record in records]

    @staticmethod
    async def list_sanctioned(limit: int) -> list[Person]:
        """List sanctioned persons."""
        cypher = """
            MATCH (p:Person {is_sanctioned: true})
            RETURN p
            ORDER BY p.name
            LIMIT $limit
        """
        records = await Neo4jClient.execute_query(cypher, {"limit": limit})
        return [Person(**record["p"]) for record in records]

    @staticmethod
    async def get_by_id(person_id: str) -> Optional[Person]:
        """Get person by ID."""
        cypher = "MATCH (p:Person {id: $id}) RETURN p"
        records = await Neo4jClient.execute_query(cypher, {"id": person_id})
        return Person(**records[0]["p"]) if records else None

    @staticmethod
    async def get_associated_companies(person_id: str) -> list[Company]:
        """Get all companies associated with a person."""
        cypher = """
            MATCH (p:Person {id: $id})
            MATCH (p)-[:OWNS|OFFICER_OF|DIRECTOR_OF]->(c:Company)
            RETURN DISTINCT c
            ORDER BY c.name
        """
        records = await Neo4jClient.execute_query(cypher, {"id": person_id})
        return [Company(**record["c"]) for record in records]

    @staticmethod
    async def create(person: PersonCreate) -> Person:
        """Create a new person."""
        import uuid

        person_id = str(uuid.uuid4())
        normalized = person.name.upper().strip()

        cypher = """
            CREATE (p:Person {
                id: $id,
                name: $name,
                normalized_name: $normalized_name,
                is_pep: $is_pep,
                is_sanctioned: $is_sanctioned
            })
            RETURN p
        """
        params = {
            "id": person_id,
            "name": person.name,
            "normalized_name": normalized,
            "is_pep": person.is_pep,
            "is_sanctioned": person.is_sanctioned,
        }

        records = await Neo4jClient.execute_query(cypher, params)
        return Person(**records[0]["p"])

    @staticmethod
    async def update(person_id: str, person: PersonUpdate) -> Optional[Person]:
        """Update a person."""
        updates = person.model_dump(exclude_unset=True)
        if not updates:
            return await PersonService.get_by_id(person_id)

        set_parts = [f"p.{key} = ${key}" for key in updates]
        set_clause = ", ".join(set_parts)

        cypher = f"""
            MATCH (p:Person {{id: $id}})
            SET {set_clause}
            RETURN p
        """
        params = {"id": person_id, **updates}

        records = await Neo4jClient.execute_query(cypher, params)
        return Person(**records[0]["p"]) if records else None

    @staticmethod
    async def delete(person_id: str) -> bool:
        """Delete a person and their relationships."""
        cypher = """
            MATCH (p:Person {id: $id})
            DETACH DELETE p
            RETURN count(*) as deleted
        """
        result = await Neo4jClient.execute_write(cypher, {"id": person_id})
        return result["nodes_deleted"] > 0
