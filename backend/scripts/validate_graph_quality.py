"""
Validate overall graph quality after ingestion.

Runs a series of diagnostic queries to assess data quality,
coverage, and potential issues.

Usage:
    python -m scripts.validate_graph_quality
    python -m scripts.validate_graph_quality --json  # Output as JSON
"""

import argparse
import asyncio
import json
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.db.neo4j_client import Neo4jClient


class GraphQualityValidator:
    """Validates graph data quality."""

    def __init__(self):
        self.results = {}

    async def run_all_checks(self) -> dict:
        """Run all quality validation queries."""
        checks = [
            ("node_counts", "Total nodes by type", self._check_node_counts),
            (
                "relationship_counts",
                "Total relationships by type",
                self._check_relationship_counts,
            ),
            (
                "orphan_companies",
                "Companies with zero relationships",
                self._check_orphan_companies,
            ),
            (
                "citation_coverage",
                "Citation coverage by relationship type",
                self._check_citation_coverage,
            ),
            (
                "missing_citations",
                "Relationships missing citations",
                self._check_missing_citations,
            ),
            (
                "sanctioned_entities",
                "Sanctioned entities in graph",
                self._check_sanctioned_entities,
            ),
            (
                "sanctions_connections",
                "Entities connected to sanctioned",
                self._check_sanctions_connections,
            ),
            (
                "prolific_directors",
                "Persons with most directorships",
                self._check_prolific_directors,
            ),
            (
                "most_connected",
                "Most connected companies",
                self._check_most_connected,
            ),
            (
                "extraction_methods",
                "Extraction method distribution",
                self._check_extraction_methods,
            ),
            (
                "low_confidence",
                "Low confidence extractions",
                self._check_low_confidence,
            ),
            (
                "data_freshness",
                "Data freshness (recent filings)",
                self._check_data_freshness,
            ),
            (
                "ownership_depth",
                "Ownership chain depth analysis",
                self._check_ownership_depth,
            ),
        ]

        for key, name, check_fn in checks:
            try:
                self.results[key] = {
                    "name": name,
                    "data": await check_fn(),
                    "status": "ok",
                }
            except Exception as e:
                self.results[key] = {
                    "name": name,
                    "data": None,
                    "status": "error",
                    "error": str(e),
                }

        return self.results

    async def _check_node_counts(self) -> list[dict]:
        """Count nodes by label."""
        query = """
            MATCH (n)
            UNWIND labels(n) as label
            RETURN label, count(n) as count
            ORDER BY count DESC
        """
        return await Neo4jClient.execute_query(query)

    async def _check_relationship_counts(self) -> list[dict]:
        """Count relationships by type."""
        query = """
            MATCH ()-[r]->()
            RETURN type(r) as type, count(r) as count
            ORDER BY count DESC
        """
        return await Neo4jClient.execute_query(query)

    async def _check_orphan_companies(self) -> list[dict]:
        """Find companies with no relationships."""
        query = """
            MATCH (c:Company)
            WHERE NOT (c)--()
            RETURN c.cik as cik, c.name as name
            LIMIT 20
        """
        return await Neo4jClient.execute_query(query)

    async def _check_citation_coverage(self) -> list[dict]:
        """Check citation coverage by relationship type."""
        query = """
            MATCH ()-[r]->()
            WHERE NOT type(r) IN ['FILED', 'MENTIONED_IN', 'INCORPORATED_IN']
            WITH type(r) as rel_type,
                 count(r) as total,
                 count(CASE WHEN r.source_filing IS NOT NULL THEN 1 END) as with_filing,
                 count(CASE WHEN r.raw_text IS NOT NULL AND r.raw_text <> '' THEN 1 END) as with_raw_text
            RETURN rel_type,
                   total,
                   with_filing,
                   with_raw_text,
                   round(toFloat(with_filing) / total * 100, 1) as filing_coverage_pct,
                   round(toFloat(with_raw_text) / total * 100, 1) as raw_text_coverage_pct
            ORDER BY total DESC
        """
        return await Neo4jClient.execute_query(query)

    async def _check_missing_citations(self) -> list[dict]:
        """Count relationships missing citations."""
        query = """
            MATCH ()-[r]->()
            WHERE NOT type(r) IN ['FILED', 'MENTIONED_IN', 'INCORPORATED_IN', 'SANCTIONED_AS']
              AND r.source_filing IS NULL
            RETURN type(r) as type, count(r) as missing_count
            ORDER BY missing_count DESC
        """
        return await Neo4jClient.execute_query(query)

    async def _check_sanctioned_entities(self) -> list[dict]:
        """Count sanctioned entities."""
        query = """
            MATCH (n)
            WHERE n.is_sanctioned = true
            UNWIND labels(n) as label
            WITH label, n
            WHERE label <> 'SanctionedEntity'
            RETURN label as type, count(DISTINCT n) as count
        """
        return await Neo4jClient.execute_query(query)

    async def _check_sanctions_connections(self) -> list[dict]:
        """Find entities connected to sanctioned."""
        query = """
            MATCH (n)-[*1..2]-(sanctioned)
            WHERE sanctioned.is_sanctioned = true
              AND (n.is_sanctioned IS NULL OR n.is_sanctioned = false)
              AND NOT n:Filing
              AND NOT n:SanctionedEntity
            UNWIND labels(n) as label
            WITH label, n
            WHERE label <> 'SanctionedEntity'
            RETURN label as type, count(DISTINCT n) as connected_count
        """
        return await Neo4jClient.execute_query(query)

    async def _check_prolific_directors(self) -> list[dict]:
        """Find persons on many boards (potential nominees)."""
        query = """
            MATCH (p:Person)-[:DIRECTOR_OF]->(c:Company)
            WITH p, count(c) as board_count
            WHERE board_count >= 3
            RETURN p.name as person, board_count
            ORDER BY board_count DESC
            LIMIT 15
        """
        return await Neo4jClient.execute_query(query)

    async def _check_most_connected(self) -> list[dict]:
        """Find most connected companies."""
        query = """
            MATCH (c:Company)-[r]-()
            WHERE NOT type(r) = 'FILED'
            WITH c, count(r) as connections
            RETURN c.name as company, c.cik as cik, connections
            ORDER BY connections DESC
            LIMIT 15
        """
        return await Neo4jClient.execute_query(query)

    async def _check_extraction_methods(self) -> list[dict]:
        """Check extraction method distribution."""
        query = """
            MATCH ()-[r]->()
            WHERE r.extraction_method IS NOT NULL
            RETURN r.extraction_method as method, count(r) as count
            ORDER BY count DESC
        """
        return await Neo4jClient.execute_query(query)

    async def _check_low_confidence(self) -> list[dict]:
        """Find low confidence extractions."""
        query = """
            MATCH ()-[r]->()
            WHERE r.confidence IS NOT NULL AND r.confidence < 0.8
            RETURN type(r) as rel_type,
                   count(r) as low_confidence_count,
                   round(avg(r.confidence) * 100, 1) as avg_confidence_pct
            ORDER BY low_confidence_count DESC
        """
        return await Neo4jClient.execute_query(query)

    async def _check_data_freshness(self) -> list[dict]:
        """Check data freshness by filing date."""
        query = """
            MATCH (f:Filing)
            WHERE f.filing_date IS NOT NULL
            WITH f.filing_date as filing_date
            ORDER BY filing_date DESC
            LIMIT 1
            WITH filing_date as most_recent
            MATCH (f:Filing)
            WHERE f.filing_date IS NOT NULL
            RETURN
                count(f) as total_filings,
                toString(most_recent) as most_recent_filing,
                count(CASE WHEN f.filing_date >= date() - duration('P1Y') THEN 1 END) as filings_last_year,
                count(CASE WHEN f.filing_date >= date() - duration('P3Y') THEN 1 END) as filings_last_3_years
        """
        return await Neo4jClient.execute_query(query)

    async def _check_ownership_depth(self) -> list[dict]:
        """Analyze ownership chain depths."""
        query = """
            MATCH path = (owner)-[:OWNS*]->(c:Company)
            WHERE owner:Person OR owner:Company
            WITH length(path) as depth
            RETURN depth, count(*) as count
            ORDER BY depth
        """
        return await Neo4jClient.execute_query(query)

    def print_results(self) -> None:
        """Print results in human-readable format."""
        print("=" * 70)
        print("GRAPH QUALITY REPORT")
        print(f"Generated: {datetime.now().isoformat()}")
        print("=" * 70)

        for key, result in self.results.items():
            print(f"\n### {result['name']}")

            if result["status"] == "error":
                print(f"  ERROR: {result['error']}")
                continue

            data = result["data"]
            if not data:
                print("  (no results)")
                continue

            # Print as simple table
            if isinstance(data, list) and len(data) > 0:
                keys = list(data[0].keys())
                # Header
                header = " | ".join(str(k).ljust(20)[:20] for k in keys)
                print(f"  {header}")
                print(f"  {'-' * len(header)}")
                # Rows
                for record in data[:15]:  # Limit rows
                    row = " | ".join(str(record.get(k, ""))[:20].ljust(20) for k in keys)
                    print(f"  {row}")
                if len(data) > 15:
                    print(f"  ... and {len(data) - 15} more rows")

    def get_summary(self) -> dict:
        """Get summary statistics."""
        summary = {
            "generated_at": datetime.now().isoformat(),
            "checks_run": len(self.results),
            "checks_passed": sum(
                1 for r in self.results.values() if r["status"] == "ok"
            ),
            "checks_failed": sum(
                1 for r in self.results.values() if r["status"] == "error"
            ),
        }

        # Extract key metrics
        if "node_counts" in self.results and self.results["node_counts"]["data"]:
            summary["node_counts"] = {
                r["label"]: r["count"]
                for r in self.results["node_counts"]["data"]
            }

        if (
            "relationship_counts" in self.results
            and self.results["relationship_counts"]["data"]
        ):
            summary["relationship_counts"] = {
                r["type"]: r["count"]
                for r in self.results["relationship_counts"]["data"]
            }

        if (
            "sanctioned_entities" in self.results
            and self.results["sanctioned_entities"]["data"]
        ):
            summary["sanctioned_entity_counts"] = {
                r["type"]: r["count"]
                for r in self.results["sanctioned_entities"]["data"]
            }

        return summary


async def main():
    parser = argparse.ArgumentParser(description="Validate graph quality")
    parser.add_argument(
        "--json", action="store_true", help="Output results as JSON"
    )
    parser.add_argument(
        "--save", action="store_true", help="Save report to logs directory"
    )
    args = parser.parse_args()

    await Neo4jClient.connect()

    try:
        validator = GraphQualityValidator()
        await validator.run_all_checks()

        if args.json:
            print(json.dumps(validator.results, indent=2, default=str))
        else:
            validator.print_results()

            # Print summary
            summary = validator.get_summary()
            print("\n" + "=" * 70)
            print("SUMMARY")
            print("=" * 70)
            print(f"  Checks run: {summary['checks_run']}")
            print(f"  Passed: {summary['checks_passed']}")
            print(f"  Failed: {summary['checks_failed']}")

        if args.save:
            report_dir = Path("logs")
            report_dir.mkdir(exist_ok=True)
            report_path = (
                report_dir
                / f"graph_quality_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            )
            report_path.write_text(
                json.dumps(
                    {"summary": validator.get_summary(), "details": validator.results},
                    indent=2,
                    default=str,
                )
            )
            print(f"\nReport saved to: {report_path}")

    finally:
        await Neo4jClient.disconnect()


if __name__ == "__main__":
    asyncio.run(main())
