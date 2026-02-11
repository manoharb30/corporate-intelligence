"""Neo4j loader for OFAC SDN data."""

import logging
import uuid
from typing import Optional

from app.db.neo4j_client import Neo4jClient
from ingestion.ofac.ofac_parser import SDNEntry

logger = logging.getLogger(__name__)


class OFACLoader:
    """Load OFAC SDN entries into Neo4j."""

    def __init__(self):
        self.stats = {
            "persons_created": 0,
            "companies_created": 0,
            "persons_updated": 0,
            "companies_updated": 0,
            "errors": 0,
        }

    async def load_entries(self, entries: list[SDNEntry]) -> dict:
        """
        Load SDN entries into Neo4j.

        Creates Person or Company nodes with is_sanctioned=true flag.
        """
        logger.info(f"Loading {len(entries)} SDN entries into Neo4j")

        for entry in entries:
            try:
                if entry.entity_type == "individual":
                    await self._load_person(entry)
                else:
                    await self._load_company(entry)
            except Exception as e:
                logger.error(f"Error loading entry {entry.uid}: {e}")
                self.stats["errors"] += 1

        logger.info(f"Load complete: {self.stats}")
        return self.stats

    async def _load_person(self, entry: SDNEntry) -> str:
        """
        Load an individual SDN entry as a Person node.

        Returns the node ID.
        """
        cypher = """
            MERGE (p:Person:SanctionedEntity {ofac_uid: $ofac_uid})
            ON CREATE SET
                p.id = $id,
                p.name = $name,
                p.normalized_name = $normalized_name,
                p.is_sanctioned = true,
                p.sanction_programs = $programs,
                p.aliases = $aliases,
                p.nationality = $nationality,
                p.date_of_birth = $date_of_birth,
                p.id_numbers = $id_numbers,
                p.addresses = $addresses,
                p.remarks = $remarks,
                p.source = 'ofac',
                p.source_url = $source_url,
                p.source_date = $source_date,
                p.raw_text = $raw_text,
                p.raw_text_hash = $raw_text_hash,
                p.confidence = $confidence,
                p.created_at = datetime()
            ON MATCH SET
                p.name = $name,
                p.is_sanctioned = true,
                p.sanction_programs = $programs,
                p.aliases = $aliases,
                p.nationality = $nationality,
                p.date_of_birth = $date_of_birth,
                p.id_numbers = $id_numbers,
                p.addresses = $addresses,
                p.remarks = $remarks,
                p.source_url = $source_url,
                p.source_date = $source_date,
                p.raw_text = $raw_text,
                p.raw_text_hash = $raw_text_hash,
                p.updated_at = datetime()
            RETURN p.id as id,
                   CASE WHEN p.created_at = p.updated_at OR p.updated_at IS NULL
                        THEN 'created' ELSE 'updated' END as action
        """

        node_id = str(uuid.uuid4())
        params = {
            "id": node_id,
            "ofac_uid": entry.uid,
            "name": entry.name,
            "normalized_name": entry.name.upper().strip(),
            "programs": entry.programs,
            "aliases": entry.aliases,
            "nationality": entry.nationality,
            "date_of_birth": entry.date_of_birth,
            "id_numbers": entry.id_numbers,
            "addresses": entry.addresses,
            "remarks": entry.remarks,
            "source_url": entry.citation.source_url,
            "source_date": entry.citation.publish_date.isoformat()
            if entry.citation.publish_date
            else None,
            "raw_text": entry.citation.raw_text,
            "raw_text_hash": entry.citation.raw_text_hash,
            "confidence": entry.citation.confidence,
        }

        result = await Neo4jClient.execute_query(cypher, params)

        if result:
            if result[0].get("action") == "created":
                self.stats["persons_created"] += 1
            else:
                self.stats["persons_updated"] += 1
            return result[0]["id"]

        return node_id

    async def _load_company(self, entry: SDNEntry) -> str:
        """
        Load an entity SDN entry as a Company node.

        Returns the node ID.
        """
        cypher = """
            MERGE (c:Company:SanctionedEntity {ofac_uid: $ofac_uid})
            ON CREATE SET
                c.id = $id,
                c.name = $name,
                c.normalized_name = $normalized_name,
                c.is_sanctioned = true,
                c.sanction_programs = $programs,
                c.aliases = $aliases,
                c.addresses = $addresses,
                c.id_numbers = $id_numbers,
                c.remarks = $remarks,
                c.source = 'ofac',
                c.source_url = $source_url,
                c.source_date = $source_date,
                c.raw_text = $raw_text,
                c.raw_text_hash = $raw_text_hash,
                c.confidence = $confidence,
                c.created_at = datetime()
            ON MATCH SET
                c.name = $name,
                c.is_sanctioned = true,
                c.sanction_programs = $programs,
                c.aliases = $aliases,
                c.addresses = $addresses,
                c.id_numbers = $id_numbers,
                c.remarks = $remarks,
                c.source_url = $source_url,
                c.source_date = $source_date,
                c.raw_text = $raw_text,
                c.raw_text_hash = $raw_text_hash,
                c.updated_at = datetime()
            RETURN c.id as id,
                   CASE WHEN c.created_at = c.updated_at OR c.updated_at IS NULL
                        THEN 'created' ELSE 'updated' END as action
        """

        node_id = str(uuid.uuid4())
        params = {
            "id": node_id,
            "ofac_uid": entry.uid,
            "name": entry.name,
            "normalized_name": entry.name.upper().strip(),
            "programs": entry.programs,
            "aliases": entry.aliases,
            "addresses": entry.addresses,
            "id_numbers": entry.id_numbers,
            "remarks": entry.remarks,
            "source_url": entry.citation.source_url,
            "source_date": entry.citation.publish_date.isoformat()
            if entry.citation.publish_date
            else None,
            "raw_text": entry.citation.raw_text,
            "raw_text_hash": entry.citation.raw_text_hash,
            "confidence": entry.citation.confidence,
        }

        result = await Neo4jClient.execute_query(cypher, params)

        if result:
            if result[0].get("action") == "created":
                self.stats["companies_created"] += 1
            else:
                self.stats["companies_updated"] += 1
            return result[0]["id"]

        return node_id

    async def create_indexes(self) -> None:
        """Create indexes for efficient querying."""
        indexes = [
            "CREATE INDEX ofac_person_uid IF NOT EXISTS FOR (p:Person) ON (p.ofac_uid)",
            "CREATE INDEX ofac_company_uid IF NOT EXISTS FOR (c:Company) ON (c.ofac_uid)",
            "CREATE INDEX sanctioned_person IF NOT EXISTS FOR (p:Person) ON (p.is_sanctioned)",
            "CREATE INDEX sanctioned_company IF NOT EXISTS FOR (c:Company) ON (c.is_sanctioned)",
            "CREATE INDEX person_aliases IF NOT EXISTS FOR (p:Person) ON (p.aliases)",
            "CREATE INDEX company_aliases IF NOT EXISTS FOR (c:Company) ON (c.aliases)",
        ]

        for index_query in indexes:
            try:
                await Neo4jClient.execute_write(index_query)
                logger.debug(f"Created index: {index_query[:50]}...")
            except Exception as e:
                # Index might already exist
                logger.debug(f"Index creation note: {e}")

    async def get_sdn_stats(self) -> dict:
        """Get statistics about loaded SDN data."""
        query = """
            MATCH (n:SanctionedEntity)
            RETURN
                count(CASE WHEN n:Person THEN 1 END) as sanctioned_persons,
                count(CASE WHEN n:Company THEN 1 END) as sanctioned_companies,
                count(n) as total_sanctioned,
                max(n.source_date) as last_update
        """

        results = await Neo4jClient.execute_query(query)
        if results:
            return results[0]
        return {
            "sanctioned_persons": 0,
            "sanctioned_companies": 0,
            "total_sanctioned": 0,
            "last_update": None,
        }

    async def clear_sdn_data(self) -> dict:
        """
        Remove all SDN-sourced data (for reloading).

        Use with caution!
        """
        # First remove relationships
        rel_query = """
            MATCH (n:SanctionedEntity)-[r]-()
            WHERE n.source = 'ofac'
            DELETE r
            RETURN count(r) as relationships_deleted
        """

        # Then remove nodes
        node_query = """
            MATCH (n:SanctionedEntity)
            WHERE n.source = 'ofac'
            DELETE n
            RETURN count(n) as nodes_deleted
        """

        rel_result = await Neo4jClient.execute_query(rel_query)
        node_result = await Neo4jClient.execute_query(node_query)

        return {
            "relationships_deleted": rel_result[0]["relationships_deleted"]
            if rel_result
            else 0,
            "nodes_deleted": node_result[0]["nodes_deleted"] if node_result else 0,
        }
