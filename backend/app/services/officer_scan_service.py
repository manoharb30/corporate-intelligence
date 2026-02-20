"""Service for scanning and storing officer/director data from DEF 14A filings."""

import logging

from ingestion.sec_edgar.edgar_client import SECEdgarClient
from ingestion.sec_edgar.loader import SECDataLoader
from ingestion.sec_edgar.parsers.officer_parser import OfficerParser

logger = logging.getLogger(__name__)


class OfficerScanService:
    """Scan DEF 14A filings for officer/director data and store in Neo4j."""

    @staticmethod
    async def scan_and_store_company(
        cik: str,
        company_name: str,
        limit: int = 2,
    ) -> dict:
        """
        Fetch DEF 14A filings, parse officers/directors, and store in Neo4j.

        Uses existing pipeline components directly (not SECPipeline)
        to avoid calling Neo4jClient.disconnect() on close.

        Returns summary of what was found and stored.
        """
        client = SECEdgarClient()
        parser = OfficerParser()
        loader = SECDataLoader()

        try:
            # Get company info for name if needed
            if not company_name:
                company_info = await client.get_company_info(cik)
                company_name = company_info.name

            filings = await client.get_def14a_filings(cik, limit=limit)

            if not filings:
                logger.info(f"No DEF 14A filings found for {cik}")
                return {
                    "cik": cik,
                    "company_name": company_name,
                    "filings_found": 0,
                    "filings_parsed": 0,
                    "officers_found": 0,
                    "directors_found": 0,
                }

            total_officers = 0
            total_directors = 0
            filings_parsed = 0

            for filing in filings[:limit]:
                try:
                    html_content = await client.get_filing_document(cik, filing)

                    result = parser.extract_officers(
                        filing_html=html_content,
                        filing_accession=filing.accession_number,
                        company_cik=cik,
                        company_name=company_name,
                        filing_date=None,
                        filing_url=None,
                    )

                    if result.records:
                        stats = await loader.load_officer_data(result)
                        total_officers += stats.get("officer_relationships", 0)
                        total_directors += stats.get("director_relationships", 0)
                        filings_parsed += 1
                    else:
                        logger.info(
                            f"No officers/directors extracted from "
                            f"DEF 14A {filing.accession_number} for {cik}"
                        )

                except Exception as e:
                    logger.error(
                        f"Error processing DEF 14A {filing.accession_number} "
                        f"for {cik}: {e}"
                    )

            return {
                "cik": cik,
                "company_name": company_name,
                "filings_found": len(filings),
                "filings_parsed": filings_parsed,
                "officers_found": total_officers,
                "directors_found": total_directors,
            }

        finally:
            await client.close()
