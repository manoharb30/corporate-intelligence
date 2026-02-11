"""Service for finding connections between entities with evidence chains."""

from typing import Optional
from dataclasses import dataclass, field

from app.db.neo4j_client import Neo4jClient
from app.models.evidence_models import (
    ClaimType,
    ConnectionClaim,
    EvidenceStep,
    SharedConnection,
    SharedConnectionsResult,
)
from app.services.evidence_service import EvidenceService


@dataclass
class MultiLayerConnection:
    """Result of multi-layer connection analysis between two companies."""

    company_a: str
    company_b: str
    board_interlocks: list[dict] = field(default_factory=list)
    shared_subsidiaries: list[dict] = field(default_factory=list)
    executive_overlaps: list[dict] = field(default_factory=list)
    ownership_paths: list[dict] = field(default_factory=list)
    total_connections: int = 0
    connection_strength: str = "none"  # none, weak, moderate, strong

    def to_dict(self) -> dict:
        return {
            "company_a": self.company_a,
            "company_b": self.company_b,
            "board_interlocks": self.board_interlocks,
            "shared_subsidiaries": self.shared_subsidiaries,
            "executive_overlaps": self.executive_overlaps,
            "ownership_paths": self.ownership_paths,
            "total_connections": self.total_connections,
            "connection_strength": self.connection_strength,
            "summary": self._build_summary(),
        }

    def _build_summary(self) -> str:
        parts = []
        if self.board_interlocks:
            parts.append(f"{len(self.board_interlocks)} board interlock(s)")
        if self.shared_subsidiaries:
            parts.append(f"{len(self.shared_subsidiaries)} shared subsidiary(ies)")
        if self.executive_overlaps:
            parts.append(f"{len(self.executive_overlaps)} executive overlap(s)")
        if self.ownership_paths:
            parts.append(f"{len(self.ownership_paths)} ownership path(s)")

        if not parts:
            return f"No connections found between {self.company_a} and {self.company_b}"

        return f"{self.company_a} and {self.company_b} are connected through: {', '.join(parts)}"


class ConnectionService:
    """Service for finding and documenting connections between entities."""

    @staticmethod
    async def find_connection_with_evidence(
        entity_a_id: str,
        entity_b_id: str,
        max_hops: int = 4,
    ) -> Optional[ConnectionClaim]:
        """
        Find shortest path between two entities and return with full evidence chain.

        Returns None if no connection found within max_hops.
        """
        # Query to find shortest path with relationship details
        query = f"""
            MATCH (a {{id: $entity_a_id}}), (b {{id: $entity_b_id}})
            MATCH path = shortestPath((a)-[*1..{max_hops}]-(b))
            WITH path, nodes(path) as path_nodes, relationships(path) as rels
            UNWIND range(0, size(rels)-1) as i
            WITH path_nodes, rels, i,
                 path_nodes[i] as from_node,
                 path_nodes[i+1] as to_node,
                 rels[i] as rel
            OPTIONAL MATCH (f:Filing {{id: rel.source_filing}})
            RETURN
                from_node.id as from_id,
                from_node.name as from_name,
                labels(from_node)[0] as from_type,
                to_node.id as to_id,
                to_node.name as to_name,
                labels(to_node)[0] as to_type,
                type(rel) as rel_type,
                rel.percentage as percentage,
                rel.title as title,
                rel.raw_text as raw_text,
                rel.source_section as source_section,
                rel.confidence as confidence,
                rel.extraction_method as extraction_method,
                f.accession_number as filing_accession,
                f.form_type as filing_type,
                f.filing_date as filing_date,
                f.filing_url as filing_url
            ORDER BY i
        """

        results = await Neo4jClient.execute_query(
            query,
            {"entity_a_id": entity_a_id, "entity_b_id": entity_b_id}
        )

        if not results:
            return None

        # Build path segments for evidence chain
        path_segments = []
        rel_types = []

        for record in results:
            rel_type = record["rel_type"]
            rel_types.append(rel_type)

            # Create human-readable fact
            fact = EvidenceService.relationship_to_fact(
                from_name=record["from_name"],
                to_name=record["to_name"],
                rel_type=rel_type,
                rel_properties={
                    "percentage": record["percentage"],
                    "title": record["title"],
                },
            )

            path_segments.append({
                "from_id": record["from_id"],
                "from_name": record["from_name"],
                "to_id": record["to_id"],
                "to_name": record["to_name"],
                "rel_type": rel_type,
                "fact": fact,
                "source_type": "SEC_EDGAR",
                "filing_url": record["filing_url"],
                "filing_type": record["filing_type"],
                "filing_accession": record["filing_accession"],
                "filing_date": record["filing_date"],
                "source_section": record["source_section"],
                "raw_text": record["raw_text"] or "",
                "confidence": record["confidence"] or 0.9,
                "extraction_method": record["extraction_method"],
            })

        # Get entity names from first and last segments
        entity_a_name = path_segments[0]["from_name"]
        entity_b_name = path_segments[-1]["to_name"]

        # Build evidence chain
        evidence_chain = EvidenceService.build_connection_evidence(
            entity_a_name=entity_a_name,
            entity_b_name=entity_b_name,
            path_segments=path_segments,
        )

        return ConnectionClaim(
            entity_a_id=entity_a_id,
            entity_a_name=entity_a_name,
            entity_b_id=entity_b_id,
            entity_b_name=entity_b_name,
            connection_type=EvidenceService.determine_connection_type(rel_types),
            claim=evidence_chain.claim,
            claim_type=ClaimType.INFERRED,
            evidence_chain=evidence_chain,
            path_length=len(path_segments),
        )

    @staticmethod
    async def find_connection_by_name(
        entity_a_name: str,
        entity_b_name: str,
        max_hops: int = 4,
    ) -> Optional[ConnectionClaim]:
        """
        Find connection between two entities by name.

        First resolves names to IDs, then finds path.
        """
        # Find entity IDs by name
        query = """
            MATCH (e)
            WHERE e.name = $name OR e.normalized_name = $name
            RETURN e.id as id, e.name as name
            LIMIT 1
        """

        result_a = await Neo4jClient.execute_query(query, {"name": entity_a_name})
        result_b = await Neo4jClient.execute_query(query, {"name": entity_b_name})

        if not result_a or not result_b:
            return None

        return await ConnectionService.find_connection_with_evidence(
            entity_a_id=result_a[0]["id"],
            entity_b_id=result_b[0]["id"],
            max_hops=max_hops,
        )

    @staticmethod
    async def find_shared_connections(
        entity_a_id: str,
        entity_b_id: str,
        limit: int = 20,
    ) -> SharedConnectionsResult:
        """
        Find entities that both A and B are connected to (shared owners, directors, etc.)
        """
        query = """
            MATCH (a {id: $entity_a_id}), (b {id: $entity_b_id})
            MATCH (a)-[r1]-(shared)-[r2]-(b)
            WHERE a <> b AND a <> shared AND b <> shared
                  AND id(a) < id(b)  // Avoid duplicates
            OPTIONAL MATCH (f1:Filing {id: r1.source_filing})
            OPTIONAL MATCH (f2:Filing {id: r2.source_filing})
            RETURN DISTINCT
                shared.id as shared_id,
                shared.name as shared_name,
                labels(shared)[0] as shared_type,
                a.name as entity_a_name,
                b.name as entity_b_name,
                type(r1) as rel_type_a,
                r1.raw_text as raw_text_a,
                r1.source_section as source_section_a,
                r1.confidence as confidence_a,
                r1.extraction_method as extraction_method_a,
                f1.accession_number as filing_accession_a,
                f1.form_type as filing_type_a,
                f1.filing_url as filing_url_a,
                type(r2) as rel_type_b,
                r2.raw_text as raw_text_b,
                r2.source_section as source_section_b,
                r2.confidence as confidence_b,
                r2.extraction_method as extraction_method_b,
                f2.accession_number as filing_accession_b,
                f2.form_type as filing_type_b,
                f2.filing_url as filing_url_b
            LIMIT $limit
        """

        results = await Neo4jClient.execute_query(
            query,
            {
                "entity_a_id": entity_a_id,
                "entity_b_id": entity_b_id,
                "limit": limit,
            }
        )

        shared_connections = []
        entity_a_name = ""
        entity_b_name = ""

        for record in results:
            entity_a_name = record["entity_a_name"]
            entity_b_name = record["entity_b_name"]

            # Build evidence steps for each side of the connection
            evidence_a = EvidenceStep(
                step=1,
                fact=f"{entity_a_name} connected to {record['shared_name']} via {record['rel_type_a']}",
                claim_type=ClaimType.DIRECT,
                source_type="SEC_EDGAR",
                filing_url=record["filing_url_a"],
                filing_type=record["filing_type_a"],
                filing_accession=record["filing_accession_a"],
                source_section=record["source_section_a"],
                raw_text=(record["raw_text_a"] or "")[:1000],
                raw_text_hash=EvidenceService.hash_text(record["raw_text_a"] or ""),
                confidence=record["confidence_a"] or 0.9,
                extraction_method=record["extraction_method_a"],
            )

            evidence_b = EvidenceStep(
                step=2,
                fact=f"{entity_b_name} connected to {record['shared_name']} via {record['rel_type_b']}",
                claim_type=ClaimType.DIRECT,
                source_type="SEC_EDGAR",
                filing_url=record["filing_url_b"],
                filing_type=record["filing_type_b"],
                filing_accession=record["filing_accession_b"],
                source_section=record["source_section_b"],
                raw_text=(record["raw_text_b"] or "")[:1000],
                raw_text_hash=EvidenceService.hash_text(record["raw_text_b"] or ""),
                confidence=record["confidence_b"] or 0.9,
                extraction_method=record["extraction_method_b"],
            )

            shared_connections.append(SharedConnection(
                shared_entity_id=record["shared_id"],
                shared_entity_name=record["shared_name"],
                shared_entity_type=record["shared_type"],
                connection_to_a=record["rel_type_a"],
                connection_to_b=record["rel_type_b"],
                evidence_a=evidence_a,
                evidence_b=evidence_b,
            ))

        return SharedConnectionsResult(
            entity_a_id=entity_a_id,
            entity_a_name=entity_a_name or entity_a_id,
            entity_b_id=entity_b_id,
            entity_b_name=entity_b_name or entity_b_id,
            shared_connections=shared_connections,
            total_count=len(shared_connections),
        )

    @staticmethod
    async def get_entity_connections_with_evidence(
        entity_id: str,
        limit: int = 50,
    ) -> list[dict]:
        """
        Get all direct connections for an entity with citations.
        """
        query = """
            MATCH (e {id: $entity_id})-[r]-(connected)
            WHERE NOT 'Filing' IN labels(connected)
            OPTIONAL MATCH (f:Filing {id: r.source_filing})
            RETURN
                connected.id as connected_id,
                connected.name as connected_name,
                labels(connected)[0] as entity_type,
                type(r) as relationship,
                r.percentage as percentage,
                r.title as title,
                r.raw_text as raw_text,
                r.source_section as source_section,
                r.confidence as confidence,
                r.extraction_method as extraction_method,
                f.accession_number as filing_accession,
                f.form_type as filing_type,
                f.filing_date as filing_date,
                f.filing_url as filing_url
            ORDER BY type(r), connected.name
            LIMIT $limit
        """

        results = await Neo4jClient.execute_query(
            query,
            {"entity_id": entity_id, "limit": limit}
        )

        connections = []
        for record in results:
            connections.append({
                "connected_entity": {
                    "id": record["connected_id"],
                    "name": record["connected_name"],
                    "type": record["entity_type"],
                },
                "relationship": record["relationship"],
                "details": {
                    "percentage": record["percentage"],
                    "title": record["title"],
                },
                "citation": {
                    "filing_url": record["filing_url"],
                    "filing_type": record["filing_type"],
                    "filing_accession": record["filing_accession"],
                    "filing_date": str(record["filing_date"]) if record["filing_date"] else None,
                    "source_section": record["source_section"],
                    "raw_text": record["raw_text"],
                    "confidence": record["confidence"],
                    "extraction_method": record["extraction_method"],
                },
            })

        return connections

    @staticmethod
    async def find_multi_layer_connections(
        company_a_name: str,
        company_b_name: str,
    ) -> MultiLayerConnection:
        """
        Find all multi-layer connections between two companies.

        Checks for:
        1. Board interlocks (shared directors)
        2. Shared subsidiaries
        3. Executive overlaps (people who work at both)
        4. Ownership paths (direct or indirect ownership chains)
        """
        result = MultiLayerConnection(
            company_a=company_a_name,
            company_b=company_b_name,
        )

        # 1. Board interlocks - people who are directors at both companies
        board_query = """
            MATCH (c1:Company {name: $company_a})<-[:DIRECTOR_OF]-(p:Person)-[:DIRECTOR_OF]->(c2:Company {name: $company_b})
            RETURN p.name as person, p.id as person_id
        """
        board_results = await Neo4jClient.execute_query(
            board_query,
            {"company_a": company_a_name, "company_b": company_b_name}
        )
        for r in board_results:
            result.board_interlocks.append({
                "person": r["person"],
                "person_id": r["person_id"],
                "connection_type": "director_at_both",
            })

        # 2. Executive overlaps - people with any role at both companies
        exec_query = """
            MATCH (c1:Company {name: $company_a})<-[r1:OFFICER_OF|DIRECTOR_OF]-(p:Person)-[r2:OFFICER_OF|DIRECTOR_OF]->(c2:Company {name: $company_b})
            RETURN DISTINCT p.name as person, p.id as person_id,
                   collect(DISTINCT type(r1)) as roles_at_a,
                   collect(DISTINCT type(r2)) as roles_at_b
        """
        exec_results = await Neo4jClient.execute_query(
            exec_query,
            {"company_a": company_a_name, "company_b": company_b_name}
        )
        for r in exec_results:
            result.executive_overlaps.append({
                "person": r["person"],
                "person_id": r["person_id"],
                "roles_at_company_a": r["roles_at_a"],
                "roles_at_company_b": r["roles_at_b"],
            })

        # 3. Ownership paths - direct or indirect ownership chains
        ownership_query = """
            MATCH path = shortestPath((c1:Company {name: $company_a})-[:OWNS*1..4]-(c2:Company {name: $company_b}))
            RETURN [n in nodes(path) | n.name] as chain,
                   length(path) as path_length
            LIMIT 5
        """
        ownership_results = await Neo4jClient.execute_query(
            ownership_query,
            {"company_a": company_a_name, "company_b": company_b_name}
        )
        for r in ownership_results:
            result.ownership_paths.append({
                "chain": r["chain"],
                "path_length": r["path_length"],
            })

        # 4. Shared subsidiaries - companies owned by both
        shared_sub_query = """
            MATCH (c1:Company {name: $company_a})-[:OWNS]->(sub:Company)<-[:OWNS]-(c2:Company {name: $company_b})
            WHERE c1 <> c2
            RETURN sub.name as subsidiary, sub.id as subsidiary_id
            LIMIT 20
        """
        shared_sub_results = await Neo4jClient.execute_query(
            shared_sub_query,
            {"company_a": company_a_name, "company_b": company_b_name}
        )
        for r in shared_sub_results:
            result.shared_subsidiaries.append({
                "subsidiary": r["subsidiary"],
                "subsidiary_id": r["subsidiary_id"],
            })

        # Calculate total connections and strength
        result.total_connections = (
            len(result.board_interlocks) +
            len(result.shared_subsidiaries) +
            len(result.executive_overlaps) +
            len(result.ownership_paths)
        )

        if result.total_connections == 0:
            result.connection_strength = "none"
        elif result.total_connections <= 2:
            result.connection_strength = "weak"
        elif result.total_connections <= 5:
            result.connection_strength = "moderate"
        else:
            result.connection_strength = "strong"

        return result
