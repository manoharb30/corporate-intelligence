"""Purge InsiderTransaction rows with classification IS NULL.

These rows were written by the scanner path (InsiderTradingService.scan_and_store_company)
without going through the classification pipeline, so they carry no classification
metadata. They are invisible to cluster detection (which filters classification='GENUINE')
but occupy DB space and cause noisy pre-delete counts on every future re-ingest.

Safe because:
- detect_clusters already excludes them (classification='GENUINE' filter).
- Any valuable GENUINE-qualifying transaction they represent will be re-created by
  the next run_week.py ingest of the same date.

Log: /tmp/purge_null_classification_2026-04-24.log
"""
import asyncio
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from app.db.neo4j_client import Neo4jClient

LOG_PATH = "/tmp/purge_null_classification_2026-04-24.log"
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    handlers=[logging.FileHandler(LOG_PATH), logging.StreamHandler()],
)
log = logging.getLogger(__name__)


async def main():
    await Neo4jClient.connect()

    pre = await Neo4jClient.execute_query(
        "MATCH (t:InsiderTransaction) WHERE t.classification IS NULL RETURN count(t) AS n"
    )
    n_null = pre[0]["n"]
    log.info("Pre-delete: InsiderTransactions with NULL classification = %d", n_null)

    if n_null == 0:
        log.info("Nothing to delete.")
        return

    # Batch DETACH DELETE to keep single transaction under a reasonable size.
    # 44k rows * ~2 relationships each = ~132k writes; batching keeps memory bounded.
    batch_size = 2000
    total_deleted = 0
    while True:
        r = await Neo4jClient.execute_query(f"""
            MATCH (t:InsiderTransaction) WHERE t.classification IS NULL
            WITH t LIMIT {batch_size}
            DETACH DELETE t
            RETURN count(t) AS deleted
        """)
        deleted = r[0]["deleted"] if r else 0
        total_deleted += deleted
        log.info("Batch deleted: %d (cumulative %d)", deleted, total_deleted)
        if deleted == 0:
            break

    # Verify
    post = await Neo4jClient.execute_query(
        "MATCH (t:InsiderTransaction) WHERE t.classification IS NULL RETURN count(t) AS n"
    )
    log.info("Post-delete: NULL classification remaining = %d (expect 0)", post[0]["n"])

    # Orphan Person cleanup — some Persons existed only via these transactions
    orphan = await Neo4jClient.execute_query("""
        MATCH (p:Person) WHERE NOT (p)-[]-()
        DELETE p
        RETURN count(p) AS deleted
    """)
    log.info("Orphan Person nodes deleted: %d", orphan[0]["deleted"] if orphan else 0)

    # Total remaining transactions sanity check
    total = await Neo4jClient.execute_query(
        "MATCH (t:InsiderTransaction) RETURN count(t) AS n"
    )
    log.info("Total InsiderTransaction rows remaining in DB: %d", total[0]["n"])

    log.info("Done. Purged %d NULL-classification rows.", total_deleted)


if __name__ == "__main__":
    asyncio.run(main())
