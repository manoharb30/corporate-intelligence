"""SEC EDGAR ingestion pipeline orchestrator."""

import asyncio
import logging
from dataclasses import dataclass, field
from typing import Optional

from app.db.neo4j_client import Neo4jClient
from app.models.extraction_models import ExtractionMethod
from ingestion.sec_edgar.edgar_client import SECEdgarClient, CompanyInfo
from ingestion.sec_edgar.llm_extractor import LLMExtractor
from ingestion.sec_edgar.loader import SECDataLoader
from ingestion.sec_edgar.review_queue import ReviewQueue
from ingestion.sec_edgar.parsers.company_parser import SubsidiaryParser
from ingestion.sec_edgar.parsers.officer_parser import OfficerParser

logger = logging.getLogger(__name__)


@dataclass
class ProcessingResult:
    """Result of processing a company."""

    cik: str
    company_name: Optional[str] = None
    success: bool = True
    error: Optional[str] = None

    # Extraction counts
    rule_based_count: int = 0
    llm_count: int = 0
    failed_count: int = 0

    # Data counts
    subsidiaries_extracted: int = 0
    officers_extracted: int = 0

    # Warnings
    warnings: list[str] = field(default_factory=list)


@dataclass
class BatchResult:
    """Result of batch processing."""

    total_companies: int = 0
    successful: int = 0
    failed: int = 0
    results: list[ProcessingResult] = field(default_factory=list)

    # Aggregate extraction stats
    total_rule_based: int = 0
    total_llm: int = 0
    total_failed_extractions: int = 0

    def add_result(self, result: ProcessingResult) -> None:
        """Add a processing result."""
        self.results.append(result)
        self.total_companies += 1

        if result.success:
            self.successful += 1
        else:
            self.failed += 1

        self.total_rule_based += result.rule_based_count
        self.total_llm += result.llm_count
        self.total_failed_extractions += result.failed_count


class SECPipeline:
    """
    Orchestrate SEC EDGAR data ingestion.

    Pipeline: fetch → parse → validate → load
    """

    def __init__(
        self,
        user_agent: Optional[str] = None,
        skip_llm: bool = False,
    ):
        """
        Initialize the pipeline.

        Args:
            user_agent: SEC EDGAR User-Agent string (required by SEC)
            skip_llm: If True, skip LLM fallback (for testing/cost savings)
        """
        self.client = SECEdgarClient(user_agent=user_agent)
        self.loader = SECDataLoader()
        self.review_queue = ReviewQueue()

        # Initialize LLM extractor (may be None if no API key)
        self.llm_extractor = None if skip_llm else LLMExtractor()

        # Initialize parsers with shared dependencies
        self.subsidiary_parser = SubsidiaryParser(
            llm_extractor=self.llm_extractor,
            review_queue=self.review_queue,
        )
        self.officer_parser = OfficerParser(
            llm_extractor=self.llm_extractor,
            review_queue=self.review_queue,
        )

    async def connect(self) -> None:
        """Initialize connections (Neo4j, etc.)."""
        await Neo4jClient.connect()
        logger.info("Connected to Neo4j")

    async def close(self) -> None:
        """Close connections."""
        await self.client.close()
        await Neo4jClient.disconnect()

    async def process_company(
        self,
        cik: str,
        include_subsidiaries: bool = True,
        include_officers: bool = True,
        filings_limit: int = 5,
    ) -> ProcessingResult:
        """
        Process a single company.

        Fetches and processes:
        - DEF 14A for officers/directors
        - 10-K Exhibit 21 for subsidiaries

        Args:
            cik: SEC CIK number
            include_subsidiaries: Extract subsidiary data
            include_officers: Extract officer/director data
            filings_limit: Max number of filings per type to process
        """
        result = ProcessingResult(cik=cik)

        try:
            # Get company info
            company_info = await self.client.get_company_info(cik)
            result.company_name = company_info.name
            logger.info(f"Processing {company_info.name} (CIK: {cik})")

            # Process DEF 14A for officers/directors
            if include_officers:
                await self._process_proxy_filings(
                    cik=cik,
                    company_info=company_info,
                    result=result,
                    limit=filings_limit,
                )

            # Process 10-K for subsidiaries
            if include_subsidiaries:
                await self._process_10k_filings(
                    cik=cik,
                    company_info=company_info,
                    result=result,
                    limit=filings_limit,
                )

        except Exception as e:
            logger.error(f"Failed to process company {cik}: {e}")
            result.success = False
            result.error = str(e)

        return result

    async def process_batch(
        self,
        ciks: list[str],
        include_subsidiaries: bool = True,
        include_officers: bool = True,
        filings_limit: int = 3,
        concurrency: int = 3,
    ) -> BatchResult:
        """
        Process multiple companies.

        Args:
            ciks: List of SEC CIK numbers
            include_subsidiaries: Extract subsidiary data
            include_officers: Extract officer/director data
            filings_limit: Max number of filings per type per company
            concurrency: Number of companies to process concurrently
        """
        batch_result = BatchResult()

        # Process in batches to respect rate limits
        for i in range(0, len(ciks), concurrency):
            batch_ciks = ciks[i:i + concurrency]

            tasks = [
                self.process_company(
                    cik=cik,
                    include_subsidiaries=include_subsidiaries,
                    include_officers=include_officers,
                    filings_limit=filings_limit,
                )
                for cik in batch_ciks
            ]

            results = await asyncio.gather(*tasks, return_exceptions=True)

            for cik, result in zip(batch_ciks, results):
                if isinstance(result, Exception):
                    error_result = ProcessingResult(
                        cik=cik,
                        success=False,
                        error=str(result),
                    )
                    batch_result.add_result(error_result)
                    logger.error(f"Batch processing error for {cik}: {result}")
                else:
                    batch_result.add_result(result)

            # Log progress
            logger.info(
                f"Batch progress: {batch_result.total_companies}/{len(ciks)} "
                f"({batch_result.successful} success, {batch_result.failed} failed)"
            )

        return batch_result

    async def _process_proxy_filings(
        self,
        cik: str,
        company_info: CompanyInfo,
        result: ProcessingResult,
        limit: int,
    ) -> None:
        """Process DEF 14A proxy filings for officer/director data."""
        filings = await self.client.get_def14a_filings(cik, limit=limit)

        if not filings:
            logger.warning(f"No DEF 14A filings found for {cik}")
            result.warnings.append("No DEF 14A filings found")
            return

        for filing in filings[:limit]:
            try:
                logger.info(f"Processing DEF 14A {filing.accession_number}")

                # Fetch filing content
                html_content = await self.client.get_filing_document(cik, filing)

                # Extract officer/director data
                officer_result = self.officer_parser.extract_officers(
                    filing_html=html_content,
                    filing_accession=filing.accession_number,
                    company_cik=cik,
                    company_name=company_info.name,
                )

                # Update counts
                result.officers_extracted += len(officer_result.records)
                self._update_extraction_counts(result, officer_result.records)
                result.warnings.extend(officer_result.warnings)

                # Load into Neo4j
                if officer_result.records:
                    await self.loader.load_officer_data(officer_result)

            except Exception as e:
                logger.error(f"Error processing DEF 14A {filing.accession_number}: {e}")
                result.warnings.append(f"Failed to process {filing.accession_number}: {e}")

    async def _process_10k_filings(
        self,
        cik: str,
        company_info: CompanyInfo,
        result: ProcessingResult,
        limit: int,
    ) -> None:
        """Process 10-K filings for subsidiary data."""
        filings = await self.client.get_10k_filings(cik, limit=limit)

        if not filings:
            logger.warning(f"No 10-K filings found for {cik}")
            result.warnings.append("No 10-K filings found")
            return

        for filing in filings[:limit]:
            try:
                logger.info(f"Processing 10-K {filing.accession_number}")

                # Fetch Exhibit 21
                exhibit_21 = await self.client.get_exhibit_21(cik, filing)

                if not exhibit_21:
                    logger.debug(f"No Exhibit 21 found in {filing.accession_number}")
                    continue

                # Extract subsidiary data
                subsidiary_result = self.subsidiary_parser.extract_subsidiaries(
                    exhibit_html=exhibit_21,
                    filing_accession=filing.accession_number,
                    company_cik=cik,
                    company_name=company_info.name,
                )

                # Update counts
                result.subsidiaries_extracted += len(subsidiary_result.records)
                self._update_extraction_counts(result, subsidiary_result.records)
                result.warnings.extend(subsidiary_result.warnings)

                # Load into Neo4j
                if subsidiary_result.records:
                    await self.loader.load_subsidiary_data(subsidiary_result)

                # Usually only need the most recent 10-K for subsidiaries
                break

            except Exception as e:
                logger.error(f"Error processing 10-K {filing.accession_number}: {e}")
                result.warnings.append(f"Failed to process {filing.accession_number}: {e}")

    def _update_extraction_counts(self, result: ProcessingResult, records: list) -> None:
        """Update extraction method counts from a list of records."""
        for record in records:
            if hasattr(record, "extraction_method"):
                if record.extraction_method == ExtractionMethod.RULE_BASED:
                    result.rule_based_count += 1
                elif record.extraction_method == ExtractionMethod.LLM:
                    result.llm_count += 1

    def get_review_queue_stats(self) -> dict:
        """Get statistics about the review queue."""
        return self.review_queue.get_stats()


# Convenience function for simple usage
async def ingest_company(cik: str, user_agent: Optional[str] = None) -> ProcessingResult:
    """
    Convenience function to ingest a single company.

    Usage:
        result = await ingest_company("0000320193")  # Apple
    """
    pipeline = SECPipeline(user_agent=user_agent)
    try:
        await pipeline.connect()
        return await pipeline.process_company(cik)
    finally:
        await pipeline.close()


async def ingest_batch(ciks: list[str], user_agent: Optional[str] = None) -> BatchResult:
    """
    Convenience function to ingest multiple companies.

    Usage:
        result = await ingest_batch(["0000320193", "0000789019"])  # Apple, Microsoft
    """
    pipeline = SECPipeline(user_agent=user_agent)
    try:
        await pipeline.connect()
        return await pipeline.process_batch(ciks)
    finally:
        await pipeline.close()
