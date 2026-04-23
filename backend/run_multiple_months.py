"""Run multiple monthly pipelines sequentially (set-and-forget mode).

Wraps run_month.py to process a list of months in order without manual trigger.
If one month halts (e.g., consecutive day failures), the wrapper continues to
the next month — each month is independent.

Optional --wipe-each flag: deletes all InsiderTransaction records for each
month before processing (clean-slate pattern, matches what we did manually
for Aug 2025).

Usage:
    # Sequential processing
    python run_multiple_months.py --months 2025-09 2025-06 2025-05

    # Clean-slate wipe per month before running
    python run_multiple_months.py --months 2025-09 2025-06 --wipe-each

    # Different worker count
    python run_multiple_months.py --months 2025-09 2025-06 --workers 5
"""

import argparse
import asyncio
import subprocess
import sys
import time
from datetime import datetime

sys.stdout.reconfigure(line_buffering=True)
sys.path.insert(0, ".")

PY = "venv/bin/python"


async def wipe_month(year_month: str) -> tuple[int, int]:
    """Delete all InsiderTransaction records with filing_date in the month.

    Returns (records_deleted, orphan_persons_deleted).
    """
    from app.db.neo4j_client import Neo4jClient
    await Neo4jClient.connect()
    r = await Neo4jClient.execute_query("""
        MATCH (t:InsiderTransaction)
        WHERE t.filing_date STARTS WITH $prefix
        DETACH DELETE t
        RETURN count(t) AS deleted
    """, {"prefix": year_month})
    deleted = r[0]["deleted"] if r else 0

    r2 = await Neo4jClient.execute_query("""
        MATCH (p:Person) WHERE NOT (p)-[]-()
        DELETE p
        RETURN count(p) AS deleted
    """)
    orphans = r2[0]["deleted"] if r2 else 0

    await Neo4jClient.disconnect()
    return deleted, orphans


def run_one_month(year_month: str, workers: int) -> int:
    """Run run_month.py for one month. Returns subprocess exit code."""
    return subprocess.run([
        PY, "run_month.py", "--month", year_month, "--workers", str(workers)
    ]).returncode


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--months", nargs="+", required=True,
                    help="Months in YYYY-MM format (e.g., 2025-09 2025-06 2025-05)")
    ap.add_argument("--workers", type=int, default=10,
                    help="LLM workers per month (default: 10)")
    ap.add_argument("--wipe-each", action="store_true",
                    help="Wipe each month's records before processing (clean slate)")
    args = ap.parse_args()

    # Validate all month formats upfront
    for m in args.months:
        try:
            datetime.strptime(m, "%Y-%m")
        except ValueError:
            print(f"ERROR: invalid month format '{m}' (expected YYYY-MM)")
            sys.exit(1)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_path = f"/tmp/run_multiple_months_{timestamp}.log"
    log_file = open(log_path, "w", buffering=1)

    def log(msg):
        print(msg, flush=True)
        log_file.write(msg + "\n")
        log_file.flush()

    log(f"Multi-month pipeline")
    log(f"Months ({len(args.months)}): {args.months}")
    log(f"LLM workers per month: {args.workers}")
    log(f"Wipe each month first: {args.wipe_each}")
    log(f"Log: {log_path}\n")

    start = time.time()
    results = []  # list of (month, exit_code, elapsed_sec, wipe_info)

    for i, month in enumerate(args.months, 1):
        log(f"\n{'#' * 72}")
        log(f"MONTH {i}/{len(args.months)}: {month}")
        log(f"{'#' * 72}")
        month_start = time.time()

        wipe_info = None
        if args.wipe_each:
            log(f"\n[Wipe] Deleting existing records for {month}...")
            try:
                deleted, orphans = asyncio.run(wipe_month(month))
                log(f"  Deleted {deleted} records, {orphans} orphan Persons")
                wipe_info = (deleted, orphans)
            except Exception as e:
                log(f"  ⚠️  Wipe failed: {e}")
                log(f"  Continuing anyway — per-day delete in ingest is safety net")

        log(f"\n[Pipeline] Starting run_month for {month}...")
        exit_code = run_one_month(month, args.workers)
        elapsed = round(time.time() - month_start, 1)

        status = "✓ OK" if exit_code == 0 else f"✗ FAILED (exit {exit_code})"
        log(f"\n[{month}] {status} ({elapsed/60:.1f} min)")
        results.append((month, exit_code, elapsed, wipe_info))

    total_elapsed = round(time.time() - start, 1)

    # Final summary
    log(f"\n\n{'=' * 72}")
    log(f"  MULTI-MONTH PIPELINE COMPLETE — {total_elapsed/60:.1f} min total")
    log(f"{'=' * 72}")
    log(f"{'Month':10} {'Status':15} {'Time':>8}  {'Wiped':>8}")
    log("-" * 55)
    ok = failed = 0
    for month, code, elapsed, wipe in results:
        status = "OK" if code == 0 else f"FAILED ({code})"
        wipe_str = f"{wipe[0]}" if wipe else "-"
        log(f"{month:10} {status:15} {elapsed/60:>6.1f}m  {wipe_str:>8}")
        if code == 0:
            ok += 1
        else:
            failed += 1
    log(f"\n  Summary: {ok} OK, {failed} failed")
    log(f"  Per-month reports: see /tmp/run_month_YYYYMM.log")

    log_file.close()


if __name__ == "__main__":
    main()
