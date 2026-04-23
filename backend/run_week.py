"""Weekly Form 4 P transaction pipeline runner.

Runs the 5-step pipeline (fetch → filter → parse → classify → ingest) for each
US trading day in a date range. Halts on any non-zero subprocess exit.

Skip-if-exists: If intermediate files exist, that step is skipped. This makes
the pipeline resumable if it crashes mid-week.

Ingest always runs (it uses delete-then-insert, so is idempotent).

Usage:
    python run_week.py --start 2025-10-13 --days 5
"""

import argparse
import json
import os
import shutil
import subprocess
import sys
import time
from datetime import datetime, timedelta

sys.stdout.reconfigure(line_buffering=True)

# SEC federal holidays (SEC closed, daily master.idx not published)
# Covers 2024, 2025, 2026. Good Friday NOT included — SEC is open even though NYSE is closed.
SEC_HOLIDAYS = {
    # 2024
    "2024-01-01",  # New Year's Day
    "2024-01-15",  # MLK Day
    "2024-02-19",  # Presidents Day
    "2024-05-27",  # Memorial Day
    "2024-06-19",  # Juneteenth
    "2024-07-04",  # Independence Day
    "2024-09-02",  # Labor Day
    "2024-10-14",  # Columbus Day
    "2024-11-11",  # Veterans Day
    "2024-11-28",  # Thanksgiving
    "2024-12-25",  # Christmas
    # 2025
    "2025-01-01",  # New Year's Day
    "2025-01-09",  # National Day of Mourning (Carter) — federal offices closed
    "2025-01-20",  # MLK Day
    "2025-02-17",  # Presidents Day
    "2025-05-26",  # Memorial Day
    "2025-06-19",  # Juneteenth
    "2025-07-04",  # Independence Day
    "2025-09-01",  # Labor Day
    "2025-10-13",  # Columbus Day
    "2025-11-11",  # Veterans Day
    "2025-11-27",  # Thanksgiving
    "2025-12-25",  # Christmas
    # 2026
    "2026-01-01",  # New Year's Day (Thu)
    "2026-01-19",  # MLK Day (Mon)
    "2026-02-16",  # Presidents Day (Mon)
    "2026-05-25",  # Memorial Day (Mon)
    "2026-06-19",  # Juneteenth (Fri)
    "2026-07-03",  # Independence Day observed (Fri, Jul 4 is Sat)
    "2026-09-07",  # Labor Day (Mon)
    "2026-10-12",  # Columbus Day (Mon)
    "2026-11-11",  # Veterans Day (Wed)
    "2026-11-26",  # Thanksgiving (Thu)
    "2026-12-25",  # Christmas (Fri)
}


def is_trading_day(d: datetime) -> bool:
    """SEC business day check — weekday AND not a federal holiday."""
    if d.weekday() >= 5:  # Saturday=5, Sunday=6
        return False
    if d.strftime("%Y-%m-%d") in SEC_HOLIDAYS:
        return False
    return True


def get_trading_days(start: str, count: int) -> list[str]:
    """Return N consecutive US trading days starting from `start` (skipping non-trading)."""
    days = []
    d = datetime.strptime(start, "%Y-%m-%d")
    while len(days) < count:
        if is_trading_day(d):
            days.append(d.strftime("%Y-%m-%d"))
        d += timedelta(days=1)
    return days


def run_step(cmd: list, step_name: str, log) -> None:
    """Run a subprocess. Halt script on non-zero exit."""
    log(f"  → {step_name}")
    result = subprocess.run(cmd)
    if result.returncode != 0:
        log(f"  ✗ HALT: {step_name} exited with code {result.returncode}")
        sys.exit(result.returncode)


def summarize_day(date: str) -> dict:
    """Read day's classified JSON and extract stats for summary table."""
    date_compact = date.replace("-", "")
    classified = f"form4_index_{date_compact}_p_classified.json"
    if not os.path.exists(classified):
        return {"date": date, "total": 0, "genuine": 0, "llm": 0}
    with open(classified) as f:
        data = json.load(f)
    counts = data.get("classification_counts", {})
    return {
        "date": date,
        "total": data.get("total_classified", 0),
        "genuine": counts.get("GENUINE", 0),
        "not_genuine": counts.get("NOT_GENUINE", 0),
        "ambiguous": counts.get("AMBIGUOUS", 0),
        "error": counts.get("PARSE_ERROR", 0) + counts.get("API_ERROR", 0),
        "prefilter": data.get("prefilter_caught", 0),
        "llm": data.get("llm_called", 0),
    }


def run_day(date: str, log, workers: int = 10) -> None:
    """Run the pipeline for a single trading day using the split architecture.

    Steps: fetch → filter → parse → prefilter → batch_llm → merge → ingest
    """
    date_compact = date.replace("-", "")
    py = "venv/bin/python"
    WORKERS = workers

    # File paths
    index_path = f"/tmp/form4_index_{date_compact}.json"
    p_only_path = f"/tmp/form4_index_{date_compact}_p_only.json"
    p_parsed_tmp = f"/tmp/form4_index_{date_compact}_p_parsed.json"
    p_parsed_local = f"form4_index_{date_compact}_p_parsed.json"
    p_prefiltered = f"form4_index_{date_compact}_p_prefiltered.json"
    p_queue = f"form4_index_{date_compact}_p_llm_queue.json"
    p_classified_path = f"form4_index_{date_compact}_p_classified.json"

    log(f"\n{'=' * 70}")
    log(f"DAY: {date}")
    log(f"{'=' * 70}")

    # Step 1: Fetch index
    if os.path.exists(index_path):
        log(f"  ⊘ Skip fetch (exists)")
    else:
        run_step([py, "fetch_form4_index.py", "--date", date], "fetch", log)

    # Step 2: Filter to P-only
    if os.path.exists(p_only_path):
        log(f"  ⊘ Skip filter (exists)")
    else:
        run_step([py, "filter_form4_p_only.py", "--input", index_path], "filter", log)

    # Step 3: Parse XML → JSON
    if os.path.exists(p_parsed_tmp):
        log(f"  ⊘ Skip parse (exists)")
    else:
        run_step([py, "parse_form4_p_to_json.py", "--input", p_only_path], "parse", log)

    # Copy parsed JSON to CWD (downstream scripts expect local path)
    if not os.path.exists(p_parsed_local):
        shutil.copy(p_parsed_tmp, p_parsed_local)

    # Step 4a: Prefilter (produces prefiltered.json + llm_queue.json)
    if os.path.exists(p_prefiltered) and os.path.exists(p_queue):
        log(f"  ⊘ Skip prefilter (exists)")
    else:
        run_step([py, "prefilter_p.py", "--input", p_parsed_local], "prefilter", log)

    # Step 4b: Batch LLM classify (parallel workers even for single day)
    run_step([py, "batch_llm_classify.py", "--workers", str(WORKERS),
              "--queues", p_queue], "batch_llm", log)

    # Step 4c: Merge prefilter + LLM results → classified.json
    run_step([py, "merge_classifications.py", "--date", date], "merge", log)

    # Step 5: Ingest to Neo4j (delete-then-insert; always runs; unchanged)
    run_step([py, "ingest_genuine_p_to_neo4j.py", "--date", date], "ingest", log)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--start", required=True, help="Start date YYYY-MM-DD")
    ap.add_argument("--days", type=int, required=True,
                    help="Number of trading days to process (skips weekends/holidays)")
    ap.add_argument("--workers", type=int, default=10,
                    help="Parallel LLM workers for Phase B (default: 10)")
    args = ap.parse_args()

    trading_days = get_trading_days(args.start, args.days)

    log_path = (f"/tmp/run_week_{trading_days[0].replace('-','')}_"
                f"{trading_days[-1].replace('-','')}.log")
    log_file = open(log_path, "w", buffering=1)

    def log(msg):
        print(msg, flush=True)
        log_file.write(msg + "\n")
        log_file.flush()

    log(f"Week pipeline")
    log(f"Trading days: {trading_days}")
    log(f"LLM workers: {args.workers}")
    log(f"Log: {log_path}\n")

    start = time.time()
    for date in trading_days:
        run_day(date, log, workers=args.workers)
    elapsed = round(time.time() - start, 1)

    # Summary table
    log(f"\n{'=' * 70}")
    log(f"WEEK COMPLETE — {len(trading_days)} days in {elapsed}s ({elapsed/60:.1f} min)")
    log(f"{'=' * 70}")
    log(f"{'Date':12} {'Total':>6} {'Prefilter':>10} {'LLM':>5} "
        f"{'Genuine':>8} {'NotGen':>7} {'Ambig':>6} {'Err':>4}")
    log("-" * 70)
    totals = {"total": 0, "prefilter": 0, "llm": 0, "genuine": 0,
              "not_genuine": 0, "ambiguous": 0, "error": 0}
    for date in trading_days:
        s = summarize_day(date)
        log(f"{s['date']:12} {s['total']:>6} {s['prefilter']:>10} {s['llm']:>5} "
            f"{s['genuine']:>8} {s['not_genuine']:>7} {s['ambiguous']:>6} {s['error']:>4}")
        for k in totals:
            totals[k] += s.get(k, 0)
    log("-" * 70)
    log(f"{'TOTAL':12} {totals['total']:>6} {totals['prefilter']:>10} "
        f"{totals['llm']:>5} {totals['genuine']:>8} {totals['not_genuine']:>7} "
        f"{totals['ambiguous']:>6} {totals['error']:>4}")
    log(f"{'=' * 70}")

    log_file.close()


if __name__ == "__main__":
    main()
