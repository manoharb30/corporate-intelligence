"""Company-related business logic."""

import logging
from typing import Optional

from app.models import (
    Company,
    CompanyCreate,
    CompanyUpdate,
    PaginatedResponse,
    OwnershipChain,
    CompanySearchResult,
    CompanySearchResponse,
    PersonSummary,
    SubsidiarySummary,
    RedFlag,
    CompanyIntelligenceResponse,
)
from app.db.neo4j_client import Neo4jClient
from ingestion.sec_edgar.edgar_client import SECEdgarClient

logger = logging.getLogger(__name__)


class CompanyService:
    """Service for company operations."""

    @staticmethod
    async def list_companies(
        page: int,
        page_size: int,
        jurisdiction: Optional[str] = None,
        status: Optional[str] = None,
    ) -> PaginatedResponse[Company]:
        """List companies with pagination and filtering."""
        skip = (page - 1) * page_size

        # Build WHERE clause
        where_clauses = []
        params = {"skip": skip, "limit": page_size}

        if jurisdiction:
            where_clauses.append("c.jurisdiction = $jurisdiction")
            params["jurisdiction"] = jurisdiction
        if status:
            where_clauses.append("c.status = $status")
            params["status"] = status

        where_str = f"WHERE {' AND '.join(where_clauses)}" if where_clauses else ""

        # Count query
        count_query = f"MATCH (c:Company) {where_str} RETURN count(c) as total"
        count_result = await Neo4jClient.execute_query(count_query, params)
        total = count_result[0]["total"] if count_result else 0

        # Data query
        data_query = f"""
            MATCH (c:Company) {where_str}
            RETURN c
            ORDER BY c.name
            SKIP $skip LIMIT $limit
        """
        records = await Neo4jClient.execute_query(data_query, params)

        companies = [Company(**record["c"]) for record in records]
        pages = (total + page_size - 1) // page_size

        return PaginatedResponse(
            items=companies,
            total=total,
            page=page,
            page_size=page_size,
            pages=pages,
        )

    @staticmethod
    async def search_by_name(query: str, limit: int) -> list[Company]:
        """Search companies by name using full-text search."""
        cypher = """
            CALL db.index.fulltext.queryNodes('company_name_fulltext_idx', $query)
            YIELD node, score
            RETURN node as c
            ORDER BY score DESC
            LIMIT $limit
        """
        records = await Neo4jClient.execute_query(cypher, {"query": query, "limit": limit})
        return [Company(**record["c"]) for record in records]

    @staticmethod
    async def search_combined(query: str, limit: int = 20) -> CompanySearchResponse:
        """
        Search companies from both our graph and SEC EDGAR.

        Returns results indicating whether each company is already in our graph.
        Graph results appear first, followed by SEC EDGAR results.
        """
        results: list[CompanySearchResult] = []
        graph_count = 0
        edgar_count = 0

        # First, search our graph - prioritize companies with CIK (SEC-registered)
        try:
            cypher = """
                CALL db.index.fulltext.queryNodes('company_name_fulltext_idx', $query)
                YIELD node, score
                RETURN node.id as id, node.name as name, node.cik as cik
                ORDER BY CASE WHEN node.cik IS NOT NULL AND node.cik <> '' THEN 0 ELSE 1 END, score DESC
                LIMIT $limit
            """
            records = await Neo4jClient.execute_query(cypher, {"query": query, "limit": limit})

            seen_ciks = set()
            for record in records:
                cik = record.get("cik") or ""
                if cik:
                    seen_ciks.add(cik)
                results.append(CompanySearchResult(
                    cik=cik,
                    name=record["name"],
                    ticker=None,  # We don't store ticker in graph currently
                    in_graph=True,
                    company_id=record["id"],
                ))
            graph_count = len(results)

        except Exception as e:
            logger.warning(f"Graph search failed: {e}")
            seen_ciks = set()

        # Then, search SEC EDGAR for additional companies
        if len(results) < limit:
            try:
                edgar_client = SECEdgarClient()
                edgar_results = await edgar_client.search_companies(
                    query, limit=limit - len(results) + 10  # Get extras to filter duplicates
                )
                await edgar_client.close()

                for edgar_result in edgar_results:
                    # Skip if already in results (by CIK)
                    if edgar_result.cik in seen_ciks:
                        continue

                    # Check if this CIK exists in our graph
                    check_cypher = """
                        MATCH (c:Company {cik: $cik})
                        RETURN c.id as id, c.name as name
                        LIMIT 1
                    """
                    existing = await Neo4jClient.execute_query(
                        check_cypher, {"cik": edgar_result.cik}
                    )

                    if existing:
                        # Already in graph but wasn't found by name search
                        results.append(CompanySearchResult(
                            cik=edgar_result.cik,
                            name=edgar_result.name,
                            ticker=edgar_result.ticker,
                            in_graph=True,
                            company_id=existing[0]["id"],
                        ))
                    else:
                        # Not in graph yet
                        results.append(CompanySearchResult(
                            cik=edgar_result.cik,
                            name=edgar_result.name,
                            ticker=edgar_result.ticker,
                            in_graph=False,
                            company_id=None,
                        ))

                    seen_ciks.add(edgar_result.cik)

                    if len(results) >= limit:
                        break

                edgar_count = len(results) - graph_count

            except Exception as e:
                logger.warning(f"SEC EDGAR search failed: {e}")

        return CompanySearchResponse(
            query=query,
            results=results[:limit],
            graph_count=graph_count,
            edgar_count=edgar_count,
        )

    @staticmethod
    async def get_by_cik(cik: str) -> Optional[Company]:
        """Get company by CIK."""
        cypher = "MATCH (c:Company {cik: $cik}) RETURN c"
        records = await Neo4jClient.execute_query(cypher, {"cik": cik})
        return Company(**records[0]["c"]) if records else None

    @staticmethod
    async def get_by_id(company_id: str) -> Optional[Company]:
        """Get company by ID."""
        cypher = "MATCH (c:Company {id: $id}) RETURN c"
        records = await Neo4jClient.execute_query(cypher, {"id": company_id})
        return Company(**records[0]["c"]) if records else None

    @staticmethod
    async def get_ownership_chains(
        company_id: str,
        max_depth: int,
    ) -> list[OwnershipChain]:
        """Get beneficial ownership chains leading to a company."""
        cypher = """
            MATCH path = (owner)-[:OWNS*1..%d]->(c:Company {id: $company_id})
            WHERE (owner:Person OR owner:Company)
            AND NOT (owner)<-[:OWNS]-()
            RETURN path
        """ % max_depth

        records = await Neo4jClient.execute_query(cypher, {"company_id": company_id})
        # Process paths into OwnershipChain objects
        # Implementation depends on specific requirements
        return []

    @staticmethod
    async def get_subsidiaries(company_id: str, max_depth: int) -> list[Company]:
        """Get all subsidiaries of a company."""
        cypher = """
            MATCH (parent:Company {id: $company_id})-[:OWNS*1..%d]->(subsidiary:Company)
            RETURN DISTINCT subsidiary as c
        """ % max_depth

        records = await Neo4jClient.execute_query(cypher, {"company_id": company_id})
        return [Company(**record["c"]) for record in records]

    @staticmethod
    async def create(company: CompanyCreate) -> Company:
        """Create a new company."""
        import uuid

        company_id = str(uuid.uuid4())
        normalized = company.name.upper().strip()

        cypher = """
            CREATE (c:Company {
                id: $id,
                name: $name,
                normalized_name: $normalized_name,
                cik: $cik,
                lei: $lei,
                jurisdiction: $jurisdiction,
                incorporation_date: $incorporation_date,
                status: $status
            })
            RETURN c
        """
        params = {
            "id": company_id,
            "name": company.name,
            "normalized_name": normalized,
            "cik": company.cik,
            "lei": company.lei,
            "jurisdiction": company.jurisdiction,
            "incorporation_date": str(company.incorporation_date) if company.incorporation_date else None,
            "status": company.status,
        }

        records = await Neo4jClient.execute_query(cypher, params)
        return Company(**records[0]["c"])

    @staticmethod
    async def update(company_id: str, company: CompanyUpdate) -> Optional[Company]:
        """Update a company."""
        # Build SET clause from non-None values
        updates = company.model_dump(exclude_unset=True)
        if not updates:
            return await CompanyService.get_by_id(company_id)

        set_parts = [f"c.{key} = ${key}" for key in updates]
        set_clause = ", ".join(set_parts)

        cypher = f"""
            MATCH (c:Company {{id: $id}})
            SET {set_clause}
            RETURN c
        """
        params = {"id": company_id, **updates}

        records = await Neo4jClient.execute_query(cypher, params)
        return Company(**records[0]["c"]) if records else None

    @staticmethod
    async def get_intelligence(company_id: str) -> Optional[CompanyIntelligenceResponse]:
        """
        Get full intelligence about a company including people, structure, and red flags.

        This is the main endpoint for the product - returns everything needed
        to understand a company's ownership and management structure.
        """
        # First get the company
        company = await CompanyService.get_by_id(company_id)
        if not company:
            return None

        officers: list[PersonSummary] = []
        directors: list[PersonSummary] = []
        beneficial_owners: list[PersonSummary] = []
        subsidiaries: list[SubsidiarySummary] = []
        red_flags: list[RedFlag] = []

        # Get officers with count of other companies they're connected to
        officer_query = """
            MATCH (p:Person)-[r:OFFICER_OF]->(c:Company {id: $company_id})
            WITH p, r
            OPTIONAL MATCH (p)-[:OFFICER_OF|DIRECTOR_OF]->(other:Company)
            WHERE other.id <> $company_id
            WITH p, r, collect(DISTINCT other) as others
            RETURN p.id as id, p.name as name, r.title as title,
                   p.is_sanctioned as is_sanctioned, p.is_pep as is_pep,
                   size(others) as other_count
        """
        officer_records = await Neo4jClient.execute_query(
            officer_query, {"company_id": company_id}
        )
        for rec in officer_records:
            officers.append(PersonSummary(
                id=rec["id"],
                name=rec["name"],
                title=rec.get("title"),
                is_officer=True,
                is_director=False,
                other_companies_count=rec.get("other_count") or 0,
                is_sanctioned=rec.get("is_sanctioned", False) or False,
                is_pep=rec.get("is_pep", False) or False,
            ))

        # Get directors with count of other companies they're connected to
        director_query = """
            MATCH (p:Person)-[r:DIRECTOR_OF]->(c:Company {id: $company_id})
            WITH p, r
            OPTIONAL MATCH (p)-[:OFFICER_OF|DIRECTOR_OF]->(other:Company)
            WHERE other.id <> $company_id
            WITH p, r, collect(DISTINCT other) as others
            RETURN p.id as id, p.name as name, r.title as title,
                   p.is_sanctioned as is_sanctioned, p.is_pep as is_pep,
                   size(others) as other_count
        """
        director_records = await Neo4jClient.execute_query(
            director_query, {"company_id": company_id}
        )
        for rec in director_records:
            # Check if already in officers list (some people are both)
            existing_officer = next((o for o in officers if o.id == rec["id"]), None)
            if existing_officer:
                existing_officer.is_director = True
            else:
                directors.append(PersonSummary(
                    id=rec["id"],
                    name=rec["name"],
                    title=rec.get("title"),
                    is_officer=False,
                    is_director=True,
                    other_companies_count=rec.get("other_count") or 0,
                    is_sanctioned=rec.get("is_sanctioned", False) or False,
                    is_pep=rec.get("is_pep", False) or False,
                ))

        # Get beneficial owners (people or companies that OWNS this company)
        owner_query = """
            MATCH (owner)-[r:OWNS]->(c:Company {id: $company_id})
            WHERE owner:Person OR owner:Company
            RETURN owner.id as id, owner.name as name,
                   r.percentage as percentage,
                   labels(owner)[0] as owner_type,
                   owner.is_sanctioned as is_sanctioned, owner.is_pep as is_pep
        """
        owner_records = await Neo4jClient.execute_query(
            owner_query, {"company_id": company_id}
        )
        for rec in owner_records:
            if rec.get("owner_type") == "Person":
                beneficial_owners.append(PersonSummary(
                    id=rec["id"],
                    name=rec["name"],
                    is_beneficial_owner=True,
                    ownership_percentage=rec.get("percentage"),
                    is_sanctioned=rec.get("is_sanctioned", False) or False,
                    is_pep=rec.get("is_pep", False) or False,
                ))

        # Get subsidiaries
        subsidiary_query = """
            MATCH (c:Company {id: $company_id})-[r:OWNS]->(sub:Company)
            RETURN sub.id as id, sub.name as name,
                   sub.jurisdiction as jurisdiction,
                   r.percentage as percentage
        """
        subsidiary_records = await Neo4jClient.execute_query(
            subsidiary_query, {"company_id": company_id}
        )
        for rec in subsidiary_records:
            subsidiaries.append(SubsidiarySummary(
                id=rec["id"],
                name=rec["name"],
                jurisdiction=rec.get("jurisdiction"),
                ownership_percentage=rec.get("percentage"),
            ))

        # Get parent company (if any)
        parent_query = """
            MATCH (parent:Company)-[r:OWNS]->(c:Company {id: $company_id})
            RETURN parent.id as id, parent.name as name,
                   parent.jurisdiction as jurisdiction,
                   r.percentage as percentage
            LIMIT 1
        """
        parent_records = await Neo4jClient.execute_query(
            parent_query, {"company_id": company_id}
        )
        parent_company = None
        if parent_records:
            rec = parent_records[0]
            parent_company = SubsidiarySummary(
                id=rec["id"],
                name=rec["name"],
                jurisdiction=rec.get("jurisdiction"),
                ownership_percentage=rec.get("percentage"),
            )

        # Detect red flags
        # 1. Sanctioned individuals
        all_people = officers + directors + beneficial_owners
        for person in all_people:
            if person.is_sanctioned:
                red_flags.append(RedFlag(
                    type="sanctions_match",
                    severity="high",
                    description=f"{person.name} appears on a sanctions list",
                    entity_id=person.id,
                    entity_name=person.name,
                ))

        # 2. People connected to other companies (potential conflicts)
        for person in all_people:
            if person.other_companies_count >= 1:
                red_flags.append(RedFlag(
                    type="conflict_of_interest",
                    severity="medium" if person.other_companies_count >= 3 else "low",
                    description=f"{person.name} is also connected to {person.other_companies_count} other {'company' if person.other_companies_count == 1 else 'companies'}",
                    entity_id=person.id,
                    entity_name=person.name,
                ))

        # 3. PEPs
        for person in all_people:
            if person.is_pep:
                red_flags.append(RedFlag(
                    type="pep",
                    severity="medium",
                    description=f"{person.name} is a Politically Exposed Person",
                    entity_id=person.id,
                    entity_name=person.name,
                ))

        # Get filing count
        filing_query = """
            MATCH (c:Company {id: $company_id})-[:FILED]->(f:Filing)
            RETURN count(f) as count, max(f.filing_date) as latest_date
        """
        filing_records = await Neo4jClient.execute_query(
            filing_query, {"company_id": company_id}
        )
        filings_count = 0
        data_freshness = None
        if filing_records:
            filings_count = filing_records[0].get("count", 0)
            data_freshness = filing_records[0].get("latest_date")

        return CompanyIntelligenceResponse(
            company_id=company.id,
            company_name=company.name,
            cik=company.cik,
            jurisdiction=company.jurisdiction,
            officers=officers,
            directors=directors,
            beneficial_owners=beneficial_owners,
            subsidiaries=subsidiaries,
            parent_company=parent_company,
            red_flags=red_flags,
            data_freshness=data_freshness,
            filings_count=filings_count,
        )

    @staticmethod
    async def delete(company_id: str) -> bool:
        """Delete a company and its relationships."""
        cypher = """
            MATCH (c:Company {id: $id})
            DETACH DELETE c
            RETURN count(*) as deleted
        """
        result = await Neo4jClient.execute_write(cypher, {"id": company_id})
        return result["nodes_deleted"] > 0
