"""Service for detecting compound signals by cross-referencing multiple data sources.

Compound signals fire when independent signal sources converge on the same company
within a time window — e.g., insider buying cluster + activist 13D filing + 8-K event.
These are the highest-conviction signals in the system.
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Optional

from app.db.neo4j_client import Neo4jClient
from app.services.feed_service import pick_ticker

logger = logging.getLogger(__name__)


@dataclass
class CompoundSignal:
    """A compound signal combining multiple independent data sources."""

    cik: str
    company_name: str
    ticker: Optional[str]
    compound_type: str  # insider_activist, activist_8k, triple_convergence, insider_activist_sell
    score: int  # 0-100
    signal_date: str  # Date of most recent component signal
    components: list[dict] = field(default_factory=list)  # [{source, signal_level, date, summary}]
    activist_filing: Optional[dict] = None  # 13D details
    insider_context: Optional[dict] = None  # Cluster info
    event_context: Optional[dict] = None  # 8-K info
    decision: str = "WATCH"  # BUY, WATCH, PASS
    one_liner: str = ""

    @property
    def accession_number(self) -> str:
        return f"COMPOUND-{self.cik}-{self.signal_date}"

    def to_dict(self) -> dict:
        return {
            "cik": self.cik,
            "company_name": self.company_name,
            "ticker": self.ticker,
            "compound_type": self.compound_type,
            "score": self.score,
            "signal_date": self.signal_date,
            "components": self.components,
            "activist_filing": self.activist_filing,
            "insider_context": self.insider_context,
            "event_context": self.event_context,
            "decision": self.decision,
            "one_liner": self.one_liner,
            "accession_number": self.accession_number,
        }


def score_compound(
    activist_pct: float,
    insider_value: float,
    insider_count: int,
    has_8k: bool,
    timing_gap_days: int,
    source_count: int,
) -> int:
    """Score a compound signal from 0-100.

    Args:
        activist_pct: Activist ownership percentage
        insider_value: Total insider buy/sell value in dollars
        insider_count: Number of distinct insiders
        has_8k: Whether an 8-K event overlaps
        timing_gap_days: Days between closest pair of component signals
        source_count: Number of independent sources (2 or 3)
    """
    # Base score from source count
    if source_count >= 3:
        score = 85
    else:
        score = 60

    # Activist percentage bonus
    if activist_pct > 10:
        score += 10
    elif activist_pct >= 7:
        score += 5

    # Insider value bonus
    if insider_value > 500_000:
        score += 10
    elif insider_value > 100_000:
        score += 5

    # Timing proximity bonus (closer = better)
    if timing_gap_days <= 7:
        score += 10
    elif timing_gap_days <= 14:
        score += 5

    # 8-K material agreement bonus
    if has_8k:
        score += 5

    return min(score, 100)


def decide_action(compound_type: str, score: int) -> str:
    """Determine BUY/WATCH/PASS from compound type and score.

    Compounds with insider cluster component (insider_activist,
    triple_convergence) can be BUY — the cluster is a leading indicator.
    Compounds without cluster (activist_8k) max out at WATCH — these
    are lagging indicators.
    """
    if compound_type == "insider_activist_sell":
        return "PASS"

    has_cluster = compound_type in ("insider_activist", "triple_convergence")

    if has_cluster:
        if score >= 70:
            return "BUY"
        if score >= 50:
            return "WATCH"
        return "PASS"
    else:
        # activist_8k: no cluster = lagging indicator, max WATCH
        if score >= 50:
            return "WATCH"
        return "PASS"


class CompoundSignalService:
    """Detect compound signals by cross-referencing Neo4j data across sources."""

    @staticmethod
    async def detect_compound_signals(days: int = 90) -> list[CompoundSignal]:
        """Detect all compound signals from the last N days.

        Checks for:
        1. insider_activist: Insider cluster buy + 13D filing (±30d)
        2. activist_8k: 13D filing + 8-K material agreement (±90d)
        3. triple_convergence: All three sources overlap (±90d)
        4. insider_activist_sell: Insider sell cluster + 13D filing (±30d)
        """
        signals: list[CompoundSignal] = []
        seen_ciks: dict[str, CompoundSignal] = {}  # Dedupe: one compound per company

        # --- Query 1: insider_activist (buy clusters near 13D filings) ---
        try:
            buy_results = await CompoundSignalService._find_insider_activist(days)
            for r in buy_results:
                cik = r["cik"]
                sig = CompoundSignalService._build_insider_activist(r, direction="buy")
                if sig and (cik not in seen_ciks or sig.score > seen_ciks[cik].score):
                    seen_ciks[cik] = sig
        except Exception as e:
            logger.warning(f"Failed to detect insider_activist compounds: {e}")

        # --- Query 2: activist_8k (13D + 8-K overlap) ---
        try:
            eight_k_results = await CompoundSignalService._find_activist_8k(days)
            for r in eight_k_results:
                cik = r["cik"]
                existing = seen_ciks.get(cik)
                if existing and existing.compound_type == "insider_activist":
                    # Upgrade to triple_convergence
                    upgraded = CompoundSignalService._upgrade_to_triple(existing, r)
                    seen_ciks[cik] = upgraded
                else:
                    sig = CompoundSignalService._build_activist_8k(r)
                    if sig and (cik not in seen_ciks or sig.score > seen_ciks[cik].score):
                        seen_ciks[cik] = sig
        except Exception as e:
            logger.warning(f"Failed to detect activist_8k compounds: {e}")

        # --- Query 3: insider_activist_sell (sell clusters near 13D filings) ---
        try:
            sell_results = await CompoundSignalService._find_insider_activist(days, direction="sell")
            for r in sell_results:
                cik = r["cik"]
                if cik not in seen_ciks:  # Don't overwrite bullish compounds
                    sig = CompoundSignalService._build_insider_activist(r, direction="sell")
                    if sig:
                        seen_ciks[cik] = sig
        except Exception as e:
            logger.warning(f"Failed to detect insider_activist_sell compounds: {e}")

        signals = list(seen_ciks.values())
        signals.sort(key=lambda s: s.score, reverse=True)
        return signals

    @staticmethod
    async def _find_insider_activist(days: int, direction: str = "buy") -> list[dict]:
        """Find companies with both 13D filings and insider clusters within ±30 days."""
        tx_code = "P" if direction == "buy" else "S"
        min_traders = 2

        query = """
            MATCH (af:ActivistFiling)-[:TARGETS]->(c:Company)-[:INSIDER_TRADE_OF]->(t:InsiderTransaction)
            WHERE af.filing_date >= toString(date() - duration({days: $days}))
              AND t.transaction_code = $tx_code
              AND t.transaction_date >= toString(date(af.filing_date) - duration({days: 30}))
              AND t.transaction_date <= toString(date(af.filing_date) + duration({days: 30}))
            WITH c, af,
                 collect(DISTINCT t.transaction_date) AS trade_dates,
                 sum(CASE WHEN t.total_value IS NOT NULL THEN abs(t.total_value) ELSE 0 END) AS total_value,
                 count(DISTINCT t.insider_name) AS trader_count
            WHERE trader_count >= $min_traders
            RETURN c.cik AS cik,
                   c.name AS company_name,
                   c.tickers AS tickers,
                   af.filer_name AS filer_name,
                   af.percentage AS percentage,
                   af.filing_date AS activist_date,
                   af.signal_summary AS activist_summary,
                   af.accession_number AS activist_accession,
                   total_value,
                   trader_count,
                   trade_dates
            ORDER BY total_value DESC
        """
        return await Neo4jClient.execute_query(query, {
            "days": days,
            "tx_code": tx_code,
            "min_traders": min_traders,
        })

    @staticmethod
    async def _find_activist_8k(days: int) -> list[dict]:
        """Find companies with both 13D filings and 8-K material events within ±90 days."""
        query = """
            MATCH (af:ActivistFiling)-[:TARGETS]->(c:Company)-[:FILED_EVENT]->(e:Event)
            WHERE af.filing_date >= toString(date() - duration({days: $days}))
              AND e.is_ma_signal = true
              AND e.filing_date >= toString(date(af.filing_date) - duration({days: 90}))
              AND e.filing_date <= toString(date(af.filing_date) + duration({days: 90}))
            WITH c, af, collect(e) AS events
            RETURN c.cik AS cik,
                   c.name AS company_name,
                   c.tickers AS tickers,
                   af.filer_name AS filer_name,
                   af.percentage AS percentage,
                   af.filing_date AS activist_date,
                   af.signal_summary AS activist_summary,
                   af.accession_number AS activist_accession,
                   [ev IN events | {
                       item_number: ev.item_number,
                       item_name: ev.item_name,
                       filing_date: ev.filing_date,
                       accession_number: ev.accession_number,
                       signal_type: ev.signal_type
                   }] AS event_list
            ORDER BY af.filing_date DESC
        """
        return await Neo4jClient.execute_query(query, {"days": days})

    @staticmethod
    def _build_insider_activist(row: dict, direction: str = "buy") -> Optional[CompoundSignal]:
        """Build a CompoundSignal from an insider+activist query result."""
        cik = row["cik"]
        activist_date = row["activist_date"]
        trade_dates = sorted(row.get("trade_dates", []))
        total_value = row.get("total_value", 0) or 0
        trader_count = row.get("trader_count", 0) or 0
        pct = row.get("percentage") or 0

        # Find the closest trade date to the activist filing
        timing_gap = 30  # default
        if trade_dates and activist_date:
            try:
                a_dt = datetime.strptime(activist_date, "%Y-%m-%d")
                gaps = [abs((a_dt - datetime.strptime(d, "%Y-%m-%d")).days) for d in trade_dates if d]
                if gaps:
                    timing_gap = min(gaps)
            except (ValueError, TypeError):
                pass

        compound_type = "insider_activist_sell" if direction == "sell" else "insider_activist"
        sc = score_compound(
            activist_pct=pct,
            insider_value=total_value,
            insider_count=trader_count,
            has_8k=False,
            timing_gap_days=timing_gap,
            source_count=2,
        )

        # Pick most recent date as signal_date
        all_dates = [d for d in ([activist_date] + trade_dates) if d]
        signal_date = max(all_dates) if all_dates else activist_date

        dir_word = "selling" if direction == "sell" else "buying"
        filer = row.get("filer_name", "Activist")
        pct_str = f"{pct:.1f}% stake" if pct else "stake"
        one_liner = f"{trader_count} insiders {dir_word} + {filer} {pct_str}"

        components = [
            {"source": "13D", "date": activist_date, "summary": row.get("activist_summary", "")},
            {"source": "Form 4", "date": signal_date, "summary": f"{trader_count} insiders {dir_word} ${total_value:,.0f}"},
        ]

        return CompoundSignal(
            cik=cik,
            company_name=row.get("company_name", ""),
            ticker=pick_ticker(row.get("tickers")),
            compound_type=compound_type,
            score=sc,
            signal_date=signal_date,
            components=components,
            activist_filing={
                "filer_name": filer,
                "percentage": pct,
                "filing_date": activist_date,
                "accession_number": row.get("activist_accession"),
            },
            insider_context={
                "direction": direction,
                "trader_count": trader_count,
                "total_value": total_value,
                "trade_dates": trade_dates,
            },
            decision=decide_action(compound_type, sc),
            one_liner=one_liner,
        )

    @staticmethod
    def _build_activist_8k(row: dict) -> Optional[CompoundSignal]:
        """Build a CompoundSignal from an activist+8K query result."""
        cik = row["cik"]
        activist_date = row["activist_date"]
        pct = row.get("percentage") or 0
        events = row.get("event_list", [])

        if not events:
            return None

        # Check for material agreement item 1.01
        has_101 = any(ev.get("item_number") == "1.01" for ev in events)
        event_dates = [ev["filing_date"] for ev in events if ev.get("filing_date")]

        # Timing gap between activist filing and closest event
        timing_gap = 90
        if event_dates and activist_date:
            try:
                a_dt = datetime.strptime(activist_date, "%Y-%m-%d")
                gaps = [abs((a_dt - datetime.strptime(d, "%Y-%m-%d")).days) for d in event_dates if d]
                if gaps:
                    timing_gap = min(gaps)
            except (ValueError, TypeError):
                pass

        sc = score_compound(
            activist_pct=pct,
            insider_value=0,
            insider_count=0,
            has_8k=has_101,
            timing_gap_days=timing_gap,
            source_count=2,
        )

        all_dates = [d for d in ([activist_date] + event_dates) if d]
        signal_date = max(all_dates) if all_dates else activist_date

        filer = row.get("filer_name", "Activist")
        pct_str = f"{pct:.1f}% stake" if pct else "stake"
        item_desc = "material agreement" if has_101 else "8-K event"
        one_liner = f"{filer} {pct_str} + {item_desc}"

        components = [
            {"source": "13D", "date": activist_date, "summary": row.get("activist_summary", "")},
            {"source": "8-K", "date": event_dates[0] if event_dates else "", "summary": f"{len(events)} 8-K events"},
        ]

        return CompoundSignal(
            cik=cik,
            company_name=row.get("company_name", ""),
            ticker=pick_ticker(row.get("tickers")),
            compound_type="activist_8k",
            score=sc,
            signal_date=signal_date,
            components=components,
            activist_filing={
                "filer_name": filer,
                "percentage": pct,
                "filing_date": activist_date,
                "accession_number": row.get("activist_accession"),
            },
            event_context={
                "event_count": len(events),
                "has_material_agreement": has_101,
                "events": events[:5],
            },
            decision=decide_action("activist_8k", sc),
            one_liner=one_liner,
        )

    @staticmethod
    def _upgrade_to_triple(existing: CompoundSignal, eight_k_row: dict) -> CompoundSignal:
        """Upgrade an insider_activist signal to triple_convergence with 8-K data."""
        events = eight_k_row.get("event_list", [])
        has_101 = any(ev.get("item_number") == "1.01" for ev in events)
        event_dates = [ev["filing_date"] for ev in events if ev.get("filing_date")]

        # Recalculate score with 3 sources
        pct = (existing.activist_filing or {}).get("percentage", 0) or 0
        insider_val = (existing.insider_context or {}).get("total_value", 0) or 0
        insider_cnt = (existing.insider_context or {}).get("trader_count", 0) or 0

        sc = score_compound(
            activist_pct=pct,
            insider_value=insider_val,
            insider_count=insider_cnt,
            has_8k=has_101,
            timing_gap_days=7,  # Already overlapping, give proximity bonus
            source_count=3,
        )

        all_dates = [existing.signal_date] + event_dates
        signal_date = max(d for d in all_dates if d)

        item_desc = "material agreement" if has_101 else "8-K event"
        one_liner = f"{existing.one_liner} + {item_desc}"

        components = existing.components + [
            {"source": "8-K", "date": event_dates[0] if event_dates else "", "summary": f"{len(events)} 8-K events"},
        ]

        return CompoundSignal(
            cik=existing.cik,
            company_name=existing.company_name,
            ticker=existing.ticker,
            compound_type="triple_convergence",
            score=sc,
            signal_date=signal_date,
            components=components,
            activist_filing=existing.activist_filing,
            insider_context=existing.insider_context,
            event_context={
                "event_count": len(events),
                "has_material_agreement": has_101,
                "events": events[:5],
            },
            decision=decide_action("triple_convergence", sc),
            one_liner=one_liner,
        )

    @staticmethod
    async def _fetch_insider_trades(cik: str, signal_date: str, direction: str = "buy") -> list[dict]:
        """Fetch individual insider trades near the signal date for display."""
        tx_code = "S" if direction == "sell" else "P"
        query = """
            MATCH (c:Company {cik: $cik})-[:INSIDER_TRADE_OF]->(t:InsiderTransaction)<-[:TRADED_BY]-(p:Person)
            WHERE t.transaction_code = $tx_code
              AND t.transaction_date >= toString(date($signal_date) - duration({days: 30}))
              AND t.transaction_date <= toString(date($signal_date) + duration({days: 30}))
            RETURN p.name AS name,
                   t.insider_title AS title,
                   t.transaction_date AS date,
                   t.total_value AS value,
                   t.shares AS shares,
                   t.price_per_share AS price,
                   t.transaction_code AS code
            ORDER BY t.transaction_date DESC
        """
        return await Neo4jClient.execute_query(query, {
            "cik": cik,
            "tx_code": tx_code,
            "signal_date": signal_date,
        })

    @staticmethod
    async def get_compound_detail(compound_id: str, confidence_stats: Optional[dict] = None) -> Optional[dict]:
        """Get full details for a compound signal, in EventDetailResponse shape.

        compound_id format: COMPOUND-{cik}-{date}
        """
        parts = compound_id.split("-", 2)
        if len(parts) < 3 or parts[0] != "COMPOUND":
            return None

        cik = parts[1]

        # Re-run detection to find the matching signal
        signals = await CompoundSignalService.detect_compound_signals(days=180)
        sig = None
        for s in signals:
            if s.cik == cik:
                sig = s
                break
        if not sig:
            return None

        # Fetch actual insider trades from Neo4j
        direction = (sig.insider_context or {}).get("direction", "buy")
        trades = await CompoundSignalService._fetch_insider_trades(cik, sig.signal_date, direction)

        # Build timeline from trades + components
        # Use type="trade" so the frontend InsiderTimeline/SignalStory recognizes them
        timeline = []
        for t in trades:
            val = abs(t["value"] or 0)
            action = "sold" if t["code"] == "S" else "bought"
            trade_type = "sell" if t["code"] == "S" else "buy"
            title = t["title"] or ""
            title_str = f" ({title})" if title else ""
            shares = t.get("shares", 0) or 0
            price = t.get("price", 0) or 0
            timeline.append({
                "date": t["date"],
                "type": "trade",
                "trade_type": trade_type,
                "notable": True,
                "description": f"{t['name']}{title_str} {action} ${val:,.0f} ({shares:,.0f} shares @ ${price:.2f})",
                "insider_name": t["name"],
                "insider_title": title,
                "value": val,
                "shares": shares,
            })
        # Add activist filing to timeline
        if sig.activist_filing:
            af = sig.activist_filing
            timeline.append({
                "date": af.get("filing_date", sig.signal_date),
                "type": "event",
                "description": f"{af.get('filer_name', 'Activist')} filed 13D — {af.get('percentage', 0):.1f}% stake",
                "signal_level": "high",
            })
        # Add 8-K events to timeline
        if sig.event_context:
            for ev in (sig.event_context.get("events") or []):
                timeline.append({
                    "date": ev.get("filing_date", ""),
                    "type": "event",
                    "description": f"8-K Item {ev.get('item_number', '?')} — {ev.get('item_name', 'Filing')}",
                    "signal_level": ev.get("signal_level", "medium"),
                })
        timeline.sort(key=lambda t: t["date"], reverse=True)

        # Build parties from activist filing + insider traders
        parties = []
        if sig.activist_filing:
            parties.append({
                "name": sig.activist_filing.get("filer_name", "Unknown"),
                "source_quote": f"13D filer — {sig.activist_filing.get('percentage', 0):.1f}% stake",
            })
        # Group trades by person for parties list
        trader_totals: dict[str, dict] = {}
        for t in trades:
            name = t["name"]
            if name not in trader_totals:
                trader_totals[name] = {"value": 0, "title": t.get("title", ""), "count": 0}
            trader_totals[name]["value"] += abs(t["value"] or 0)
            trader_totals[name]["count"] += 1
        dir_word = "sold" if direction == "sell" else "bought"
        for name, info in sorted(trader_totals.items(), key=lambda x: x[1]["value"], reverse=True):
            title_str = f" ({info['title']})" if info["title"] else ""
            parties.append({
                "name": name,
                "source_quote": f"{dir_word} ${info['value']:,.0f} in {info['count']} trade(s){title_str}",
            })

        # Build notable trades for insider_context
        notable = []
        for name, info in sorted(trader_totals.items(), key=lambda x: x[1]["value"], reverse=True)[:5]:
            label = info["title"].split(",")[0].strip() if info["title"] else name
            notable.append(f"{label} {dir_word} ${info['value']:,.0f}")

        # Build analysis text
        type_labels = {
            "insider_activist": "Insider Cluster + Activist Filing",
            "activist_8k": "Activist Filing + 8-K Event",
            "triple_convergence": "Triple Convergence (Insider + Activist + 8-K)",
            "insider_activist_sell": "Insider Sell Cluster + Activist Filing",
        }
        agreement_type = type_labels.get(sig.compound_type, "Compound Signal")

        summary_parts = []
        if sig.activist_filing:
            af = sig.activist_filing
            pct = af.get("percentage", 0)
            summary_parts.append(f"{af.get('filer_name', 'Activist')} filed a 13D with {pct:.1f}% stake (filed {af.get('filing_date', 'N/A')}).")
        if trader_totals:
            total_val = sum(info["value"] for info in trader_totals.values())
            summary_parts.append(f"{len(trader_totals)} insiders {dir_word} totaling ${total_val:,.0f}:")
            for name, info in sorted(trader_totals.items(), key=lambda x: x[1]["value"], reverse=True):
                title_str = f" ({info['title']})" if info["title"] else ""
                summary_parts.append(f"  - {name}{title_str}: ${info['value']:,.0f}")
        if sig.event_context:
            ec = sig.event_context
            summary_parts.append(f"{ec.get('event_count', 0)} 8-K event(s) filed nearby{' including Material Agreement (1.01)' if ec.get('has_material_agreement') else ''}.")

        summary = "\n".join(summary_parts) if summary_parts else sig.one_liner

        forward_looking = (
            "Multiple independent signal sources converging on the same company "
            "is the highest-conviction pattern in our system. "
            f"Compound score: {sig.score}/100."
        )

        # Decision card — must match frontend DecisionCard interface
        conviction_map = {"Strong": "HIGH", "Moderate": "MEDIUM", "Weak": "LOW"}
        conviction = "Strong" if sig.score >= 80 else "Moderate" if sig.score >= 60 else "Weak"
        insider_dir = "buying" if direction == "buy" else "selling" if direction == "sell" else "none"
        try:
            days_since = (datetime.now() - datetime.strptime(sig.signal_date, "%Y-%m-%d")).days
        except (ValueError, TypeError):
            days_since = None
        decision_card = {
            "action": sig.decision,
            "conviction": conviction_map[conviction],
            "one_liner": sig.one_liner,
            "insider_direction": insider_dir,
            "insider_buy_type": "open_market" if direction == "buy" else "none",
            "days_since_filing": days_since,
            "compound_score": sig.score,
            "compound_type": sig.compound_type,
        }

        # Insider context in the standard shape
        total_trade_value = sum(info["value"] for info in trader_totals.values())
        insider_ctx = {
            "net_direction": "buying" if direction == "buy" else "selling" if direction == "sell" else "none",
            "total_buy_value": total_trade_value if direction == "buy" else 0,
            "total_sell_value": total_trade_value if direction == "sell" else 0,
            "notable_trades": notable,
            "cluster_activity": len(trader_totals) >= 3,
            "trade_count": len(trades),
            "person_matches": [],
            "near_filing_count": len(trades),
            "near_filing_direction": "buying" if direction == "buy" else "selling" if direction == "sell" else "none",
            "near_filing_buy_type": "open_market" if direction == "buy" else "none",
        }

        combined_level = "critical" if sig.score >= 80 else "high"

        return {
            "event": {
                "accession_number": sig.accession_number,
                "filing_date": sig.signal_date,
                "signal_level": "high",
                "signal_summary": sig.one_liner,
                "items": [],
                "item_numbers": [],
                "persons_mentioned": [],
            },
            "analysis": {
                "agreement_type": agreement_type,
                "summary": summary,
                "parties_involved": parties,
                "key_terms": [],
                "forward_looking": forward_looking,
                "forward_looking_source": "Compound signal analysis",
                "market_implications": f"Conviction: {conviction} ({sig.score}/100). Action: {sig.decision}.",
                "market_implications_source": "Multi-source convergence",
                "cached": True,
            },
            "timeline": timeline,
            "deals": [],
            "company": {
                "cik": sig.cik,
                "name": sig.company_name,
                "ticker": sig.ticker,
            },
            "combined_signal_level": combined_level,
            "insider_context": insider_ctx,
            "decision_card": decision_card,
            "company_context": {
                "sic_description": None,
                "state_of_incorporation": None,
                "officers": [],
                "directors": [],
                "board_connections": [],
                "subsidiaries_count": 0,
            },
            "signal_type": "compound",
            "compound_detail": sig.to_dict(),
        }
