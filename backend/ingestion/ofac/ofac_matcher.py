"""OFAC matcher - match SDN entries against existing graph entities."""

import logging
from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field

from app.db.neo4j_client import Neo4jClient

logger = logging.getLogger(__name__)


class MatchMethod(str, Enum):
    """How the match was determined."""

    EXACT_NAME = "exact_name"
    ALIAS_MATCH = "alias_match"
    FUZZY_NAME = "fuzzy_name"


class SanctionMatch(BaseModel):
    """A match between an existing entity and an SDN entry."""

    existing_entity_id: str = Field(..., description="ID of existing entity")
    existing_entity_name: str = Field(..., description="Name of existing entity")
    existing_entity_type: str = Field(..., description="'Person' or 'Company'")
    sanctioned_entity_id: str = Field(..., description="ID of SDN entity")
    sanctioned_entity_name: str = Field(..., description="Name from SDN list")
    ofac_uid: str = Field(..., description="OFAC unique identifier")
    match_method: MatchMethod = Field(..., description="How match was determined")
    matched_on: str = Field(..., description="The string that matched")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Match confidence")
    sanction_programs: list[str] = Field(
        default_factory=list, description="Sanctions programs"
    )
    requires_review: bool = Field(
        default=False, description="Whether human review is needed"
    )


class OFACMatcher:
    """Match OFAC SDN entries against existing entities in the graph."""

    # Confidence thresholds
    EXACT_MATCH_CONFIDENCE = 1.0
    ALIAS_MATCH_CONFIDENCE = 0.95
    FUZZY_MATCH_THRESHOLD = 0.9  # Minimum similarity for fuzzy match
    FUZZY_MATCH_CONFIDENCE = 0.8

    def __init__(self):
        self.stats = {
            "exact_matches": 0,
            "alias_matches": 0,
            "fuzzy_matches": 0,
            "total_matches": 0,
            "relationships_created": 0,
        }

    async def find_matches(
        self,
        auto_link: bool = False,
        fuzzy_matching: bool = True,
    ) -> list[SanctionMatch]:
        """
        Find existing entities that match OFAC SDN entries.

        Args:
            auto_link: If True, automatically create SANCTIONED_AS relationships
                       for high-confidence matches (exact and alias only)
            fuzzy_matching: If True, also find fuzzy name matches (requires review)

        Returns:
            List of SanctionMatch objects
        """
        matches = []

        # 1. Exact name matches
        exact_matches = await self._find_exact_matches()
        matches.extend(exact_matches)
        self.stats["exact_matches"] = len(exact_matches)

        # 2. Alias matches
        alias_matches = await self._find_alias_matches()
        matches.extend(alias_matches)
        self.stats["alias_matches"] = len(alias_matches)

        # 3. Fuzzy matches (optional)
        if fuzzy_matching:
            fuzzy_matches = await self._find_fuzzy_matches()
            matches.extend(fuzzy_matches)
            self.stats["fuzzy_matches"] = len(fuzzy_matches)

        self.stats["total_matches"] = len(matches)
        logger.info(f"Found {len(matches)} potential matches: {self.stats}")

        # Auto-link high confidence matches if requested
        if auto_link:
            for match in matches:
                if match.confidence >= self.ALIAS_MATCH_CONFIDENCE and not match.requires_review:
                    await self._create_sanction_link(match)

        return matches

    async def _find_exact_matches(self) -> list[SanctionMatch]:
        """Find entities with exact name match to SDN entries."""
        # Match persons
        person_query = """
            MATCH (existing:Person)
            WHERE existing.source <> 'ofac' AND NOT existing.is_sanctioned
            MATCH (sanctioned:Person:SanctionedEntity)
            WHERE sanctioned.source = 'ofac'
              AND existing.normalized_name = sanctioned.normalized_name
            RETURN
                existing.id as existing_id,
                existing.name as existing_name,
                'Person' as entity_type,
                sanctioned.id as sanctioned_id,
                sanctioned.name as sanctioned_name,
                sanctioned.ofac_uid as ofac_uid,
                sanctioned.sanction_programs as programs
        """

        # Match companies
        company_query = """
            MATCH (existing:Company)
            WHERE existing.source <> 'ofac' AND NOT existing.is_sanctioned
            MATCH (sanctioned:Company:SanctionedEntity)
            WHERE sanctioned.source = 'ofac'
              AND existing.normalized_name = sanctioned.normalized_name
            RETURN
                existing.id as existing_id,
                existing.name as existing_name,
                'Company' as entity_type,
                sanctioned.id as sanctioned_id,
                sanctioned.name as sanctioned_name,
                sanctioned.ofac_uid as ofac_uid,
                sanctioned.sanction_programs as programs
        """

        matches = []

        for query in [person_query, company_query]:
            results = await Neo4jClient.execute_query(query)
            for r in results:
                matches.append(
                    SanctionMatch(
                        existing_entity_id=r["existing_id"],
                        existing_entity_name=r["existing_name"],
                        existing_entity_type=r["entity_type"],
                        sanctioned_entity_id=r["sanctioned_id"],
                        sanctioned_entity_name=r["sanctioned_name"],
                        ofac_uid=r["ofac_uid"],
                        match_method=MatchMethod.EXACT_NAME,
                        matched_on=r["existing_name"],
                        confidence=self.EXACT_MATCH_CONFIDENCE,
                        sanction_programs=r["programs"] or [],
                        requires_review=False,
                    )
                )

        return matches

    async def _find_alias_matches(self) -> list[SanctionMatch]:
        """Find entities matching SDN aliases."""
        # Match persons by alias
        person_query = """
            MATCH (existing:Person)
            WHERE existing.source <> 'ofac' AND NOT existing.is_sanctioned
            MATCH (sanctioned:Person:SanctionedEntity)
            WHERE sanctioned.source = 'ofac'
              AND sanctioned.aliases IS NOT NULL
              AND size(sanctioned.aliases) > 0
            WITH existing, sanctioned,
                 [alias IN sanctioned.aliases WHERE toUpper(trim(alias)) = existing.normalized_name | alias] as matched_aliases
            WHERE size(matched_aliases) > 0
            RETURN
                existing.id as existing_id,
                existing.name as existing_name,
                'Person' as entity_type,
                sanctioned.id as sanctioned_id,
                sanctioned.name as sanctioned_name,
                sanctioned.ofac_uid as ofac_uid,
                sanctioned.sanction_programs as programs,
                matched_aliases[0] as matched_alias
        """

        # Match companies by alias
        company_query = """
            MATCH (existing:Company)
            WHERE existing.source <> 'ofac' AND NOT existing.is_sanctioned
            MATCH (sanctioned:Company:SanctionedEntity)
            WHERE sanctioned.source = 'ofac'
              AND sanctioned.aliases IS NOT NULL
              AND size(sanctioned.aliases) > 0
            WITH existing, sanctioned,
                 [alias IN sanctioned.aliases WHERE toUpper(trim(alias)) = existing.normalized_name | alias] as matched_aliases
            WHERE size(matched_aliases) > 0
            RETURN
                existing.id as existing_id,
                existing.name as existing_name,
                'Company' as entity_type,
                sanctioned.id as sanctioned_id,
                sanctioned.name as sanctioned_name,
                sanctioned.ofac_uid as ofac_uid,
                sanctioned.sanction_programs as programs,
                matched_aliases[0] as matched_alias
        """

        matches = []

        for query in [person_query, company_query]:
            results = await Neo4jClient.execute_query(query)
            for r in results:
                matches.append(
                    SanctionMatch(
                        existing_entity_id=r["existing_id"],
                        existing_entity_name=r["existing_name"],
                        existing_entity_type=r["entity_type"],
                        sanctioned_entity_id=r["sanctioned_id"],
                        sanctioned_entity_name=r["sanctioned_name"],
                        ofac_uid=r["ofac_uid"],
                        match_method=MatchMethod.ALIAS_MATCH,
                        matched_on=r["matched_alias"],
                        confidence=self.ALIAS_MATCH_CONFIDENCE,
                        sanction_programs=r["programs"] or [],
                        requires_review=False,
                    )
                )

        return matches

    async def _find_fuzzy_matches(self) -> list[SanctionMatch]:
        """
        Find entities with fuzzy name match to SDN entries.

        Uses Neo4j's apoc.text.jaroWinklerDistance for similarity.
        These matches require human review.
        """
        # Check if APOC is available
        apoc_check = """
            RETURN apoc.version() as version
        """
        try:
            await Neo4jClient.execute_query(apoc_check)
        except Exception:
            logger.warning("APOC not available, skipping fuzzy matching")
            return []

        # Fuzzy match persons
        person_query = """
            MATCH (existing:Person)
            WHERE existing.source <> 'ofac' AND NOT existing.is_sanctioned
            MATCH (sanctioned:Person:SanctionedEntity)
            WHERE sanctioned.source = 'ofac'
              AND existing.normalized_name <> sanctioned.normalized_name
            WITH existing, sanctioned,
                 apoc.text.jaroWinklerDistance(existing.normalized_name, sanctioned.normalized_name) as similarity
            WHERE similarity >= $threshold
            RETURN
                existing.id as existing_id,
                existing.name as existing_name,
                'Person' as entity_type,
                sanctioned.id as sanctioned_id,
                sanctioned.name as sanctioned_name,
                sanctioned.ofac_uid as ofac_uid,
                sanctioned.sanction_programs as programs,
                similarity
            ORDER BY similarity DESC
            LIMIT 100
        """

        # Fuzzy match companies
        company_query = """
            MATCH (existing:Company)
            WHERE existing.source <> 'ofac' AND NOT existing.is_sanctioned
            MATCH (sanctioned:Company:SanctionedEntity)
            WHERE sanctioned.source = 'ofac'
              AND existing.normalized_name <> sanctioned.normalized_name
            WITH existing, sanctioned,
                 apoc.text.jaroWinklerDistance(existing.normalized_name, sanctioned.normalized_name) as similarity
            WHERE similarity >= $threshold
            RETURN
                existing.id as existing_id,
                existing.name as existing_name,
                'Company' as entity_type,
                sanctioned.id as sanctioned_id,
                sanctioned.name as sanctioned_name,
                sanctioned.ofac_uid as ofac_uid,
                sanctioned.sanction_programs as programs,
                similarity
            ORDER BY similarity DESC
            LIMIT 100
        """

        matches = []
        params = {"threshold": self.FUZZY_MATCH_THRESHOLD}

        for query in [person_query, company_query]:
            try:
                results = await Neo4jClient.execute_query(query, params)
                for r in results:
                    matches.append(
                        SanctionMatch(
                            existing_entity_id=r["existing_id"],
                            existing_entity_name=r["existing_name"],
                            existing_entity_type=r["entity_type"],
                            sanctioned_entity_id=r["sanctioned_id"],
                            sanctioned_entity_name=r["sanctioned_name"],
                            ofac_uid=r["ofac_uid"],
                            match_method=MatchMethod.FUZZY_NAME,
                            matched_on=f"Similarity: {r['similarity']:.2%}",
                            confidence=r["similarity"] * self.FUZZY_MATCH_CONFIDENCE,
                            sanction_programs=r["programs"] or [],
                            requires_review=True,  # Always require review for fuzzy
                        )
                    )
            except Exception as e:
                logger.warning(f"Fuzzy matching failed: {e}")

        return matches

    async def _create_sanction_link(self, match: SanctionMatch) -> None:
        """Create SANCTIONED_AS relationship between existing and SDN entity."""
        query = """
            MATCH (existing {id: $existing_id})
            MATCH (sanctioned {id: $sanctioned_id})
            MERGE (existing)-[r:SANCTIONED_AS]->(sanctioned)
            SET r.match_method = $match_method,
                r.matched_on = $matched_on,
                r.confidence = $confidence,
                r.created_at = datetime()
            RETURN r
        """

        params = {
            "existing_id": match.existing_entity_id,
            "sanctioned_id": match.sanctioned_entity_id,
            "match_method": match.match_method.value,
            "matched_on": match.matched_on,
            "confidence": match.confidence,
        }

        await Neo4jClient.execute_query(query, params)
        self.stats["relationships_created"] += 1
        logger.info(
            f"Created SANCTIONED_AS: {match.existing_entity_name} -> {match.sanctioned_entity_name}"
        )

    async def link_match(self, match: SanctionMatch) -> None:
        """
        Manually link a match (for human-reviewed fuzzy matches).

        Call this after human review approves a fuzzy match.
        """
        await self._create_sanction_link(match)

    async def get_unlinked_sanctioned_entities(self) -> list[dict]:
        """Get SDN entities that haven't been linked to any existing entity."""
        query = """
            MATCH (s:SanctionedEntity)
            WHERE s.source = 'ofac'
              AND NOT (s)<-[:SANCTIONED_AS]-()
            RETURN
                s.id as id,
                s.name as name,
                s.ofac_uid as ofac_uid,
                labels(s) as labels,
                s.sanction_programs as programs
            ORDER BY s.name
        """

        results = await Neo4jClient.execute_query(query)
        return [
            {
                "id": r["id"],
                "name": r["name"],
                "ofac_uid": r["ofac_uid"],
                "entity_type": "Person" if "Person" in r["labels"] else "Company",
                "programs": r["programs"] or [],
            }
            for r in results
        ]

    async def get_linked_entities(self) -> list[dict]:
        """Get existing entities that have been linked to SDN entries."""
        query = """
            MATCH (existing)-[r:SANCTIONED_AS]->(sanctioned:SanctionedEntity)
            WHERE sanctioned.source = 'ofac'
            RETURN
                existing.id as existing_id,
                existing.name as existing_name,
                labels(existing) as existing_labels,
                sanctioned.name as sanctioned_name,
                sanctioned.ofac_uid as ofac_uid,
                sanctioned.sanction_programs as programs,
                r.match_method as match_method,
                r.confidence as confidence
            ORDER BY existing.name
        """

        results = await Neo4jClient.execute_query(query)
        return [
            {
                "existing_id": r["existing_id"],
                "existing_name": r["existing_name"],
                "existing_type": "Person"
                if "Person" in r["existing_labels"]
                else "Company",
                "sanctioned_name": r["sanctioned_name"],
                "ofac_uid": r["ofac_uid"],
                "programs": r["programs"] or [],
                "match_method": r["match_method"],
                "confidence": r["confidence"],
            }
            for r in results
        ]
