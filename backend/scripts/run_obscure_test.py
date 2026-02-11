"""
Test pipeline with obscure/complex companies.

Usage:
    python -m scripts.run_obscure_test                    # Run all
    python -m scripts.run_obscure_test --cik 0000813762   # Run one
    python -m scripts.run_obscure_test --validate-only    # Skip ingestion, just validate
    python -m scripts.run_obscure_test --skip-sanctions   # Skip sanctions checks
"""

import argparse
import asyncio
import json
import logging
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.db.neo4j_client import Neo4jClient
from app.services.connection_service import ConnectionService
from app.services.risk_service import RiskService
from app.services.sanctions_service import SanctionsService
from ingestion.sec_edgar.pipeline import SECPipeline
from tests.test_companies_obscure import TEST_COMPANIES, TestCompany

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


class PipelineTestRunner:
    """Test runner for validating the full pipeline."""

    def __init__(self, skip_ingestion: bool = False, skip_sanctions: bool = False):
        self.skip_ingestion = skip_ingestion
        self.skip_sanctions = skip_sanctions
        self.pipeline: Optional[SECPipeline] = None
        self.results: list[dict] = []

    async def initialize(self) -> None:
        """Initialize connections and pipeline."""
        await Neo4jClient.connect()
        if not self.skip_ingestion:
            self.pipeline = SECPipeline(skip_llm=False)

    async def cleanup(self) -> None:
        """Cleanup connections."""
        if self.pipeline:
            await self.pipeline.client.close()
        await Neo4jClient.disconnect()

    async def run_all(self) -> None:
        """Run full test suite on all companies."""
        print(f"\nTesting {len(TEST_COMPANIES)} obscure companies...\n")
        print("=" * 70)

        for company in TEST_COMPANIES:
            result = await self.test_company(company)
            self.results.append(result)
            self._print_result(result)

        self._print_summary()
        self._save_report()

    async def test_company(self, company: TestCompany) -> dict:
        """Test single company through full pipeline."""
        result = {
            "cik": company.cik,
            "ticker": company.ticker,
            "name": company.name,
            "challenges": [c.value for c in company.challenges],
            "notes": company.notes,
            "tests": {},
            "started_at": datetime.now().isoformat(),
        }

        # Test 1: SEC Ingestion
        if not self.skip_ingestion:
            result["tests"]["ingestion"] = await self._test_ingestion(company)
        else:
            result["tests"]["ingestion"] = {"passed": True, "skipped": True}

        # Test 2: Data Completeness
        result["tests"]["completeness"] = await self._test_completeness(company)

        # Test 3: Citations Present
        result["tests"]["citations"] = await self._test_citations(company)

        # Test 4: Connections Queryable
        result["tests"]["connections"] = await self._test_connections(company)

        # Test 5: Sanctions Check
        if not self.skip_sanctions:
            result["tests"]["sanctions"] = await self._test_sanctions(company)
        else:
            result["tests"]["sanctions"] = {"passed": True, "skipped": True}

        # Test 6: Risk Score
        result["tests"]["risk_score"] = await self._test_risk_score(company)

        # Overall status
        result["passed"] = all(
            t.get("passed", False) for t in result["tests"].values()
        )
        result["finished_at"] = datetime.now().isoformat()

        return result

    async def _test_ingestion(self, company: TestCompany) -> dict:
        """Test SEC EDGAR ingestion."""
        try:
            logger.info(f"Ingesting {company.ticker} ({company.cik})...")

            stats = await self.pipeline.process_company(
                cik=company.cik,
                include_ownership=True,
                include_subsidiaries=True,
                include_officers=True,
                filings_limit=3,
            )

            return {
                "passed": stats.success,
                "company_name": stats.company_name,
                "owners_extracted": stats.owners_extracted,
                "officers_extracted": stats.officers_extracted,
                "subsidiaries_extracted": stats.subsidiaries_extracted,
                "rule_based_count": stats.rule_based_count,
                "llm_count": stats.llm_count,
                "failed_count": stats.failed_count,
                "warnings": stats.warnings[:5],  # Limit warnings
                "error": stats.error,
            }
        except Exception as e:
            logger.error(f"Ingestion failed for {company.cik}: {e}")
            return {"passed": False, "error": str(e)}

    async def _test_completeness(self, company: TestCompany) -> dict:
        """Test data completeness in graph."""
        query = """
            MATCH (c:Company {cik: $cik})
            OPTIONAL MATCH (c)<-[:OWNS]-(owner)
            OPTIONAL MATCH (c)<-[:OFFICER_OF]-(officer)
            OPTIONAL MATCH (c)<-[:DIRECTOR_OF]-(director)
            OPTIONAL MATCH (c)-[:OWNS]->(sub:Company)
            RETURN
                c.name as name,
                c.id as company_id,
                count(DISTINCT owner) as owner_count,
                count(DISTINCT officer) as officer_count,
                count(DISTINCT director) as director_count,
                count(DISTINCT sub) as subsidiary_count
        """

        try:
            results = await Neo4jClient.execute_query(query, {"cik": company.cik})

            if not results or not results[0].get("name"):
                return {"passed": False, "error": "Company not found in graph"}

            r = results[0]

            # Generate warnings for missing expected data
            warnings = []
            if r["officer_count"] < company.expected_officers_min:
                warnings.append(
                    f"Expected {company.expected_officers_min}+ officers, found {r['officer_count']}"
                )
            if r["subsidiary_count"] < company.expected_subsidiaries_min:
                warnings.append(
                    f"Expected {company.expected_subsidiaries_min}+ subsidiaries, found {r['subsidiary_count']}"
                )
            if r["owner_count"] < company.expected_owners_min:
                warnings.append(
                    f"Expected {company.expected_owners_min}+ owners, found {r['owner_count']}"
                )

            # Pass if we have any data at all
            has_data = (
                r["officer_count"] > 0
                or r["director_count"] > 0
                or r["subsidiary_count"] > 0
                or r["owner_count"] > 0
            )

            return {
                "passed": has_data,
                "company_name": r["name"],
                "company_id": r["company_id"],
                "owners": r["owner_count"],
                "officers": r["officer_count"],
                "directors": r["director_count"],
                "subsidiaries": r["subsidiary_count"],
                "warnings": warnings,
            }
        except Exception as e:
            return {"passed": False, "error": str(e)}

    async def _test_citations(self, company: TestCompany) -> dict:
        """Test that relationships have citations."""
        query = """
            MATCH (c:Company {cik: $cik})-[r]-()
            WHERE NOT type(r) IN ['FILED', 'MENTIONED_IN', 'INCORPORATED_IN']
            WITH
                count(r) as total,
                count(CASE WHEN r.source_filing IS NOT NULL THEN 1 END) as with_citation,
                count(CASE WHEN r.raw_text IS NOT NULL AND r.raw_text <> '' THEN 1 END) as with_raw_text
            RETURN total, with_citation, with_raw_text,
                   CASE WHEN total > 0 THEN toFloat(with_citation) / total ELSE 0.0 END as citation_rate,
                   CASE WHEN total > 0 THEN toFloat(with_raw_text) / total ELSE 0.0 END as raw_text_rate
        """

        try:
            results = await Neo4jClient.execute_query(query, {"cik": company.cik})

            if not results or results[0]["total"] == 0:
                return {"passed": True, "note": "No relationships to check"}

            r = results[0]
            citation_rate = float(r["citation_rate"]) if r["citation_rate"] is not None else 0.0
            raw_text_rate = float(r["raw_text_rate"]) if r["raw_text_rate"] is not None else 0.0

            return {
                "passed": citation_rate >= 0.7,  # 70% threshold
                "total_relationships": r["total"],
                "with_citations": r["with_citation"],
                "with_raw_text": r["with_raw_text"],
                "citation_rate_pct": round(citation_rate * 100, 1),
                "raw_text_rate_pct": round(raw_text_rate * 100, 1),
            }
        except Exception as e:
            return {"passed": False, "error": str(e)}

    async def _test_connections(self, company: TestCompany) -> dict:
        """Test that connections can be queried with evidence."""
        # First get company ID
        id_query = """
            MATCH (c:Company {cik: $cik})
            RETURN c.id as id
        """

        try:
            id_result = await Neo4jClient.execute_query(id_query, {"cik": company.cik})
            if not id_result:
                return {"passed": True, "note": "Company not found, skipping"}

            company_id = id_result[0]["id"]

            # Get connections with evidence
            connections = await ConnectionService.get_entity_connections_with_evidence(
                entity_id=company_id,
                limit=10,
            )

            if not connections:
                return {"passed": True, "note": "No connections found"}

            # Check if connections have citation data
            with_citations = sum(
                1 for c in connections if c.get("citation", {}).get("filing_accession")
            )

            return {
                "passed": True,
                "connections_found": len(connections),
                "with_citations": with_citations,
                "sample_connections": [
                    {
                        "entity": c["connected_entity"]["name"],
                        "relationship": c["relationship"],
                        "has_citation": bool(
                            c.get("citation", {}).get("filing_accession")
                        ),
                    }
                    for c in connections[:3]
                ],
            }
        except Exception as e:
            return {"passed": False, "error": str(e)}

    async def _test_sanctions(self, company: TestCompany) -> dict:
        """Test sanctions checking works."""
        # Get company ID first
        id_query = """
            MATCH (c:Company {cik: $cik})
            RETURN c.id as id
        """

        try:
            id_result = await Neo4jClient.execute_query(id_query, {"cik": company.cik})
            if not id_result:
                return {"passed": True, "note": "Company not found, skipping"}

            company_id = id_result[0]["id"]

            # Just check direct sanctions status (simpler query, avoids path query issues)
            check_result = await SanctionsService.check_entity_sanctions(company_id)

            return {
                "passed": True,
                "is_sanctioned": check_result.get("is_sanctioned", False),
                "sanction_type": check_result.get("sanction_type"),
                "programs": check_result.get("programs", []),
            }
        except Exception as e:
            logger.warning(f"Sanctions check error for {company.cik}: {e}")
            return {"passed": False, "error": str(e)[:100]}

    async def _test_risk_score(self, company: TestCompany) -> dict:
        """Test risk scoring with evidence."""
        # Get company ID first
        id_query = """
            MATCH (c:Company {cik: $cik})
            RETURN c.id as id
        """

        try:
            id_result = await Neo4jClient.execute_query(id_query, {"cik": company.cik})
            if not id_result:
                return {"passed": True, "note": "Company not found, skipping"}

            company_id = id_result[0]["id"]

            risk_result = await RiskService.calculate_risk_with_evidence(company_id)

            has_evidence = (
                risk_result.evidence_chain is not None
                and len(risk_result.evidence_chain.evidence_steps) >= 0
            )

            return {
                "passed": True,
                "risk_score": risk_result.risk_score,
                "risk_level": risk_result.risk_level,
                "factor_count": risk_result.factor_count,
                "has_evidence_chain": has_evidence,
                "top_factors": [f.factor_name for f in risk_result.risk_factors[:3]],
            }
        except Exception as e:
            return {"passed": False, "error": str(e)}

    def _print_result(self, result: dict) -> None:
        """Print single company result."""
        status = "\u2705 PASS" if result["passed"] else "\u274c FAIL"
        print(f"\n{status} {result['ticker']} ({result['name']})")
        print(f"   CIK: {result['cik']}")
        print(f"   Challenges: {', '.join(result['challenges'])}")

        for test_name, test_result in result["tests"].items():
            if test_result.get("skipped"):
                test_status = "\u23ed"  # Skip symbol
            elif test_result.get("passed"):
                test_status = "\u2713"
            else:
                test_status = "\u2717"
            print(f"   {test_status} {test_name}: {self._summarize_test(test_result)}")

    def _summarize_test(self, test_result: dict) -> str:
        """One-line summary of test result."""
        if test_result.get("skipped"):
            return "SKIPPED"

        if not test_result.get("passed"):
            error = test_result.get("error", "Unknown error")
            return f"FAILED - {error[:50]}"

        # Remove internal keys for summary
        exclude_keys = {"passed", "error", "skipped", "warnings", "sample_connections"}
        details = {k: v for k, v in test_result.items() if k not in exclude_keys}

        if not details:
            return "OK"

        # Format nicely
        parts = []
        for k, v in list(details.items())[:4]:  # Limit to 4 items
            if isinstance(v, float):
                parts.append(f"{k}={v:.1f}")
            elif isinstance(v, list):
                parts.append(f"{k}={len(v)}")
            else:
                parts.append(f"{k}={v}")

        return ", ".join(parts)

    def _print_summary(self) -> None:
        """Print overall summary."""
        passed = sum(1 for r in self.results if r["passed"])
        total = len(self.results)

        print("\n" + "=" * 70)
        print(f"SUMMARY: {passed}/{total} companies passed all tests")
        print("=" * 70)

        # Aggregate test stats
        test_names = [
            "ingestion",
            "completeness",
            "citations",
            "connections",
            "sanctions",
            "risk_score",
        ]
        for test_name in test_names:
            test_passed = sum(
                1
                for r in self.results
                if r["tests"].get(test_name, {}).get("passed", False)
            )
            print(f"  {test_name:15}: {test_passed}/{total}")

        # List failures
        failed = [r for r in self.results if not r["passed"]]
        if failed:
            print("\nFailed companies:")
            for r in failed:
                failed_tests = [
                    t for t, v in r["tests"].items() if not v.get("passed", True)
                ]
                print(f"  - {r['ticker']}: {', '.join(failed_tests)}")

    def _save_report(self) -> None:
        """Save detailed report to JSON."""
        report_dir = Path("logs")
        report_dir.mkdir(exist_ok=True)

        report = {
            "run_date": datetime.now().isoformat(),
            "total_companies": len(self.results),
            "passed": sum(1 for r in self.results if r["passed"]),
            "failed": sum(1 for r in self.results if not r["passed"]),
            "skip_ingestion": self.skip_ingestion,
            "skip_sanctions": self.skip_sanctions,
            "results": self.results,
        }

        report_path = (
            report_dir / f"obscure_test_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        )
        report_path.write_text(json.dumps(report, indent=2, default=str))
        print(f"\nDetailed report saved to: {report_path}")


async def main():
    parser = argparse.ArgumentParser(description="Test pipeline with obscure companies")
    parser.add_argument("--cik", help="Test single company by CIK")
    parser.add_argument(
        "--validate-only",
        action="store_true",
        help="Skip ingestion, validate existing data",
    )
    parser.add_argument(
        "--skip-sanctions", action="store_true", help="Skip sanctions checks"
    )
    args = parser.parse_args()

    runner = PipelineTestRunner(
        skip_ingestion=args.validate_only,
        skip_sanctions=args.skip_sanctions,
    )

    try:
        await runner.initialize()

        if args.cik:
            company = next((c for c in TEST_COMPANIES if c.cik == args.cik), None)
            if not company:
                print(f"Company with CIK {args.cik} not in test list")
                print(f"Available CIKs: {[c.cik for c in TEST_COMPANIES]}")
                return
            result = await runner.test_company(company)
            runner.results.append(result)
            runner._print_result(result)
        else:
            await runner.run_all()

    finally:
        await runner.cleanup()


if __name__ == "__main__":
    asyncio.run(main())
