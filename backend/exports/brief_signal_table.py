"""Generate a month-grouped markdown of all 141 signals for the brief's §5.7.

Reads the Phase 4 CSV and stats.json, groups signals by filing-date month,
emits one subheading + summary + per-signal table per month (most recent
month first). Output matches how the live Performance page organizes signals.

Run from backend/:
    venv/bin/python -m exports.brief_signal_table
"""

import argparse
import csv
import datetime as _dt
import json
import sys
from collections import defaultdict
from pathlib import Path


def find_latest_csv(output_dir: Path) -> Path:
    candidates = sorted(output_dir.glob("signals_v1_1_*.csv"), reverse=True)
    if not candidates:
        raise FileNotFoundError(f"No signals_v1_1_*.csv found in {output_dir}")
    return candidates[0]


def fmt_price(s: str) -> str:
    try:
        return f"${float(s):,.2f}"
    except (ValueError, TypeError):
        return "—"


def fmt_pct(s: str) -> str:
    try:
        v = float(s)
        return f"{v:+.1f}%"
    except (ValueError, TypeError):
        return "—"


def fmt_pp(s: str) -> str:
    try:
        v = float(s)
        return f"{v:+.1f}"
    except (ValueError, TypeError):
        return "—"


def month_label(yyyymm: str) -> str:
    try:
        y, m = yyyymm.split("-")
        month_name = _dt.date(int(y), int(m), 1).strftime("%B")
        return f"{month_name} {y}"
    except (ValueError, TypeError):
        return yyyymm


def main() -> int:
    parser = argparse.ArgumentParser(description="Emit month-grouped per-signal markdown for brief")
    parser.add_argument("--csv", type=Path, default=None)
    parser.add_argument("--export-dir", type=Path, default=Path("exports/out"))
    parser.add_argument(
        "--stats-json",
        type=Path,
        default=Path("../.paul/phases/05-research-brief-pdf/stats.json"),
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("../.paul/phases/05-research-brief-pdf/per_signal_table.md"),
    )
    args = parser.parse_args()

    csv_path = args.csv or find_latest_csv(args.export_dir)

    rows: list[dict] = []
    with open(csv_path, encoding="utf-8") as f:
        reader = csv.DictReader(line for line in f if not line.startswith("#"))
        for row in reader:
            rows.append(row)

    # Load monthly aggregate stats
    with open(args.stats_json, encoding="utf-8") as f:
        stats = json.load(f)
    by_month = stats.get("breakdowns", {}).get("by_month", {})

    # Group rows by month, each month sorted internally by filing_date desc
    groups: dict[str, list[dict]] = defaultdict(list)
    for r in rows:
        key = r.get("filing_date", "")[:7]
        groups[key].append(r)
    for k in groups:
        groups[k].sort(key=lambda r: r.get("filing_date", ""), reverse=True)

    months_desc = sorted(groups.keys(), reverse=True)

    lines: list[str] = []
    hostile_count_total = 0

    for yyyymm in months_desc:
        gs = groups[yyyymm]
        summary = by_month.get(yyyymm, {})
        n = summary.get("n", len(gs))
        hr = summary.get("hit_rate")
        ret = summary.get("mean_return_day0")
        alpha = summary.get("mean_alpha")

        summary_parts = [f"n = {n}"]
        if hr is not None:
            summary_parts.append(f"hit rate {hr * 100:.0f}%")
        if ret is not None:
            summary_parts.append(f"mean return {ret:+.1f}%")
        if alpha is not None:
            summary_parts.append(f"mean alpha {alpha:+.1f} pp")

        lines.append(f"#### {month_label(yyyymm)}")
        lines.append("")
        lines.append(f"_{' · '.join(summary_parts)}_")
        lines.append("")
        lines.append("| Filing Date | Ticker | Conv | #I | Entry | Exit | 90d Return | Alpha (pp) |")
        lines.append("|---|---|---|---|---|---|---|---|")

        for r in gs:
            ticker = r["ticker"]
            hostile = r.get("hostile_flag", "").strip().lower() == "true"
            if hostile:
                ticker = f"{ticker}†"
                hostile_count_total += 1
            conv = r.get("signal_level", "").strip().upper() or "—"

            lines.append(
                f"| {r['filing_date']} "
                f"| {ticker} "
                f"| {conv} "
                f"| {r['num_insiders']} "
                f"| {fmt_price(r['price_day0'])} "
                f"| {fmt_price(r['price_day90'])} "
                f"| {fmt_pct(r['return_day0'])} "
                f"| {fmt_pp(r['alpha_90d'])} |"
            )

        lines.append("")  # blank line between months

    if hostile_count_total:
        lines.append(f"*† Signal with contemporaneous hostile Schedule 13D filing ({hostile_count_total} of {len(rows)}).*")

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(
        f"Wrote {args.output} — {len(rows)} rows across {len(months_desc)} months, "
        f"{hostile_count_total} hostile-flagged"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
