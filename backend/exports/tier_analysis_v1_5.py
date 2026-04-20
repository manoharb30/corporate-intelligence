"""v1.5 Phase 14: per-tier statistical analysis.

Reads `tier_candidates_v1_5.csv` (from Phase 13). For each size tier
(small, midcap baseline, large), computes matured-pool statistics and
tests whether small-cap and/or large-cap candidate pools are
significantly different from the midcap baseline.

Output: `tier_analysis_v1_5_stats.csv` + console summary.

Run from backend/:
    venv/bin/python -m exports.tier_analysis_v1_5
"""

import argparse
import csv
import logging
import math
from pathlib import Path
from typing import Optional

import pandas as pd
from scipy.stats import fisher_exact, mannwhitneyu

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")


COLUMN_ORDER = [
    "tier",
    "n_total",
    "n_mature",
    "hit_rate_pct",
    "avg_return_pct",
    "avg_alpha_pct",
    "std_return_pct",
    "p_fisher_vs_midcap",
    "p_mannwhitney_vs_midcap",
    "p_fisher_bonferroni",
    "verdict",
]


def to_bool(v) -> Optional[bool]:
    if v is None or (isinstance(v, float) and math.isnan(v)):
        return None
    if isinstance(v, bool):
        return v
    s = str(v).lower()
    if s == "true":
        return True
    if s == "false":
        return False
    return None


def stats_for_pool(df: pd.DataFrame) -> dict:
    mature = df[df["is_mature_by_age_bool"] & df["price_day90"].notna()].copy()
    n_total = len(df)
    n_mature = len(mature)
    if n_mature == 0:
        return {
            "n_total": n_total,
            "n_mature": 0,
            "hit_rate_pct": None,
            "avg_return_pct": None,
            "avg_alpha_pct": None,
            "std_return_pct": None,
            "hits": 0,
            "misses": 0,
            "returns": [],
        }
    hits = int(mature["hit_90d_bool"].fillna(False).sum())
    misses = n_mature - hits
    hr = round(hits / n_mature * 100, 4)
    avg_ret = round(mature["return_90d_pct"].mean(), 4)
    avg_alpha = round(mature["alpha_90d_pct"].dropna().mean(), 4) if mature["alpha_90d_pct"].notna().any() else None
    std_ret = round(mature["return_90d_pct"].std(), 4) if n_mature >= 2 else None
    return {
        "n_total": n_total,
        "n_mature": n_mature,
        "hit_rate_pct": hr,
        "avg_return_pct": avg_ret,
        "avg_alpha_pct": avg_alpha,
        "std_return_pct": std_ret,
        "hits": hits,
        "misses": misses,
        "returns": mature["return_90d_pct"].dropna().tolist(),
    }


def p_fisher_vs(candidate: dict, baseline: dict) -> Optional[float]:
    if candidate["n_mature"] < 2 or baseline["n_mature"] < 2:
        return None
    table = [
        [candidate["hits"], candidate["misses"]],
        [baseline["hits"], baseline["misses"]],
    ]
    try:
        _, p = fisher_exact(table, alternative="two-sided")
        return round(p, 6)
    except ValueError:
        return None


def p_mannwhitney_vs(candidate: dict, baseline: dict) -> Optional[float]:
    if len(candidate["returns"]) < 3 or len(baseline["returns"]) < 3:
        return None
    try:
        _, p = mannwhitneyu(
            candidate["returns"], baseline["returns"], alternative="two-sided"
        )
        return round(p, 6)
    except ValueError:
        return None


def verdict(p_bonf: Optional[float]) -> str:
    if p_bonf is None:
        return "untestable"
    if p_bonf < 0.05:
        return "ADOPT"
    if p_bonf > 0.10:
        return "REJECT"
    return "INCONCLUSIVE"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--in", dest="in_path", type=str, default="exports/out/tier_candidates_v1_5.csv")
    ap.add_argument("--out-csv", type=str, default="exports/out/tier_analysis_v1_5_stats.csv")
    ap.add_argument("--out-report", type=str, default="exports/TIER_ANALYSIS_V1_5_REPORT.md")
    args = ap.parse_args()

    df = pd.read_csv(args.in_path)
    df["hit_90d_bool"] = df["hit_90d"].apply(to_bool)
    df["is_mature_by_age_bool"] = df["is_mature_by_age"].apply(to_bool)
    logger.info(f"Input: {len(df)} candidate rows")

    # Partition by size tier
    pools = {
        "small": df[df.size_tier == "small"],
        "midcap": df[df.size_tier == "midcap"],
        "large": df[df.size_tier == "large"],
    }

    stats = {k: stats_for_pool(v) for k, v in pools.items()}

    # Also compute an "extended" pool = small + large (if we were to adopt both)
    ext_df = pd.concat([pools["small"], pools["large"]])
    stats["small+large (extended)"] = stats_for_pool(ext_df)

    # Baseline for comparison = midcap
    baseline = stats["midcap"]
    n_bonf = 3  # small, large, small+large

    rows = []
    for tier_name in ["small", "midcap", "large", "small+large (extended)"]:
        s = stats[tier_name]
        row = {
            "tier": tier_name,
            "n_total": s["n_total"],
            "n_mature": s["n_mature"],
            "hit_rate_pct": s["hit_rate_pct"],
            "avg_return_pct": s["avg_return_pct"],
            "avg_alpha_pct": s["avg_alpha_pct"],
            "std_return_pct": s["std_return_pct"],
        }
        if tier_name == "midcap":
            row["p_fisher_vs_midcap"] = None
            row["p_mannwhitney_vs_midcap"] = None
            row["p_fisher_bonferroni"] = None
            row["verdict"] = "baseline"
        else:
            p_f = p_fisher_vs(s, baseline)
            p_mw = p_mannwhitney_vs(s, baseline)
            p_bonf = round(min(1.0, p_f * n_bonf), 6) if p_f is not None else None
            row["p_fisher_vs_midcap"] = p_f
            row["p_mannwhitney_vs_midcap"] = p_mw
            row["p_fisher_bonferroni"] = p_bonf
            row["verdict"] = verdict(p_bonf)
        rows.append(row)

    # Write CSV
    out_csv = Path(args.out_csv)
    out_csv.parent.mkdir(parents=True, exist_ok=True)
    with open(out_csv, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=COLUMN_ORDER, extrasaction="ignore")
        w.writeheader()
        for r in rows:
            out_row = {}
            for k in COLUMN_ORDER:
                v = r.get(k)
                out_row[k] = "" if v is None else v
            w.writerow(out_row)
    logger.info(f"CSV: {out_csv}")

    # Console summary
    print(f"\n{'='*80}")
    print(f"  PER-TIER ANALYSIS — v1.5 Phase 14")
    print(f"{'='*80}")
    print(f"{'tier':28} {'n_mat':>5} {'HR':>7} {'ret':>8} {'alpha':>8} {'p_f':>8} {'p_mw':>8} {'p_bonf':>8} {'verdict':10}")
    print("-" * 100)
    for r in rows:
        print(
            f"{r['tier']:28} {r['n_mature']:>5} "
            f"{(r['hit_rate_pct'] or 0):>6.2f}% "
            f"{(r['avg_return_pct'] or 0):>+7.2f}% "
            f"{(r['avg_alpha_pct'] or 0):>+7.2f}% "
            f"{(r['p_fisher_vs_midcap'] or 0):>8.4f} "
            f"{(r['p_mannwhitney_vs_midcap'] or 0):>8.4f} "
            f"{(r['p_fisher_bonferroni'] or 0):>8.4f} "
            f"{r['verdict']:10}"
        )
    print("-" * 100)
    print(f"Bonferroni n: {n_bonf} (2 tier comparisons + 1 combined)")
    print(f"{'='*80}\n")

    # Write report markdown
    out_report = Path(args.out_report)
    out_report.parent.mkdir(parents=True, exist_ok=True)

    small = stats["small"]
    mid = stats["midcap"]
    large = stats["large"]
    ext = stats["small+large (extended)"]
    small_row = next(r for r in rows if r["tier"] == "small")
    large_row = next(r for r in rows if r["tier"] == "large")
    ext_row = next(r for r in rows if r["tier"] == "small+large (extended)")

    lines = [
        "# v1.5 Signal Tier Extension — Phase 14 Report",
        "",
        f"*Generated: 2026-04-20*",
        f"*Input: `backend/exports/out/tier_candidates_v1_5.csv` ({len(df)} total candidate clusters).*",
        f"*Baseline: midcap tier's matured pool (n_mature = {mid['n_mature']}).*",
        f"*Bonferroni n = {n_bonf} (small + large + small+large combined).*",
        "",
        "## Per-tier stats (matured pool)",
        "",
        "| Tier | n_mat | Hit rate | Avg return | Avg alpha | p_fisher | p_mannwhitney | p_bonferroni | Verdict |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    for r in rows:
        hr = f"{r['hit_rate_pct']:.2f}%" if r["hit_rate_pct"] is not None else "—"
        ret = f"{r['avg_return_pct']:+.2f}%" if r["avg_return_pct"] is not None else "—"
        al = f"{r['avg_alpha_pct']:+.2f}%" if r["avg_alpha_pct"] is not None else "—"
        pf = f"{r['p_fisher_vs_midcap']:.4f}" if r["p_fisher_vs_midcap"] is not None else "—"
        pmw = f"{r['p_mannwhitney_vs_midcap']:.4f}" if r["p_mannwhitney_vs_midcap"] is not None else "—"
        pb = f"{r['p_fisher_bonferroni']:.4f}" if r["p_fisher_bonferroni"] is not None else "—"
        lines.append(
            f"| **{r['tier']}** | {r['n_mature']} | {hr} | {ret} | {al} | {pf} | {pmw} | {pb} | **{r['verdict']}** |"
        )

    lines += [
        "",
        "## Recommendations",
        "",
        f"### `small_cap_strong_buy` tier (ground-truth mcap $100M–$300M)",
        f"- n_mature = {small['n_mature']}, hit rate = {small['hit_rate_pct'] or 0:.2f}%, avg return = {small['avg_return_pct'] or 0:+.2f}%, avg alpha = {small['avg_alpha_pct'] or 0:+.2f}%",
        f"- vs baseline (midcap, {mid['hit_rate_pct']:.2f}% hr): p_fisher = {small_row['p_fisher_vs_midcap']}, p_bonferroni = {small_row['p_fisher_bonferroni']}",
        f"- **Verdict: {small_row['verdict']}**",
        "",
        f"### `large_cap_strong_buy` tier (ground-truth mcap > $5B)",
        f"- n_mature = {large['n_mature']}, hit rate = {large['hit_rate_pct'] or 0:.2f}%, avg return = {large['avg_return_pct'] or 0:+.2f}%, avg alpha = {large['avg_alpha_pct'] or 0:+.2f}%",
        f"- vs baseline (midcap): p_fisher = {large_row['p_fisher_vs_midcap']}, p_bonferroni = {large_row['p_fisher_bonferroni']}",
        f"- **Verdict: {large_row['verdict']}**",
        "",
        f"### Combined `small + large` (if we adopt both)",
        f"- n_mature = {ext['n_mature']}, hit rate = {ext['hit_rate_pct'] or 0:.2f}%, avg return = {ext['avg_return_pct'] or 0:+.2f}%",
        f"- vs baseline: p_fisher = {ext_row['p_fisher_vs_midcap']}, p_bonferroni = {ext_row['p_fisher_bonferroni']}",
        f"- **Verdict: {ext_row['verdict']}**",
        "",
        "## Phase 15 guidance",
        "",
        f"*Adoption rule: a tier is adopted only if p_fisher_bonferroni < 0.05.*",
        "",
    ]
    adopt = [r for r in rows if r["verdict"] == "ADOPT"]
    if adopt:
        lines.append("**Tiers to adopt in Phase 15:**")
        for r in adopt:
            lines.append(f"- `{r['tier']}` — introduce `conviction_tier = '{r['tier'].replace('+', '_').replace(' ', '_')}_strong_buy'`. Tag new rows `methodology_version = 'v1.5'`.")
    else:
        lines.append("**No tiers pass the p<0.05 Bonferroni bar. Phase 15 closes v1.5 without new tier values.** This is a defensible outcome — the signal quality data for candidate tiers is either similar-to or indistinguishable-from the midcap baseline.")
    lines += [
        "",
        "The v1.1 headline remains the defining methodology. Growing the dataset further (additional months) is still the highest-leverage move for future tier or filter refinements.",
        "",
    ]

    out_report.write_text("\n".join(lines))
    logger.info(f"Report: {out_report}")


if __name__ == "__main__":
    main()
