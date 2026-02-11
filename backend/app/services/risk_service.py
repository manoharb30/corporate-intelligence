"""Service for risk assessment with evidence chains."""

from typing import Optional

from app.db.neo4j_client import Neo4jClient
from app.models.evidence_models import (
    RiskFactor,
    RiskAssessment,
)
from app.services.evidence_service import EvidenceService


class RiskService:
    """Service for calculating risk scores with full evidence trails."""

    # Risk weights for different factors
    RISK_WEIGHTS = {
        "secrecy_jurisdiction": 20,
        "high_secrecy_jurisdiction": 30,  # Score >= 70
        "mass_registration_address": 15,
        "circular_ownership": 25,
        "long_ownership_chain": 10,  # > 4 levels
        "nominee_director": 15,  # Person on 10+ boards
        "pep_connection": 20,
        "sanctioned_connection": 40,
        "shell_company_indicator": 15,
    }

    @staticmethod
    async def calculate_risk_with_evidence(
        entity_id: str,
    ) -> RiskAssessment:
        """
        Calculate risk score with full evidence for each factor.

        Returns a RiskAssessment with individual factors and evidence chain.
        """
        risk_factors: list[RiskFactor] = []
        total_score = 0

        # Get entity name first
        entity_name = await RiskService._get_entity_name(entity_id)

        # Factor 1: Secrecy jurisdiction
        secrecy_factor = await RiskService._check_secrecy_jurisdiction(entity_id)
        if secrecy_factor:
            risk_factors.append(secrecy_factor)
            total_score += secrecy_factor.weight

        # Factor 2: Mass registration address
        address_factor = await RiskService._check_mass_registration_address(entity_id)
        if address_factor:
            risk_factors.append(address_factor)
            total_score += address_factor.weight

        # Factor 3: Circular ownership
        circular_factor = await RiskService._check_circular_ownership(entity_id)
        if circular_factor:
            risk_factors.append(circular_factor)
            total_score += circular_factor.weight

        # Factor 4: Long ownership chain
        chain_factor = await RiskService._check_ownership_chain_length(entity_id)
        if chain_factor:
            risk_factors.append(chain_factor)
            total_score += chain_factor.weight

        # Factor 5: Nominee directors
        nominee_factor = await RiskService._check_nominee_directors(entity_id)
        if nominee_factor:
            risk_factors.append(nominee_factor)
            total_score += nominee_factor.weight

        # Factor 6: PEP connections
        pep_factor = await RiskService._check_pep_connections(entity_id)
        if pep_factor:
            risk_factors.append(pep_factor)
            total_score += pep_factor.weight

        # Factor 7: Sanctioned connections
        sanctioned_factor = await RiskService._check_sanctioned_connections(entity_id)
        if sanctioned_factor:
            risk_factors.append(sanctioned_factor)
            total_score += sanctioned_factor.weight

        # Build evidence chain
        evidence_chain = EvidenceService.build_risk_score_evidence(
            entity_name=entity_name or entity_id,
            risk_score=total_score,
            risk_factors=risk_factors,
        )

        # Determine risk level
        if total_score >= 76:
            risk_level = "CRITICAL"
        elif total_score >= 51:
            risk_level = "HIGH"
        elif total_score >= 21:
            risk_level = "MEDIUM"
        else:
            risk_level = "LOW"

        return RiskAssessment(
            entity_id=entity_id,
            entity_name=entity_name,
            risk_score=total_score,
            risk_level=risk_level,
            factor_count=len(risk_factors),
            risk_factors=risk_factors,
            evidence_chain=evidence_chain,
        )

    @staticmethod
    async def _get_entity_name(entity_id: str) -> Optional[str]:
        """Get entity name from ID."""
        query = """
            MATCH (e {id: $entity_id})
            RETURN e.name as name
        """
        results = await Neo4jClient.execute_query(query, {"entity_id": entity_id})
        return results[0]["name"] if results else None

    @staticmethod
    async def _check_secrecy_jurisdiction(entity_id: str) -> Optional[RiskFactor]:
        """Check if entity is incorporated in a secrecy jurisdiction."""
        query = """
            MATCH (c:Company {id: $entity_id})-[r:INCORPORATED_IN]->(j:Jurisdiction)
            WHERE j.is_secrecy_jurisdiction = true OR j.secrecy_score >= 50
            OPTIONAL MATCH (f:Filing {id: r.source_filing})
            RETURN
                j.name as jurisdiction,
                j.secrecy_score as secrecy_score,
                r.raw_text as raw_text,
                f.filing_url as filing_url,
                f.form_type as filing_type
        """
        results = await Neo4jClient.execute_query(query, {"entity_id": entity_id})

        if results:
            record = results[0]
            secrecy_score = record.get("secrecy_score") or 50
            weight = (
                RiskService.RISK_WEIGHTS["high_secrecy_jurisdiction"]
                if secrecy_score >= 70
                else RiskService.RISK_WEIGHTS["secrecy_jurisdiction"]
            )

            return RiskFactor(
                factor_name=f"Secrecy jurisdiction: {record['jurisdiction']}",
                factor_description=f"Entity incorporated in {record['jurisdiction']} (secrecy score: {secrecy_score})",
                weight=weight,
                source_type="SEC_EDGAR",
                filing_url=record["filing_url"],
                filing_type=record["filing_type"],
                raw_text=record["raw_text"] or f"Jurisdiction: {record['jurisdiction']}",
                confidence=0.95,
            )
        return None

    @staticmethod
    async def _check_mass_registration_address(entity_id: str) -> Optional[RiskFactor]:
        """Check if entity is at an address with many other entities."""
        query = """
            MATCH (c:Company {id: $entity_id})-[r:REGISTERED_AT]->(a:Address)
            WHERE a.entity_count > 50 OR size([(e)-[:REGISTERED_AT]->(a) | e]) > 50
            OPTIONAL MATCH (f:Filing {id: r.source_filing})
            WITH a, r, f, size([(e)-[:REGISTERED_AT]->(a) | e]) as entity_count
            RETURN
                a.full_address as address,
                entity_count,
                r.raw_text as raw_text,
                f.filing_url as filing_url,
                f.form_type as filing_type
        """
        results = await Neo4jClient.execute_query(query, {"entity_id": entity_id})

        if results:
            record = results[0]
            return RiskFactor(
                factor_name=f"Mass registration address ({record['entity_count']} entities)",
                factor_description=f"Registered at address shared by {record['entity_count']} entities",
                weight=RiskService.RISK_WEIGHTS["mass_registration_address"],
                source_type="SEC_EDGAR",
                filing_url=record["filing_url"],
                filing_type=record["filing_type"],
                raw_text=record["raw_text"] or f"Address: {record['address']}",
                confidence=0.9,
            )
        return None

    @staticmethod
    async def _check_circular_ownership(entity_id: str) -> Optional[RiskFactor]:
        """Check for circular ownership patterns."""
        query = """
            MATCH path = (c:Company {id: $entity_id})-[:OWNS*2..6]->(c)
            WITH path, [n in nodes(path) | n.name] as cycle_companies
            RETURN
                cycle_companies,
                length(path) as cycle_length
            LIMIT 1
        """
        results = await Neo4jClient.execute_query(query, {"entity_id": entity_id})

        if results:
            record = results[0]
            cycle_str = " -> ".join(record["cycle_companies"])
            return RiskFactor(
                factor_name=f"Circular ownership ({record['cycle_length']} hops)",
                factor_description=f"Circular ownership structure detected",
                weight=RiskService.RISK_WEIGHTS["circular_ownership"],
                source_type="COMPUTED",
                filing_url=None,
                filing_type=None,
                raw_text=f"Ownership cycle: {cycle_str}",
                confidence=1.0,
            )
        return None

    @staticmethod
    async def _check_ownership_chain_length(entity_id: str) -> Optional[RiskFactor]:
        """Check for unusually long ownership chains."""
        query = """
            MATCH (c:Company {id: $entity_id})
            MATCH path = (owner)-[:OWNS*]->(c)
            WITH max(length(path)) as max_chain
            WHERE max_chain > 4
            RETURN max_chain
        """
        results = await Neo4jClient.execute_query(query, {"entity_id": entity_id})

        if results and results[0].get("max_chain"):
            max_chain = results[0]["max_chain"]
            return RiskFactor(
                factor_name=f"Long ownership chain ({max_chain} levels)",
                factor_description=f"Ownership chain with {max_chain} levels may obscure beneficial ownership",
                weight=RiskService.RISK_WEIGHTS["long_ownership_chain"],
                source_type="COMPUTED",
                filing_url=None,
                filing_type=None,
                raw_text=f"Maximum ownership chain depth: {max_chain} levels",
                confidence=1.0,
            )
        return None

    @staticmethod
    async def _check_nominee_directors(entity_id: str) -> Optional[RiskFactor]:
        """Check for directors who serve on many boards (potential nominees)."""
        query = """
            MATCH (c:Company {id: $entity_id})<-[r:DIRECTOR_OF]-(p:Person)
            MATCH (p)-[:DIRECTOR_OF]->(all_companies:Company)
            WITH p, count(DISTINCT all_companies) as total_boards, r
            WHERE total_boards >= 10
            OPTIONAL MATCH (f:Filing {id: r.source_filing})
            RETURN
                p.name as director_name,
                total_boards,
                r.raw_text as raw_text,
                f.filing_url as filing_url,
                f.form_type as filing_type
            LIMIT 1
        """
        results = await Neo4jClient.execute_query(query, {"entity_id": entity_id})

        if results:
            record = results[0]
            return RiskFactor(
                factor_name=f"Potential nominee director: {record['director_name']}",
                factor_description=f"{record['director_name']} serves on {record['total_boards']} boards",
                weight=RiskService.RISK_WEIGHTS["nominee_director"],
                source_type="SEC_EDGAR",
                filing_url=record["filing_url"],
                filing_type=record["filing_type"],
                raw_text=record["raw_text"] or f"Director {record['director_name']} on {record['total_boards']} boards",
                confidence=0.85,
            )
        return None

    @staticmethod
    async def _check_pep_connections(entity_id: str) -> Optional[RiskFactor]:
        """Check for connections to politically exposed persons."""
        query = """
            MATCH (c:Company {id: $entity_id})<-[r:OWNS|OFFICER_OF|DIRECTOR_OF]-(p:Person)
            WHERE p.is_pep = true
            OPTIONAL MATCH (f:Filing {id: r.source_filing})
            WITH p, type(r) as rel_type, r.raw_text as raw_text,
                 f.filing_url as filing_url, f.form_type as filing_type
            RETURN
                p.name as pep_name,
                rel_type,
                raw_text,
                filing_url,
                filing_type
            LIMIT 1
        """
        results = await Neo4jClient.execute_query(query, {"entity_id": entity_id})

        if results:
            record = results[0]
            return RiskFactor(
                factor_name=f"PEP connection: {record['pep_name']}",
                factor_description=f"Connected to politically exposed person via {record['rel_type']}",
                weight=RiskService.RISK_WEIGHTS["pep_connection"],
                source_type="SEC_EDGAR",
                filing_url=record["filing_url"],
                filing_type=record["filing_type"],
                raw_text=record["raw_text"] or f"PEP: {record['pep_name']}",
                confidence=0.9,
            )
        return None

    @staticmethod
    async def _check_sanctioned_connections(entity_id: str) -> Optional[RiskFactor]:
        """Check for connections to sanctioned entities/persons."""
        query = """
            MATCH (c:Company {id: $entity_id})<-[r:OWNS|OFFICER_OF|DIRECTOR_OF]-(p:Person)
            WHERE p.is_sanctioned = true
            OPTIONAL MATCH (f:Filing {id: r.source_filing})
            WITH p, type(r) as rel_type, r.raw_text as raw_text,
                 f.filing_url as filing_url, f.form_type as filing_type
            RETURN
                p.name as sanctioned_name,
                rel_type,
                raw_text,
                filing_url,
                filing_type
            LIMIT 1
        """
        results = await Neo4jClient.execute_query(query, {"entity_id": entity_id})

        if results:
            record = results[0]
            return RiskFactor(
                factor_name=f"Sanctioned connection: {record['sanctioned_name']}",
                factor_description=f"Connected to sanctioned entity via {record['rel_type']}",
                weight=RiskService.RISK_WEIGHTS["sanctioned_connection"],
                source_type="SEC_EDGAR",
                filing_url=record["filing_url"],
                filing_type=record["filing_type"],
                raw_text=record["raw_text"] or f"Sanctioned: {record['sanctioned_name']}",
                confidence=0.95,
            )
        return None

    @staticmethod
    async def get_risk_summary(entity_id: str) -> dict:
        """
        Get a simple risk summary without full evidence (for list views).
        """
        assessment = await RiskService.calculate_risk_with_evidence(entity_id)
        return {
            "entity_id": entity_id,
            "entity_name": assessment.entity_name,
            "risk_score": assessment.risk_score,
            "risk_level": assessment.risk_level,
            "factor_count": assessment.factor_count,
            "top_factors": [f.factor_name for f in assessment.risk_factors[:3]],
        }
