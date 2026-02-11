#!/usr/bin/env python3
"""
Validate Neo4j graph data quality.

Runs various queries to check data integrity and extraction quality.

Usage:
    python -m scripts.validate_graph
"""

import asyncio
import json
import sys
from datetime import datetime
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.db.neo4j_client import Neo4jClient


async def count_nodes_by_type() -> dict:
    """Count nodes by label."""
    query = """
    MATCH (n)
    RETURN labels(n)[0] as label, count(*) as count
    ORDER BY count DESC
    """
    results = await Neo4jClient.execute_query(query)
    return {r["label"]: r["count"] for r in results}


async def count_relationships_by_type() -> dict:
    """Count relationships by type."""
    query = """
    MATCH ()-[r]->()
    RETURN type(r) as type, count(*) as count
    ORDER BY count DESC
    """
    results = await Neo4jClient.execute_query(query)
    return {r["type"]: r["count"] for r in results}


async def find_orphan_companies() -> list[dict]:
    """Find companies with no ownership relationships (potential parsing failures)."""
    query = """
    MATCH (c:Company)
    WHERE NOT (c)<-[:OWNS]-() AND NOT (c)-[:OWNS]->()
    AND NOT (c)<-[:OFFICER_OF]-() AND NOT (c)<-[:DIRECTOR_OF]-()
    RETURN c.id as id, c.name as name, c.cik as cik
    LIMIT 20
    """
    results = await Neo4jClient.execute_query(query)
    return [dict(r) for r in results]


async def find_multi_company_persons() -> list[dict]:
    """Find persons connected to multiple companies (expected for directors)."""
    query = """
    MATCH (p:Person)-[r]->(c:Company)
    WHERE type(r) IN ['OFFICER_OF', 'DIRECTOR_OF', 'OWNS']
    WITH p, collect(DISTINCT c.name) as companies, count(DISTINCT c) as company_count
    WHERE company_count > 1
    RETURN p.name as person_name, company_count, companies[..5] as sample_companies
    ORDER BY company_count DESC
    LIMIT 20
    """
    results = await Neo4jClient.execute_query(query)
    return [dict(r) for r in results]


async def find_major_holders() -> list[dict]:
    """Find entities that own multiple companies (institutional holders)."""
    query = """
    MATCH (owner)-[r:OWNS]->(c:Company)
    WITH owner, count(DISTINCT c) as holdings, collect(DISTINCT c.name)[..5] as sample_holdings
    WHERE holdings > 1
    RETURN
        labels(owner)[0] as owner_type,
        owner.name as owner_name,
        holdings,
        sample_holdings
    ORDER BY holdings DESC
    LIMIT 20
    """
    results = await Neo4jClient.execute_query(query)
    return [dict(r) for r in results]


async def get_companies_with_stats() -> list[dict]:
    """Get companies with their ownership and officer counts."""
    query = """
    MATCH (c:Company)
    WHERE c.cik IS NOT NULL
    OPTIONAL MATCH (owner)-[owns:OWNS]->(c)
    OPTIONAL MATCH (officer)-[off:OFFICER_OF]->(c)
    OPTIONAL MATCH (director)-[dir:DIRECTOR_OF]->(c)
    OPTIONAL MATCH (c)-[sub:OWNS]->(subsidiary:Company)
    WITH c,
         count(DISTINCT owner) as owner_count,
         count(DISTINCT officer) as officer_count,
         count(DISTINCT director) as director_count,
         count(DISTINCT subsidiary) as subsidiary_count
    RETURN
        c.name as name,
        c.cik as cik,
        owner_count,
        officer_count,
        director_count,
        subsidiary_count
    ORDER BY c.name
    """
    results = await Neo4jClient.execute_query(query)
    return [dict(r) for r in results]


async def find_data_quality_issues() -> list[dict]:
    """Find potential data quality issues."""
    issues = []

    # Companies with very long names (might be garbage)
    query = """
    MATCH (c:Company)
    WHERE size(c.name) > 100
    RETURN 'Long company name' as issue, c.name as value, c.id as id
    LIMIT 10
    """
    results = await Neo4jClient.execute_query(query)
    issues.extend([dict(r) for r in results])

    # Persons with very long names
    query = """
    MATCH (p:Person)
    WHERE size(p.name) > 100
    RETURN 'Long person name' as issue, p.name as value, p.id as id
    LIMIT 10
    """
    results = await Neo4jClient.execute_query(query)
    issues.extend([dict(r) for r in results])

    # Duplicate company names
    query = """
    MATCH (c:Company)
    WITH c.normalized_name as name, collect(c) as companies, count(*) as cnt
    WHERE cnt > 1
    RETURN 'Duplicate company' as issue, name as value, cnt as count
    LIMIT 10
    """
    results = await Neo4jClient.execute_query(query)
    issues.extend([dict(r) for r in results])

    return issues


async def get_filing_coverage() -> list[dict]:
    """Get filing coverage per company."""
    query = """
    MATCH (c:Company)<-[:FILED_BY]-(f:Filing)
    WITH c, collect(DISTINCT f.form_type) as form_types, count(f) as filing_count
    RETURN c.name as company, c.cik as cik, form_types, filing_count
    ORDER BY filing_count DESC
    """
    results = await Neo4jClient.execute_query(query)
    return [dict(r) for r in results]


async def run_validation() -> dict:
    """Run all validation queries and compile report."""

    await Neo4jClient.connect()

    try:
        print("Running graph validation...\n")

        # Collect all stats
        report = {
            "run_date": datetime.now().isoformat(),
            "node_counts": await count_nodes_by_type(),
            "relationship_counts": await count_relationships_by_type(),
            "orphan_companies": await find_orphan_companies(),
            "multi_company_persons": await find_multi_company_persons(),
            "major_holders": await find_major_holders(),
            "company_stats": await get_companies_with_stats(),
            "data_quality_issues": await find_data_quality_issues(),
            "filing_coverage": await get_filing_coverage(),
        }

        # Print summary
        print("=" * 60)
        print("GRAPH VALIDATION REPORT")
        print("=" * 60)

        print("\nNode Counts:")
        for label, count in report["node_counts"].items():
            print(f"  {label}: {count:,}")

        print("\nRelationship Counts:")
        for rel_type, count in report["relationship_counts"].items():
            print(f"  {rel_type}: {count:,}")

        print(f"\nOrphan Companies (no relationships): {len(report['orphan_companies'])}")
        if report["orphan_companies"]:
            for company in report["orphan_companies"][:5]:
                print(f"  - {company['name']}")

        print(f"\nPersons on Multiple Boards: {len(report['multi_company_persons'])}")
        if report["multi_company_persons"]:
            for person in report["multi_company_persons"][:5]:
                print(f"  - {person['person_name']}: {person['company_count']} companies")

        print(f"\nMajor Holders (multiple holdings): {len(report['major_holders'])}")
        if report["major_holders"]:
            for holder in report["major_holders"][:5]:
                print(f"  - {holder['owner_name']}: {holder['holdings']} holdings")

        print(f"\nData Quality Issues: {len(report['data_quality_issues'])}")
        if report["data_quality_issues"]:
            for issue in report["data_quality_issues"][:5]:
                print(f"  - {issue['issue']}: {issue.get('value', '')[:50]}...")

        print("\nCompany Stats:")
        for company in report["company_stats"][:10]:
            print(f"  {company['name'][:40]}: "
                  f"{company['owner_count']} owners, "
                  f"{company['officer_count']} officers, "
                  f"{company['subsidiary_count']} subsidiaries")

        print("=" * 60)

        # Save report
        report_path = Path("logs/validation_report.json")
        with open(report_path, "w") as f:
            json.dump(report, f, indent=2, default=str)
        print(f"\nFull report saved to {report_path}")

        return report

    finally:
        await Neo4jClient.disconnect()


def main():
    # Ensure logs directory exists
    Path("logs").mkdir(exist_ok=True)

    report = asyncio.run(run_validation())

    # Exit with error if too many issues
    if len(report["data_quality_issues"]) > 20:
        print("\nWARNING: Many data quality issues detected!")
        sys.exit(1)


if __name__ == "__main__":
    main()
