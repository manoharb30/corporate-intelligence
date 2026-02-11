#!/usr/bin/env python3
"""
Run SEC EDGAR ingestion pipeline on test companies.

Usage:
    python -m scripts.run_test_ingestion [--companies N] [--skip-llm]
"""

import argparse
import asyncio
import json
import logging
import sys
from datetime import datetime
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from tests.test_companies import TEST_COMPANIES, get_test_ciks
from ingestion.sec_edgar.pipeline import SECPipeline, BatchResult

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(name)s - %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("logs/ingestion.log"),
    ],
)
logger = logging.getLogger(__name__)


def create_report(batch_result: BatchResult, companies: list[dict]) -> dict:
    """Create a JSON report from batch results."""
    per_company = []

    for result in batch_result.results:
        company_info = next(
            (c for c in companies if c["cik"] == result.cik.zfill(10)),
            {"ticker": "UNKNOWN", "name": result.company_name}
        )

        per_company.append({
            "cik": result.cik,
            "ticker": company_info.get("ticker", "UNKNOWN"),
            "name": result.company_name or company_info.get("name", "Unknown"),
            "status": "success" if result.success else "failed",
            "error": result.error,
            "owners_extracted": result.owners_extracted,
            "officers_extracted": result.officers_extracted,
            "subsidiaries_extracted": result.subsidiaries_extracted,
            "rule_based_count": result.rule_based_count,
            "llm_count": result.llm_count,
            "warnings": result.warnings[:5] if result.warnings else [],
        })

    report = {
        "run_date": datetime.now().isoformat(),
        "companies_processed": batch_result.total_companies,
        "success": batch_result.successful,
        "failed": batch_result.failed,
        "extraction_stats": {
            "rule_based": batch_result.total_rule_based,
            "llm_fallback": batch_result.total_llm,
            "failed": batch_result.total_failed_extractions,
        },
        "per_company": per_company,
    }

    return report


async def run_ingestion(
    num_companies: int = 10,
    skip_llm: bool = False,
    filings_limit: int = 3,
) -> dict:
    """Run ingestion on test companies."""

    # Select companies to process
    companies = TEST_COMPANIES[:num_companies]
    ciks = [c["cik"] for c in companies]

    logger.info(f"Starting ingestion for {len(ciks)} companies")
    logger.info(f"Companies: {[c['ticker'] for c in companies]}")

    # Initialize pipeline
    pipeline = SECPipeline(skip_llm=skip_llm)

    try:
        # Connect to Neo4j
        await pipeline.connect()
        logger.info("Connected to Neo4j")

        # Process companies
        batch_result = await pipeline.process_batch(
            ciks=ciks,
            include_ownership=True,
            include_subsidiaries=True,
            include_officers=True,
            filings_limit=filings_limit,
            concurrency=2,  # Be gentle on SEC API
        )

        # Get review queue stats
        review_stats = pipeline.get_review_queue_stats()

        # Create report
        report = create_report(batch_result, companies)
        report["review_queue_count"] = review_stats.get("pending", 0)

        # Save report
        report_path = Path("logs/ingestion_report.json")
        with open(report_path, "w") as f:
            json.dump(report, f, indent=2, default=str)

        logger.info(f"Report saved to {report_path}")

        # Print summary
        print("\n" + "=" * 60)
        print("INGESTION SUMMARY")
        print("=" * 60)
        print(f"Companies processed: {report['companies_processed']}")
        print(f"Successful: {report['success']}")
        print(f"Failed: {report['failed']}")
        print(f"\nExtraction Stats:")
        print(f"  Rule-based: {report['extraction_stats']['rule_based']}")
        print(f"  LLM fallback: {report['extraction_stats']['llm_fallback']}")
        print(f"  Failed: {report['extraction_stats']['failed']}")
        print(f"\nReview queue: {report['review_queue_count']} items")
        print("\nPer-company results:")
        for pc in report["per_company"]:
            status_icon = "✓" if pc["status"] == "success" else "✗"
            print(f"  {status_icon} {pc['ticker']}: {pc['owners_extracted']} owners, "
                  f"{pc['officers_extracted']} officers, {pc['subsidiaries_extracted']} subsidiaries")
        print("=" * 60)

        return report

    finally:
        await pipeline.close()
        logger.info("Pipeline closed")


def main():
    parser = argparse.ArgumentParser(description="Run SEC EDGAR test ingestion")
    parser.add_argument(
        "--companies", "-n",
        type=int,
        default=10,
        help="Number of companies to process (default: 10)",
    )
    parser.add_argument(
        "--skip-llm",
        action="store_true",
        help="Skip LLM fallback (faster, less accurate)",
    )
    parser.add_argument(
        "--filings-limit",
        type=int,
        default=3,
        help="Max filings per type per company (default: 3)",
    )

    args = parser.parse_args()

    # Ensure logs directory exists
    Path("logs").mkdir(exist_ok=True)

    # Run ingestion
    report = asyncio.run(run_ingestion(
        num_companies=args.companies,
        skip_llm=args.skip_llm,
        filings_limit=args.filings_limit,
    ))

    # Exit with error code if too many failures
    success_rate = report["success"] / report["companies_processed"] if report["companies_processed"] > 0 else 0
    if success_rate < 0.8:
        logger.warning(f"Success rate {success_rate:.0%} below 80% threshold")
        sys.exit(1)


if __name__ == "__main__":
    main()
