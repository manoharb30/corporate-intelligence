"""Operator CLI: record Promise nodes for an open signal from a JSON file.

Usage:
    python record_promises.py TICKER SIGNAL_DATE promises.json
    python record_promises.py TICKER SIGNAL_DATE promises.json --score METRIC VERDICT ACTUAL

promises.json = list of objects:
    [{"metric": "...", "target": "...", "quote": "...",
      "source_call_date": "YYYY-MM-DD", "break_condition": "..." | null}, ...]

Idempotent: re-running MERGEs on metric, existing verdicts untouched.
"""
import argparse
import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from app.db.neo4j_client import Neo4jClient
from app.services.signal_watch_service import SignalWatchService


async def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("ticker")
    ap.add_argument("signal_date")
    ap.add_argument("promises_file", nargs="?", default=None)
    ap.add_argument("--score", nargs=3, metavar=("METRIC", "VERDICT", "ACTUAL"), default=None)
    args = ap.parse_args()

    await Neo4jClient.connect()
    try:
        if args.promises_file:
            promises = json.loads(Path(args.promises_file).read_text())
            n = await SignalWatchService.record_promises(args.ticker, args.signal_date, promises)
            print(f"Recorded {n} promises for {args.ticker} {args.signal_date}")
        if args.score:
            metric, verdict, actual = args.score
            ok = await SignalWatchService.score_promise(
                args.ticker, args.signal_date, metric, verdict, actual
            )
            print(f"Scored '{metric}' = {verdict} ({actual})" if ok
                  else f"WARNING: no promise '{metric}' found")
            if not ok:
                sys.exit(1)
    finally:
        await Neo4jClient.disconnect()


if __name__ == "__main__":
    asyncio.run(main())
