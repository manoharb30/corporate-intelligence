"""Graph exploration and analysis service."""

from app.models import GraphResponse, GraphNode, GraphEdge
from app.db.neo4j_client import Neo4jClient


class GraphService:
    """Service for graph exploration and visualization."""

    @staticmethod
    async def get_entity_neighborhood(
        entity_id: str,
        depth: int,
        include_filings: bool,
    ) -> GraphResponse:
        """Get graph neighborhood around an entity."""
        filing_filter = "" if include_filings else "AND NOT 'Filing' IN labels(n)"

        cypher = f"""
            MATCH (start {{id: $entity_id}})
            CALL apoc.path.subgraphAll(start, {{
                maxLevel: $depth,
                relationshipFilter: 'OWNS|OFFICER_OF|DIRECTOR_OF|REGISTERED_AT|INCORPORATED_IN',
                labelFilter: '-Filing'
            }})
            YIELD nodes, relationships
            RETURN nodes, relationships
        """

        # Fallback if APOC not available
        fallback_cypher = f"""
            MATCH (start {{id: $entity_id}})
            MATCH path = (start)-[*1..{depth}]-(n)
            WHERE NOT 'Filing' IN labels(n) OR $include_filings
            WITH collect(DISTINCT n) + [start] as nodes,
                 [r IN collect(DISTINCT relationships(path)) | r] as rels
            UNWIND nodes as node
            UNWIND rels as relList
            UNWIND relList as rel
            RETURN collect(DISTINCT node) as nodes, collect(DISTINCT rel) as relationships
        """

        try:
            records = await Neo4jClient.execute_query(
                cypher,
                {"entity_id": entity_id, "depth": depth}
            )
        except Exception:
            records = await Neo4jClient.execute_query(
                fallback_cypher,
                {"entity_id": entity_id, "include_filings": include_filings}
            )

        return GraphService._records_to_graph_response(records)

    @staticmethod
    async def get_ownership_graph(
        entity_id: str,
        direction: str,
        max_depth: int,
    ) -> GraphResponse:
        """Get ownership structure graph."""
        if direction == "up":
            cypher = f"""
                MATCH path = (owner)-[:OWNS*1..{max_depth}]->(target {{id: $entity_id}})
                WITH collect(path) as paths
                CALL apoc.convert.toTree(paths) yield value
                RETURN value
            """
            fallback = f"""
                MATCH path = (owner)-[:OWNS*1..{max_depth}]->(target {{id: $entity_id}})
                UNWIND nodes(path) as n
                UNWIND relationships(path) as r
                RETURN collect(DISTINCT n) as nodes, collect(DISTINCT r) as relationships
            """
        elif direction == "down":
            cypher = f"""
                MATCH path = (parent {{id: $entity_id}})-[:OWNS*1..{max_depth}]->(subsidiary)
                UNWIND nodes(path) as n
                UNWIND relationships(path) as r
                RETURN collect(DISTINCT n) as nodes, collect(DISTINCT r) as relationships
            """
            fallback = cypher
        else:  # both
            cypher = f"""
                MATCH path = (a)-[:OWNS*1..{max_depth}]-(b)
                WHERE a.id = $entity_id OR b.id = $entity_id
                UNWIND nodes(path) as n
                UNWIND relationships(path) as r
                RETURN collect(DISTINCT n) as nodes, collect(DISTINCT r) as relationships
            """
            fallback = cypher

        try:
            records = await Neo4jClient.execute_query(cypher, {"entity_id": entity_id})
        except Exception:
            records = await Neo4jClient.execute_query(fallback, {"entity_id": entity_id})

        return GraphService._records_to_graph_response(records)

    @staticmethod
    async def find_shortest_path(
        source_id: str,
        target_id: str,
        max_depth: int,
    ) -> GraphResponse:
        """Find shortest path between two entities."""
        cypher = f"""
            MATCH (source {{id: $source_id}}), (target {{id: $target_id}})
            MATCH path = shortestPath((source)-[*1..{max_depth}]-(target))
            RETURN nodes(path) as nodes, relationships(path) as relationships
        """

        records = await Neo4jClient.execute_query(
            cypher,
            {"source_id": source_id, "target_id": target_id}
        )

        return GraphService._records_to_graph_response(records)

    @staticmethod
    async def get_address_clusters(min_entities: int, limit: int) -> list[dict]:
        """Find addresses with multiple entities (potential shell company indicators)."""
        cypher = """
            MATCH (a:Address)<-[:REGISTERED_AT]-(e)
            WITH a, count(e) as entity_count, collect(e.name) as entity_names
            WHERE entity_count >= $min_entities
            RETURN a.id as address_id,
                   a.full_address as address,
                   entity_count,
                   entity_names[0..10] as sample_entities
            ORDER BY entity_count DESC
            LIMIT $limit
        """

        records = await Neo4jClient.execute_query(
            cypher,
            {"min_entities": min_entities, "limit": limit}
        )

        return [dict(r) for r in records]

    @staticmethod
    async def get_secrecy_jurisdiction_entities(
        min_secrecy_score: float,
        limit: int,
    ) -> list[dict]:
        """Find entities in secrecy jurisdictions."""
        cypher = """
            MATCH (c:Company)-[:INCORPORATED_IN]->(j:Jurisdiction)
            WHERE j.secrecy_score >= $min_score
            RETURN c.id as company_id,
                   c.name as company_name,
                   j.code as jurisdiction_code,
                   j.name as jurisdiction_name,
                   j.secrecy_score as secrecy_score
            ORDER BY j.secrecy_score DESC, c.name
            LIMIT $limit
        """

        records = await Neo4jClient.execute_query(
            cypher,
            {"min_score": min_secrecy_score, "limit": limit}
        )

        return [dict(r) for r in records]

    @staticmethod
    async def analyze_risk_indicators(entity_id: str) -> dict:
        """Analyze risk indicators for an entity."""
        # Check ownership chain complexity
        chain_query = """
            MATCH (e {id: $entity_id})
            OPTIONAL MATCH path = (owner)-[:OWNS*]->(e)
            WITH e, max(length(path)) as max_chain_length
            RETURN max_chain_length
        """

        # Check for circular ownership
        circular_query = """
            MATCH (e {id: $entity_id})
            MATCH path = (e)-[:OWNS*2..10]->(e)
            RETURN count(path) > 0 as has_circular_ownership
        """

        # Check secrecy jurisdiction
        jurisdiction_query = """
            MATCH (c:Company {id: $entity_id})-[:INCORPORATED_IN]->(j:Jurisdiction)
            RETURN j.is_secrecy_jurisdiction as in_secrecy_jurisdiction,
                   j.secrecy_score as secrecy_score
        """

        # Check PEP/sanctioned connections
        connections_query = """
            MATCH (e {id: $entity_id})
            OPTIONAL MATCH (e)<-[:OWNS|OFFICER_OF|DIRECTOR_OF]-(p:Person)
            WHERE p.is_pep = true OR p.is_sanctioned = true
            RETURN count(DISTINCT CASE WHEN p.is_pep THEN p END) as pep_connections,
                   count(DISTINCT CASE WHEN p.is_sanctioned THEN p END) as sanctioned_connections
        """

        # Check address clustering
        address_query = """
            MATCH (e {id: $entity_id})-[:REGISTERED_AT]->(a:Address)
            RETURN a.entity_count as shared_address_count
        """

        params = {"entity_id": entity_id}

        chain_result = await Neo4jClient.execute_query(chain_query, params)
        circular_result = await Neo4jClient.execute_query(circular_query, params)
        jurisdiction_result = await Neo4jClient.execute_query(jurisdiction_query, params)
        connections_result = await Neo4jClient.execute_query(connections_query, params)
        address_result = await Neo4jClient.execute_query(address_query, params)

        return {
            "entity_id": entity_id,
            "ownership_complexity": {
                "max_chain_length": chain_result[0]["max_chain_length"] if chain_result else 0,
                "has_circular_ownership": circular_result[0]["has_circular_ownership"] if circular_result else False,
            },
            "jurisdiction_risk": {
                "in_secrecy_jurisdiction": jurisdiction_result[0]["in_secrecy_jurisdiction"] if jurisdiction_result else False,
                "secrecy_score": jurisdiction_result[0]["secrecy_score"] if jurisdiction_result else None,
            },
            "connections": {
                "pep_connections": connections_result[0]["pep_connections"] if connections_result else 0,
                "sanctioned_connections": connections_result[0]["sanctioned_connections"] if connections_result else 0,
            },
            "address_risk": {
                "shared_address_count": address_result[0]["shared_address_count"] if address_result else 0,
            },
        }

    @staticmethod
    def _records_to_graph_response(records: list[dict]) -> GraphResponse:
        """Convert Neo4j records to GraphResponse."""
        if not records:
            return GraphResponse(nodes=[], edges=[])

        nodes = []
        edges = []

        record = records[0]
        raw_nodes = record.get("nodes", [])
        raw_rels = record.get("relationships", [])

        for node in raw_nodes:
            if node:
                labels = list(node.labels) if hasattr(node, "labels") else ["Unknown"]
                nodes.append(GraphNode(
                    id=node.get("id", str(node.id)),
                    label=node.get("name", node.get("full_address", "Unknown")),
                    type=labels[0] if labels else "Unknown",
                    properties=dict(node),
                ))

        for rel in raw_rels:
            if rel:
                edges.append(GraphEdge(
                    id=str(rel.id) if hasattr(rel, "id") else str(id(rel)),
                    source=str(rel.start_node.get("id", rel.start_node.id)),
                    target=str(rel.end_node.get("id", rel.end_node.id)),
                    type=rel.type,
                    properties=dict(rel),
                ))

        return GraphResponse(nodes=nodes, edges=edges)
