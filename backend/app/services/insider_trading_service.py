"""Service for insider trading (Form 4) data."""

import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Optional

from app.db.neo4j_client import Neo4jClient
from ingestion.sec_edgar.edgar_client import SECEdgarClient
from ingestion.sec_edgar.parsers.form4_parser import Form4Parser

logger = logging.getLogger(__name__)


@dataclass
class InsiderTradeItem:
    """A single insider trade for display."""

    insider_name: str
    insider_title: str
    transaction_date: str
    transaction_code: str
    transaction_type: str
    security_title: str
    shares: float
    price_per_share: float
    total_value: float
    shares_after_transaction: float
    ownership_type: str
    is_derivative: bool
    filing_date: str
    accession_number: str

    def to_dict(self) -> dict:
        return {
            "insider_name": self.insider_name,
            "insider_title": self.insider_title,
            "transaction_date": self.transaction_date,
            "transaction_code": self.transaction_code,
            "transaction_type": self.transaction_type,
            "security_title": self.security_title,
            "shares": self.shares,
            "price_per_share": self.price_per_share,
            "total_value": self.total_value,
            "shares_after_transaction": self.shares_after_transaction,
            "ownership_type": self.ownership_type,
            "is_derivative": self.is_derivative,
            "filing_date": self.filing_date,
            "accession_number": self.accession_number,
        }


class InsiderTradingService:
    """Service for insider trading data."""

    @staticmethod
    async def scan_and_store_company(
        cik: str,
        company_name: str,
        limit: int = 50,
    ) -> dict:
        """
        Fetch Form 4 filings, parse XML, and store transactions in Neo4j.

        Returns summary of what was found and stored.
        """
        client = SECEdgarClient()
        parser = Form4Parser()

        try:
            filings = await client.get_form4_filings(cik, limit=limit)

            parsed_count = 0
            stored_count = 0
            skipped_count = 0

            for filing in filings:
                try:
                    content = await client.get_form4_xml(cik, filing)
                    if content is None:
                        skipped_count += 1
                        continue

                    result = parser.parse_form4(
                        xml_content=content,
                        accession_number=filing.accession_number,
                        filing_date=filing.filing_date,
                    )

                    if result is None:
                        skipped_count += 1
                        continue

                    parsed_count += 1

                    # Store each transaction
                    for idx, txn in enumerate(result.transactions):
                        txn_id = f"{filing.accession_number}_{idx}"

                        query = """
                            MERGE (c:Company {cik: $cik})
                            ON CREATE SET c.name = $company_name

                            MERGE (t:InsiderTransaction {id: $txn_id})
                            SET t.accession_number = $accession_number,
                                t.filing_date = $filing_date,
                                t.transaction_date = $transaction_date,
                                t.transaction_code = $transaction_code,
                                t.transaction_type = $transaction_type,
                                t.security_title = $security_title,
                                t.shares = $shares,
                                t.price_per_share = $price_per_share,
                                t.total_value = $total_value,
                                t.shares_after_transaction = $shares_after,
                                t.ownership_type = $ownership_type,
                                t.is_derivative = $is_derivative,
                                t.insider_name = $insider_name,
                                t.insider_title = $insider_title

                            MERGE (c)-[:INSIDER_TRADE_OF]->(t)

                            WITH t
                            MERGE (p:Person {normalized_name: toLower($insider_name)})
                            ON CREATE SET p.name = $insider_name,
                                          p.id = randomUUID()
                            MERGE (p)-[:TRADED_BY]->(t)

                            RETURN t.id
                        """

                        await Neo4jClient.execute_query(query, {
                            "cik": cik,
                            "company_name": company_name,
                            "txn_id": txn_id,
                            "accession_number": filing.accession_number,
                            "filing_date": filing.filing_date,
                            "transaction_date": txn.transaction_date,
                            "transaction_code": txn.transaction_code,
                            "transaction_type": txn.transaction_type,
                            "security_title": txn.security_title,
                            "shares": txn.shares,
                            "price_per_share": txn.price_per_share,
                            "total_value": txn.total_value,
                            "shares_after": txn.shares_after_transaction,
                            "ownership_type": txn.ownership_type,
                            "is_derivative": txn.is_derivative,
                            "insider_name": result.insider.name,
                            "insider_title": result.insider.title,
                        })
                        stored_count += 1

                except Exception as e:
                    logger.error(f"Error processing Form 4 {filing.accession_number}: {e}")

            return {
                "cik": cik,
                "company_name": company_name,
                "filings_found": len(filings),
                "filings_parsed": parsed_count,
                "filings_skipped": skipped_count,
                "transactions_stored": stored_count,
            }

        finally:
            await client.close()

    @staticmethod
    async def get_company_insider_trades(
        cik: str,
        days: int = 90,
        limit: int = 50,
    ) -> list[InsiderTradeItem]:
        """Get stored insider trades for a company."""
        since_date = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")

        query = """
            MATCH (c:Company {cik: $cik})-[:INSIDER_TRADE_OF]->(t:InsiderTransaction)
            WHERE t.filing_date >= $since_date
            RETURN t.insider_name as insider_name,
                   t.insider_title as insider_title,
                   t.transaction_date as transaction_date,
                   t.transaction_code as transaction_code,
                   t.transaction_type as transaction_type,
                   t.security_title as security_title,
                   t.shares as shares,
                   t.price_per_share as price_per_share,
                   t.total_value as total_value,
                   t.shares_after_transaction as shares_after_transaction,
                   t.ownership_type as ownership_type,
                   t.is_derivative as is_derivative,
                   t.filing_date as filing_date,
                   t.accession_number as accession_number
            ORDER BY t.transaction_date DESC
            LIMIT $limit
        """

        results = await Neo4jClient.execute_query(query, {
            "cik": cik,
            "since_date": since_date,
            "limit": limit,
        })

        return [
            InsiderTradeItem(
                insider_name=r["insider_name"] or "",
                insider_title=r["insider_title"] or "",
                transaction_date=r["transaction_date"] or "",
                transaction_code=r["transaction_code"] or "",
                transaction_type=r["transaction_type"] or "",
                security_title=r["security_title"] or "",
                shares=r["shares"] or 0,
                price_per_share=r["price_per_share"] or 0,
                total_value=r["total_value"] or 0,
                shares_after_transaction=r["shares_after_transaction"] or 0,
                ownership_type=r["ownership_type"] or "D",
                is_derivative=r["is_derivative"] or False,
                filing_date=r["filing_date"] or "",
                accession_number=r["accession_number"] or "",
            )
            for r in results
        ]

    @staticmethod
    async def get_insider_trade_summary(
        cik: str,
        days: int = 90,
    ) -> dict:
        """Get aggregated insider trading summary with signal classification."""
        since_date = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")

        query = """
            MATCH (c:Company {cik: $cik})-[:INSIDER_TRADE_OF]->(t:InsiderTransaction)
            WHERE t.filing_date >= $since_date
            RETURN t.insider_name as insider_name,
                   t.transaction_code as code,
                   t.shares as shares,
                   t.total_value as total_value,
                   t.transaction_date as txn_date
        """

        results = await Neo4jClient.execute_query(query, {
            "cik": cik,
            "since_date": since_date,
        })

        if not results:
            return {
                "total_transactions": 0,
                "unique_insiders": 0,
                "purchases": 0,
                "sales": 0,
                "awards": 0,
                "other": 0,
                "total_purchase_value": 0,
                "total_sale_value": 0,
                "net_value": 0,
                "signal_level": "none",
                "signal_summary": "No insider trading data",
                "buying_insiders": [],
            }

        unique_insiders = set()
        buying_insiders = set()
        purchases = 0
        sales = 0
        awards = 0
        other = 0
        total_purchase_value = 0.0
        total_sale_value = 0.0

        for r in results:
            name = r["insider_name"]
            code = r["code"]
            value = r["total_value"] or 0

            unique_insiders.add(name)

            if code == "P":
                purchases += 1
                total_purchase_value += value
                buying_insiders.add(name)
            elif code == "S":
                sales += 1
                total_sale_value += value
            elif code == "A":
                awards += 1
            else:
                other += 1

        # Classify the signal
        signal_level, signal_summary = InsiderTradingService.classify_insider_signal(
            results, days=30
        )

        return {
            "total_transactions": len(results),
            "unique_insiders": len(unique_insiders),
            "purchases": purchases,
            "sales": sales,
            "awards": awards,
            "other": other,
            "total_purchase_value": total_purchase_value,
            "total_sale_value": total_sale_value,
            "net_value": total_purchase_value - total_sale_value,
            "signal_level": signal_level,
            "signal_summary": signal_summary,
            "buying_insiders": list(buying_insiders),
        }

    @staticmethod
    def classify_insider_signal(
        trades: list[dict],
        days: int = 30,
    ) -> tuple[str, str]:
        """
        Classify insider trading signal.

        Focuses on recent trades (within `days`) for signal strength.

        Returns: (level, summary)
        """
        cutoff = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")

        recent_buyers = set()
        total_purchase_value = 0.0

        for t in trades:
            txn_date = t.get("txn_date") or t.get("transaction_date", "")
            if txn_date >= cutoff and t["code"] == "P":
                recent_buyers.add(t["insider_name"])
                total_purchase_value += (t.get("total_value") or 0)

        num_buyers = len(recent_buyers)

        # HIGH: 3+ insiders buying (cluster buy)
        if num_buyers >= 3:
            return "high", f"Cluster Buy - {num_buyers} insiders purchasing"

        # MEDIUM: 2 insiders buying, or single large purchase > $500K
        if num_buyers >= 2:
            return "medium", f"{num_buyers} insiders purchasing"
        if num_buyers == 1 and total_purchase_value > 500_000:
            buyer = list(recent_buyers)[0]
            return "medium", f"Large purchase by {buyer} (${total_purchase_value:,.0f})"

        # LOW: single purchase or routine activity
        if num_buyers == 1:
            buyer = list(recent_buyers)[0]
            return "low", f"Single purchase by {buyer}"

        return "none", "No recent purchases"
