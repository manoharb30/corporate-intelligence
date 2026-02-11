"""Service for tracking and surfacing 8-K material events."""

import logging
from dataclasses import dataclass, field
from typing import Optional

from app.db.neo4j_client import Neo4jClient
from ingestion.sec_edgar.edgar_client import SECEdgarClient
from ingestion.sec_edgar.parsers.event_parser import EventParser, Filing8KResult

logger = logging.getLogger(__name__)


@dataclass
class MASignal:
    """An M&A signal detected from 8-K filings."""

    company_name: str
    cik: str
    filing_date: str
    signal_type: str
    item_number: str
    description: str
    persons_involved: list[str] = field(default_factory=list)
    accession_number: str = ""


class EventService:
    """Service for detecting and storing 8-K events."""

    def __init__(self):
        self.client = SECEdgarClient()
        self.parser = EventParser()

    async def close(self):
        await self.client.close()

    async def scan_company_events(
        self,
        cik: str,
        company_name: str,
        limit: int = 20,
    ) -> list[Filing8KResult]:
        """
        Scan a company's recent 8-K filings for events.

        Returns list of parsed 8-K results.
        """
        filings = await self.client.get_8k_filings(cik, limit=limit)
        results = []

        for filing in filings:
            try:
                content = await self.client.get_filing_document(cik, filing)

                result = self.parser.parse_8k(
                    html_content=content,
                    cik=cik,
                    company_name=company_name,
                    accession_number=filing.accession_number,
                    filing_date=filing.filing_date,
                )

                results.append(result)

            except Exception as e:
                logger.error(f"Error parsing 8-K {filing.accession_number}: {e}")

        return results

    async def get_ma_signals(
        self,
        cik: str,
        company_name: str,
        limit: int = 20,
    ) -> list[MASignal]:
        """
        Get M&A signals from a company's 8-K filings.

        Returns only events that are potential M&A indicators:
        - Item 5.02: Executive changes
        - Item 2.01: Acquisitions/dispositions
        - Item 1.01: Material agreements
        - Item 5.01: Control changes
        - Item 5.03: Governance changes
        """
        results = await self.scan_company_events(cik, company_name, limit)
        signals = []

        for result in results:
            for event in result.events:
                if event.is_ma_signal:
                    signals.append(MASignal(
                        company_name=company_name,
                        cik=cik,
                        filing_date=result.filing_date,
                        signal_type=event.signal_type,
                        item_number=event.item_number,
                        description=event.item_name,
                        persons_involved=event.persons_mentioned,
                        accession_number=result.accession_number,
                    ))

        return signals

    async def store_events(self, results: list[Filing8KResult]) -> int:
        """
        Store 8-K events in Neo4j.

        Creates Event nodes linked to Company nodes.
        Returns count of events stored.
        """
        count = 0

        for result in results:
            for event in result.events:
                query = """
                    MATCH (c:Company {cik: $cik})
                    MERGE (e:Event {
                        accession_number: $accession_number,
                        item_number: $item_number
                    })
                    SET e.company_name = $company_name,
                        e.filing_date = $filing_date,
                        e.item_name = $item_name,
                        e.signal_type = $signal_type,
                        e.is_ma_signal = $is_ma_signal,
                        e.persons_mentioned = $persons_mentioned,
                        e.raw_text = $raw_text
                    MERGE (c)-[:FILED_EVENT]->(e)
                    RETURN e
                """

                await Neo4jClient.execute_query(query, {
                    "cik": result.cik,
                    "company_name": result.company_name,
                    "accession_number": result.accession_number,
                    "item_number": event.item_number,
                    "filing_date": result.filing_date,
                    "item_name": event.item_name,
                    "signal_type": event.signal_type,
                    "is_ma_signal": event.is_ma_signal,
                    "persons_mentioned": event.persons_mentioned,
                    "raw_text": event.raw_text[:1000] if event.raw_text else "",
                })

                count += 1

        return count

    @staticmethod
    async def get_recent_ma_signals(limit: int = 50) -> list[dict]:
        """
        Get recent M&A signals from stored events.
        """
        query = """
            MATCH (c:Company)-[:FILED_EVENT]->(e:Event)
            WHERE e.is_ma_signal = true
            RETURN c.name as company_name,
                   c.cik as cik,
                   e.filing_date as filing_date,
                   e.item_number as item_number,
                   e.item_name as item_name,
                   e.signal_type as signal_type,
                   e.persons_mentioned as persons_mentioned,
                   e.accession_number as accession_number
            ORDER BY e.filing_date DESC
            LIMIT $limit
        """

        results = await Neo4jClient.execute_query(query, {"limit": limit})

        return [
            {
                "company_name": r["company_name"],
                "cik": r["cik"],
                "filing_date": r["filing_date"],
                "item_number": r["item_number"],
                "item_name": r["item_name"],
                "signal_type": r["signal_type"],
                "persons_mentioned": r["persons_mentioned"] or [],
                "accession_number": r["accession_number"],
            }
            for r in results
        ]

    @staticmethod
    async def get_company_events(cik: str, limit: int = 20) -> list[dict]:
        """
        Get stored events for a specific company.
        """
        query = """
            MATCH (c:Company {cik: $cik})-[:FILED_EVENT]->(e:Event)
            RETURN e.filing_date as filing_date,
                   e.item_number as item_number,
                   e.item_name as item_name,
                   e.signal_type as signal_type,
                   e.is_ma_signal as is_ma_signal,
                   e.persons_mentioned as persons_mentioned
            ORDER BY e.filing_date DESC
            LIMIT $limit
        """

        results = await Neo4jClient.execute_query(query, {"cik": cik, "limit": limit})

        return [
            {
                "filing_date": r["filing_date"],
                "item_number": r["item_number"],
                "item_name": r["item_name"],
                "signal_type": r["signal_type"],
                "is_ma_signal": r["is_ma_signal"],
                "persons_mentioned": r["persons_mentioned"] or [],
            }
            for r in results
        ]
