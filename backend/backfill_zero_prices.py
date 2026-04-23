"""Backfill zero-price insider transactions from SEC EDGAR Form 4 footnotes.

Finds all InsiderTransaction nodes with price_per_share = 0 and shares > 0,
fetches the original Form 4 XML from EDGAR, extracts the actual price from
footnotes, and updates the Neo4j nodes.

Usage:
    python backfill_zero_prices.py --dry-run    # Show what would change
    python backfill_zero_prices.py --apply       # Actually update Neo4j
"""

import asyncio
import re
import sys
import time
import xml.etree.ElementTree as ET

import requests

# Add app to path
sys.path.insert(0, ".")
from app.db.neo4j_client import Neo4jClient

EDGAR_HEADERS = {"User-Agent": "LookInsight research@lookinsight.ai"}
EDGAR_DELAY = 0.5  # seconds between requests


def parse_price_from_footnotes(xml_content: bytes, target_shares: float) -> float | None:
    """Parse Form 4 XML and extract price from footnotes for a specific transaction."""
    try:
        root = ET.fromstring(xml_content)
    except ET.ParseError:
        return None

    for txn in root.findall(".//nonDerivativeTransaction"):
        shares_elem = txn.find(".//transactionShares/value")
        if shares_elem is None:
            continue
        try:
            shares = float(shares_elem.text)
        except (ValueError, TypeError):
            continue

        # Match by share count (within 1 share tolerance for rounding)
        if abs(shares - target_shares) > 1:
            continue

        price_elem = txn.find(".//transactionPricePerShare/value")
        if price_elem is None:
            continue

        try:
            price = float(price_elem.text)
        except (ValueError, TypeError):
            price = 0

        # If price is already non-zero, return it
        if price > 0:
            return price

        # Price is 0 — check footnotes
        footnote_ids = [f.get("id") for f in txn.findall(".//transactionPricePerShare/footnoteId")]
        if not footnote_ids:
            continue

        # Find the footnote text
        for fn in root.findall(".//footnote"):
            fn_id = fn.get("id", "")
            if fn_id not in footnote_ids:
                continue
            if not fn.text:
                continue

            text = fn.text

            # Pattern 1: "ranged from $X to $Y"
            match = re.search(r"ranged from \$?([\d,]+\.?\d*)\s*to\s*\$?([\d,]+\.?\d*)", text)
            if match:
                low = float(match.group(1).replace(",", ""))
                high = float(match.group(2).replace(",", ""))
                return round((low + high) / 2, 4)

            # Pattern 2: "weighted average price of $X" or "average price was $X"
            match = re.search(r"(?:average price|price)(?:\s+was)?\s+(?:of\s+)?\$?([\d,]+\.?\d*)", text)
            if match:
                return float(match.group(1).replace(",", ""))

            # Pattern 3: "at a price of $X" or "at $X per share"
            match = re.search(r"at (?:a price of )?\$?([\d,]+\.?\d*)\s*(?:per share)?", text)
            if match:
                return float(match.group(1).replace(",", ""))

            # Pattern 4: just a dollar amount in the footnote
            match = re.search(r"\$([\d,]+\.?\d{2,})", text)
            if match:
                val = float(match.group(1).replace(",", ""))
                if val > 0.01:  # Sanity check — not zero or dust
                    return val

    return None


async def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else "--dry-run"
    is_apply = mode == "--apply"

    print(f"Mode: {'APPLY (will update Neo4j)' if is_apply else 'DRY RUN (no changes)'}")
    print()

    await Neo4jClient.connect()

    # Get all zero-price trades
    trades = await Neo4jClient.execute_query("""
        MATCH (c:Company)-[:INSIDER_TRADE_OF]->(t:InsiderTransaction)
        WHERE t.transaction_code IN ['P', 'S']
          AND (t.is_derivative IS NULL OR t.is_derivative = false)
          AND t.price_per_share = 0
          AND t.shares > 0
        RETURN t.id AS txn_id, t.accession_number AS accession,
               t.primary_document AS doc, t.insider_name AS name,
               t.shares AS shares, t.transaction_date AS date,
               t.transaction_code AS code,
               c.cik AS cik, c.tickers[0] AS ticker
        ORDER BY c.tickers[0], t.transaction_date
    """, {})

    print(f"Found {len(trades)} trades with price = $0\n")

    updated = 0
    skipped = 0
    failed = 0
    fetched_cache = {}

    for i, t in enumerate(trades):
        ticker = t["ticker"] or "N/A"
        cik = t["cik"].lstrip("0")
        accession = t["accession"]
        doc = t["doc"] or "primary_doc.xml"
        shares = t["shares"]

        # Build EDGAR URL
        acc_nodash = accession.replace("-", "")
        # Try the primary doc, strip xsl prefix if present
        if doc.startswith("xsl"):
            doc_name = doc.split("/")[-1]
        else:
            doc_name = doc
        url = f"https://www.sec.gov/Archives/edgar/data/{cik}/{acc_nodash}/{doc_name}"

        # Fetch XML (cache by accession — multiple trades per filing)
        if accession not in fetched_cache:
            try:
                resp = requests.get(url, headers=EDGAR_HEADERS, timeout=10)
                if resp.status_code == 200:
                    fetched_cache[accession] = resp.content
                else:
                    fetched_cache[accession] = None
                time.sleep(EDGAR_DELAY)
            except Exception as e:
                fetched_cache[accession] = None
                print(f"  FETCH ERROR: {ticker} {accession}: {e}")

        xml_content = fetched_cache.get(accession)
        if not xml_content:
            skipped += 1
            continue

        # Parse price from footnotes
        price = parse_price_from_footnotes(xml_content, shares)

        if price and price > 0 and price < 100_000:
            total_value = round(shares * price, 2)
            action = "UPDATE" if is_apply else "WOULD UPDATE"
            print(f"  {action}: {ticker:8s} {t['date']} {t['code']} {shares:>8,.0f} shares  $0 → ${price:,.4f}  total: ${total_value:,.2f}  ({t['name'][:25]})")

            if is_apply:
                await Neo4jClient.execute_write("""
                    MATCH (t:InsiderTransaction {id: $txn_id})
                    SET t.price_per_share = $price,
                        t.total_value = $total_value
                """, {"txn_id": t["txn_id"], "price": price, "total_value": total_value})

            updated += 1
        else:
            print(f"  SKIP: {ticker:8s} {t['date']} {t['code']} {shares:>8,.0f} shares  (no price in footnotes)")
            skipped += 1

    print(f"\n{'=' * 60}")
    print(f"  {'Updated' if is_apply else 'Would update'}: {updated}")
    print(f"  Skipped (no price found): {skipped}")
    print(f"  Total: {len(trades)}")

    await Neo4jClient.disconnect()


if __name__ == "__main__":
    asyncio.run(main())
