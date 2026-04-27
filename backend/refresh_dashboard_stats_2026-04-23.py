"""Recompute DashboardStats{id:'hero'} from current mature strong_buy SP rows.

Why: After the 23-row DELETE, the DashboardStats blob still carries pre-delete
numbers (165, 63.6%, +6.6%) because it's only updated during compute_all.

This script reads current SP rows directly and MERGEs the stats node — no
recomputation of SignalPerformance, so the 23 deleted rows stay deleted.

Log: /tmp/refresh_dashboard_stats_2026-04-23.log
"""
import asyncio
import logging
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from app.db.neo4j_client import Neo4jClient

LOG_PATH = "/tmp/refresh_dashboard_stats_2026-04-23.log"
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    handlers=[logging.FileHandler(LOG_PATH), logging.StreamHandler()],
)
log = logging.getLogger(__name__)


async def main():
    await Neo4jClient.connect()

    # Read current DashboardStats (for before/after comparison)
    before = await Neo4jClient.execute_query(
        "MATCH (ds:DashboardStats {id: 'hero'}) "
        "RETURN ds.total_signals AS n, ds.hit_rate AS hit, ds.avg_alpha AS alpha, "
        "ds.beat_spy_pct AS beat, ds.computed_at AS at"
    )
    if before:
        b = before[0]
        log.info("BEFORE: total=%s hit_rate=%s alpha=%s beat_spy=%s computed_at=%s",
                 b["n"], b["hit"], b["alpha"], b["beat"], b["at"])

    # Fetch current mature strong_buy rows with the fields needed for stats
    rows = await Neo4jClient.execute_query(
        "MATCH (sp:SignalPerformance) "
        "WHERE sp.is_mature = true "
        "  AND sp.conviction_tier = 'strong_buy' "
        "  AND sp.direction = 'buy' "
        "RETURN sp.return_day0 AS return_day0, sp.spy_return_90d AS spy_return_90d"
    )
    n = len(rows)
    log.info("Current mature strong_buy rows: %d", n)
    if n == 0:
        log.error("No rows found — ABORTING")
        sys.exit(1)

    wins = sum(1 for r in rows if (r["return_day0"] or 0) > 0)
    hit_rate = round(wins / n * 100, 1)

    with_spy = [r for r in rows if r["spy_return_90d"] is not None]
    alphas = [(r["return_day0"] or 0) - (r["spy_return_90d"] or 0) for r in with_spy]
    avg_alpha = round(sum(alphas) / len(alphas), 1) if alphas else 0
    beat_spy = sum(1 for a in alphas if a > 0)
    beat_spy_pct = round(beat_spy / len(with_spy) * 100, 1) if with_spy else 0
    avg_return = round(sum((r["return_day0"] or 0) for r in rows) / n, 1)

    stats = {
        "total_signals": n,
        "wins": wins,
        "losses": n - wins,
        "hit_rate": hit_rate,
        "avg_return": avg_return,
        "avg_alpha": avg_alpha,
        "beat_spy_pct": beat_spy_pct,
        "computed_at": datetime.now().isoformat(),
    }

    log.info("NEW:    total=%s wins=%s losses=%s hit_rate=%s avg_return=%s avg_alpha=%s beat_spy=%s",
             stats["total_signals"], stats["wins"], stats["losses"], stats["hit_rate"],
             stats["avg_return"], stats["avg_alpha"], stats["beat_spy_pct"])

    await Neo4jClient.execute_query(
        "MERGE (ds:DashboardStats {id: 'hero'}) "
        "SET ds.total_signals = $total_signals, "
        "    ds.wins = $wins, "
        "    ds.losses = $losses, "
        "    ds.hit_rate = $hit_rate, "
        "    ds.avg_return = $avg_return, "
        "    ds.avg_alpha = $avg_alpha, "
        "    ds.beat_spy_pct = $beat_spy_pct, "
        "    ds.computed_at = $computed_at",
        stats,
    )
    log.info("DashboardStats updated.")


if __name__ == "__main__":
    asyncio.run(main())
