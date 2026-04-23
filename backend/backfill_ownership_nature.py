"""Backfill ownership_nature for existing indirect (I) InsiderTransaction nodes.

Optimized approach:
1. Group transactions by CIK (company) to minimize HTTP calls
2. Use primary_document when available (1 call) vs index.json fallback (2 calls)
3. Batch Neo4j updates per company
4. Periodic reconnect to prevent Aura timeout
5. Respectful SEC rate limiting with backoff on 503s
"""

import asyncio
import logging
import xml.etree.ElementTree as ET

import httpx

from app.db.neo4j_client import Neo4jClient

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

SEC_DELAY = 0.15  # seconds between EDGAR requests
BACKOFF_DELAY = 5.0  # seconds to wait after a 503
MAX_503_STREAK = 5  # after this many consecutive 503s, pause longer
RECONNECT_EVERY = 50  # reconnect Neo4j every N companies

SEC_HEADERS = {
    "User-Agent": "LookInsight manohar@lookinsight.ai",
    "Accept-Encoding": "gzip, deflate",
}


def extract_ownership_natures(xml_content: str) -> dict[str, str]:
    """Parse Form 4 XML and extract ownership_nature for all indirect transactions.

    Returns dict mapping transaction index pattern to nature string.
    Since a single filing may have multiple transactions, we return
    all indirect natures found. In practice most filings have one nature
    that applies to all indirect transactions.
    """
    try:
        root = ET.fromstring(xml_content)
    except ET.ParseError:
        return {}

    natures: list[str] = []
    for table_tag in ["nonDerivativeTable", "derivativeTable"]:
        table = root.find(table_tag)
        if table is None:
            continue
        for txn_tag in ["nonDerivativeTransaction", "nonDerivativeHolding",
                        "derivativeTransaction", "derivativeHolding"]:
            for txn in table.findall(txn_tag):
                ownership_elem = txn.find("ownershipNature")
                if ownership_elem is None:
                    continue
                doi = ownership_elem.find("directOrIndirectOwnership/value")
                if doi is not None and doi.text and doi.text.strip() == "I":
                    nature_elem = ownership_elem.find("natureOfOwnership/value")
                    if nature_elem is not None and nature_elem.text and nature_elem.text.strip():
                        natures.append(nature_elem.text.strip())

    # Return the most common nature (usually all the same within one filing)
    if natures:
        return {"nature": max(set(natures), key=natures.count)}
    return {}


async def fetch_xml_direct(client: httpx.AsyncClient, cik: str, accession: str, primary_doc: str) -> str | None:
    """Fetch Form 4 XML directly using known primary_document filename. 1 HTTP call."""
    clean_acc = accession.replace("-", "")
    # primary_doc may have xslF345X05/ prefix — strip it for raw XML
    doc_name = primary_doc.split("/")[-1] if "/" in primary_doc else primary_doc
    url = f"https://www.sec.gov/Archives/edgar/data/{cik}/{clean_acc}/{doc_name}"
    try:
        resp = await client.get(url, follow_redirects=True)
        if resp.status_code == 200:
            return resp.text
        if resp.status_code == 503:
            return "503"
    except Exception:
        pass
    return None


async def fetch_xml_via_index(client: httpx.AsyncClient, cik: str, accession: str) -> str | None:
    """Fetch Form 4 XML via index.json lookup. 2 HTTP calls."""
    clean_acc = accession.replace("-", "")
    url = f"https://www.sec.gov/Archives/edgar/data/{cik}/{clean_acc}/index.json"
    try:
        resp = await client.get(url, follow_redirects=True)
        if resp.status_code == 503:
            return "503"
        if resp.status_code != 200:
            return None
        index_data = resp.json()
        for item in index_data.get("directory", {}).get("item", []):
            name = item.get("name", "")
            if name.endswith(".xml") and "index" not in name.lower() and "R" not in name:
                xml_url = f"https://www.sec.gov/Archives/edgar/data/{cik}/{clean_acc}/{name}"
                xml_resp = await client.get(xml_url, follow_redirects=True)
                if xml_resp.status_code == 200:
                    return xml_resp.text
                if xml_resp.status_code == 503:
                    return "503"
                break
    except Exception:
        pass
    return None


async def main():
    await Neo4jClient.connect()

    # Get remaining I-type transactions grouped by company CIK, then by accession
    rows = await Neo4jClient.execute_query("""
        MATCH (c:Company)-[:INSIDER_TRADE_OF]->(t:InsiderTransaction)
        WHERE t.ownership_type = 'I'
          AND t.ownership_nature IS NULL
          AND t.accession_number IS NOT NULL
        WITH c.cik as cik,
             t.accession_number as accession,
             collect(t.id) as txn_ids,
             head(collect(t.primary_document)) as primary_doc
        ORDER BY cik, accession
        RETURN cik, collect({accession: accession, txn_ids: txn_ids, primary_doc: primary_doc}) as filings
    """, {})

    total_companies = len(rows)
    total_filings = sum(len(r["filings"]) for r in rows)
    logger.info(f"Companies: {total_companies}, Filings: {total_filings}")

    updated = 0
    skipped = 0
    errors = 0
    http_calls = 0
    consecutive_503 = 0

    async with httpx.AsyncClient(headers=SEC_HEADERS, timeout=15.0) as client:
        for ci, row in enumerate(rows):
            cik = row["cik"].lstrip("0") or row["cik"]
            filings = row["filings"]

            # Periodic Neo4j reconnect
            if ci > 0 and ci % RECONNECT_EVERY == 0:
                logger.info(f"Reconnecting Neo4j after {ci} companies")
                await Neo4jClient.reconnect()

            # Process each filing for this company
            natures_to_write: list[tuple[list[str], str]] = []  # (txn_ids, nature)
            empties_to_write: list[str] = []  # txn_ids with no nature

            for filing in filings:
                accession = filing["accession"]
                txn_ids = filing["txn_ids"]
                primary_doc = filing["primary_doc"]

                # Try direct fetch first if we have primary_document
                xml_content = None
                if primary_doc:
                    xml_content = await fetch_xml_direct(client, cik, accession, primary_doc)
                    http_calls += 1
                    if xml_content == "503":
                        consecutive_503 += 1
                        xml_content = None
                        if consecutive_503 >= MAX_503_STREAK:
                            logger.info(f"  {consecutive_503} consecutive 503s — backing off {BACKOFF_DELAY * 3}s")
                            await asyncio.sleep(BACKOFF_DELAY * 3)
                            consecutive_503 = 0
                        else:
                            await asyncio.sleep(BACKOFF_DELAY)
                        continue
                    elif xml_content is None:
                        # Direct fetch failed (404 etc), try index fallback
                        xml_content = await fetch_xml_via_index(client, cik, accession)
                        http_calls += 2
                else:
                    # No primary_document, use index
                    xml_content = await fetch_xml_via_index(client, cik, accession)
                    http_calls += 2

                if xml_content == "503":
                    consecutive_503 += 1
                    if consecutive_503 >= MAX_503_STREAK:
                        logger.info(f"  {consecutive_503} consecutive 503s — backing off {BACKOFF_DELAY * 3}s")
                        await asyncio.sleep(BACKOFF_DELAY * 3)
                        consecutive_503 = 0
                    else:
                        await asyncio.sleep(BACKOFF_DELAY)
                    continue

                consecutive_503 = 0  # reset on success

                if xml_content:
                    result = extract_ownership_natures(xml_content)
                    nature = result.get("nature", "")
                    if nature:
                        natures_to_write.append((txn_ids, nature))
                        updated += len(txn_ids)
                    else:
                        empties_to_write.extend(txn_ids)
                        skipped += len(txn_ids)
                else:
                    empties_to_write.extend(txn_ids)
                    skipped += len(txn_ids)

                await asyncio.sleep(SEC_DELAY)

            # Batch write all natures for this company (with retry on connection failure)
            try:
                for txn_ids, nature in natures_to_write:
                    await Neo4jClient.execute_write("""
                        UNWIND $ids as id
                        MATCH (t:InsiderTransaction {id: id})
                        SET t.ownership_nature = $nature
                    """, {"ids": txn_ids, "nature": nature})

                if empties_to_write:
                    await Neo4jClient.execute_write("""
                        UNWIND $ids as id
                        MATCH (t:InsiderTransaction {id: id})
                        SET t.ownership_nature = ''
                    """, {"ids": empties_to_write})
            except Exception as e:
                logger.warning(f"Neo4j write failed for CIK {cik}, reconnecting: {e}")
                await Neo4jClient.reconnect()
                # Retry once
                try:
                    for txn_ids, nature in natures_to_write:
                        await Neo4jClient.execute_write("""
                            UNWIND $ids as id
                            MATCH (t:InsiderTransaction {id: id})
                            SET t.ownership_nature = $nature
                        """, {"ids": txn_ids, "nature": nature})
                    if empties_to_write:
                        await Neo4jClient.execute_write("""
                            UNWIND $ids as id
                            MATCH (t:InsiderTransaction {id: id})
                            SET t.ownership_nature = ''
                        """, {"ids": empties_to_write})
                except Exception as e2:
                    logger.error(f"Neo4j retry failed for CIK {cik}: {e2}")
                    errors += len(natures_to_write) + len(empties_to_write)

            if (ci + 1) % 50 == 0:
                logger.info(
                    f"[{ci+1}/{total_companies}] updated: {updated}, skipped: {skipped}, "
                    f"errors: {errors}, http_calls: {http_calls}"
                )

    logger.info(
        f"BACKFILL COMPLETE — updated: {updated}, skipped: {skipped}, "
        f"errors: {errors}, http_calls: {http_calls}"
    )

    # Show distribution
    dist = await Neo4jClient.execute_query("""
        MATCH (t:InsiderTransaction)
        WHERE t.ownership_type = 'I' AND t.ownership_nature IS NOT NULL AND t.ownership_nature <> ''
        RETURN t.ownership_nature as nature, count(*) as cnt
        ORDER BY cnt DESC LIMIT 20
    """, {})
    logger.info("Ownership nature distribution:")
    for r in dist:
        logger.info(f"  {r['nature']:40s} : {r['cnt']:>5,}")

    await Neo4jClient.disconnect()


if __name__ == "__main__":
    asyncio.run(main())
