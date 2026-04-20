"""v1.4 Phase 11 per-loser detail printer.

Emits one markdown block per losing signal from `signal_audit_v1_4.csv`.
Each block has structured fields + a `root_cause_tag` placeholder
(default: "unclassified") for manual review.

Run from backend/:
    venv/bin/python -m exports.audit_v1_4_loser_detail
    venv/bin/python -m exports.audit_v1_4_loser_detail --in exports/out/signal_audit_v1_4.csv --out exports/out/audit_v1_4_losers.md
"""

import argparse
import logging
from pathlib import Path

import pandas as pd

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")


CANDIDATE_TAGS = [
    "distressed_penny_stock",
    "c_suite_distribution_before",
    "post_earnings_disappointment",
    "sector_drawdown",
    "dilution_event",
    "activist_escalation",
    "narrative_reversal",
    "random_miss",
    "none_identified",
]


def fmt_usd(v, m=False, b=False) -> str:
    if pd.isna(v):
        return "null"
    if b:
        return f"${v/1e9:,.2f}B"
    if m:
        return f"${v/1e6:,.0f}M"
    return f"${v:,.0f}"


def fmt_pct(v) -> str:
    if pd.isna(v):
        return "null"
    return f"{v:+.2f}%"


def fmt_bool(v) -> str:
    if pd.isna(v):
        return "null"
    if isinstance(v, str):
        return v
    return "true" if v else "false"


def emit_block(row: pd.Series) -> str:
    """Produce one markdown block for a losing signal."""
    ticker = row.get("ticker") or "—"
    company = row.get("company_name") or "—"
    sd = row.get("signal_date") or "—"

    mcap_true = row.get("mcap_at_signal_true_usd")
    mcap_src = row.get("mcap_at_signal_true_source") or "null"

    pre_count = int(row.get("pre_cluster_sells_count_180d") or 0)
    pre_sellers = int(row.get("pre_cluster_sellers_count_180d") or 0)
    pre_value = row.get("pre_cluster_sells_value_usd_180d") or 0
    pre_latest = row.get("pre_cluster_sells_latest_date_180d") or "—"
    post_count = int(row.get("post_signal_sells_count_90d") or 0)
    post_value = row.get("post_signal_sells_value_usd_90d") or 0

    pre_summary = (
        f"{pre_count} sells by {pre_sellers} officers, "
        f"{fmt_usd(pre_value)} total"
        + (f", latest: {pre_latest}" if pre_count > 0 else "")
    )
    post_summary = (
        f"{post_count} sells, {fmt_usd(post_value)} total"
        if post_count > 0
        else "none"
    )

    return f"""### {ticker} · {company} · {sd}

| field | value |
|---|---|
| return_90d_pct | {fmt_pct(row.get('return_90d_pct'))} |
| alpha_90d_pct | {fmt_pct(row.get('alpha_90d_pct'))} |
| spy_return_90d_pct | {fmt_pct(row.get('spy_return_90d_pct'))} |
| price_day0 → price_day90 | ${row.get('price_day0'):.2f} → ${row.get('price_day90'):.2f} (split-adjusted) |
| avg_raw_execution_price_usd | {fmt_usd(row.get('avg_raw_execution_price_usd'))} |
| num_insiders | {int(row.get('num_insiders') or 0)} |
| total_cluster_value_usd | {fmt_usd(row.get('total_cluster_value_usd'))} |
| mcap_at_signal_true_usd | {fmt_usd(mcap_true, m=True)} (source: {mcap_src}) |
| is_midcap_by_true_mcap | {fmt_bool(row.get('is_midcap_by_true_mcap'))} |
| market_cap_ratio_estimate_usd (old) | {fmt_usd(row.get('market_cap_ratio_estimate_usd'), m=True)} |
| mcap_delta_pct | {fmt_pct(row.get('mcap_delta_pct'))} |
| industry | {row.get('industry') or '—'} |
| days_to_next_earnings_at_signal | {row.get('days_to_next_earnings_at_signal') if not pd.isna(row.get('days_to_next_earnings_at_signal')) else 'null'} |
| days_from_last_earnings_at_signal | {row.get('days_from_last_earnings_at_signal') if not pd.isna(row.get('days_from_last_earnings_at_signal')) else 'null'} |
| pre_cluster officer sells (180d) | {pre_summary} |
| post_signal officer sells (90d) | {post_summary} |
| stock_volatility_30d_pct (annualized) | {row.get('stock_volatility_30d_pct'):.1f}% |
| has_hostile_activist | {fmt_bool(row.get('has_hostile_activist'))} |

**root_cause_tag:** unclassified

*Candidate tags (fill manually):* {" | ".join(CANDIDATE_TAGS)}

---
"""


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--in", dest="in_path", type=str, default="exports/out/signal_audit_v1_4.csv")
    ap.add_argument("--out", dest="out_path", type=str, default="exports/out/audit_v1_4_losers.md")
    args = ap.parse_args()

    df = pd.read_csv(args.in_path)
    # Normalize hit_90d to bool
    if df["hit_90d"].dtype == object:
        df["hit_90d"] = df["hit_90d"].astype(str).str.lower().map(
            {"true": True, "false": False}
        )
    losers = df[~df.hit_90d.astype(bool)].copy()
    losers.sort_values("return_90d_pct", ascending=True, inplace=True)

    logger.info(f"Losers: {len(losers)} of {len(df)} ({len(losers)/len(df)*100:.1f}%)")

    out = Path(args.out_path)
    out.parent.mkdir(parents=True, exist_ok=True)

    with open(out, "w") as f:
        f.write(f"# v1.4 Audit — Per-Loser Detail\n\n")
        f.write(
            f"*{len(losers)} losing signals from `signal_audit_v1_4.csv` "
            f"({len(df)} total, {len(losers)/len(df)*100:.1f}% loss rate). "
            f"Sorted worst → best by return_90d_pct.*\n\n"
        )
        f.write(
            "Each block has a `root_cause_tag` placeholder set to `unclassified`. "
            "Fill manually during review; do not auto-populate.\n\n---\n\n"
        )
        for _, row in losers.iterrows():
            f.write(emit_block(row))

    print(f"\nWrote {len(losers)} loser blocks to {out}\n")


if __name__ == "__main__":
    main()
