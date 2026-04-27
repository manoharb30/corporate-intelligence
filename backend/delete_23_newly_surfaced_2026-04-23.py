"""Delete the 23 newly-surfaced mature strong_buy SignalPerformance rows.

Context: After Phase 18 fix + enrichment refresh on 2026-04-23, 23 SP rows with
is_mature=True and signal_dates between 2024-09 and 2025-12 surfaced in DB that
were silently dropped in prior compute_all runs (missing price/mcap data).

User decision 2026-04-23: mature cohort must remain at 142 (v1.0-v1.6 baseline).
These 23 are to be deleted.

Note: deletion alone is unstable — next compute_all will recreate them. A
separate cutoff rule in _compute_one is required for durability (open item).

Log: /tmp/delete_23_newly_surfaced_2026-04-23.log
"""
import asyncio
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from app.db.neo4j_client import Neo4jClient

LOG_PATH = "/tmp/delete_23_newly_surfaced_2026-04-23.log"
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    handlers=[logging.FileHandler(LOG_PATH), logging.StreamHandler()],
)
log = logging.getLogger(__name__)

# 23 (ticker, signal_date YYYY-MM-DD) pairs — from HANDOFF-2026-04-23.md
TARGETS = [
    ("QDEL", "2025-12-10"),
    ("LUCK", "2025-12-08"),
    ("GSHD", "2025-11-28"),
    ("RPD",  "2025-11-24"),
    ("PEBO", "2025-11-21"),
    ("BBWI", "2025-11-21"),
    ("EVLV", "2025-11-21"),
    ("GEF",  "2025-11-20"),
    ("ACVA", "2025-11-17"),
    ("SG",   "2025-11-12"),
    ("MTDR", "2025-11-06"),
    ("CBK",  "2025-10-03"),
    ("FRPT", "2025-09-15"),
    ("KRO",  "2025-08-13"),
    ("ICFI", "2025-06-09"),
    ("MG",   "2025-03-20"),
    ("FLNC", "2025-03-14"),
    ("CMTG", "2025-03-13"),
    ("RC",   "2025-03-12"),
    ("BFC",  "2025-03-04"),
    ("ACDC", "2025-02-26"),
    ("TCNNF","2024-11-21"),
    ("LMB",  "2024-09-12"),
]

MATCH_CLAUSE = """
MATCH (sp:SignalPerformance)
WHERE sp.is_mature = true
  AND sp.conviction_tier = 'strong_buy'
  AND sp.computed_at >= '2026-04-23'
  AND [sp.ticker, substring(sp.signal_date, 0, 10)] IN $targets
"""


async def main():
    await Neo4jClient.connect()

    targets = [[t, d] for t, d in TARGETS]
    log.info("Targets: %d pairs", len(targets))

    # Pre-check: total mature count + count of targets
    pre = await Neo4jClient.execute_query(
        "MATCH (sp:SignalPerformance) WHERE sp.is_mature = true AND sp.conviction_tier = 'strong_buy' "
        "RETURN count(sp) AS n"
    )
    log.info("Pre-delete mature strong_buy total: %d (expect 165)", pre[0]["n"])

    matches = await Neo4jClient.execute_query(
        MATCH_CLAUSE + "RETURN sp.ticker AS ticker, substring(sp.signal_date, 0, 10) AS d, "
                       "sp.signal_id AS signal_id, sp.computed_at AS computed_at "
                       "ORDER BY sp.signal_date DESC",
        {"targets": targets},
    )
    log.info("Matched rows: %d", len(matches))
    for m in matches:
        log.info("  %s  %s  %s  computed_at=%s", m["ticker"], m["d"], m["signal_id"], m["computed_at"])

    if len(matches) != 23:
        log.error("Expected 23 matches, got %d — ABORTING", len(matches))
        missing = {(t, d) for t, d in TARGETS} - {(m["ticker"], m["d"]) for m in matches}
        extra = {(m["ticker"], m["d"]) for m in matches} - {(t, d) for t, d in TARGETS}
        if missing:
            log.error("Missing from DB: %s", sorted(missing))
        if extra:
            log.error("Unexpected in DB: %s", sorted(extra))
        await Neo4jClient.close()
        sys.exit(1)

    # Delete
    result = await Neo4jClient.execute_query(
        MATCH_CLAUSE + "DETACH DELETE sp RETURN count(sp) AS deleted",
        {"targets": targets},
    )
    deleted = result[0]["deleted"]
    log.info("DELETED: %d rows", deleted)

    # Post-check
    post = await Neo4jClient.execute_query(
        "MATCH (sp:SignalPerformance) WHERE sp.is_mature = true AND sp.conviction_tier = 'strong_buy' "
        "RETURN count(sp) AS n"
    )
    log.info("Post-delete mature strong_buy total: %d (expect 142)", post[0]["n"])

    if post[0]["n"] != 142:
        log.error("POST-DELETE COUNT MISMATCH: got %d, expected 142", post[0]["n"])
        sys.exit(2)

    log.info("Success — mature cohort now at 142.")
    await Neo4jClient.close()


if __name__ == "__main__":
    asyncio.run(main())
