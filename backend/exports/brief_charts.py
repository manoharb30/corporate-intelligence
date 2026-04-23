"""Generate v1.1 research brief charts (PNG).

Reads stats.json and the Phase 4 CSV, produces three PNGs for the brief:
    funnel.png                   — filter drop-off at each stage
    return_distribution.png      — histogram of 90-day returns with signal + SPY means
    alpha_waterfall.png          — each signal's alpha, sorted descending

Run from the backend/ directory:
    venv/bin/python -m exports.brief_charts

All charts use matplotlib defaults — clean, institutional, no theming.
"""

import argparse
import csv
import json
import logging
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")  # headless backend
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.ticker import FuncFormatter  # noqa: E402

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(message)s")


GREEN = "#2d7a2d"
RED = "#b02828"
SIGNAL_COLOR = "#1f4e9c"
SPY_COLOR = "#999999"


def load_stats(path: Path) -> dict:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def load_cohort_csv(path: Path) -> list[dict]:
    rows: list[dict] = []
    with open(path, encoding="utf-8") as f:
        reader = csv.DictReader(line for line in f if not line.startswith("#"))
        for row in reader:
            rows.append(row)
    return rows


def find_latest_csv(output_dir: Path) -> Path:
    candidates = sorted(output_dir.glob("signals_v1_1_*.csv"), reverse=True)
    if not candidates:
        raise FileNotFoundError(f"No signals_v1_1_*.csv found in {output_dir}")
    return candidates[0]


def format_thousands(x: float, _pos) -> str:
    if x >= 1000:
        return f"{int(x):,}"
    return f"{int(x)}"


def chart_funnel(stats: dict, output: Path) -> None:
    """Horizontal bar chart of funnel stages with drop-rate annotations."""
    funnel = stats["funnel"]
    stages = [s["stage"] for s in funnel]
    counts = [s["count"] for s in funnel]
    drops = [s.get("drop_rate_from_prior") for s in funnel]

    fig, ax = plt.subplots(figsize=(11, 5.5))
    y_pos = list(range(len(stages)))
    y_pos.reverse()  # top stage at top of chart

    bars = ax.barh(y_pos, counts, color=SIGNAL_COLOR, alpha=0.85, edgecolor="black", linewidth=0.5)
    ax.set_yticks(y_pos)
    ax.set_yticklabels(stages, fontsize=10)
    ax.set_xscale("log")
    ax.set_xlabel("Count (log scale)", fontsize=10)
    ax.xaxis.set_major_formatter(FuncFormatter(format_thousands))

    for i, (bar, count, drop) in enumerate(zip(bars, counts, drops)):
        # count annotation at bar end
        ax.text(
            bar.get_width() * 1.08,
            bar.get_y() + bar.get_height() / 2,
            f"{count:,}",
            va="center", ha="left", fontsize=10, color="black",
        )
        # drop-rate annotation between stages (below the bar)
        if drop is not None:
            drop_pct = drop * 100
            ax.text(
                bar.get_width() * 0.5,
                bar.get_y() - 0.08,
                f"↓ {drop_pct:.1f}% dropped",
                va="top", ha="center", fontsize=8, color="#666666", style="italic",
            )

    cohort_n = stats["cohort"]["n"]
    raw_count = counts[0]
    ax.set_title(
        f"Filter funnel: {raw_count:,} raw transactions → {cohort_n} mature strong_buy signals",
        fontsize=12, pad=15,
    )
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.grid(axis="x", alpha=0.3, linestyle=":")
    plt.tight_layout()
    plt.savefig(output, dpi=150, bbox_inches="tight")
    plt.close()
    logger.info("Wrote %s", output)


def chart_return_distribution(stats: dict, rows: list[dict], output: Path) -> None:
    """Histogram of return_day0 with signal mean + SPY mean reference lines."""
    returns = [float(r["return_day0"]) for r in rows]
    signal_mean = stats["headline"]["mean_return_day0"]
    spy_mean = stats["headline"]["mean_spy_return_90d"]

    fig, ax = plt.subplots(figsize=(11, 5.5))
    ax.hist(returns, bins=25, color=SIGNAL_COLOR, alpha=0.75, edgecolor="black", linewidth=0.5)

    ax.axvline(signal_mean, color=GREEN, linestyle="-", linewidth=2,
               label=f"Signal mean: +{signal_mean:.1f}%")
    ax.axvline(spy_mean, color=SPY_COLOR, linestyle="--", linewidth=2,
               label=f"SPY mean: +{spy_mean:.1f}%")
    ax.axvline(0, color="black", linestyle="-", linewidth=0.5, alpha=0.5)

    ax.set_xlabel("90-day return (%)", fontsize=10)
    ax.set_ylabel("Signal count", fontsize=10)
    ax.set_title(
        f"90-day return distribution — {stats['cohort']['n']} mature strong_buy signals",
        fontsize=12, pad=15,
    )
    ax.legend(loc="upper right", fontsize=10, framealpha=0.9)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.grid(axis="y", alpha=0.3, linestyle=":")
    plt.tight_layout()
    plt.savefig(output, dpi=150, bbox_inches="tight")
    plt.close()
    logger.info("Wrote %s", output)


def chart_alpha_waterfall(stats: dict, rows: list[dict], output: Path) -> None:
    """Sorted alpha bars, green for positive / red for negative."""
    alphas = sorted([float(r["alpha_90d"]) for r in rows], reverse=True)
    n = len(alphas)
    colors = [GREEN if a > 0 else RED for a in alphas]
    positive = sum(1 for a in alphas if a > 0)
    negative = n - positive

    fig, ax = plt.subplots(figsize=(12, 5.5))
    ax.bar(range(n), alphas, color=colors, width=1.0, edgecolor="none")
    ax.axhline(0, color="black", linewidth=0.8)

    ax.set_xlabel(f"Signals ranked by alpha (n={n})", fontsize=10)
    ax.set_ylabel("Alpha vs SPY (percentage points)", fontsize=10)
    mean_alpha = stats["headline"]["mean_alpha"]
    p_alpha = stats["headline"]["p_alpha_formatted"]
    ax.set_title(
        f"Signal alpha distribution — mean +{mean_alpha:.1f}pp (p={p_alpha}), "
        f"{positive}/{n} positive",
        fontsize=12, pad=15,
    )

    ax.text(
        0.02, 0.96,
        f"Positive alpha: {positive}/{n} ({positive / n * 100:.0f}%)\n"
        f"Negative alpha: {negative}/{n} ({negative / n * 100:.0f}%)",
        transform=ax.transAxes, fontsize=10, verticalalignment="top",
        bbox=dict(boxstyle="round", facecolor="white", edgecolor="#cccccc", alpha=0.9),
    )

    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.grid(axis="y", alpha=0.3, linestyle=":")
    plt.tight_layout()
    plt.savefig(output, dpi=150, bbox_inches="tight")
    plt.close()
    logger.info("Wrote %s", output)


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate v1.1 brief charts")
    parser.add_argument(
        "--stats-json",
        type=Path,
        default=Path("../.paul/phases/05-research-brief-pdf/stats.json"),
    )
    parser.add_argument("--csv", type=Path, default=None)
    parser.add_argument("--export-dir", type=Path, default=Path("exports/out"))
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("../.paul/phases/05-research-brief-pdf/charts"),
    )
    args = parser.parse_args()

    csv_path = args.csv or find_latest_csv(args.export_dir)
    logger.info("Stats: %s", args.stats_json)
    logger.info("CSV:   %s", csv_path)
    logger.info("Out:   %s", args.output_dir)

    args.output_dir.mkdir(parents=True, exist_ok=True)
    stats = load_stats(args.stats_json)
    rows = load_cohort_csv(csv_path)

    chart_funnel(stats, args.output_dir / "funnel.png")
    chart_return_distribution(stats, rows, args.output_dir / "return_distribution.png")
    chart_alpha_waterfall(stats, rows, args.output_dir / "alpha_waterfall.png")

    logger.info("All 3 charts generated.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
