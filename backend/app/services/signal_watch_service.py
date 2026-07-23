"""Signal Watch — promise-vs-delivery monitoring for open signals.

Records, per SignalPerformance row:
- (:SignalPerformance)-[:HAS_PROMISE]->(:Promise)      management commitments
  extracted from the last call before the insider cluster
- (:SignalPerformance)-[:HAS_EVENT]->(:SignalEvent)    material events during
  the 90-day window (day-indexed), including the print that scores delivery

Additive only: never mutates SignalPerformance properties. Frozen mature
rows are out of scope — the trail is forward-only from open signals.
"""

import logging
from datetime import datetime

from app.db.neo4j_client import Neo4jClient

logger = logging.getLogger(__name__)

EVENT_TYPES = {
    "earnings_call",
    "guidance",
    "capital_action",
    "regulatory",
    "insider_followon",
    "ma",
    "analyst",
    "index",
}

DIRECTIONS = {"confirming", "breaking", "neutral"}

VERDICTS = {"pass", "fail", "pending"}


def _date(d: str) -> datetime:
    return datetime.strptime(d[:10], "%Y-%m-%d")


def day_index(signal_date: str, event_date: str) -> int:
    """Day of the 90-day window an event lands on (day 0 = signal date).

    Negative for pre-window dates. Tolerates TZ suffixes on either date.
    """
    return (_date(event_date) - _date(signal_date)).days


def watch_summary(promises: list[dict]) -> dict:
    """Rollup of promise verdicts for display: on_track = zero fails."""
    passed = sum(1 for p in promises if p.get("verdict") == "pass")
    failed = sum(1 for p in promises if p.get("verdict") == "fail")
    pending = sum(1 for p in promises if p.get("verdict") == "pending")
    return {
        "total": len(promises),
        "passed": passed,
        "failed": failed,
        "pending": pending,
        "on_track": failed == 0,
    }


def validate_event(event: dict) -> None:
    """Raise ValueError on any field outside the closed vocabularies."""
    if not event.get("event_date"):
        raise ValueError("event_date is required")
    if event.get("event_type") not in EVENT_TYPES:
        raise ValueError(f"event_type must be one of {sorted(EVENT_TYPES)}")
    if event.get("direction") not in DIRECTIONS:
        raise ValueError(f"direction must be one of {sorted(DIRECTIONS)}")
    if not event.get("headline"):
        raise ValueError("headline is required")


class SignalWatchService:
    @staticmethod
    async def record_promises(ticker: str, signal_date: str, promises: list[dict]) -> int:
        """MERGE Promise nodes onto a signal, keyed on metric (idempotent).

        Each promise: {metric, target, quote, source_call_date, break_condition}.
        Verdict starts 'pending'; score_promise() resolves it on print day.
        """
        for p in promises:
            if not p.get("metric"):
                raise ValueError("every promise requires a metric")
        if not promises:
            return 0

        rows = [
            {
                "metric": p["metric"],
                "target": p.get("target"),
                "quote": p.get("quote"),
                "source_call_date": p.get("source_call_date"),
                "source_url": p.get("source_url"),
                "break_condition": p.get("break_condition"),
            }
            for p in promises
        ]
        # Evidence fields (quote, source_call_date, source_url) refresh on
        # re-run so provenance can be added later; verdict/actual are only
        # ever touched by score_promise.
        results = await Neo4jClient.execute_query(
            """
            MATCH (sp:SignalPerformance)
            WHERE sp.ticker = $ticker AND substring(sp.signal_date, 0, 10) = $signal_date
            UNWIND $promises AS row
            MERGE (sp)-[:HAS_PROMISE]->(pr:Promise {metric: row.metric})
            ON CREATE SET
                pr.target = row.target,
                pr.quote = row.quote,
                pr.source_call_date = row.source_call_date,
                pr.source_url = row.source_url,
                pr.break_condition = row.break_condition,
                pr.verdict = 'pending',
                pr.recorded_at = datetime()
            ON MATCH SET
                pr.target = row.target,
                pr.quote = row.quote,
                pr.source_call_date = row.source_call_date,
                pr.source_url = row.source_url,
                pr.break_condition = row.break_condition
            RETURN count(pr) AS n
            """,
            {"ticker": ticker, "signal_date": signal_date[:10], "promises": rows},
        )
        n = results[0]["n"] if results else 0
        logger.info(f"record_promises {ticker} {signal_date[:10]}: {n} merged")
        return n

    @staticmethod
    async def record_event(ticker: str, signal_date: str, event: dict) -> dict:
        """MERGE one SignalEvent onto a signal (keyed on date+type+headline).

        Event: {event_date, event_type, direction, headline, detail?, source_url?}.
        day_index is computed here — day 0 = signal date, negative = pre-window.
        """
        validate_event(event)
        row = {
            "event_date": event["event_date"][:10],
            "day_index": day_index(signal_date, event["event_date"]),
            "event_type": event["event_type"],
            "direction": event["direction"],
            "headline": event["headline"],
            "detail": event.get("detail"),
            "source_url": event.get("source_url"),
        }
        results = await Neo4jClient.execute_query(
            """
            MATCH (sp:SignalPerformance)
            WHERE sp.ticker = $ticker AND substring(sp.signal_date, 0, 10) = $signal_date
            MERGE (sp)-[:HAS_EVENT]->(ev:SignalEvent {
                event_date: $event.event_date,
                event_type: $event.event_type,
                headline: $event.headline
            })
            ON CREATE SET
                ev.day_index = $event.day_index,
                ev.direction = $event.direction,
                ev.detail = $event.detail,
                ev.source_url = $event.source_url,
                ev.recorded_at = datetime()
            ON MATCH SET
                ev.direction = $event.direction,
                ev.detail = $event.detail,
                ev.source_url = $event.source_url
            RETURN count(ev) AS created
            """,
            {"ticker": ticker, "signal_date": signal_date[:10], "event": row},
        )
        logger.info(
            f"record_event {ticker} day {row['day_index']}: "
            f"{row['event_type']}/{row['direction']} — {row['headline']}"
        )
        return {**row, "stored": bool(results and results[0]["created"])}

    @staticmethod
    async def score_promise(
        ticker: str, signal_date: str, metric: str, verdict: str, actual: str | None
    ) -> bool:
        """Resolve one promise's verdict on print day. Returns False if no match."""
        if verdict not in VERDICTS:
            raise ValueError(f"verdict must be one of {sorted(VERDICTS)}")
        results = await Neo4jClient.execute_query(
            """
            MATCH (sp:SignalPerformance)-[:HAS_PROMISE]->(pr:Promise {metric: $metric})
            WHERE sp.ticker = $ticker AND substring(sp.signal_date, 0, 10) = $signal_date
            SET pr.verdict = $verdict, pr.actual = $actual, pr.scored_at = datetime()
            RETURN count(pr) AS updated
            """,
            {
                "ticker": ticker,
                "signal_date": signal_date[:10],
                "metric": metric,
                "verdict": verdict,
                "actual": actual,
            },
        )
        updated = bool(results and results[0]["updated"])
        if not updated:
            logger.warning(f"score_promise: no Promise '{metric}' on {ticker} {signal_date[:10]}")
        return updated

    @staticmethod
    async def get_watch(ticker: str, signal_date: str) -> dict:
        """Full watch record for one signal: promises + events, chronological."""
        promises = await Neo4jClient.execute_query(
            """
            MATCH (sp:SignalPerformance)-[:HAS_PROMISE]->(pr:Promise)
            WHERE sp.ticker = $ticker AND substring(sp.signal_date, 0, 10) = $signal_date
            RETURN pr.metric AS metric, pr.target AS target, pr.quote AS quote,
                   pr.source_call_date AS source_call_date,
                   pr.source_url AS source_url,
                   pr.break_condition AS break_condition,
                   pr.verdict AS verdict, pr.actual AS actual
            ORDER BY pr.metric
            """,
            {"ticker": ticker, "signal_date": signal_date[:10]},
        )
        events = await Neo4jClient.execute_query(
            """
            MATCH (sp:SignalPerformance)-[:HAS_EVENT]->(ev:SignalEvent)
            WHERE sp.ticker = $ticker AND substring(sp.signal_date, 0, 10) = $signal_date
            RETURN ev.event_date AS event_date, ev.day_index AS day_index,
                   ev.event_type AS event_type, ev.direction AS direction,
                   ev.headline AS headline, ev.detail AS detail,
                   ev.source_url AS source_url
            ORDER BY ev.event_date
            """,
            {"ticker": ticker, "signal_date": signal_date[:10]},
        )
        return {"ticker": ticker, "signal_date": signal_date[:10],
                "promises": promises, "events": events}
