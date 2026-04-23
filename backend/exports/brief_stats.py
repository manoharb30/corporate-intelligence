"""Compute v1.1 research brief statistics.

Reads the Phase 4 CSV (141-row strong_buy cohort) and Neo4j (funnel counts),
emits a structured JSON consumed by brief_charts.py and the brief narrative.

Run from the backend/ directory:
    venv/bin/python -m exports.brief_stats
    venv/bin/python -m exports.brief_stats --csv <path> --output <path>

Outputs:
    ../.paul/phases/05-research-brief-pdf/stats.json
"""

import argparse
import asyncio
import csv
import json
import logging
import statistics
import sys
from collections import defaultdict
from datetime import date
from pathlib import Path

from scipy import stats as sp_stats

from app.db.neo4j_client import Neo4jClient

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(message)s")


EXPECTED_COHORT_N = 141


def format_pvalue(p: float) -> str:
    """Format p-value as '<0.001' for very small values, else 4-decimal string."""
    if p is None:
        return "n/a"
    if p < 0.001:
        return "<0.001"
    return f"{p:.4f}"


def wilson_ci(wins: int, n: int, confidence: float = 0.95) -> tuple[float, float]:
    """Wilson score interval for a binomial proportion (matches scipy>=1.11 method='wilson')."""
    if n == 0:
        return (0.0, 0.0)
    result = sp_stats.binomtest(wins, n, p=0.5)
    ci = result.proportion_ci(confidence_level=confidence, method="wilson")
    return (float(ci.low), float(ci.high))


def t_interval(values: list[float], confidence: float = 0.95) -> tuple[float, float]:
    """95% CI for the mean via t-distribution."""
    n = len(values)
    if n < 2:
        return (float("nan"), float("nan"))
    m = statistics.mean(values)
    sem = statistics.stdev(values) / (n ** 0.5)
    low, high = sp_stats.t.interval(confidence, df=n - 1, loc=m, scale=sem)
    return (float(low), float(high))


async def fetch_funnel_counts() -> list[dict]:
    """Query Neo4j for each funnel stage count."""
    stages: list[dict] = []

    async def count(query: str) -> int:
        rows = await Neo4jClient.execute_query(query)
        return int(rows[0]["n"]) if rows else 0

    # Stage 1: all insider transactions ingested
    n1 = await count("MATCH (it:InsiderTransaction) RETURN count(it) AS n")
    stages.append({"stage": "Raw insider transactions", "count": n1, "drop_rate_from_prior": None})

    # Stage 2: P transactions only
    n2 = await count(
        "MATCH (it:InsiderTransaction) WHERE it.transaction_code = 'P' RETURN count(it) AS n"
    )
    stages.append({
        "stage": "Open-market purchases (P transactions)",
        "count": n2,
        "drop_rate_from_prior": (1 - n2 / n1) if n1 else None,
    })

    # Stage 3: GENUINE P (after LLM classifier)
    n3 = await count(
        "MATCH (it:InsiderTransaction) "
        "WHERE it.transaction_code = 'P' AND it.classification = 'GENUINE' "
        "RETURN count(it) AS n"
    )
    stages.append({
        "stage": "Genuine P (post-LLM classification)",
        "count": n3,
        "drop_rate_from_prior": (1 - n3 / n2) if n2 else None,
    })

    # Stage 4: SignalPerformance nodes (all directions, all tiers, all maturity)
    n4 = await count("MATCH (sp:SignalPerformance) RETURN count(sp) AS n")
    stages.append({
        "stage": "Clusters detected (SignalPerformance nodes)",
        "count": n4,
        "drop_rate_from_prior": (1 - n4 / n3) if n3 else None,
    })

    # Stage 5: strong_buy clusters (direction+tier filter)
    n5 = await count(
        "MATCH (sp:SignalPerformance) "
        "WHERE sp.direction = 'buy' AND sp.conviction_tier = 'strong_buy' "
        "RETURN count(sp) AS n"
    )
    stages.append({
        "stage": "Strong_buy clusters (midcap + $100K + 2+ insiders + earn≤60d)",
        "count": n5,
        "drop_rate_from_prior": (1 - n5 / n4) if n4 else None,
    })

    # Stage 6: mature strong_buy (≥97d + day-90 price available)
    n6 = await count(
        "MATCH (sp:SignalPerformance) "
        "WHERE sp.direction = 'buy' AND sp.conviction_tier = 'strong_buy' "
        "AND sp.is_mature = true "
        "RETURN count(sp) AS n"
    )
    stages.append({
        "stage": "Mature strong_buy (≥97d, day-90 price available)",
        "count": n6,
        "drop_rate_from_prior": (1 - n6 / n5) if n5 else None,
    })

    return stages


def load_cohort_csv(path: Path) -> list[dict]:
    """Load Phase 4 CSV, skipping the comment row."""
    rows: list[dict] = []
    with open(path, encoding="utf-8") as f:
        reader = csv.DictReader(line for line in f if not line.startswith("#"))
        for row in reader:
            rows.append(row)
    return rows


def find_latest_csv(output_dir: Path) -> Path:
    """Find the most recent signals_v1_1_*.csv in the export output directory."""
    candidates = sorted(output_dir.glob("signals_v1_1_*.csv"), reverse=True)
    if not candidates:
        raise FileNotFoundError(
            f"No signals_v1_1_*.csv found in {output_dir}. "
            "Run `python -m exports.export_signals_v1_1` first."
        )
    return candidates[0]


def num_insiders_bucket(n: int) -> str:
    if n == 2:
        return "2"
    if n == 3:
        return "3"
    if n == 4:
        return "4"
    return "5+"


def compute_breakdown(rows: list[dict], key_fn) -> dict[str, dict]:
    groups: dict[str, list[dict]] = defaultdict(list)
    for row in rows:
        groups[key_fn(row)].append(row)

    out: dict[str, dict] = {}
    for key in sorted(groups.keys()):
        grp = groups[key]
        returns = [float(r["return_day0"]) for r in grp]
        alphas = [float(r["alpha_90d"]) for r in grp]
        wins = sum(1 for r in returns if r > 0)
        out[key] = {
            "n": len(grp),
            "hit_rate": wins / len(grp),
            "mean_return_day0": statistics.mean(returns),
            "mean_alpha": statistics.mean(alphas),
        }
    return out


async def main() -> int:
    parser = argparse.ArgumentParser(description="Compute v1.1 brief statistics")
    parser.add_argument("--csv", type=Path, default=None, help="Phase 4 signals CSV (auto-discovers if not specified)")
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("../.paul/phases/05-research-brief-pdf/stats.json"),
        help="Output JSON path",
    )
    parser.add_argument(
        "--export-dir",
        type=Path,
        default=Path("exports/out"),
        help="Phase 4 CSV discovery directory",
    )
    args = parser.parse_args()

    csv_path = args.csv or find_latest_csv(args.export_dir)
    logger.info("Using CSV: %s", csv_path)

    rows = load_cohort_csv(csv_path)
    logger.info("Loaded %d rows from CSV", len(rows))

    if len(rows) != EXPECTED_COHORT_N:
        raise AssertionError(
            f"Cohort drift: CSV has {len(rows)} rows, expected {EXPECTED_COHORT_N}. "
            "Re-run the Phase 4 export or update EXPECTED_COHORT_N if intentional."
        )

    returns = [float(r["return_day0"]) for r in rows]
    spy_returns = [float(r["spy_return_90d"]) for r in rows]
    alphas = [float(r["alpha_90d"]) for r in rows]

    wins = sum(1 for r in returns if r > 0)
    n_positive_alpha = sum(1 for a in alphas if a > 0)
    hit_rate = wins / len(rows)
    hr_low, hr_high = wilson_ci(wins, len(rows))

    mean_alpha = statistics.mean(alphas)
    alpha_ci_low, alpha_ci_high = t_interval(alphas)
    mean_return = statistics.mean(returns)
    median_return = statistics.median(returns)
    mean_spy = statistics.mean(spy_returns)

    p_hit_rate = sp_stats.binomtest(wins, len(rows), p=0.5, alternative="two-sided").pvalue
    p_alpha = sp_stats.ttest_1samp(alphas, 0.0, alternative="two-sided").pvalue

    filing_dates = [r["filing_date"] for r in rows if r.get("filing_date")]
    window_start = min(filing_dates) if filing_dates else None
    window_end = max(filing_dates) if filing_dates else None

    await Neo4jClient.connect()
    try:
        funnel = await fetch_funnel_counts()
    finally:
        await Neo4jClient.disconnect()

    stats = {
        "cohort": {
            "n": len(rows),
            "window_start": window_start,
            "window_end": window_end,
            "snapshot_date": date.today().isoformat(),
            "source_csv": str(csv_path.name),
        },
        "funnel": funnel,
        "headline": {
            "hit_rate": round(hit_rate, 4),
            "hit_rate_ci95_low": round(hr_low, 4),
            "hit_rate_ci95_high": round(hr_high, 4),
            "mean_alpha": round(mean_alpha, 2),
            "alpha_ci95_low": round(alpha_ci_low, 2),
            "alpha_ci95_high": round(alpha_ci_high, 2),
            "mean_return_day0": round(mean_return, 2),
            "median_return_day0": round(median_return, 2),
            "mean_spy_return_90d": round(mean_spy, 2),
            "n_wins": wins,
            "n_losses": len(rows) - wins,
            "n_positive_alpha": n_positive_alpha,
            "n_negative_alpha": len(rows) - n_positive_alpha,
            "p_hit_rate": p_hit_rate,
            "p_hit_rate_formatted": format_pvalue(p_hit_rate),
            "p_alpha": p_alpha,
            "p_alpha_formatted": format_pvalue(p_alpha),
        },
        "breakdowns": {
            "by_num_insiders": compute_breakdown(rows, lambda r: num_insiders_bucket(int(r["num_insiders"]))),
            "by_hostile_flag": compute_breakdown(rows, lambda r: r["hostile_flag"].strip().lower()),
            "by_signal_level": compute_breakdown(rows, lambda r: r.get("signal_level", "").strip().lower() or "unspecified"),
            "by_month": compute_breakdown(rows, lambda r: r["filing_date"][:7] if r.get("filing_date") else "unknown"),
        },
    }

    args.output.parent.mkdir(parents=True, exist_ok=True)
    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(stats, f, indent=2, sort_keys=False, default=str)

    logger.info("Wrote stats: %s", args.output)
    logger.info(
        "Summary: n=%d, HR=%.1f%% (p=%s), alpha=+%.1fpp (p=%s)",
        len(rows), hit_rate * 100, format_pvalue(p_hit_rate),
        mean_alpha, format_pvalue(p_alpha),
    )
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
