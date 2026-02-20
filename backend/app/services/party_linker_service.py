"""Service for linking LLM-extracted parties to Company nodes in Neo4j."""

import json
import logging
from typing import Optional

from app.db.neo4j_client import Neo4jClient
from app.services.llm_analysis_service import LLMAnalysisService
from app.services.feed_service import pick_ticker

logger = logging.getLogger(__name__)

# Common suffixes to strip for fuzzy matching
COMPANY_SUFFIXES = [
    ", Inc.", " Inc.", " Inc", ", LLC", " LLC", " Ltd.", " Ltd",
    " Corp.", " Corp", " Corporation", " Co.", " Co",
    " plc", " PLC", " S.A.", " S.A.S.", " N.V.", " SE",
    " Limited", " Group", " Holdings",
]


def normalize_company_name(name: str) -> str:
    """Normalize a company name for matching."""
    normalized = name.strip()
    for suffix in COMPANY_SUFFIXES:
        if normalized.endswith(suffix):
            normalized = normalized[: -len(suffix)].strip()
    # Also strip leading "The "
    if normalized.startswith("The "):
        normalized = normalized[4:]
    return normalized.lower()


class PartyLinkerService:
    """Links LLM-extracted party names to Company nodes in Neo4j."""

    @staticmethod
    async def find_company_match(party_name: str) -> Optional[dict]:
        """
        Try to match a party name to an existing Company node.

        Uses progressively looser matching:
        1. Exact name match (case-insensitive)
        2. Name contains match
        3. Ticker match
        """
        normalized = normalize_company_name(party_name)

        # Skip if too short or clearly not a company
        if len(normalized) < 3:
            return None

        # Strategy 1: Exact match on normalized name
        query = """
            MATCH (c:Company)
            WHERE c.cik IS NOT NULL AND c.cik <> ''
            AND toLower(c.name) CONTAINS $normalized
            RETURN c.cik as cik, c.name as name, c.tickers as tickers
            LIMIT 5
        """

        results = await Neo4jClient.execute_query(query, {"normalized": normalized})

        if results:
            # Pick the best match — shortest name that contains our search
            # (avoids matching "Apple" to "Apple Hospitality REIT")
            best = min(results, key=lambda r: len(r["name"]))
            return {
                "cik": best["cik"],
                "name": best["name"],
                "ticker": pick_ticker(best.get("tickers")),
            }

        return None

    @staticmethod
    async def link_event_parties(accession_number: str, item_number: str) -> list[dict]:
        """
        For a given event, match LLM-extracted parties to Company nodes
        and create COUNTERPARTY_IN relationships.

        Returns list of linked parties.
        """
        # Get the event and its LLM parties
        query = """
            MATCH (source:Company)-[:FILED_EVENT]->(e:Event {
                accession_number: $accession_number,
                item_number: $item_number
            })
            WHERE e.llm_parties IS NOT NULL
            RETURN source.cik as source_cik, source.name as source_name,
                   e.llm_parties as parties, e.filing_date as filing_date,
                   e.llm_agreement_type as agreement_type
        """

        results = await Neo4jClient.execute_query(query, {
            "accession_number": accession_number,
            "item_number": item_number,
        })

        if not results:
            return []

        r = results[0]
        source_cik = r["source_cik"]
        parties_json = r["parties"]
        filing_date = r["filing_date"]
        agreement_type = r["agreement_type"] or "Agreement"

        try:
            parties = json.loads(parties_json) if isinstance(parties_json, str) else parties_json
        except (json.JSONDecodeError, TypeError):
            return []

        linked = []
        for party in parties:
            party_name = party.get("name", "") if isinstance(party, dict) else str(party)
            source_quote = party.get("source_quote", "") if isinstance(party, dict) else ""

            if not party_name:
                continue

            # Try to match to a Company node
            match = await PartyLinkerService.find_company_match(party_name)
            if not match:
                continue

            # Skip self-references
            if match["cik"] == source_cik:
                continue

            # Create COUNTERPARTY_IN relationship
            link_query = """
                MATCH (source:Company {cik: $source_cik})
                MATCH (target:Company {cik: $target_cik})
                MATCH (e:Event {accession_number: $accession_number, item_number: $item_number})
                MERGE (source)-[r:COUNTERPARTY_IN]->(e)<-[r2:COUNTERPARTY_IN]-(target)
                ON CREATE SET r.created_at = datetime(),
                              r.role = 'filer',
                              r2.created_at = datetime(),
                              r2.role = 'counterparty'
                RETURN source.name as source, target.name as target
            """

            await Neo4jClient.execute_query(link_query, {
                "source_cik": source_cik,
                "target_cik": match["cik"],
                "accession_number": accession_number,
                "item_number": item_number,
            })

            # Also create a direct DEAL_WITH relationship between companies
            deal_query = """
                MATCH (source:Company {cik: $source_cik})
                MATCH (target:Company {cik: $target_cik})
                MERGE (source)-[r:DEAL_WITH {accession_number: $accession_number}]->(target)
                SET r.agreement_type = $agreement_type,
                    r.filing_date = $filing_date,
                    r.source_quote = $source_quote,
                    r.updated_at = datetime()
            """

            await Neo4jClient.execute_query(deal_query, {
                "source_cik": source_cik,
                "target_cik": match["cik"],
                "accession_number": accession_number,
                "agreement_type": agreement_type,
                "filing_date": filing_date,
                "source_quote": source_quote[:500] if source_quote else "",
            })

            linked.append({
                "party_name": party_name,
                "matched_company": match["name"],
                "matched_cik": match["cik"],
                "matched_ticker": match.get("ticker"),
                "source_quote": source_quote,
            })

            logger.info(
                f"Linked party '{party_name}' -> {match['name']} (CIK {match['cik']}) "
                f"for event {accession_number}"
            )

        return linked

    @staticmethod
    async def link_all_analyzed_events() -> dict:
        """
        Scan all events that have LLM analysis and link their parties.

        Returns summary of linking results.
        """
        query = """
            MATCH (c:Company)-[:FILED_EVENT]->(e:Event)
            WHERE e.llm_parties IS NOT NULL AND e.llm_version = 2
            RETURN e.accession_number as accession_number,
                   e.item_number as item_number,
                   c.name as company
        """

        events = await Neo4jClient.execute_query(query)
        total_linked = 0
        results = []

        for event in events:
            linked = await PartyLinkerService.link_event_parties(
                event["accession_number"],
                event["item_number"],
            )
            if linked:
                total_linked += len(linked)
                results.append({
                    "company": event["company"],
                    "accession_number": event["accession_number"],
                    "linked_parties": linked,
                })

        return {
            "events_scanned": len(events),
            "total_links_created": total_linked,
            "results": results,
        }

    @staticmethod
    async def get_company_deals(cik: str) -> list[dict]:
        """Get all deal connections for a company."""
        query = """
            MATCH (c:Company {cik: $cik})-[r:DEAL_WITH]-(other:Company)
            RETURN other.cik as cik,
                   other.name as name,
                   other.tickers as tickers,
                   r.agreement_type as agreement_type,
                   r.filing_date as filing_date,
                   r.accession_number as accession_number,
                   r.source_quote as source_quote
            ORDER BY r.filing_date DESC
        """

        results = await Neo4jClient.execute_query(query, {"cik": cik})

        # Deduplicate by counterparty CIK (keep first/latest per counterparty)
        seen_ciks: set[str] = set()
        deals = []
        for row in results:
            if row["cik"] in seen_ciks:
                continue
            seen_ciks.add(row["cik"])
            deals.append({
                "cik": row["cik"],
                "name": row["name"],
                "ticker": pick_ticker(row.get("tickers")),
                "agreement_type": row["agreement_type"],
                "filing_date": row["filing_date"],
                "accession_number": row["accession_number"],
                "source_quote": row["source_quote"],
            })

        return deals
