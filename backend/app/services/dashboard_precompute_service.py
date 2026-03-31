"""Service for pre-computing and storing the dashboard data in Neo4j.

Instead of computing feed, pulse, accuracy, anomalies on every dashboard visit,
this service runs once after each scanner run and stores the results as a
DashboardSnapshot node in Neo4j. The dashboard endpoint then reads this node
instantly — no computation, no yfinance calls, survives restarts.
"""

import asyncio
import json
import logging
import time
from datetime import datetime

from app.db.neo4j_client import Neo4jClient
from app.services.feed_service import FeedService
from app.services.dashboard_service import DashboardService
from app.services.accuracy_service import AccuracyService
from app.services.snapshot_service import SnapshotService
from app.services.signal_reason_service import SignalReasonService

logger = logging.getLogger(__name__)


class DashboardPrecomputeService:
    """Pre-computes dashboard data and stores in Neo4j."""

    @staticmethod
    async def compute_and_store() -> dict:
        """Run all dashboard computations and store as DashboardSnapshot in Neo4j.

        Returns summary of what was computed.
        """
        start = time.time()
        snapshot = {}

        # 1. Stats (node counts)
        try:
            stats_query = """
                CALL {
                    MATCH (c:Company) WHERE c.cik IS NOT NULL RETURN 'companies' as label, count(c) as cnt
                    UNION ALL
                    MATCH (e:Event) RETURN 'events' as label, count(e) as cnt
                    UNION ALL
                    MATCH (p:Person) RETURN 'persons' as label, count(p) as cnt
                    UNION ALL
                    MATCH (t:InsiderTransaction) RETURN 'insider_transactions' as label, count(t) as cnt
                    UNION ALL
                    MATCH (j:Jurisdiction) RETURN 'jurisdictions' as label, count(j) as cnt
                }
                RETURN label, cnt
            """
            stats_results = await Neo4jClient.execute_query(stats_query, {})
            stats = {r["label"]: r["cnt"] for r in stats_results}
            stats["total_nodes"] = sum(stats.values())
            snapshot["stats"] = stats
            logger.info(f"Dashboard precompute: stats done")
        except Exception as e:
            logger.error(f"Dashboard precompute: stats failed: {e}")
            snapshot["stats"] = None

        # 2. Feed (top signals with insider context, clusters, compounds)
        try:
            signals, _ = await FeedService.get_feed(days=30, min_level="medium")
            signals_list = []
            for s in signals[:10]:
                signals_list.append(s.to_dict())
            snapshot["signals"] = signals_list
            snapshot["signal_count"] = len(signals)

            # Full feed for signals page (stored separately, not in dashboard response)
            feed_full = []
            for s in signals[:50]:
                feed_full.append(s.to_dict())
            snapshot["feed_full"] = feed_full

            # By level counts
            by_level = {"high": 0, "medium": 0, "low": 0}
            by_combined = {}
            for s in signals:
                by_level[s.signal_level] = by_level.get(s.signal_level, 0) + 1
                cl = s.combined_signal_level or s.signal_level
                by_combined[cl] = by_combined.get(cl, 0) + 1
            snapshot["by_level"] = by_level
            snapshot["by_combined"] = by_combined
            logger.info(f"Dashboard precompute: feed done ({len(signals)} signals)")
        except Exception as e:
            logger.error(f"Dashboard precompute: feed failed: {e}")
            snapshot["signals"] = []
            snapshot["signal_count"] = 0
            snapshot["by_level"] = {}
            snapshot["by_combined"] = {}

        # 3. Accuracy summary
        try:
            accuracy = await AccuracyService.get_accuracy_summary(
                lookback_days=365, min_signal_age_days=30, min_level="medium"
            )
            snapshot["accuracy"] = accuracy
            logger.info(f"Dashboard precompute: accuracy done")
        except Exception as e:
            logger.error(f"Dashboard precompute: accuracy failed: {e}")
            snapshot["accuracy"] = None

        # 4. Pulse (last signal, mood, movers, scorecard)
        try:
            pulse = await DashboardService.get_pulse()
            snapshot["pulse"] = pulse
            logger.info(f"Dashboard precompute: pulse done")
        except Exception as e:
            logger.error(f"Dashboard precompute: pulse failed: {e}")
            snapshot["pulse"] = None

        # 5. Anomalies (pre-event insider selling)
        try:
            anomaly_query = """
                MATCH (c:Company)-[:FILED_EVENT]->(e:Event)
                WHERE e.is_ma_signal = true AND e.filing_date IS NOT NULL
                MATCH (c)-[:INSIDER_TRADE_OF]->(t:InsiderTransaction)
                WHERE t.transaction_code = 'S'
                  AND t.total_value > 0
                  AND t.transaction_date IS NOT NULL
                  AND t.transaction_date < e.filing_date
                  AND t.transaction_date >= toString(date(substring(e.filing_date, 0, 10)) - duration('P90D'))
                  AND toLower(t.insider_name) <> toLower(c.name)
                WITH c, e,
                     count(DISTINCT t.insider_name) as seller_count,
                     sum(t.total_value) as pre_sell_value,
                     collect(DISTINCT t.insider_name) as sellers,
                     avg(duration.between(date(substring(t.transaction_date, 0, 10)), date(substring(e.filing_date, 0, 10))).days) as avg_days_before
                WHERE seller_count >= 2 AND pre_sell_value > 10000
                WITH c, e, seller_count, pre_sell_value, sellers, avg_days_before,
                     pre_sell_value / CASE WHEN seller_count > 0 THEN seller_count ELSE 1 END as value_per_seller
                ORDER BY pre_sell_value DESC
                LIMIT 15
                RETURN c.cik as cik, c.name as company_name, c.tickers as tickers,
                       e.item_number as event_type, e.filing_date as event_date,
                       e.accession_number as accession_number,
                       seller_count as num_insiders, pre_sell_value,
                       sellers as insider_list, avg_days_before as avg_days_before_event
            """
            anomaly_results = await Neo4jClient.execute_query(anomaly_query, {})
            anomalies = []
            for r in anomaly_results:
                tickers = r.get("tickers") or []
                ticker = tickers[0] if tickers else None
                if ticker == "MDLN":
                    continue
                anomalies.append({
                    "cik": r["cik"],
                    "company_name": r["company_name"],
                    "ticker": ticker,
                    "event_type": r["event_type"],
                    "event_date": r["event_date"],
                    "accession_number": r["accession_number"],
                    "num_insiders": r["num_insiders"],
                    "pre_event_sell_value": r["pre_sell_value"],
                    "insider_list": r["insider_list"][:5] if r["insider_list"] else [],
                    "avg_days_before_event": round(r["avg_days_before_event"]) if r["avg_days_before_event"] else None,
                })
            snapshot["anomalies"] = anomalies
            logger.info(f"Dashboard precompute: anomalies done ({len(anomalies)})")
        except Exception as e:
            logger.error(f"Dashboard precompute: anomalies failed: {e}")
            snapshot["anomalies"] = []

        # 6. Proof wall (top hits) — used on pricing page
        try:
            top_hits = await AccuracyService.get_top_hits(limit=10)
            snapshot["top_hits"] = top_hits
            logger.info(f"Dashboard precompute: top hits done ({len(top_hits)})")
        except Exception as e:
            logger.error(f"Dashboard precompute: top hits failed: {e}")
            snapshot["top_hits"] = []

        # 7. Scorecard (live signal performance — buy + sell stats with prices)
        try:
            scorecard = await SnapshotService.get_weekly_snapshot(days=30)
            snapshot["scorecard"] = scorecard
            logger.info(f"Dashboard precompute: scorecard done ({scorecard.get('total_signals', 0)} buy, {scorecard.get('sell_stats', {}).get('total', 0)} sell)")
        except Exception as e:
            logger.error(f"Dashboard precompute: scorecard failed: {e}")
            snapshot["scorecard"] = None

        # 8. LLM reason lines for qualifying signals in the scorecard
        try:
            scorecard_data = snapshot.get("scorecard") or {}
            signals = scorecard_data.get("signals") or []
            generated = 0
            for sig in signals:
                sig_id = sig.get("accession_number", "")
                if not sig_id or not sig.get("ticker"):
                    continue
                # Qualify: strong_buy buys >= $100K or high sells >= $500K
                is_buy = sig.get("signal_action") != "PASS"
                value = sig.get("total_value") or 0
                if is_buy and value < 100_000:
                    continue
                if not is_buy and value < 500_000:
                    continue

                direction = "buy" if is_buy else "sell"
                # Extract CIK and window from signal_id
                cik = sig.get("cik", "")
                signal_date = sig.get("signal_date", "")
                if not cik or not signal_date:
                    continue

                # Window: signal_date - 14 days
                from datetime import timedelta
                try:
                    end_dt = datetime.strptime(signal_date[:10], "%Y-%m-%d")
                    start_dt = end_dt - timedelta(days=14)
                    window_start = start_dt.strftime("%Y-%m-%d")
                    window_end = signal_date[:10]
                except (ValueError, TypeError):
                    continue

                reason = await SignalReasonService.generate_and_store(
                    signal_id=sig_id,
                    ticker=sig["ticker"],
                    company_name=sig.get("company_name", ""),
                    direction=direction,
                    cik=cik,
                    window_start=window_start,
                    window_end=window_end,
                )
                if reason:
                    sig["reason"] = reason
                    generated += 1

            # Also add template reasons for non-qualifying signals
            for sig in signals:
                if sig.get("reason"):
                    continue
                is_buy = sig.get("signal_action") != "PASS"
                direction = "sell" if not is_buy else "buy"
                num = sig.get("num_insiders") or 0
                val = sig.get("total_value") or 0
                title = ""
                headline = SignalReasonService.generate_headline(
                    direction, num, val, title
                )
                sig["reason"] = headline

            snapshot["scorecard"] = scorecard_data
            logger.info(f"Dashboard precompute: signal reasons done ({generated} LLM, {len(signals) - generated} template)")
        except Exception as e:
            logger.error(f"Dashboard precompute: signal reasons failed: {e}")

        snapshot["computed_at"] = datetime.now().isoformat()
        elapsed = round(time.time() - start, 1)
        snapshot["compute_seconds"] = elapsed

        # Store in Neo4j — delete old snapshot first so no stale properties linger
        try:
            await Neo4jClient.execute_write(
                "MATCH (d:DashboardSnapshot {snapshot_key: 'latest'}) DELETE d", {}
            )
            store_query = """
                CREATE (d:DashboardSnapshot {
                    snapshot_key: 'latest',
                    stats_json: $stats_json,
                    signals_json: $signals_json,
                    signal_count: $signal_count,
                    by_level_json: $by_level_json,
                    by_combined_json: $by_combined_json,
                    accuracy_json: $accuracy_json,
                    pulse_json: $pulse_json,
                    anomalies_json: $anomalies_json,
                    top_hits_json: $top_hits_json,
                    scorecard_json: $scorecard_json,
                    feed_full_json: $feed_full_json,
                    computed_at: $computed_at,
                    compute_seconds: $compute_seconds
                })
            """
            await Neo4jClient.execute_write(store_query, {
                "stats_json": json.dumps(snapshot.get("stats")),
                "signals_json": json.dumps(snapshot.get("signals", [])[:10]),
                "signal_count": snapshot.get("signal_count", 0),
                "by_level_json": json.dumps(snapshot.get("by_level", {})),
                "by_combined_json": json.dumps(snapshot.get("by_combined", {})),
                "accuracy_json": json.dumps(snapshot.get("accuracy")),
                "pulse_json": json.dumps(snapshot.get("pulse")),
                "anomalies_json": json.dumps(snapshot.get("anomalies", [])),
                "top_hits_json": json.dumps(snapshot.get("top_hits", [])),
                "scorecard_json": json.dumps(DashboardPrecomputeService._trim_scorecard(snapshot.get("scorecard"))),
                "feed_full_json": json.dumps(snapshot.get("feed_full", [])),
                "computed_at": snapshot["computed_at"],
                "compute_seconds": elapsed,
            })
            logger.info(f"Dashboard precompute: stored in Neo4j ({elapsed}s)")
        except Exception as e:
            logger.error(f"Dashboard precompute: failed to store in Neo4j: {e}")

        return {
            "status": "completed",
            "computed_at": snapshot["computed_at"],
            "elapsed_seconds": elapsed,
            "signal_count": snapshot.get("signal_count", 0),
            "anomaly_count": len(snapshot.get("anomalies", [])),
        }

    @staticmethod
    def _trim_scorecard(scorecard: dict | None) -> dict | None:
        """Trim scorecard signals to top 20 sell + top 20 buy for storage.

        Keeps aggregate stats intact, just reduces the signals list.
        """
        if not scorecard:
            return scorecard
        signals = scorecard.get("signals") or []
        sells = [s for s in signals if s.get("signal_action") == "PASS"]
        buys = [s for s in signals if s.get("signal_action") != "PASS"]
        # Sort by value descending, take top 20 each
        sells.sort(key=lambda s: abs(s.get("total_value") or 0), reverse=True)
        buys.sort(key=lambda s: abs(s.get("total_value") or 0), reverse=True)
        scorecard["signals"] = sells[:20] + buys[:20]
        return scorecard

    @staticmethod
    async def get_cached() -> dict | None:
        """Read the pre-computed dashboard snapshot from Neo4j.

        Returns the full dashboard data or None if not yet computed.
        """
        query = """
            MATCH (d:DashboardSnapshot {snapshot_key: 'latest'})
            RETURN d.stats_json as stats,
                   d.signals_json as signals,
                   d.signal_count as signal_count,
                   d.by_level_json as by_level,
                   d.by_combined_json as by_combined,
                   d.accuracy_json as accuracy,
                   d.pulse_json as pulse,
                   d.anomalies_json as anomalies,
                   d.top_hits_json as top_hits,
                   d.scorecard_json as scorecard,
                   d.computed_at as computed_at,
                   d.compute_seconds as compute_seconds
        """
        results = await Neo4jClient.execute_query(query, {})
        if not results:
            return None

        r = results[0]
        return {
            "stats": json.loads(r["stats"]) if r["stats"] else None,
            "signals": json.loads(r["signals"]) if r["signals"] else [],
            "signal_count": r["signal_count"],
            "by_level": json.loads(r["by_level"]) if r["by_level"] else {},
            "by_combined": json.loads(r["by_combined"]) if r["by_combined"] else {},
            "accuracy": json.loads(r["accuracy"]) if r["accuracy"] else None,
            "pulse": json.loads(r["pulse"]) if r["pulse"] else None,
            "anomalies": json.loads(r["anomalies"]) if r["anomalies"] else [],
            "top_hits": json.loads(r["top_hits"]) if r["top_hits"] else [],
            "scorecard": json.loads(r["scorecard"]) if r.get("scorecard") else None,
            "computed_at": r["computed_at"],
            "compute_seconds": r["compute_seconds"],
        }

    @staticmethod
    async def get_cached_feed() -> dict | None:
        """Read just the pre-computed feed signals from Neo4j.

        Separate from get_cached() to avoid loading the full dashboard blob
        when only the signals page needs feed data.
        """
        query = """
            MATCH (d:DashboardSnapshot {snapshot_key: 'latest'})
            RETURN d.feed_full_json as feed_full,
                   d.signal_count as signal_count,
                   d.by_level_json as by_level,
                   d.by_combined_json as by_combined,
                   d.computed_at as computed_at
        """
        results = await Neo4jClient.execute_query(query, {})
        if not results:
            return None

        r = results[0]
        feed = r.get("feed_full")
        if not feed:
            return None

        return {
            "signals": json.loads(feed),
            "total_count": r.get("signal_count") or 0,
            "by_level": json.loads(r["by_level"]) if r.get("by_level") else {},
            "by_combined": json.loads(r["by_combined"]) if r.get("by_combined") else {},
            "computed_at": r.get("computed_at"),
        }
