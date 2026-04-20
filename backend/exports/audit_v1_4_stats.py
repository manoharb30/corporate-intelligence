"""v1.4 Phase 11 filter-candidate statistical harness.

Reads `signal_audit_v1_4.csv` and tests a declared set of candidate filters
against the 142 mature strong_buy pool. For each candidate: Fisher's exact
test (hit rate) + Mann-Whitney U (return distribution) + Bonferroni
correction across all tests.

Output: `audit_v1_4_filter_candidates.csv` — one row per candidate, sorted
by Bonferroni-adjusted p-value ascending.

Run from backend/:
    venv/bin/python -m exports.audit_v1_4_stats
    venv/bin/python -m exports.audit_v1_4_stats --in exports/out/signal_audit_v1_4.csv --out exports/out/audit_v1_4_filter_candidates.csv
"""

import argparse
import csv
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional

import pandas as pd
from scipy.stats import fisher_exact, mannwhitneyu

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")


@dataclass
class Candidate:
    axis: str          # human-readable axis name
    threshold: float   # the threshold value (NaN if N/A)
    direction: str     # "exclude_below" | "exclude_above" | "exclude_if_true" | "exclude_if_flag"
    predicate: Callable[[pd.DataFrame], pd.Series]  # returns bool Series: True = row is EXCLUDED
    note: str = ""     # optional context


def build_candidates() -> list[Candidate]:
    """Declared list of filter candidates to test.

    Thresholds are pre-declared — no threshold mining.
    Every candidate's `predicate` returns True for rows to be EXCLUDED.
    """
    candidates: list[Candidate] = []

    # Mcap-based: true mcap below threshold (small-cap exclusion)
    for t in (100_000_000, 200_000_000, 300_000_000, 500_000_000):
        candidates.append(
            Candidate(
                axis="mcap_at_signal_true_usd",
                threshold=float(t),
                direction="exclude_below",
                predicate=lambda d, t=t: (d.mcap_at_signal_true_usd.fillna(0) < t),
                note=f"Exclude true-mcap < ${t/1e6:.0f}M (null treated as 0 → excluded).",
            )
        )

    # Mcap-based: true mcap above threshold (upper-band)
    for t in (3_000_000_000, 5_000_000_000):
        candidates.append(
            Candidate(
                axis="mcap_at_signal_true_usd",
                threshold=float(t),
                direction="exclude_above",
                predicate=lambda d, t=t: (d.mcap_at_signal_true_usd.fillna(0) > t),
                note=f"Exclude true-mcap > ${t/1e9:.1f}B.",
            )
        )

    # Pre-cluster sellers count
    for k in (1, 2, 3):
        candidates.append(
            Candidate(
                axis="pre_cluster_sellers_count_180d",
                threshold=float(k),
                direction="exclude_at_or_above",
                predicate=lambda d, k=k: (d.pre_cluster_sellers_count_180d.fillna(0) >= k),
                note=f"Exclude if >= {k} distinct officer/director sellers in prior 180d.",
            )
        )

    # Pre-cluster sells value
    candidates.append(
        Candidate(
            axis="pre_cluster_sells_value_usd_180d",
            threshold=500_000.0,
            direction="exclude_above",
            predicate=lambda d: (d.pre_cluster_sells_value_usd_180d.fillna(0) > 500_000),
            note="Exclude if > $500K sold by officers in prior 180d.",
        )
    )

    # Post-signal sells count
    for k in (1, 2):
        candidates.append(
            Candidate(
                axis="post_signal_sells_count_90d",
                threshold=float(k),
                direction="exclude_at_or_above",
                predicate=lambda d, k=k: (d.post_signal_sells_count_90d.fillna(0) >= k),
                note=f"Exclude if >= {k} officer sells in first 90d after signal.",
            )
        )

    # Post-signal sells value
    candidates.append(
        Candidate(
            axis="post_signal_sells_value_usd_90d",
            threshold=500_000.0,
            direction="exclude_above",
            predicate=lambda d: (d.post_signal_sells_value_usd_90d.fillna(0) > 500_000),
            note="Exclude if > $500K post-signal officer sells.",
        )
    )

    # Earnings proximity
    candidates.append(
        Candidate(
            axis="days_to_next_earnings_at_signal",
            threshold=60.0,
            direction="exclude_above",
            predicate=lambda d: (d.days_to_next_earnings_at_signal.fillna(0) > 60),
            note="Exclude if > 60d to next earnings (v1.0 rule; re-test).",
        )
    )
    candidates.append(
        Candidate(
            axis="days_from_last_earnings_at_signal",
            threshold=7.0,
            direction="exclude_below",
            predicate=lambda d: (d.days_from_last_earnings_at_signal.fillna(999) < 7),
            note="Exclude if < 7d after last earnings (post-earnings drift zone).",
        )
    )

    # Volatility
    for t in (50.0, 75.0):
        candidates.append(
            Candidate(
                axis="stock_volatility_30d_pct",
                threshold=t,
                direction="exclude_above",
                predicate=lambda d, t=t: (d.stock_volatility_30d_pct.fillna(0) > t),
                note=f"Exclude if 30d vol > {t}% annualized.",
            )
        )

    # Cluster size
    candidates.append(
        Candidate(
            axis="num_insiders",
            threshold=3.0,
            direction="exclude_below",
            predicate=lambda d: (d.num_insiders.fillna(0) < 3),
            note="Exclude if < 3 distinct buyers.",
        )
    )
    for v in (200_000.0, 500_000.0):
        candidates.append(
            Candidate(
                axis="total_cluster_value_usd",
                threshold=v,
                direction="exclude_below",
                predicate=lambda d, v=v: (d.total_cluster_value_usd.fillna(0) < v),
                note=f"Exclude if cluster value < ${v/1e3:.0f}K.",
            )
        )

    # Hostile flag
    candidates.append(
        Candidate(
            axis="has_hostile_activist",
            threshold=float("nan"),
            direction="exclude_if_true",
            predicate=lambda d: (d.has_hostile_activist.fillna(False).astype(bool)),
            note="Exclude if has_hostile_activist flag set.",
        )
    )

    # Industry: bottom-quartile-by-hit-rate industries
    # (computed dynamically from the data — documented caveat: this is
    # a data-driven threshold, not pre-declared. Included for completeness
    # but its p-value should be read with skepticism.)
    candidates.append(
        Candidate(
            axis="industry",
            threshold=float("nan"),
            direction="exclude_bottom_quartile_by_hit_rate",
            predicate=_industry_bottom_quartile_predicate,
            note="Exclude rows in industries whose sample hit rate is in bottom quartile (≥3 signals). Data-driven threshold — interpret p-value with caution.",
        )
    )

    return candidates


def _industry_bottom_quartile_predicate(d: pd.DataFrame) -> pd.Series:
    """Return True for rows in industries with bottom-quartile hit rate.

    Requires ≥3 signals per industry to qualify (avoids 1-row industries
    dominating). Industries with <3 signals are never excluded.
    """
    hit_col = d.hit_90d.astype(str).str.lower().eq("true")
    grouped = d.groupby("industry").agg(
        n=("industry", "size"),
        hits=(hit_col.name if hit_col.name else "hit_90d", lambda s: (s.astype(str).str.lower() == "true").sum()),
    )
    # Fallback: use d['hit_90d'] directly
    grouped = d.assign(_hit=hit_col).groupby("industry").agg(n=("industry", "size"), hits=("_hit", "sum"))
    grouped["hit_rate"] = grouped["hits"] / grouped["n"]
    qualifying = grouped[grouped.n >= 3]
    if qualifying.empty:
        return pd.Series([False] * len(d), index=d.index)
    q1 = qualifying["hit_rate"].quantile(0.25)
    bad_industries = set(qualifying[qualifying.hit_rate <= q1].index)
    return d.industry.isin(bad_industries)


def evaluate_candidate(df: pd.DataFrame, cand: Candidate) -> dict:
    """Apply filter, compute stats, return a row dict."""
    excl_mask = cand.predicate(df).astype(bool)
    retained = df[~excl_mask]
    excluded = df[excl_mask]

    # Normalize hit column to Python bool
    def as_bool(s):
        if s.dtype == bool:
            return s
        return s.astype(str).str.lower().map({"true": True, "false": False}).astype(bool)

    r_hits = as_bool(retained.hit_90d)
    e_hits = as_bool(excluded.hit_90d)

    n_ret = len(retained)
    n_exc = len(excluded)

    hr_ret = r_hits.mean() * 100 if n_ret > 0 else None
    hr_exc = e_hits.mean() * 100 if n_exc > 0 else None

    alpha_ret = retained.alpha_90d_pct.dropna().mean() if n_ret > 0 else None
    alpha_exc = excluded.alpha_90d_pct.dropna().mean() if n_exc > 0 else None

    # Fisher's exact on 2x2: rows = retained/excluded, cols = hit/miss
    p_fisher: Optional[float] = None
    if n_ret >= 2 and n_exc >= 2:
        ret_hits = int(r_hits.sum())
        ret_miss = int(n_ret - ret_hits)
        exc_hits = int(e_hits.sum())
        exc_miss = int(n_exc - exc_hits)
        try:
            _, p_fisher = fisher_exact(
                [[ret_hits, ret_miss], [exc_hits, exc_miss]], alternative="two-sided"
            )
        except ValueError:
            p_fisher = None

    # Mann-Whitney U on returns
    p_mw: Optional[float] = None
    r_ret_vals = retained.return_90d_pct.dropna().values
    e_ret_vals = excluded.return_90d_pct.dropna().values
    if len(r_ret_vals) >= 3 and len(e_ret_vals) >= 3:
        try:
            _, p_mw = mannwhitneyu(
                r_ret_vals, e_ret_vals, alternative="two-sided"
            )
        except ValueError:
            p_mw = None

    return {
        "axis": cand.axis,
        "threshold": cand.threshold,
        "direction": cand.direction,
        "note": cand.note,
        "n_retained": n_ret,
        "n_excluded": n_exc,
        "hit_rate_retained_pct": round(hr_ret, 4) if hr_ret is not None else None,
        "hit_rate_excluded_pct": round(hr_exc, 4) if hr_exc is not None else None,
        "hit_rate_delta_pp": (
            round(hr_ret - hr_exc, 4) if (hr_ret is not None and hr_exc is not None) else None
        ),
        "alpha_mean_retained_pct": round(alpha_ret, 4) if alpha_ret is not None else None,
        "alpha_mean_excluded_pct": round(alpha_exc, 4) if alpha_exc is not None else None,
        "p_fisher": round(p_fisher, 6) if p_fisher is not None else None,
        "p_mannwhitney": round(p_mw, 6) if p_mw is not None else None,
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--in", dest="in_path", type=str, default="exports/out/signal_audit_v1_4.csv")
    ap.add_argument("--out", dest="out_path", type=str, default="exports/out/audit_v1_4_filter_candidates.csv")
    args = ap.parse_args()

    df = pd.read_csv(args.in_path)
    # Normalize booleans that pandas read as strings
    for col in ("hit_90d", "is_midcap_by_true_mcap", "would_remain_strong_buy", "has_hostile_activist"):
        if col in df.columns and df[col].dtype == object:
            df[col] = df[col].astype(str).str.lower().map({"true": True, "false": False})

    # Baseline report for the audit report to cite
    baseline_hit_rate = df.hit_90d.astype(bool).mean() * 100
    baseline_alpha = df.alpha_90d_pct.dropna().mean()
    logger.info(f"Baseline (142 signals): hit={baseline_hit_rate:.2f}%, alpha={baseline_alpha:+.2f}%")

    candidates = build_candidates()
    logger.info(f"Testing {len(candidates)} candidate filters")

    rows = []
    for c in candidates:
        row = evaluate_candidate(df, c)
        rows.append(row)

    n_tests = len(candidates)
    # Bonferroni adjustment on p_fisher
    for r in rows:
        if r["p_fisher"] is not None:
            r["p_fisher_bonferroni"] = round(min(1.0, r["p_fisher"] * n_tests), 6)
        else:
            r["p_fisher_bonferroni"] = None
        r["n_tests_total"] = n_tests

    # Sort by p_fisher_bonferroni ascending; place nulls last
    rows.sort(key=lambda r: (1 if r["p_fisher_bonferroni"] is None else 0, r["p_fisher_bonferroni"] or 2.0))

    # Locked column order for determinism
    col_order = [
        "axis",
        "threshold",
        "direction",
        "note",
        "n_retained",
        "n_excluded",
        "hit_rate_retained_pct",
        "hit_rate_excluded_pct",
        "hit_rate_delta_pp",
        "alpha_mean_retained_pct",
        "alpha_mean_excluded_pct",
        "p_fisher",
        "p_mannwhitney",
        "p_fisher_bonferroni",
        "n_tests_total",
    ]

    out = Path(args.out_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=col_order, extrasaction="ignore")
        w.writeheader()
        for r in rows:
            # Normalize None to empty
            out_row = {}
            for k in col_order:
                v = r.get(k)
                out_row[k] = "" if v is None else v
            w.writerow(out_row)

    print(f"\n{'='*60}")
    print(f"  FILTER CANDIDATES EVALUATED")
    print(f"  Baseline:     {baseline_hit_rate:.2f}% HR, {baseline_alpha:+.2f}% alpha on 142 signals")
    print(f"  Candidates:   {len(rows)}")
    print(f"  Bonferroni n: {n_tests}")
    print(f"  Output:       {out}")
    print(f"{'='*60}\n")

    # Preview top 10
    print(f"{'rank':>4} {'axis':35} {'thr':>12} {'dir':28} {'n_ex':>5} {'HR_ret':>7} {'HR_exc':>7} {'p_bonf':>9}")
    print("-" * 120)
    for i, r in enumerate(rows[:10], 1):
        axis = (r["axis"] or "")[:35]
        thr = r["threshold"]
        thr_s = f"{thr:.0f}" if isinstance(thr, (int, float)) and thr == thr and abs(thr) < 1e6 else (
            f"{thr:.2e}" if isinstance(thr, (int, float)) and thr == thr else "—"
        )
        p = r["p_fisher_bonferroni"]
        p_s = f"{p:.4f}" if p is not None else "—"
        print(
            f"{i:>4} {axis:35} {thr_s:>12} {(r['direction'] or '')[:28]:28} "
            f"{r['n_excluded']:>5} "
            f"{(r['hit_rate_retained_pct'] or 0):>6.1f}% "
            f"{(r['hit_rate_excluded_pct'] or 0):>6.1f}% "
            f"{p_s:>9}"
        )


if __name__ == "__main__":
    main()
