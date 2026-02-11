"""Service for sanctions checking with evidence chains."""

from datetime import date
from typing import Optional

from pydantic import BaseModel, Field

from app.db.neo4j_client import Neo4jClient
from app.models.evidence_models import EvidenceChain, EvidenceStep, ClaimType


class SanctionConnection(BaseModel):
    """A connection path to a sanctioned entity."""

    sanctioned_entity: str = Field(..., description="Name of sanctioned entity")
    sanctioned_entity_id: str = Field(..., description="ID of sanctioned entity")
    ofac_uid: str = Field(..., description="OFAC unique identifier")
    programs: list[str] = Field(default_factory=list, description="Sanctions programs")
    hops: int = Field(..., description="Number of hops to sanctioned entity")
    path: str = Field(..., description="Human-readable path")
    path_entities: list[str] = Field(
        default_factory=list, description="Entity names in path"
    )
    evidence_chain: Optional[EvidenceChain] = None


class SanctionsExposure(BaseModel):
    """Full sanctions exposure report for an entity."""

    entity_id: str
    entity_name: str
    direct_sanctions: bool = Field(
        default=False, description="Is entity directly sanctioned?"
    )
    direct_sanction_info: Optional[dict] = None
    sanctioned_owners: list[SanctionConnection] = Field(default_factory=list)
    sanctioned_directors: list[SanctionConnection] = Field(default_factory=list)
    indirect_connections: list[SanctionConnection] = Field(default_factory=list)
    risk_level: str = Field(default="NONE", description="NONE, LOW, MEDIUM, HIGH")
    checked_at: date = Field(default_factory=date.today)


class SanctionsService:
    """Service for checking sanctions exposure with evidence."""

    @staticmethod
    async def check_entity_sanctions(entity_id: str) -> dict:
        """
        Check if an entity is directly sanctioned.

        Returns sanctioned status and details if found.
        """
        query = """
            MATCH (e {id: $entity_id})
            OPTIONAL MATCH (e)-[r:SANCTIONED_AS]->(s:SanctionedEntity)
            RETURN
                e.name as name,
                e.is_sanctioned as is_directly_sanctioned,
                e.sanction_programs as direct_programs,
                e.ofac_uid as direct_ofac_uid,
                s.name as linked_sanctioned_name,
                s.ofac_uid as linked_ofac_uid,
                s.sanction_programs as linked_programs,
                r.match_method as match_method,
                r.confidence as match_confidence
        """

        results = await Neo4jClient.execute_query(query, {"entity_id": entity_id})

        if not results:
            return {"entity_id": entity_id, "found": False, "is_sanctioned": False}

        r = results[0]

        # Check if directly sanctioned (OFAC entity)
        if r.get("is_directly_sanctioned"):
            return {
                "entity_id": entity_id,
                "found": True,
                "is_sanctioned": True,
                "sanction_type": "direct",
                "name": r["name"],
                "ofac_uid": r["direct_ofac_uid"],
                "programs": r["direct_programs"] or [],
                "source": "OFAC SDN List",
            }

        # Check if linked to sanctioned entity
        if r.get("linked_sanctioned_name"):
            return {
                "entity_id": entity_id,
                "found": True,
                "is_sanctioned": True,
                "sanction_type": "linked",
                "name": r["name"],
                "linked_to": r["linked_sanctioned_name"],
                "ofac_uid": r["linked_ofac_uid"],
                "programs": r["linked_programs"] or [],
                "match_method": r["match_method"],
                "match_confidence": r["match_confidence"],
                "source": "OFAC SDN List",
            }

        return {
            "entity_id": entity_id,
            "found": True,
            "is_sanctioned": False,
            "name": r["name"],
        }

    @staticmethod
    async def check_connection_to_sanctioned(
        entity_id: str,
        max_hops: int = 3,
    ) -> list[SanctionConnection]:
        """
        Find paths from entity to any sanctioned person/company.

        Returns list of connections with path details.
        """
        query = """
            MATCH (start {id: $entity_id})
            MATCH path = shortestPath((start)-[*1..$max_hops]-(sanctioned:SanctionedEntity))
            WHERE sanctioned.is_sanctioned = true
              AND start <> sanctioned
            WITH path, sanctioned, length(path) as hops,
                 [n in nodes(path) | n.name] as path_names,
                 [r in relationships(path) | type(r)] as rel_types
            RETURN
                sanctioned.name as sanctioned_name,
                sanctioned.id as sanctioned_id,
                sanctioned.ofac_uid as ofac_uid,
                sanctioned.sanction_programs as programs,
                hops,
                path_names,
                rel_types
            ORDER BY hops
            LIMIT 10
        """

        results = await Neo4jClient.execute_query(
            query, {"entity_id": entity_id, "max_hops": max_hops}
        )

        connections = []
        for r in results:
            # Build human-readable path
            path_str = SanctionsService._build_path_string(
                r["path_names"], r["rel_types"]
            )

            connections.append(
                SanctionConnection(
                    sanctioned_entity=r["sanctioned_name"],
                    sanctioned_entity_id=r["sanctioned_id"],
                    ofac_uid=r["ofac_uid"] or "",
                    programs=r["programs"] or [],
                    hops=r["hops"],
                    path=path_str,
                    path_entities=r["path_names"],
                )
            )

        return connections

    @staticmethod
    async def get_sanctions_exposure(
        entity_id: str,
        max_hops: int = 3,
    ) -> SanctionsExposure:
        """
        Get full sanctions exposure report for an entity.

        Checks:
        - Direct sanctions (entity itself is sanctioned)
        - Ownership by sanctioned entities
        - Sanctioned directors/officers
        - Indirect connections within N hops
        """
        # Get entity name
        name_query = "MATCH (e {id: $entity_id}) RETURN e.name as name"
        name_result = await Neo4jClient.execute_query(
            name_query, {"entity_id": entity_id}
        )
        entity_name = name_result[0]["name"] if name_result else "Unknown"

        exposure = SanctionsExposure(
            entity_id=entity_id,
            entity_name=entity_name,
        )

        # 1. Check direct sanctions
        direct_check = await SanctionsService.check_entity_sanctions(entity_id)
        if direct_check.get("is_sanctioned"):
            exposure.direct_sanctions = True
            exposure.direct_sanction_info = direct_check
            exposure.risk_level = "HIGH"
            return exposure

        # 2. Check sanctioned owners
        owner_query = """
            MATCH (c {id: $entity_id})<-[:OWNS]-(owner)
            WHERE owner.is_sanctioned = true OR (owner)-[:SANCTIONED_AS]->()
            OPTIONAL MATCH (owner)-[:SANCTIONED_AS]->(s:SanctionedEntity)
            RETURN
                COALESCE(s.name, owner.name) as sanctioned_name,
                COALESCE(s.id, owner.id) as sanctioned_id,
                COALESCE(s.ofac_uid, owner.ofac_uid) as ofac_uid,
                COALESCE(s.sanction_programs, owner.sanction_programs) as programs,
                owner.name as owner_name
        """
        owner_results = await Neo4jClient.execute_query(
            owner_query, {"entity_id": entity_id}
        )

        for r in owner_results:
            exposure.sanctioned_owners.append(
                SanctionConnection(
                    sanctioned_entity=r["sanctioned_name"],
                    sanctioned_entity_id=r["sanctioned_id"],
                    ofac_uid=r["ofac_uid"] or "",
                    programs=r["programs"] or [],
                    hops=1,
                    path=f"{entity_name} <-[OWNS]- {r['owner_name']}",
                    path_entities=[entity_name, r["owner_name"]],
                )
            )

        # 3. Check sanctioned directors/officers
        director_query = """
            MATCH (c {id: $entity_id})<-[:DIRECTOR_OF|OFFICER_OF]-(person)
            WHERE person.is_sanctioned = true OR (person)-[:SANCTIONED_AS]->()
            OPTIONAL MATCH (person)-[:SANCTIONED_AS]->(s:SanctionedEntity)
            RETURN
                COALESCE(s.name, person.name) as sanctioned_name,
                COALESCE(s.id, person.id) as sanctioned_id,
                COALESCE(s.ofac_uid, person.ofac_uid) as ofac_uid,
                COALESCE(s.sanction_programs, person.sanction_programs) as programs,
                person.name as person_name
        """
        director_results = await Neo4jClient.execute_query(
            director_query, {"entity_id": entity_id}
        )

        for r in director_results:
            exposure.sanctioned_directors.append(
                SanctionConnection(
                    sanctioned_entity=r["sanctioned_name"],
                    sanctioned_entity_id=r["sanctioned_id"],
                    ofac_uid=r["ofac_uid"] or "",
                    programs=r["programs"] or [],
                    hops=1,
                    path=f"{r['person_name']} -[DIRECTOR/OFFICER]-> {entity_name}",
                    path_entities=[r["person_name"], entity_name],
                )
            )

        # 4. Check indirect connections
        if max_hops > 1:
            indirect = await SanctionsService.check_connection_to_sanctioned(
                entity_id, max_hops
            )
            # Filter out direct owners/directors already captured
            direct_ids = {c.sanctioned_entity_id for c in exposure.sanctioned_owners}
            direct_ids.update(c.sanctioned_entity_id for c in exposure.sanctioned_directors)

            for conn in indirect:
                if conn.sanctioned_entity_id not in direct_ids and conn.hops > 1:
                    exposure.indirect_connections.append(conn)

        # Calculate risk level
        exposure.risk_level = SanctionsService._calculate_risk_level(exposure)

        return exposure

    @staticmethod
    async def get_sdn_stats() -> dict:
        """Get statistics about loaded SDN data."""
        query = """
            MATCH (n:SanctionedEntity)
            WHERE n.source = 'ofac'
            RETURN
                count(CASE WHEN n:Person THEN 1 END) as sanctioned_persons,
                count(CASE WHEN n:Company THEN 1 END) as sanctioned_companies,
                count(n) as total_sanctioned,
                max(n.source_date) as last_update
        """

        results = await Neo4jClient.execute_query(query)
        if results:
            r = results[0]
            return {
                "sanctioned_persons": r["sanctioned_persons"],
                "sanctioned_companies": r["sanctioned_companies"],
                "total_sanctioned": r["total_sanctioned"],
                "last_update": r["last_update"],
            }

        return {
            "sanctioned_persons": 0,
            "sanctioned_companies": 0,
            "total_sanctioned": 0,
            "last_update": None,
        }

    @staticmethod
    async def search_sanctioned_entities(
        query_str: str,
        entity_type: Optional[str] = None,
        limit: int = 20,
    ) -> list[dict]:
        """
        Search sanctioned entities by name or alias.

        Args:
            query_str: Search string
            entity_type: 'person' or 'company' or None for both
            limit: Maximum results
        """
        type_filter = ""
        if entity_type == "person":
            type_filter = "AND n:Person"
        elif entity_type == "company":
            type_filter = "AND n:Company"

        query = f"""
            MATCH (n:SanctionedEntity)
            WHERE n.source = 'ofac' {type_filter}
              AND (
                toLower(n.name) CONTAINS toLower($query)
                OR any(alias IN n.aliases WHERE toLower(alias) CONTAINS toLower($query))
              )
            RETURN
                n.id as id,
                n.name as name,
                n.ofac_uid as ofac_uid,
                n.sanction_programs as programs,
                n.aliases as aliases,
                n.nationality as nationality,
                labels(n) as labels
            LIMIT $limit
        """

        results = await Neo4jClient.execute_query(
            query, {"query": query_str, "limit": limit}
        )

        return [
            {
                "id": r["id"],
                "name": r["name"],
                "ofac_uid": r["ofac_uid"],
                "programs": r["programs"] or [],
                "aliases": (r["aliases"] or [])[:5],  # Limit aliases shown
                "nationality": r["nationality"],
                "entity_type": "Person" if "Person" in r["labels"] else "Company",
            }
            for r in results
        ]

    @staticmethod
    def _build_path_string(names: list[str], rel_types: list[str]) -> str:
        """Build human-readable path string."""
        if not names:
            return ""

        parts = [names[0]]
        for i, rel in enumerate(rel_types):
            if i + 1 < len(names):
                parts.append(f"-[{rel}]->")
                parts.append(names[i + 1])

        return " ".join(parts)

    @staticmethod
    def _calculate_risk_level(exposure: SanctionsExposure) -> str:
        """Calculate overall risk level based on exposure."""
        if exposure.direct_sanctions:
            return "HIGH"

        if exposure.sanctioned_owners or exposure.sanctioned_directors:
            return "HIGH"

        if exposure.indirect_connections:
            # Check how close the connections are
            min_hops = min(c.hops for c in exposure.indirect_connections)
            if min_hops <= 2:
                return "MEDIUM"
            return "LOW"

        return "NONE"
