"""Violin plot of days-to-next-earnings for the 6,327 FILTERED transactions.

The earnings filter rejects transactions where next earnings is >60 days away.
The classification_reason field carries the measured distance in the form
"Earnings in Nd — beyond 60d threshold". This plot shows the distribution
of N across all FILTERED rows, so we can see whether rejections cluster just
past the threshold or are spread across the window.

Output: /tmp/filtered_earnings_distance_violin.png
"""
import asyncio
import re
import sys
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np

sys.path.insert(0, str(Path(__file__).parent))
from app.db.neo4j_client import Neo4jClient

OUT_PATH = "/tmp/filtered_earnings_distance_violin.png"


async def fetch_days() -> list[int]:
    await Neo4jClient.connect()
    rows = await Neo4jClient.execute_query("""
        MATCH (t:InsiderTransaction)
        WHERE t.classification = 'FILTERED'
          AND t.classification_rule = 'EARNINGS_FILTER'
        RETURN t.classification_reason AS reason
    """)
    pattern = re.compile(r"Earnings in (-?\d+)d")
    days = []
    unparsed = 0
    for r in rows:
        m = pattern.search(r.get("reason") or "")
        if m:
            days.append(int(m.group(1)))
        else:
            unparsed += 1
    print(f"Parsed {len(days)} days from {len(rows)} FILTERED rows"
          f" ({unparsed} unparseable)")
    return days


def plot(days: list[int]) -> None:
    arr = np.array(days)
    n = len(arr)
    p25, p50, p75 = np.percentile(arr, [25, 50, 75])
    p90, p95, p99 = np.percentile(arr, [90, 95, 99])
    print(f"n={n}  min={arr.min()}  p25={p25:.0f}  median={p50:.0f}  "
          f"p75={p75:.0f}  p90={p90:.0f}  p95={p95:.0f}  p99={p99:.0f}  max={arr.max()}")

    fig, ax = plt.subplots(figsize=(8, 7))

    parts = ax.violinplot(
        arr, positions=[1], widths=0.7,
        showmedians=True, showextrema=True,
    )
    for pc in parts["bodies"]:
        pc.set_facecolor("#4B89DC")
        pc.set_edgecolor("#2C5A9A")
        pc.set_alpha(0.6)
    # Style the whiskers / median
    for key in ("cmedians", "cmins", "cmaxes", "cbars"):
        if key in parts:
            parts[key].set_edgecolor("#2C5A9A")

    # Threshold line
    ax.axhline(60, color="red", linestyle="--", linewidth=1.5,
               label="60d filter threshold")

    # Median annotation
    ax.annotate(
        f"Median: {p50:.0f}d",
        xy=(1.0, p50), xytext=(1.45, p50),
        fontsize=10, va="center",
        arrowprops=dict(arrowstyle="-", color="gray", lw=0.8),
    )

    ax.set_xticks([1])
    ax.set_xticklabels([f"FILTERED (n={n:,})"])
    ax.set_ylabel("Days until next earnings")
    ax.set_title(
        "Days-to-earnings distribution for FILTERED transactions\n"
        f"all n={n:,} rejected because next earnings > 60d away"
    )
    ax.grid(axis="y", linestyle=":", alpha=0.4)
    ax.legend(loc="upper right")

    # Subtitle with percentile stats
    stats_text = (
        f"min={arr.min()}   p25={p25:.0f}   median={p50:.0f}   "
        f"p75={p75:.0f}   p90={p90:.0f}   p99={p99:.0f}   max={arr.max()}"
    )
    fig.text(0.5, 0.02, stats_text, ha="center", fontsize=8,
             color="#555", family="monospace")

    plt.tight_layout(rect=(0, 0.04, 1, 1))
    plt.savefig(OUT_PATH, dpi=140)
    print(f"Saved: {OUT_PATH}")


async def main():
    days = await fetch_days()
    if not days:
        print("No FILTERED rows found.")
        return
    plot(days)


if __name__ == "__main__":
    asyncio.run(main())
