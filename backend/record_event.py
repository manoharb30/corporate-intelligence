"""Operator CLI: record one SignalEvent against an open signal.

Usage:
    python record_event.py TICKER SIGNAL_DATE \
        --date 2026-07-20 --type earnings_call --direction confirming \
        --headline "Q2 print: 7/8 promises pass" \
        [--detail "..."] [--source-url "https://..."]

Types: earnings_call guidance capital_action regulatory insider_followon ma analyst index
Directions: confirming breaking neutral
"""
import argparse
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from app.db.neo4j_client import Neo4jClient
from app.services.signal_watch_service import SignalWatchService


async def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("ticker")
    ap.add_argument("signal_date")
    ap.add_argument("--date", required=True, dest="event_date")
    ap.add_argument("--type", required=True, dest="event_type")
    ap.add_argument("--direction", required=True)
    ap.add_argument("--headline", required=True)
    ap.add_argument("--detail", default=None)
    ap.add_argument("--source-url", default=None, dest="source_url")
    args = ap.parse_args()

    await Neo4jClient.connect()
    try:
        result = await SignalWatchService.record_event(
            args.ticker,
            args.signal_date,
            {
                "event_date": args.event_date,
                "event_type": args.event_type,
                "direction": args.direction,
                "headline": args.headline,
                "detail": args.detail,
                "source_url": args.source_url,
            },
        )
        if not result["stored"]:
            print(f"WARNING: no SignalPerformance matched {args.ticker} {args.signal_date}")
            sys.exit(1)
        print(
            f"Recorded: {args.ticker} day {result['day_index']} "
            f"[{result['event_type']}/{result['direction']}] {result['headline']}"
        )
    finally:
        await Neo4jClient.disconnect()


if __name__ == "__main__":
    asyncio.run(main())
