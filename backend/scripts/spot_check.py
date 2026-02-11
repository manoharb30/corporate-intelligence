#!/usr/bin/env python3
"""
Spot check extracted data against known facts.

Compares extracted officers, major holders, and subsidiaries
against manually verified data points.

Usage:
    python -m scripts.spot_check [--cik CIK]
"""

import argparse
import asyncio
import json
import sys
from datetime import datetime
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.db.neo4j_client import Neo4jClient
from tests.test_companies import KNOWN_FACTS, TEST_COMPANIES


def fuzzy_match(name1: str, name2: str) -> bool:
    """Check if two names match (case-insensitive, partial match)."""
    n1 = name1.lower().strip()
    n2 = name2.lower().strip()

    # Exact match
    if n1 == n2:
        return True

    # One contains the other
    if n1 in n2 or n2 in n1:
        return True

    # Check last name match (for persons)
    parts1 = n1.split()
    parts2 = n2.split()
    if len(parts1) >= 2 and len(parts2) >= 2:
        if parts1[-1] == parts2[-1]:  # Last name match
            return True

    return False


async def get_company_officers(cik: str) -> list[str]:
    """Get officers/directors for a company from the graph."""
    query = """
    MATCH (c:Company {cik: $cik})<-[:OFFICER_OF|DIRECTOR_OF]-(p:Person)
    RETURN DISTINCT p.name as name
    """
    results = await Neo4jClient.execute_query(query, {"cik": cik})
    return [r["name"] for r in results]


async def get_company_owners(cik: str) -> list[dict]:
    """Get owners for a company from the graph."""
    query = """
    MATCH (c:Company {cik: $cik})<-[r:OWNS]-(owner)
    RETURN
        owner.name as name,
        labels(owner)[0] as type,
        r.percentage as percentage
    ORDER BY COALESCE(r.percentage, 0) DESC
    """
    results = await Neo4jClient.execute_query(query, {"cik": cik})
    return [dict(r) for r in results]


async def get_company_subsidiaries(cik: str) -> list[str]:
    """Get subsidiaries for a company from the graph."""
    query = """
    MATCH (c:Company {cik: $cik})-[:OWNS]->(sub:Company)
    RETURN DISTINCT sub.name as name
    """
    results = await Neo4jClient.execute_query(query, {"cik": cik})
    return [r["name"] for r in results]


async def spot_check_company(cik: str) -> dict:
    """Run spot check for a single company."""
    facts = KNOWN_FACTS.get(cik)
    if not facts:
        return {"error": f"No known facts for CIK {cik}"}

    result = {
        "cik": cik,
        "name": facts["name"],
        "ticker": facts["ticker"],
        "checks": [],
        "passed": 0,
        "failed": 0,
        "warnings": 0,
    }

    # Check officers
    extracted_officers = await get_company_officers(cik)
    for expected_officer in facts.get("expected_officers", []):
        found = any(fuzzy_match(expected_officer, eo) for eo in extracted_officers)
        check = {
            "type": "officer",
            "expected": expected_officer,
            "found": found,
            "status": "PASS" if found else "FAIL",
        }
        result["checks"].append(check)
        if found:
            result["passed"] += 1
        else:
            result["failed"] += 1

    # Check major holders
    extracted_owners = await get_company_owners(cik)
    owner_names = [o["name"] for o in extracted_owners]
    for expected_holder in facts.get("expected_major_holders", []):
        found = any(fuzzy_match(expected_holder, on) for on in owner_names)
        check = {
            "type": "major_holder",
            "expected": expected_holder,
            "found": found,
            "status": "PASS" if found else "FAIL",
        }
        result["checks"].append(check)
        if found:
            result["passed"] += 1
        else:
            result["failed"] += 1

    # Check subsidiary count
    extracted_subsidiaries = await get_company_subsidiaries(cik)
    min_expected = facts.get("subsidiary_count_min", 0)
    actual_count = len(extracted_subsidiaries)
    subsidiary_ok = actual_count >= min_expected * 0.5  # Allow 50% margin

    check = {
        "type": "subsidiary_count",
        "expected_min": min_expected,
        "actual": actual_count,
        "status": "PASS" if subsidiary_ok else "WARN",
    }
    result["checks"].append(check)
    if subsidiary_ok:
        result["passed"] += 1
    else:
        result["warnings"] += 1

    # Calculate score
    total = result["passed"] + result["failed"] + result["warnings"]
    result["score"] = result["passed"] / total if total > 0 else 0
    result["extracted_officers"] = extracted_officers[:10]
    result["extracted_owners"] = owner_names[:10]
    result["extracted_subsidiary_count"] = actual_count

    return result


async def run_spot_checks(cik: str | None = None) -> dict:
    """Run spot checks for all or one company."""

    await Neo4jClient.connect()

    try:
        if cik:
            ciks_to_check = [cik]
        else:
            ciks_to_check = list(KNOWN_FACTS.keys())

        report = {
            "run_date": datetime.now().isoformat(),
            "companies_checked": len(ciks_to_check),
            "results": [],
            "summary": {
                "total_passed": 0,
                "total_failed": 0,
                "total_warnings": 0,
            },
        }

        print("=" * 60)
        print("SPOT CHECK REPORT")
        print("=" * 60)

        for check_cik in ciks_to_check:
            result = await spot_check_company(check_cik)
            report["results"].append(result)

            if "error" in result:
                print(f"\n{check_cik}: {result['error']}")
                continue

            report["summary"]["total_passed"] += result["passed"]
            report["summary"]["total_failed"] += result["failed"]
            report["summary"]["total_warnings"] += result["warnings"]

            # Print result
            score_pct = result["score"] * 100
            status = "PASS" if score_pct >= 70 else "WARN" if score_pct >= 50 else "FAIL"
            print(f"\n{result['ticker']} ({result['name']}): {status} ({score_pct:.0f}%)")
            print(f"  Checks: {result['passed']} passed, {result['failed']} failed, {result['warnings']} warnings")

            for check in result["checks"]:
                icon = "✓" if check["status"] == "PASS" else "⚠" if check["status"] == "WARN" else "✗"
                if check["type"] in ["officer", "major_holder"]:
                    print(f"    {icon} {check['type']}: {check['expected']} - {check['status']}")
                else:
                    print(f"    {icon} {check['type']}: {check.get('actual', 'N/A')}/{check.get('expected_min', 'N/A')} - {check['status']}")

        # Print summary
        total = report["summary"]["total_passed"] + report["summary"]["total_failed"]
        if total > 0:
            overall_score = report["summary"]["total_passed"] / total * 100
        else:
            overall_score = 0

        print("\n" + "=" * 60)
        print("SUMMARY")
        print("=" * 60)
        print(f"Total checks: {total}")
        print(f"Passed: {report['summary']['total_passed']}")
        print(f"Failed: {report['summary']['total_failed']}")
        print(f"Warnings: {report['summary']['total_warnings']}")
        print(f"Overall accuracy: {overall_score:.1f}%")
        print("=" * 60)

        report["summary"]["overall_accuracy"] = overall_score

        # Save report
        report_path = Path("logs/spot_check_report.json")
        with open(report_path, "w") as f:
            json.dump(report, f, indent=2, default=str)
        print(f"\nFull report saved to {report_path}")

        return report

    finally:
        await Neo4jClient.disconnect()


def main():
    parser = argparse.ArgumentParser(description="Spot check extracted data against known facts")
    parser.add_argument(
        "--cik",
        type=str,
        help="Check specific CIK only (e.g., 0000320193 for Apple)",
    )

    args = parser.parse_args()

    # Ensure logs directory exists
    Path("logs").mkdir(exist_ok=True)

    report = asyncio.run(run_spot_checks(args.cik))

    # Exit with error if accuracy below threshold
    if report["summary"]["overall_accuracy"] < 50:
        print("\nWARNING: Overall accuracy below 50%!")
        sys.exit(1)


if __name__ == "__main__":
    main()
