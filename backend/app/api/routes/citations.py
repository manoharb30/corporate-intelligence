"""Citation-related API endpoints for data provenance."""

from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from app.db.neo4j_client import Neo4jClient
from app.models.citation_models import (
    CitationQuery,
    CitationSummary,
    FactType,
    SourceCitation,
)

router = APIRouter()


@router.get("/entity/{entity_id}")
async def get_entity_citations(
    entity_id: str,
    fact_type: Optional[FactType] = None,
    min_confidence: float = Query(0.0, ge=0.0, le=1.0),
    limit: int = Query(50, ge=1, le=200),
) -> list[dict]:
    """
    Get all citations for an entity (company or person).

    Returns the source citations for all facts extracted about this entity.
    """
    # Build query based on fact type
    if fact_type == FactType.OFFICER_ROLE:
        query = """
            MATCH (e {id: $entity_id})-[r:OFFICER_OF]->(c:Company)
            MATCH (f:Filing {id: r.source_filing})
            WHERE r.confidence >= $min_confidence
            RETURN
                'officer_role' as fact_type,
                e.name as entity_name,
                c.name as related_entity,
                r.title as fact_value,
                r.raw_text as raw_text,
                r.source_section as section_name,
                r.source_table as table_name,
                r.confidence as confidence,
                r.extraction_method as extraction_method,
                f.accession_number as filing_accession,
                f.form_type as filing_type,
                f.filing_date as filing_date,
                f.filing_url as filing_url
            LIMIT $limit
        """
    elif fact_type == FactType.DIRECTOR_ROLE:
        query = """
            MATCH (e {id: $entity_id})-[r:DIRECTOR_OF]->(c:Company)
            MATCH (f:Filing {id: r.source_filing})
            WHERE r.confidence >= $min_confidence
            RETURN
                'director_role' as fact_type,
                e.name as entity_name,
                c.name as related_entity,
                'Director' as fact_value,
                r.raw_text as raw_text,
                r.source_section as section_name,
                r.source_table as table_name,
                r.confidence as confidence,
                r.extraction_method as extraction_method,
                f.accession_number as filing_accession,
                f.form_type as filing_type,
                f.filing_date as filing_date,
                f.filing_url as filing_url
            LIMIT $limit
        """
    elif fact_type == FactType.OWNERSHIP_PERCENTAGE:
        query = """
            MATCH (e {id: $entity_id})-[r:OWNS]->(c:Company)
            MATCH (f:Filing {id: r.source_filing})
            WHERE r.confidence >= $min_confidence
            RETURN
                'ownership_percentage' as fact_type,
                e.name as entity_name,
                c.name as related_entity,
                toString(r.percentage) + '%' as fact_value,
                r.raw_text as raw_text,
                r.source_section as section_name,
                r.source_table as table_name,
                r.confidence as confidence,
                r.extraction_method as extraction_method,
                f.accession_number as filing_accession,
                f.form_type as filing_type,
                f.filing_date as filing_date,
                f.filing_url as filing_url
            LIMIT $limit
        """
    else:
        # Get all citations for the entity
        # Handle both directions:
        # - For companies: incoming officer/director, outgoing ownership
        # - For persons: outgoing officer/director/ownership
        query = """
            MATCH (e {id: $entity_id})
            // Outgoing relationships (person is officer/director of company, or entity owns company)
            OPTIONAL MATCH (e)-[r1:OFFICER_OF]->(c1:Company)
            OPTIONAL MATCH (e)-[r2:DIRECTOR_OF]->(c2:Company)
            OPTIONAL MATCH (e)-[r3:OWNS]->(c3:Company)
            // Incoming relationships (person is officer/director OF this company)
            OPTIONAL MATCH (p1:Person)-[r4:OFFICER_OF]->(e)
            OPTIONAL MATCH (p2:Person)-[r5:DIRECTOR_OF]->(e)
            WITH e,
                 collect(DISTINCT {
                     type: 'officer_role',
                     rel: r1,
                     related: c1.name,
                     value: r1.title
                 }) as officer_out_rels,
                 collect(DISTINCT {
                     type: 'director_role',
                     rel: r2,
                     related: c2.name,
                     value: 'Director'
                 }) as director_out_rels,
                 collect(DISTINCT {
                     type: 'ownership',
                     rel: r3,
                     related: c3.name,
                     value: toString(r3.percentage) + '%'
                 }) as ownership_rels,
                 collect(DISTINCT {
                     type: 'has_officer',
                     rel: r4,
                     related: p1.name,
                     value: r4.title
                 }) as officer_in_rels,
                 collect(DISTINCT {
                     type: 'has_director',
                     rel: r5,
                     related: p2.name,
                     value: 'Director'
                 }) as director_in_rels
            UNWIND (officer_out_rels + director_out_rels + ownership_rels + officer_in_rels + director_in_rels) as item
            WITH e, item
            WHERE item.rel IS NOT NULL AND item.rel.confidence >= $min_confidence
            MATCH (f:Filing {id: item.rel.source_filing})
            RETURN
                item.type as fact_type,
                e.name as entity_name,
                item.related as related_entity,
                item.value as fact_value,
                item.rel.raw_text as raw_text,
                item.rel.source_section as section_name,
                item.rel.source_table as table_name,
                item.rel.confidence as confidence,
                item.rel.extraction_method as extraction_method,
                f.accession_number as filing_accession,
                f.form_type as filing_type,
                f.filing_date as filing_date,
                f.filing_url as filing_url
            LIMIT $limit
        """

    params = {
        "entity_id": entity_id,
        "min_confidence": min_confidence,
        "limit": limit,
    }

    results = await Neo4jClient.execute_query(query, params)
    return [dict(r) for r in results]


@router.get("/relationship/{relationship_type}/{from_id}/{to_id}")
async def get_relationship_citation(
    relationship_type: str,
    from_id: str,
    to_id: str,
) -> dict:
    """
    Get citation for a specific relationship.

    Relationship types: OWNS, OFFICER_OF, DIRECTOR_OF
    """
    rel_types = {
        "OWNS": "OWNS",
        "OFFICER_OF": "OFFICER_OF",
        "DIRECTOR_OF": "DIRECTOR_OF",
        "owns": "OWNS",
        "officer_of": "OFFICER_OF",
        "director_of": "DIRECTOR_OF",
    }

    rel_type = rel_types.get(relationship_type)
    if not rel_type:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid relationship type: {relationship_type}"
        )

    query = f"""
        MATCH (from {{id: $from_id}})-[r:{rel_type}]->(to {{id: $to_id}})
        OPTIONAL MATCH (f:Filing {{id: r.source_filing}})
        RETURN
            r.raw_text as raw_text,
            r.source_section as section_name,
            r.source_table as table_name,
            r.confidence as confidence,
            r.extraction_method as extraction_method,
            f.accession_number as filing_accession,
            f.form_type as filing_type,
            f.filing_date as filing_date,
            f.filing_url as filing_url,
            from.name as from_name,
            to.name as to_name
    """

    params = {
        "from_id": from_id,
        "to_id": to_id,
    }

    results = await Neo4jClient.execute_query(query, params)
    if not results:
        raise HTTPException(status_code=404, detail="Relationship not found")

    return dict(results[0])


@router.get("/filing/{accession_number}")
async def get_filing_citations(
    accession_number: str,
    limit: int = Query(100, ge=1, le=500),
) -> dict:
    """
    Get all facts extracted from a specific filing.

    Returns the filing metadata and all extracted facts with their citations.
    """
    # Get filing info
    filing_query = """
        MATCH (f:Filing {accession_number: $accession_number})
        OPTIONAL MATCH (c:Company)-[:FILED]->(f)
        RETURN
            f.id as filing_id,
            f.accession_number as accession_number,
            f.form_type as form_type,
            f.filing_date as filing_date,
            f.filing_url as filing_url,
            f.extraction_method as extraction_method,
            toString(f.extracted_at) as extracted_at,
            c.name as company_name,
            c.cik as company_cik
    """

    filing_results = await Neo4jClient.execute_query(
        filing_query, {"accession_number": accession_number}
    )

    if not filing_results:
        raise HTTPException(status_code=404, detail="Filing not found")

    filing_info = dict(filing_results[0])

    # Get all entities mentioned in this filing
    facts_query = """
        MATCH (f:Filing {accession_number: $accession_number})
        OPTIONAL MATCH (e)-[:MENTIONED_IN]->(f)
        OPTIONAL MATCH (e)-[r]->(target)
        WITH f, e, r, target
        WHERE r IS NULL OR r.source_filing = f.id
        RETURN
            labels(e)[0] as entity_type,
            e.name as entity_name,
            e.id as entity_id,
            type(r) as relationship_type,
            target.name as target_name,
            r.raw_text as raw_text,
            r.source_section as section_name,
            r.confidence as confidence
        LIMIT $limit
    """

    facts_results = await Neo4jClient.execute_query(
        facts_query, {"accession_number": accession_number, "limit": limit}
    )

    return {
        "filing": filing_info,
        "facts": [dict(r) for r in facts_results],
    }


@router.get("/summary/{entity_id}")
async def get_citation_summary(entity_id: str) -> CitationSummary:
    """
    Get a summary of all citations for an entity.

    Returns aggregate statistics about the citations.
    """
    query = """
        MATCH (e {id: $entity_id})
        // Outgoing relationships
        OPTIONAL MATCH (e)-[r_out]->(target)
        WHERE r_out.source_filing IS NOT NULL
        // Incoming relationships (for companies: officers/directors)
        OPTIONAL MATCH (source)-[r_in]->(e)
        WHERE r_in.source_filing IS NOT NULL AND (type(r_in) = 'OFFICER_OF' OR type(r_in) = 'DIRECTOR_OF')
        WITH e, collect(r_out) + collect(r_in) as all_rels
        UNWIND all_rels as r
        WITH e, r
        WHERE r IS NOT NULL
        OPTIONAL MATCH (f:Filing {id: r.source_filing})
        WITH e,
             count(r) as total_citations,
             collect(DISTINCT f.form_type) as filing_types,
             collect(DISTINCT r.extraction_method) as extraction_methods,
             avg(r.confidence) as avg_confidence,
             min(f.filing_date) as min_date,
             max(f.filing_date) as max_date
        RETURN
            total_citations,
            filing_types,
            extraction_methods,
            avg_confidence,
            min_date,
            max_date
    """

    results = await Neo4jClient.execute_query(query, {"entity_id": entity_id})

    if not results or results[0]["total_citations"] == 0:
        return CitationSummary(
            total_citations=0,
            filing_types=[],
            avg_confidence=0.0,
            extraction_methods=[],
        )

    result = results[0]
    return CitationSummary(
        total_citations=result["total_citations"],
        filing_types=[ft for ft in result["filing_types"] if ft],
        avg_confidence=result["avg_confidence"] or 0.0,
        extraction_methods=[em for em in result["extraction_methods"] if em],
    )


@router.get("/verify/{entity_id}")
async def verify_entity_facts(
    entity_id: str,
    min_confidence: float = Query(0.8, ge=0.0, le=1.0),
) -> dict:
    """
    Verify facts about an entity by checking citation quality.

    Returns verification status for each fact type.
    """
    query = """
        MATCH (e {id: $entity_id})
        OPTIONAL MATCH (e)-[r]->(target)
        WHERE r.source_filing IS NOT NULL
        WITH e, type(r) as rel_type, r, target
        RETURN
            rel_type,
            target.name as target_name,
            r.confidence as confidence,
            r.extraction_method as extraction_method,
            r.raw_text IS NOT NULL as has_raw_text,
            r.source_section IS NOT NULL as has_section,
            CASE
                WHEN r.confidence >= $min_confidence AND r.raw_text IS NOT NULL THEN 'verified'
                WHEN r.confidence >= $min_confidence THEN 'partial'
                ELSE 'unverified'
            END as verification_status
    """

    results = await Neo4jClient.execute_query(
        query, {"entity_id": entity_id, "min_confidence": min_confidence}
    )

    facts = [dict(r) for r in results]

    # Aggregate by status
    verified = sum(1 for f in facts if f.get("verification_status") == "verified")
    partial = sum(1 for f in facts if f.get("verification_status") == "partial")
    unverified = sum(1 for f in facts if f.get("verification_status") == "unverified")

    return {
        "entity_id": entity_id,
        "total_facts": len(facts),
        "verified": verified,
        "partial": partial,
        "unverified": unverified,
        "verification_rate": verified / len(facts) if facts else 0,
        "facts": facts,
    }
