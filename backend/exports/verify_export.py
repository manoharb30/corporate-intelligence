"""Verify a v1.1 signal export against Neo4j source of truth.

Checks:
  1. CSV and Parquet row counts match.
  2. Row count equals EXPECTED_COUNT (141 for v1.1 baseline).
  3. Per-column null counts (informational — flags critical-field nulls).
  4. Spot-check: 5 random signals re-queried from Neo4j, compared cell-by-cell.

Exits 0 on success, 1 on any failure.

Run from the backend/ directory:
    venv/bin/python -m exports.verify_export --csv <path> --parquet <path>
"""

import argparse
import asyncio
import csv
import logging
import random
import sys
from pathlib import Path

import pyarrow.compute as pc
import pyarrow.parquet as pq

from app.db.neo4j_client import Neo4jClient

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(message)s")


EXPECTED_COUNT = 141
FLOAT_TOL = 0.01
CRITICAL_COLUMNS = [
    "cik", "ticker", "filing_date", "signal_date",
    "num_insiders", "total_value_usd", "return_day0", "spy_return_90d",
]
SPOT_CHECK_FIELDS = [
    ("cik", "cik", "string"),
    ("ticker", "ticker", "string"),
    ("filing_date", "actionable_date", "string"),
    ("num_insiders", "num_insiders", "int"),
    ("total_value_usd", "total_value", "float"),
    ("return_day0", "return_day0", "float"),
]


def load_csv_rows(path: Path) -> list[dict]:
    rows: list[dict] = []
    with open(path, encoding="utf-8") as f:
        reader = csv.DictReader(line for line in f if not line.startswith("#"))
        for row in reader:
            rows.append(row)
    return rows


def null_audit(table) -> dict[str, int]:
    out = {}
    for name in table.column_names:
        out[name] = pc.sum(pc.is_null(table[name])).as_py() or 0
    return out


def log_failures(failures: list[str]) -> None:
    if not failures:
        return
    for f in failures:
        logger.error("  FAIL: %s", f)


async def fetch_from_neo4j(signal_id: str) -> dict | None:
    rows = await Neo4jClient.execute_query(
        """
        MATCH (sp:SignalPerformance {signal_id: $sid})
        RETURN sp
        """,
        {"sid": signal_id},
    )
    if not rows:
        return None
    return dict(rows[0]["sp"])


def compare_value(export_val, neo_val, kind: str) -> bool:
    if kind == "string":
        return (export_val or "") == (neo_val or "")
    if kind == "int":
        try:
            return int(float(export_val)) == int(neo_val or 0)
        except (ValueError, TypeError):
            return False
    if kind == "float":
        try:
            a = float(export_val) if export_val not in ("", None) else None
            b = float(neo_val) if neo_val is not None else None
            if a is None and b is None:
                return True
            if a is None or b is None:
                return False
            return abs(a - b) <= FLOAT_TOL
        except (ValueError, TypeError):
            return False
    return False


async def main() -> int:
    parser = argparse.ArgumentParser(description="Verify v1.1 signal export")
    parser.add_argument("--csv", required=True, type=Path)
    parser.add_argument("--parquet", required=True, type=Path)
    parser.add_argument("--sample-size", type=int, default=5)
    parser.add_argument("--seed", type=int, default=0)
    args = parser.parse_args()

    failures: list[str] = []

    if not args.csv.exists():
        logger.error("CSV not found: %s", args.csv)
        return 1
    if not args.parquet.exists():
        logger.error("Parquet not found: %s", args.parquet)
        return 1

    # ---- 1. Row counts ----
    csv_rows = load_csv_rows(args.csv)
    table = pq.read_table(args.parquet)

    csv_n = len(csv_rows)
    parquet_n = table.num_rows
    logger.info("Row counts — CSV: %d | Parquet: %d | Expected: %d", csv_n, parquet_n, EXPECTED_COUNT)

    if csv_n != parquet_n:
        failures.append(f"Row count mismatch: CSV={csv_n} vs Parquet={parquet_n}")
    if csv_n != EXPECTED_COUNT:
        failures.append(f"Row count {csv_n} != expected {EXPECTED_COUNT}")

    # ---- 2. Null audit ----
    nulls = null_audit(table)
    logger.info("")
    logger.info("Null audit:")
    for col, n in nulls.items():
        flag = ""
        if col in CRITICAL_COLUMNS and n > 0:
            flag = "  <-- CRITICAL"
            failures.append(f"Critical column '{col}' has {n} null(s)")
        logger.info("  %-22s %d%s", col, n, flag)

    # ---- 3. Spot check vs Neo4j ----
    logger.info("")
    random.seed(args.seed)
    sample_size = min(args.sample_size, csv_n)
    samples = random.sample(csv_rows, sample_size)
    logger.info("Spot-check: %d signals vs Neo4j live", sample_size)

    await Neo4jClient.connect()
    try:
        for row in samples:
            sid = row["signal_id"]
            neo = await fetch_from_neo4j(sid)
            if neo is None:
                failures.append(f"Signal {sid} not found in Neo4j")
                logger.error("  %s — NOT FOUND in Neo4j", sid)
                continue
            mismatches = []
            for csv_field, neo_field, kind in SPOT_CHECK_FIELDS:
                export_val = row.get(csv_field)
                neo_val = neo.get(neo_field)
                if not compare_value(export_val, neo_val, kind):
                    mismatches.append(f"{csv_field} csv={export_val!r} neo={neo_val!r}")
            if mismatches:
                failures.append(f"Signal {sid}: {', '.join(mismatches)}")
                logger.error("  %s — MISMATCH: %s", sid, "; ".join(mismatches))
            else:
                logger.info(
                    "  %s — OK  (%s, %s, %s insiders, $%.0f, return_day0=%s)",
                    sid, row.get("ticker"), row.get("filing_date"),
                    row.get("num_insiders"),
                    float(row.get("total_value_usd") or 0),
                    row.get("return_day0"),
                )
    finally:
        await Neo4jClient.disconnect()

    # ---- Report ----
    logger.info("")
    if failures:
        logger.error("=" * 50)
        logger.error("VERIFICATION FAILED (%d issue%s)", len(failures), "s" if len(failures) != 1 else "")
        log_failures(failures)
        return 1

    logger.info("=" * 50)
    logger.info("VERIFICATION PASSED — 0 mismatches across %d spot-checked signals", sample_size)
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
