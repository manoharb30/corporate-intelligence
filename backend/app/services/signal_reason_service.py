"""Service for generating and storing one-line signal explanations.

For qualifying signals (strong_buy + $100K, high_sell + $500K), calls
Claude Haiku to generate a one-sentence reason. For others, uses a
template. Stores reasons in Neo4j SignalReason nodes — write once, read forever.
"""

import logging
import os
from datetime import datetime, timedelta
from typing import Optional

import anthropic
import yfinance as yf

from app.db.neo4j_client import Neo4jClient

logger = logging.getLogger(__name__)

ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")


def _format_volume(v: float) -> str:
    if v >= 1_000_000_000:
        return f"${v / 1_000_000_000:.1f}B"
    if v >= 1_000_000:
        return f"${v / 1_000_000:.1f}M"
    if v >= 1_000:
        return f"${v / 1_000:.0f}K"
    return f"${v:.0f}"


class SignalReasonService:
    """Generates and caches one-line signal explanations."""

    @staticmethod
    async def get_reason(signal_id: str) -> Optional[str]:
        """Read a cached reason from Neo4j."""
        results = await Neo4jClient.execute_query(
            "MATCH (r:SignalReason {signal_id: $id}) RETURN r.reason as reason",
            {"id": signal_id},
        )
        if results and results[0].get("reason"):
            return results[0]["reason"]
        return None

    @staticmethod
    async def get_reasons_batch(signal_ids: list[str]) -> dict[str, str]:
        """Batch read reasons for multiple signals."""
        if not signal_ids:
            return {}
        results = await Neo4jClient.execute_query(
            "UNWIND $ids as id "
            "MATCH (r:SignalReason {signal_id: id}) "
            "RETURN r.signal_id as id, r.reason as reason",
            {"ids": signal_ids},
        )
        return {r["id"]: r["reason"] for r in results if r.get("reason")}

    @staticmethod
    async def store_reason(signal_id: str, reason: str) -> None:
        """Store a reason in Neo4j. Idempotent — overwrites if exists."""
        await Neo4jClient.execute_write(
            "MERGE (r:SignalReason {signal_id: $id}) "
            "SET r.reason = $reason, r.created_at = $now",
            {"id": signal_id, "reason": reason, "now": datetime.now().isoformat()},
        )

    @staticmethod
    async def generate_and_store(
        signal_id: str,
        ticker: str,
        company_name: str,
        direction: str,
        cik: str,
        window_start: str,
        window_end: str,
    ) -> str:
        """Generate a one-line reason via LLM and store it.

        Returns the reason string.
        """
        # Check if already exists
        existing = await SignalReasonService.get_reason(signal_id)
        if existing:
            return existing

        # Gather context from our DB
        code = "S" if direction == "sell" else "P"
        counter_code = "P" if direction == "sell" else "S"

        # Insider details
        insiders = await Neo4jClient.execute_query(
            "MATCH (c:Company {cik: $cik})-[:INSIDER_TRADE_OF]->(t:InsiderTransaction) "
            "WHERE t.transaction_code = $code "
            "AND t.transaction_date >= $start AND t.transaction_date <= $end "
            "AND t.ownership_type = 'D' "
            "RETURN t.insider_name as name, t.insider_title as title, "
            "t.total_value as val, t.pct_of_position_traded as pct "
            "ORDER BY t.total_value DESC LIMIT 6",
            {"cik": cik, "code": code, "start": window_start, "end": window_end},
        )

        # Counter-activity (buying if sell signal, selling if buy signal)
        counter = await Neo4jClient.execute_query(
            "MATCH (c:Company {cik: $cik})-[:INSIDER_TRADE_OF]->(t:InsiderTransaction) "
            "WHERE t.transaction_code = $code "
            "AND t.transaction_date >= $since "
            "RETURN count(*) as cnt",
            {
                "cik": cik,
                "code": counter_code,
                "since": (datetime.strptime(window_end[:10], "%Y-%m-%d") - timedelta(days=90)).strftime("%Y-%m-%d"),
            },
        )
        counter_count = counter[0]["cnt"] if counter else 0

        # Recent 8-K events
        events = await Neo4jClient.execute_query(
            "MATCH (c:Company {cik: $cik})-[:FILED_EVENT]->(e:Event) "
            "WHERE e.filing_date >= $since AND e.filing_date <= $until "
            "RETURN e.filing_date as date, e.item_number as item, e.signal_summary as summary "
            "ORDER BY e.filing_date DESC LIMIT 3",
            {
                "cik": cik,
                "since": (datetime.strptime(window_end[:10], "%Y-%m-%d") - timedelta(days=90)).strftime("%Y-%m-%d"),
                "until": window_end,
            },
        )

        # News from yfinance
        news_text = "No recent news"
        try:
            tk = yf.Ticker(ticker)
            news = tk.news[:5] if hasattr(tk, "news") and tk.news else []
            if news:
                lines = []
                for n in news:
                    title = n.get("title", n.get("content", {}).get("title", ""))
                    if title:
                        lines.append(f"- {title}")
                news_text = "\n".join(lines) if lines else "No recent news"
        except Exception:
            pass

        # Build insider summary
        insider_lines = []
        for ins in insiders:
            pct = f", {ins['pct']:.1f}% of position" if ins.get("pct") else ""
            title = ins.get("title") or "Director/Owner"
            insider_lines.append(
                f"- {ins['name']}, {title}: {_format_volume(ins.get('val') or 0)}{pct}"
            )
        insider_text = "\n".join(insider_lines) if insider_lines else "No details"

        event_text = "\n".join(
            [f"- {e['date']}: {e['item']}" for e in events]
        ) if events else "None"

        action = "sold" if direction == "sell" else "bought"
        counter_action = "buying" if direction == "sell" else "selling"
        counter_text = (
            f"{counter_count} insider {counter_action} transactions in prior 90 days"
            if counter_count
            else f"Zero insider {counter_action} in prior 90 days"
        )

        prompt = (
            f"Multiple insiders at {company_name} ({ticker}) {action} open-market shares "
            f"in a coordinated cluster. Based only on the data below, explain in one sentence "
            f"why they are likely {action.rstrip('d')}ing. Do not judge whether this is bullish "
            f"or bearish. Do not rate risk. Just state the most probable reason.\n\n"
            f"INSIDER {action.upper()}:\n{insider_text}\n\n"
            f"CONTEXT:\n"
            f"- 8-K filings: {event_text}\n"
            f"- Counter-activity: {counter_text}\n"
            f"- News: {news_text}\n\n"
            f"Respond with one sentence only. No preamble."
        )

        # Call LLM
        reason = ""
        try:
            client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
            response = client.messages.create(
                model="claude-haiku-4-5-20251001",
                max_tokens=100,
                messages=[{"role": "user", "content": prompt}],
            )
            reason = response.content[0].text.strip()
        except Exception as e:
            logger.warning(f"LLM reason generation failed for {signal_id}: {e}")
            reason = ""

        if not reason:
            # Fallback to template
            reason = SignalReasonService.generate_template(
                direction, insiders, counter_count
            )

        # Store
        await SignalReasonService.store_reason(signal_id, reason)
        return reason

    @staticmethod
    def generate_template(
        direction: str,
        insiders: list[dict],
        counter_count: int,
    ) -> str:
        """Generate a template-based reason when LLM is unavailable."""
        if not insiders:
            action = "selling" if direction == "sell" else "buying"
            return f"Multiple insiders {action} in a coordinated cluster."

        top = insiders[0]
        name = top.get("name", "An insider")
        title = top.get("title") or "an executive"
        pct = top.get("pct")
        val = top.get("val") or 0
        action = "sold" if direction == "sell" else "bought"
        counter_action = "buying" if direction == "sell" else "selling"

        parts = [f"{name} ({title}) {action} {_format_volume(val)}"]
        if pct and pct >= 20:
            parts.append(f"{pct:.0f}% of their holdings")
        if counter_count == 0:
            parts.append(f"with zero insider {counter_action} in 90 days")

        return ". ".join(parts) + "."

    @staticmethod
    def generate_headline(
        direction: str,
        num_insiders: int,
        total_value: float,
        top_insider_title: str = "",
    ) -> str:
        """Generate a plain-English headline for a signal card."""
        action = "sold" if direction == "sell" else "bought"
        vol = _format_volume(total_value)

        if top_insider_title and any(
            kw in top_insider_title.upper()
            for kw in ["CEO", "CFO", "COO", "PRESIDENT", "CHAIRMAN"]
        ):
            return f"{num_insiders} executives including {top_insider_title.split(',')[0]} {action} {vol} in shares"

        return f"{num_insiders} insiders {action} {vol} in shares"
