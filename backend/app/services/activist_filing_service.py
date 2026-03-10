"""Service for Schedule 13D activist filing data."""

import logging
from typing import Optional

from app.db.neo4j_client import Neo4jClient
from ingestion.sec_edgar.parsers.schedule13_parser import Schedule13DResult

logger = logging.getLogger(__name__)


def classify_signal_level(filing: Schedule13DResult) -> str:
    """Classify signal level based on filing type and stake percentage.

    - HIGH: percentage > 10% (major stake)
    - MEDIUM: 13D with percentage 5-10% (standard activist threshold)
    - LOW: percentage < 5% or unknown
    """
    pct = filing.percentage or 0.0

    if pct > 10:
        return "HIGH"
    elif pct >= 5:
        return "MEDIUM"
    else:
        return "LOW"


def build_signal_summary(filing: Schedule13DResult) -> str:
    """Build a human-readable signal summary for the filing."""
    parts = []

    filer = filing.filer_name or "Unknown filer"
    target = filing.target_name or "unknown company"
    pct = filing.percentage

    if filing.is_amendment:
        parts.append(f"{filer} updated 13D on {target}")
    else:
        parts.append(f"{filer} filed 13D on {target}")

    if pct is not None:
        parts.append(f"({pct:.1f}% stake)")

    if filing.shares_owned:
        if filing.shares_owned >= 1_000_000:
            parts.append(f"— {filing.shares_owned / 1_000_000:.1f}M shares")
        else:
            parts.append(f"— {filing.shares_owned:,} shares")

    return " ".join(parts)


class ActivistFilingService:
    """Store and query Schedule 13D activist filings."""

    @staticmethod
    async def store_filing(filing: Schedule13DResult) -> Optional[str]:
        """Store an ActivistFiling node in Neo4j, linked to target Company.

        Uses MERGE on accession_number for deduplication.
        Creates Company node if target doesn't exist yet.

        Returns the accession_number if stored, None on error.
        """
        signal_level = classify_signal_level(filing)
        signal_summary = build_signal_summary(filing)

        # Truncate purpose text to 5000 chars to avoid storing huge blobs
        purpose_text = (filing.purpose_text or "")[:5000]

        query = """
            MERGE (c:Company {cik: $target_cik})
            ON CREATE SET c.name = $target_name,
                          c.id = randomUUID()
            SET c.name = COALESCE(c.name, $target_name)

            MERGE (af:ActivistFiling {accession_number: $accession_number})
            SET af.filing_type = $filing_type,
                af.filing_date = $filing_date,
                af.filer_name = $filer_name,
                af.filer_cik = $filer_cik,
                af.target_cik = $target_cik,
                af.reporting_person_type = $reporting_person_type,
                af.percentage = $percentage,
                af.shares_owned = $shares_owned,
                af.purpose_text = $purpose_text,
                af.is_amendment = $is_amendment,
                af.amendment_number = $amendment_number,
                af.signal_level = $signal_level,
                af.signal_summary = $signal_summary,
                af.filing_url = $filing_url,
                af.citizenship = $citizenship

            MERGE (af)-[:TARGETS]->(c)

            RETURN af.accession_number AS accession_number
        """

        try:
            result = await Neo4jClient.execute_query(query, {
                "accession_number": filing.accession_number,
                "filing_type": filing.filing_type,
                "filing_date": filing.filing_date,
                "filer_name": filing.filer_name,
                "filer_cik": filing.filer_cik,
                "target_cik": filing.target_cik,
                "target_name": filing.target_name,
                "reporting_person_type": filing.reporting_person_type,
                "percentage": filing.percentage,
                "shares_owned": filing.shares_owned,
                "purpose_text": purpose_text,
                "is_amendment": filing.is_amendment,
                "amendment_number": filing.amendment_number,
                "signal_level": signal_level,
                "signal_summary": signal_summary,
                "filing_url": filing.filing_url,
                "citizenship": filing.citizenship,
            })

            if result:
                return result[0]["accession_number"]
            return None

        except Exception as e:
            logger.error(f"Failed to store activist filing {filing.accession_number}: {e}")
            return None

    @staticmethod
    async def get_filings(
        target_cik: Optional[str] = None,
        days: int = 90,
        signal_level: Optional[str] = None,
        limit: int = 50,
    ) -> list[dict]:
        """Query activist filings with optional filters."""
        conditions = ["af.filing_date >= toString(date() - duration({days: $days}))"]
        params = {"days": days, "limit": limit}

        if target_cik:
            conditions.append("af.target_cik = $target_cik")
            params["target_cik"] = target_cik

        if signal_level:
            conditions.append("af.signal_level = $signal_level")
            params["signal_level"] = signal_level

        where_clause = " AND ".join(conditions)

        query = f"""
            MATCH (af:ActivistFiling)-[:TARGETS]->(c:Company)
            WHERE {where_clause}
            RETURN af.accession_number AS accession_number,
                   af.filing_type AS filing_type,
                   af.filing_date AS filing_date,
                   af.filer_name AS filer_name,
                   af.filer_cik AS filer_cik,
                   af.percentage AS percentage,
                   af.shares_owned AS shares_owned,
                   af.is_amendment AS is_amendment,
                   af.signal_level AS signal_level,
                   af.signal_summary AS signal_summary,
                   af.filing_url AS filing_url,
                   c.name AS target_name,
                   c.cik AS target_cik,
                   c.tickers AS tickers
            ORDER BY af.filing_date DESC
            LIMIT $limit
        """

        return await Neo4jClient.execute_query(query, params)

    @staticmethod
    async def get_filing_detail(accession_number: str) -> Optional[dict]:
        """Get full details for a single activist filing."""
        query = """
            MATCH (af:ActivistFiling {accession_number: $accession_number})-[:TARGETS]->(c:Company)
            RETURN af.accession_number AS accession_number,
                   af.filing_type AS filing_type,
                   af.filing_date AS filing_date,
                   af.filer_name AS filer_name,
                   af.filer_cik AS filer_cik,
                   af.reporting_person_type AS reporting_person_type,
                   af.percentage AS percentage,
                   af.shares_owned AS shares_owned,
                   af.purpose_text AS purpose_text,
                   af.is_amendment AS is_amendment,
                   af.amendment_number AS amendment_number,
                   af.signal_level AS signal_level,
                   af.signal_summary AS signal_summary,
                   af.filing_url AS filing_url,
                   af.citizenship AS citizenship,
                   c.name AS target_name,
                   c.cik AS target_cik,
                   c.tickers AS tickers
        """

        results = await Neo4jClient.execute_query(query, {
            "accession_number": accession_number,
        })

        if results:
            return dict(results[0])
        return None

    @staticmethod
    async def get_filing_count() -> int:
        """Get total count of activist filings in the database."""
        query = "MATCH (af:ActivistFiling) RETURN count(af) AS count"
        results = await Neo4jClient.execute_query(query)
        return results[0]["count"] if results else 0

    @staticmethod
    async def get_already_stored_accessions(accession_numbers: list[str]) -> set[str]:
        """Check which accession numbers already exist in the database.

        Used by the scanner to skip already-processed filings.
        """
        if not accession_numbers:
            return set()

        query = """
            UNWIND $accession_numbers AS acc
            MATCH (af:ActivistFiling {accession_number: acc})
            RETURN af.accession_number AS accession_number
        """

        results = await Neo4jClient.execute_query(query, {
            "accession_numbers": accession_numbers,
        })

        return {r["accession_number"] for r in results}
