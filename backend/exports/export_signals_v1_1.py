"""Export LookInsight v1.1 signal data (141 mature strong_buy).

Produces CSV + Parquet with full provenance for institutional distribution.
Reads only from Neo4j — no SEC/yfinance calls at export time.

Run from the backend/ directory:
    venv/bin/python -m exports.export_signals_v1_1
    venv/bin/python -m exports.export_signals_v1_1 --output-dir exports/out --date-suffix 2026-04-19

See exports/DATA_DICTIONARY.md for the authoritative column spec.
"""

import argparse
import asyncio
import csv
import logging
import os
from datetime import date, datetime
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq

from app.db.neo4j_client import Neo4jClient
from app.services.insider_cluster_service import InsiderClusterService

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")


COLUMNS = [
    ("signal_id", pa.string()),
    ("cik", pa.string()),
    ("ticker", pa.string()),
    ("company_name", pa.string()),
    ("industry", pa.string()),
    ("signal_date", pa.string()),
    ("filing_date", pa.string()),
    ("age_days", pa.int32()),
    ("is_mature", pa.bool_()),
    ("direction", pa.string()),
    ("conviction_tier", pa.string()),
    ("signal_level", pa.string()),
    ("num_insiders", pa.int32()),
    ("total_value_usd", pa.float64()),
    ("market_cap_usd", pa.float64()),
    ("market_cap_tier", pa.string()),
    ("pct_of_mcap", pa.float64()),
    ("price_day0", pa.float64()),
    ("price_day90", pa.float64()),
    ("price_current", pa.float64()),
    ("return_day0", pa.float64()),
    ("return_day1", pa.float64()),
    ("return_day2", pa.float64()),
    ("return_day3", pa.float64()),
    ("return_day5", pa.float64()),
    ("return_day7", pa.float64()),
    ("return_current", pa.float64()),
    ("spy_return_90d", pa.float64()),
    ("alpha_90d", pa.float64()),
    ("cluster_members", pa.string()),
    ("primary_form4_url", pa.string()),
    ("hostile_flag", pa.bool_()),
    ("computed_at", pa.string()),
]

COHORT_COUNT = 141


def market_cap_tier(mcap):
    if mcap is None:
        return "unknown"
    if mcap < 50_000_000:
        return "microcap"
    if mcap < 300_000_000:
        return "smallcap"
    if mcap <= 5_000_000_000:
        return "midcap"
    if mcap <= 10_000_000_000:
        return "midcap-large"
    return "largecap"


def compute_alpha(return_value, spy_return):
    if return_value is None or spy_return is None:
        return None
    return round(return_value - spy_return, 2)


def compute_age_days(filing_date_str, today=None):
    if not filing_date_str:
        return None
    try:
        fd = datetime.strptime(filing_date_str[:10], "%Y-%m-%d").date()
    except (ValueError, TypeError):
        return None
    today = today or date.today()
    return (today - fd).days


async def fetch_cohort():
    """Fetch all 141 mature strong_buy signals + company context."""
    query = """
        MATCH (c:Company)-[:HAS_SIGNAL_PERF]->(sp:SignalPerformance)
        WHERE sp.direction = 'buy'
          AND sp.is_mature = true
          AND sp.conviction_tier = 'strong_buy'
        RETURN sp, c.sic_description AS industry
        ORDER BY sp.signal_date DESC
    """
    return await Neo4jClient.execute_query(query)


async def build_rows():
    """Build one dict per signal with all 32 columns populated."""
    cohort = await fetch_cohort()
    total = len(cohort)
    logger.info("Fetched %d signals from Neo4j (expected %d)", total, COHORT_COUNT)
    if total != COHORT_COUNT:
        logger.warning(
            "Cohort size %d != expected %d. Re-run SignalPerformance compute "
            "if data drifted, or update COHORT_COUNT if this is intentional.",
            total, COHORT_COUNT,
        )

    today = date.today()
    rows = []
    for i, entry in enumerate(cohort, 1):
        sp = entry["sp"]
        industry = entry.get("industry") or ""
        signal_id = sp["signal_id"]

        detail = await InsiderClusterService.get_cluster_detail(signal_id)
        cluster = (detail or {}).get("cluster_detail") or {}
        buyers = cluster.get("buyers") or []
        has_hostile = bool((detail or {}).get("has_hostile_activist"))

        insider_names = sorted({b.get("name") or "" for b in buyers if b.get("name")})
        cluster_members = " | ".join(insider_names)

        primary_form4_url = ""
        for b in buyers:
            url = b.get("form4_url") or ""
            if url.startswith("http"):
                primary_form4_url = url
                break

        filing_date = sp.get("actionable_date") or sp.get("signal_date")
        total_value = sp.get("total_value")
        mcap = sp.get("market_cap")
        return_day0 = sp.get("return_day0")
        spy_ret = sp.get("spy_return_90d")

        row = {
            "signal_id": signal_id,
            "cik": sp.get("cik") or "",
            "ticker": sp.get("ticker") or "",
            "company_name": sp.get("company_name") or "",
            "industry": industry,
            "signal_date": sp.get("signal_date") or "",
            "filing_date": filing_date or "",
            "age_days": compute_age_days(filing_date, today),
            "is_mature": bool(sp.get("is_mature")),
            "direction": sp.get("direction") or "",
            "conviction_tier": sp.get("conviction_tier") or "",
            "signal_level": (sp.get("signal_level") or "").lower(),
            "num_insiders": int(sp.get("num_insiders") or 0),
            "total_value_usd": float(total_value) if total_value is not None else None,
            "market_cap_usd": float(mcap) if mcap is not None else None,
            "market_cap_tier": market_cap_tier(mcap),
            "pct_of_mcap": float(sp.get("pct_of_mcap")) if sp.get("pct_of_mcap") is not None else None,
            "price_day0": sp.get("price_day0"),
            "price_day90": sp.get("price_day90"),
            "price_current": sp.get("price_current"),
            "return_day0": return_day0,
            "return_day1": sp.get("return_day1"),
            "return_day2": sp.get("return_day2"),
            "return_day3": sp.get("return_day3"),
            "return_day5": sp.get("return_day5"),
            "return_day7": sp.get("return_day7"),
            "return_current": sp.get("return_current"),
            "spy_return_90d": spy_ret,
            "alpha_90d": compute_alpha(return_day0, spy_ret),
            "cluster_members": cluster_members,
            "primary_form4_url": primary_form4_url,
            "hostile_flag": has_hostile,
            "computed_at": sp.get("computed_at") or "",
        }
        rows.append(row)

        if i % 25 == 0 or i == total:
            logger.info("  processed %d/%d", i, total)

    return rows


def write_csv(rows, path):
    column_names = [name for name, _ in COLUMNS]
    with open(path, "w", newline="", encoding="utf-8") as f:
        f.write("# LookInsight v1.1 signals — see DATA_DICTIONARY.md\n")
        writer = csv.DictWriter(f, fieldnames=column_names, lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow({k: ("" if row.get(k) is None else row.get(k)) for k in column_names})
    logger.info("Wrote CSV: %s (%d rows)", path, len(rows))


def write_parquet(rows, path):
    schema = pa.schema(COLUMNS)
    column_names = [name for name, _ in COLUMNS]
    arrays = []
    for name, pa_type in COLUMNS:
        values = [row.get(name) for row in rows]
        arrays.append(pa.array(values, type=pa_type))
    table = pa.Table.from_arrays(arrays, names=column_names)
    pq.write_table(table, path)
    logger.info("Wrote Parquet: %s (%d rows)", path, table.num_rows)


async def main():
    parser = argparse.ArgumentParser(description="Export v1.1 signal data")
    parser.add_argument("--output-dir", default="exports/out", help="Directory for output files")
    parser.add_argument("--date-suffix", default=date.today().isoformat(), help="Date suffix for filenames (YYYY-MM-DD)")
    args = parser.parse_args()

    os.makedirs(args.output_dir, exist_ok=True)
    csv_path = Path(args.output_dir) / f"signals_v1_1_{args.date_suffix}.csv"
    parquet_path = Path(args.output_dir) / f"signals_v1_1_{args.date_suffix}.parquet"

    await Neo4jClient.connect()
    try:
        rows = await build_rows()
        write_csv(rows, csv_path)
        write_parquet(rows, parquet_path)
    finally:
        await Neo4jClient.disconnect()

    logger.info("Done. %d rows written to %s and %s", len(rows), csv_path, parquet_path)


if __name__ == "__main__":
    asyncio.run(main())
