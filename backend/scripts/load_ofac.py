"""
CLI script to load/update OFAC SDN data.

Usage:
    python -m scripts.load_ofac                    # Download and load SDN list
    python -m scripts.load_ofac --match            # Also run matching against existing entities
    python -m scripts.load_ofac --match --auto-link  # Auto-link high confidence matches
    python -m scripts.load_ofac --force            # Force re-download even if cached
    python -m scripts.load_ofac --stats            # Just show current SDN stats
    python -m scripts.load_ofac --clear            # Clear all OFAC data (careful!)
"""

import argparse
import asyncio
import logging
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.db.neo4j_client import Neo4jClient
from ingestion.ofac.ofac_client import OFACClient
from ingestion.ofac.ofac_parser import OFACParser
from ingestion.ofac.ofac_loader import OFACLoader
from ingestion.ofac.ofac_matcher import OFACMatcher

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


async def load_ofac_data(force_refresh: bool = False) -> dict:
    """Download, parse, and load OFAC SDN data."""
    logger.info("Starting OFAC SDN data load...")

    # Initialize components
    client = OFACClient()
    parser = OFACParser()
    loader = OFACLoader()

    try:
        # 1. Download SDN list
        logger.info("Downloading SDN list...")
        xml_content, download_date = await client.download_sdn_xml(
            force_refresh=force_refresh
        )
        logger.info(f"Downloaded {len(xml_content):,} bytes (date: {download_date})")

        # 2. Parse XML
        logger.info("Parsing XML...")
        entries = parser.parse(xml_content, source_date=download_date)
        logger.info(f"Parsed {len(entries)} SDN entries")

        # 3. Create indexes
        logger.info("Creating indexes...")
        await loader.create_indexes()

        # 4. Load into Neo4j
        logger.info("Loading into Neo4j...")
        stats = await loader.load_entries(entries)

        logger.info("OFAC load complete!")
        return {
            "download_date": str(download_date),
            "entries_parsed": len(entries),
            "load_stats": stats,
            "parser_stats": parser.get_stats(),
        }

    finally:
        await client.close()


async def run_matching(auto_link: bool = False, fuzzy: bool = True) -> dict:
    """Run OFAC matcher to link SDN entries to existing entities."""
    logger.info("Running OFAC matching...")

    matcher = OFACMatcher()
    matches = await matcher.find_matches(auto_link=auto_link, fuzzy_matching=fuzzy)

    logger.info(f"Found {len(matches)} potential matches")

    # Log match details
    for match in matches[:10]:  # Show first 10
        logger.info(
            f"  {match.match_method.value}: {match.existing_entity_name} "
            f"-> {match.sanctioned_entity_name} (confidence: {match.confidence:.2f})"
        )

    if len(matches) > 10:
        logger.info(f"  ... and {len(matches) - 10} more matches")

    # Show matches requiring review
    needs_review = [m for m in matches if m.requires_review]
    if needs_review:
        logger.warning(
            f"{len(needs_review)} matches require human review (fuzzy matches)"
        )

    return {
        "total_matches": len(matches),
        "stats": matcher.stats,
        "matches_requiring_review": len(needs_review),
    }


async def show_stats() -> dict:
    """Show current SDN statistics."""
    loader = OFACLoader()
    stats = await loader.get_sdn_stats()

    logger.info("Current SDN Statistics:")
    logger.info(f"  Sanctioned Persons: {stats.get('sanctioned_persons', 0)}")
    logger.info(f"  Sanctioned Companies: {stats.get('sanctioned_companies', 0)}")
    logger.info(f"  Total Sanctioned: {stats.get('total_sanctioned', 0)}")
    logger.info(f"  Last Update: {stats.get('last_update', 'Never')}")

    # Also show linked entities
    matcher = OFACMatcher()
    linked = await matcher.get_linked_entities()
    unlinked = await matcher.get_unlinked_sanctioned_entities()

    logger.info(f"  Linked to existing entities: {len(linked)}")
    logger.info(f"  Unlinked SDN entries: {len(unlinked)}")

    return {
        "sdn_stats": stats,
        "linked_count": len(linked),
        "unlinked_count": len(unlinked),
    }


async def clear_data() -> dict:
    """Clear all OFAC data from the database."""
    loader = OFACLoader()

    logger.warning("Clearing all OFAC SDN data...")
    result = await loader.clear_sdn_data()

    logger.info(f"Deleted {result['nodes_deleted']} nodes")
    logger.info(f"Deleted {result['relationships_deleted']} relationships")

    return result


async def main():
    parser = argparse.ArgumentParser(
        description="Load and manage OFAC SDN data",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )

    parser.add_argument(
        "--match",
        action="store_true",
        help="Run matching against existing entities after loading",
    )
    parser.add_argument(
        "--auto-link",
        action="store_true",
        help="Automatically link high-confidence matches (requires --match)",
    )
    parser.add_argument(
        "--no-fuzzy",
        action="store_true",
        help="Skip fuzzy matching (faster, but may miss matches)",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Force re-download even if recent cache exists",
    )
    parser.add_argument(
        "--stats",
        action="store_true",
        help="Only show current SDN statistics (don't load)",
    )
    parser.add_argument(
        "--clear",
        action="store_true",
        help="Clear all OFAC data from database",
    )
    parser.add_argument(
        "--match-only",
        action="store_true",
        help="Only run matching (skip download/load)",
    )

    args = parser.parse_args()

    # Connect to Neo4j
    await Neo4jClient.connect()

    try:
        results = {}

        if args.stats:
            # Just show stats
            results = await show_stats()

        elif args.clear:
            # Confirm before clearing
            confirm = input("Are you sure you want to clear all OFAC data? (yes/no): ")
            if confirm.lower() == "yes":
                results = await clear_data()
            else:
                logger.info("Cancelled")
                return

        elif args.match_only:
            # Just run matching
            results["matching"] = await run_matching(
                auto_link=args.auto_link,
                fuzzy=not args.no_fuzzy,
            )

        else:
            # Full load
            results["load"] = await load_ofac_data(force_refresh=args.force)

            if args.match:
                results["matching"] = await run_matching(
                    auto_link=args.auto_link,
                    fuzzy=not args.no_fuzzy,
                )

        # Print final summary
        print("\n" + "=" * 60)
        print("OFAC Load Complete")
        print("=" * 60)
        for key, value in results.items():
            print(f"\n{key.upper()}:")
            if isinstance(value, dict):
                for k, v in value.items():
                    print(f"  {k}: {v}")
            else:
                print(f"  {value}")

    finally:
        await Neo4jClient.disconnect()


if __name__ == "__main__":
    asyncio.run(main())
