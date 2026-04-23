"""Monthly Form 4 P transaction pipeline runner.

Wraps run_week.py to process an entire month of SEC trading days.

Features:
  - Auto-resolves all trading days in the given month (skips weekends + SEC holidays)
  - Delegates each day to `run_week.py --days 1` via subprocess (failure isolation)
  - Halts on N consecutive day failures (default: 2). Tolerates transient blips.
  - Per-week mini-summary printed after each Friday
  - End-of-month report:
      * Per-day breakdown table
      * Top 5 high-volume days by GENUINE count
      * Single-buyer signals >= $500K
      * Multi-buyer clusters in the month window
      * AMBIGUOUS classifications list (for manual review)
      * LLM call count + cost estimate

Usage:
    python run_month.py --month 2025-11
    python run_month.py --month 2025-11 --halt-after 3   # more tolerant
"""

import argparse
import asyncio
import calendar
import json
import os
import subprocess
import sys
import time
from datetime import datetime

sys.stdout.reconfigure(line_buffering=True)

# Reuse SEC holiday calendar + trading-day logic from run_week
sys.path.insert(0, ".")
from run_week import SEC_HOLIDAYS, is_trading_day, summarize_day


# Haiku 4.5 pricing (approximate — input + output blended)
# Based on typical P classification payload (~1500 in, ~100 out)
COST_PER_LLM_CALL = 0.0016  # ~$0.16 per 100 calls


def get_trading_days_in_month(year_month: str) -> list[str]:
    """Return list of trading days (YYYY-MM-DD) in the given month.

    Args:
        year_month: format "YYYY-MM" (e.g., "2025-11")
    """
    year, month = map(int, year_month.split("-"))
    days_in_month = calendar.monthrange(year, month)[1]
    trading_days = []
    for day in range(1, days_in_month + 1):
        d = datetime(year, month, day)
        if is_trading_day(d):
            trading_days.append(d.strftime("%Y-%m-%d"))
    return trading_days


PY = "venv/bin/python"


def run_subprocess(cmd: list) -> int:
    """Run subprocess, return exit code."""
    return subprocess.run(cmd).returncode


def run_phase_a_for_day(date: str, log) -> int:
    """Phase A: fetch → filter → parse → prefilter for single day.

    Uses skip-if-exists at each step. Returns exit code (0 = success).
    """
    date_compact = date.replace("-", "")
    index_path = f"/tmp/form4_index_{date_compact}.json"
    p_only_path = f"/tmp/form4_index_{date_compact}_p_only.json"
    p_parsed_tmp = f"/tmp/form4_index_{date_compact}_p_parsed.json"
    p_parsed_local = f"form4_index_{date_compact}_p_parsed.json"
    p_prefiltered = f"form4_index_{date_compact}_p_prefiltered.json"
    p_queue = f"form4_index_{date_compact}_p_llm_queue.json"

    log(f"  [Phase A] {date}")

    if not os.path.exists(index_path):
        code = run_subprocess([PY, "fetch_form4_index.py", "--date", date])
        if code != 0:
            return code

    if not os.path.exists(p_only_path):
        code = run_subprocess([PY, "filter_form4_p_only.py", "--input", index_path])
        if code != 0:
            return code

    if not os.path.exists(p_parsed_tmp):
        code = run_subprocess([PY, "parse_form4_p_to_json.py", "--input", p_only_path])
        if code != 0:
            return code

    if not os.path.exists(p_parsed_local):
        import shutil
        shutil.copy(p_parsed_tmp, p_parsed_local)

    if not (os.path.exists(p_prefiltered) and os.path.exists(p_queue)):
        code = run_subprocess([PY, "prefilter_p.py", "--input", p_parsed_local])
        if code != 0:
            return code

    return 0


def run_phase_b(trading_days: list[str], workers: int, log) -> int:
    """Phase B: single batch LLM call across all days' queue files.

    Collects all *_p_llm_queue.json files for the trading days, runs them
    through batch_llm_classify.py in one parallel pass.
    """
    queue_paths = []
    for date in trading_days:
        date_compact = date.replace("-", "")
        path = f"form4_index_{date_compact}_p_llm_queue.json"
        if os.path.exists(path):
            queue_paths.append(path)

    if not queue_paths:
        log("  [Phase B] No queue files found — nothing to classify")
        return 0

    log(f"  [Phase B] Batch LLM across {len(queue_paths)} queue files, {workers} workers")
    cmd = [PY, "batch_llm_classify.py", "--workers", str(workers), "--queues"] + queue_paths
    return run_subprocess(cmd)


def run_phase_c_for_day(date: str, log) -> int:
    """Phase C: merge + ingest for single day. Returns exit code."""
    log(f"  [Phase C] {date}")
    code = run_subprocess([PY, "merge_classifications.py", "--date", date])
    if code != 0:
        return code
    return run_subprocess([PY, "ingest_genuine_p_to_neo4j.py", "--date", date])


def collect_ambiguous(trading_days: list[str]) -> list[dict]:
    """Read each day's classified JSON and collect all AMBIGUOUS classifications."""
    ambiguous = []
    for date in trading_days:
        date_compact = date.replace("-", "")
        path = f"form4_index_{date_compact}_p_classified.json"
        if not os.path.exists(path):
            continue
        with open(path) as f:
            data = json.load(f)
        for r in data.get("results", []):
            if r.get("classification") == "AMBIGUOUS":
                ambiguous.append({
                    "date": date,
                    "accession": r.get("accession", ""),
                    "issuer": r.get("issuer", ""),
                    "insider": r.get("insider", ""),
                    "total_value": r.get("total_value", 0),
                    "reason": r.get("reason", ""),
                })
    return ambiguous


async def query_month_clusters(year_month: str) -> tuple[list[dict], list[dict]]:
    """Query Neo4j for clusters and big single buyers in the month.

    Returns (clusters, big_buyers) — uses GENUINE-only data.
    """
    from app.db.neo4j_client import Neo4jClient

    year, month = year_month.split("-")
    month_start = f"{year}-{month}-01"
    days_in_month = calendar.monthrange(int(year), int(month))[1]
    month_end = f"{year}-{month}-{days_in_month:02d}"

    await Neo4jClient.connect()

    # Multi-buyer clusters (>= 2 distinct buyers on same company in month window)
    cluster_query = """
        MATCH (c:Company)-[:INSIDER_TRADE_OF]->(t:InsiderTransaction)<-[:TRADED_BY]-(p:Person)
        WHERE t.classification = 'GENUINE'
          AND t.transaction_date >= $start
          AND t.transaction_date <= $end
          AND t.transaction_code = 'P'
        WITH c, count(DISTINCT p.name) AS num_buyers,
             sum(t.total_value) AS total_value,
             collect(DISTINCT p.name) AS buyer_names,
             min(t.transaction_date) AS first_date,
             max(t.transaction_date) AS last_date
        WHERE num_buyers >= 2
        RETURN c.name AS company, c.cik AS cik, c.tickers AS tickers,
               num_buyers, total_value, buyer_names, first_date, last_date
        ORDER BY num_buyers DESC, total_value DESC
    """
    clusters = await Neo4jClient.execute_query(
        cluster_query, {"start": month_start, "end": month_end}
    )

    # High-value single buyers (>= $500K)
    big_buyer_query = """
        MATCH (c:Company)-[:INSIDER_TRADE_OF]->(t:InsiderTransaction)<-[:TRADED_BY]-(p:Person)
        WHERE t.classification = 'GENUINE'
          AND t.transaction_date >= $start
          AND t.transaction_date <= $end
          AND t.transaction_code = 'P'
        WITH c, p, sum(t.total_value) AS val,
             collect(t.transaction_date)[0] AS d,
             collect(t.insider_title)[0] AS title
        WHERE val >= 500000
        RETURN c.name AS company, c.tickers AS tickers, p.name AS insider,
               title, val, d
        ORDER BY val DESC
    """
    big_buyers = await Neo4jClient.execute_query(
        big_buyer_query, {"start": month_start, "end": month_end}
    )

    await Neo4jClient.disconnect()
    return clusters, big_buyers


def print_week_summary(trading_days: list[str], week_idx: int, log) -> None:
    """Print compact summary for the most recent 5-day week block."""
    start_idx = week_idx * 5
    week_days = trading_days[start_idx:start_idx + 5]
    if not week_days:
        return

    log(f"\n{'- ' * 35}")
    log(f"Week {week_idx + 1} mini-summary ({week_days[0]} to {week_days[-1]})")
    log(f"{'Date':12} {'P':>4} {'Gen':>4} {'LLM':>4}")
    week_tot = {"total": 0, "genuine": 0, "llm": 0}
    for d in week_days:
        s = summarize_day(d)
        log(f"{d:12} {s['total']:>4} {s['genuine']:>4} {s['llm']:>4}")
        week_tot["total"] += s["total"]
        week_tot["genuine"] += s.get("genuine", 0)
        week_tot["llm"] += s.get("llm", 0)
    log(f"{'WEEK':12} {week_tot['total']:>4} {week_tot['genuine']:>4} {week_tot['llm']:>4}")
    log(f"{'- ' * 35}\n")


def print_report(
    year_month: str,
    trading_days_done: list[str],
    trading_days_all: list[str],
    clusters: list[dict],
    big_buyers: list[dict],
    ambiguous: list[dict],
    elapsed: float,
    log,
) -> None:
    """Print end-of-month report."""
    log(f"\n{'=' * 72}")
    log(f"  MONTH REPORT — {year_month}")
    log(f"{'=' * 72}")
    log(f"Trading days: {len(trading_days_done)} / {len(trading_days_all)} processed")
    log(f"Elapsed:      {elapsed/60:.1f} min")
    log("")

    # Per-day breakdown
    log(f"{'Date':12} {'Total':>6} {'Prefilter':>10} {'LLM':>5} "
        f"{'Genuine':>8} {'NotGen':>7} {'Ambig':>6} {'Err':>4}")
    log("-" * 72)
    totals = {"total": 0, "prefilter": 0, "llm": 0, "genuine": 0,
              "not_genuine": 0, "ambiguous": 0, "error": 0}
    day_summaries = []
    for d in trading_days_done:
        s = summarize_day(d)
        day_summaries.append(s)
        log(f"{s['date']:12} {s['total']:>6} {s['prefilter']:>10} {s['llm']:>5} "
            f"{s['genuine']:>8} {s['not_genuine']:>7} "
            f"{s.get('ambiguous', 0):>6} {s.get('error', 0):>4}")
        for k in totals:
            totals[k] += s.get(k, 0)
    log("-" * 72)
    log(f"{'TOTAL':12} {totals['total']:>6} {totals['prefilter']:>10} "
        f"{totals['llm']:>5} {totals['genuine']:>8} {totals['not_genuine']:>7} "
        f"{totals['ambiguous']:>6} {totals['error']:>4}")

    # Top 5 high-volume days
    top5 = sorted(day_summaries, key=lambda x: x["genuine"], reverse=True)[:5]
    log(f"\n📊 Top 5 days by GENUINE count:")
    for s in top5:
        if s["genuine"] > 0:
            log(f"  {s['date']:12} — {s['genuine']:>3} GENUINE ({s['total']} total P txns)")

    # LLM cost estimate
    est_cost = totals["llm"] * COST_PER_LLM_CALL
    log(f"\n💰 LLM cost estimate: ${est_cost:.2f} "
        f"({totals['llm']} calls × ~${COST_PER_LLM_CALL:.4f}/call)")

    # Multi-buyer clusters
    log(f"\n🎯 Multi-buyer clusters ({len(clusters)} found):")
    for i, c in enumerate(clusters[:15], 1):
        level = "HIGH" if c["num_buyers"] >= 3 else "MED"
        tickers = c.get("tickers") or []
        tkr = tickers[0] if tickers else "—"
        log(f"  {i:>2}. [{level}] {c['company'][:42]:42} ({tkr:6}) "
            f"— {c['num_buyers']} buyers, ${c['total_value']:>12,.0f} "
            f"({c['first_date']} to {c['last_date']})")

    # Big single buyers
    log(f"\n💵 High-value single buyers >= $500K ({len(big_buyers)} found):")
    for b in big_buyers[:20]:
        tickers = b.get("tickers") or []
        tkr = tickers[0] if tickers else "—"
        log(f"  {b['company'][:40]:40} ({tkr:6}) — "
            f"{b['insider'][:28]:28} ${b['val']:>14,.0f} on {b['d']}")

    # Ambiguous signals
    log(f"\n⚠️  AMBIGUOUS classifications ({len(ambiguous)} need review):")
    for a in ambiguous:
        log(f"  {a['date']} — {a['issuer'][:40]:40} / {a['insider'][:25]:25} "
            f"${a['total_value']:>10,.0f}")
        log(f"    → {a['reason'][:110]}")

    log(f"\n{'=' * 72}\n")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--month", required=True, help="Month in YYYY-MM format (e.g., 2025-11)")
    ap.add_argument("--halt-after", type=int, default=2,
                    help="Halt after N consecutive Phase A failures (default: 2)")
    ap.add_argument("--workers", type=int, default=10,
                    help="Parallel LLM workers for Phase B (default: 10)")
    args = ap.parse_args()

    try:
        datetime.strptime(args.month, "%Y-%m")
    except ValueError:
        print(f"ERROR: --month must be in YYYY-MM format (got: {args.month})")
        sys.exit(1)

    trading_days = get_trading_days_in_month(args.month)
    if not trading_days:
        print(f"ERROR: no trading days found in {args.month}")
        sys.exit(1)

    log_path = f"/tmp/run_month_{args.month.replace('-','')}.log"
    log_file = open(log_path, "w", buffering=1)

    def log(msg):
        print(msg, flush=True)
        log_file.write(msg + "\n")
        log_file.flush()

    log(f"Month pipeline: {args.month}")
    log(f"Trading days ({len(trading_days)}): {trading_days}")
    log(f"Halt-after: {args.halt_after} consecutive failures")
    log(f"LLM workers (per-day): {args.workers}")
    log(f"Log: {log_path}\n")

    start = time.time()
    days_done = []
    consecutive_failures = 0
    week_block = 0

    # Per-day flow: each day runs full A→B→C via run_week.py (using new split architecture internally)
    for i, date in enumerate(trading_days):
        log(f"\n>>> Day {i+1}/{len(trading_days)}: {date}")
        # run_week.py handles fetch → filter → parse → prefilter → batch_llm (parallel) → merge → ingest
        exit_code = subprocess.run(
            [PY, "run_week.py", "--start", date, "--days", "1",
             "--workers", str(args.workers)]
        ).returncode

        if exit_code == 0:
            consecutive_failures = 0
            days_done.append(date)
        else:
            consecutive_failures += 1
            log(f"  ⚠️  Day {date} failed (exit {exit_code}). "
                f"Consecutive failures: {consecutive_failures}/{args.halt_after}")
            if consecutive_failures >= args.halt_after:
                log(f"\n❌ HALT: {consecutive_failures} consecutive failures — aborting.")
                break

        # Mini-summary every 5 trading days
        if (i + 1) % 5 == 0:
            print_week_summary(trading_days, week_block, log)
            week_block += 1

    elapsed = round(time.time() - start, 1)

    # Gather end-of-month artifacts
    try:
        clusters, big_buyers = asyncio.run(query_month_clusters(args.month))
    except Exception as e:
        log(f"⚠️  Neo4j query failed: {e}")
        clusters, big_buyers = [], []

    ambiguous = collect_ambiguous(days_done)

    print_report(
        args.month, days_done, trading_days,
        clusters, big_buyers, ambiguous, elapsed, log,
    )

    log_file.close()


if __name__ == "__main__":
    main()
