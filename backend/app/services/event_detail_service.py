"""Service for building event detail views with LLM analysis and timeline."""

import logging
from datetime import datetime, timedelta
from typing import Optional

from app.db.neo4j_client import Neo4jClient
from app.services.feed_service import FeedService, SignalItem
from app.services.llm_analysis_service import LLMAnalysisService
from app.services.party_linker_service import PartyLinkerService

logger = logging.getLogger(__name__)


class EventDetailService:
    """Service for retrieving detailed event information with analysis."""

    @staticmethod
    async def get_event_detail(accession_number: str) -> Optional[dict]:
        """
        Get full event detail including LLM analysis and company timeline.

        Returns dict with: event, analysis, timeline, company
        """
        # Get the event and company info
        event_query = """
            MATCH (c:Company)-[:FILED_EVENT]->(e:Event)
            WHERE e.accession_number = $accession_number
            RETURN c.cik as cik,
                   c.name as company_name,
                   c.tickers as tickers,
                   e.accession_number as accession_number,
                   e.filing_date as filing_date,
                   e.item_number as item_number,
                   e.item_name as item_name,
                   e.signal_type as signal_type,
                   e.is_ma_signal as is_ma_signal,
                   e.persons_mentioned as persons_mentioned,
                   e.raw_text as raw_text
            ORDER BY e.item_number
        """

        results = await Neo4jClient.execute_query(
            event_query, {"accession_number": accession_number}
        )

        if not results:
            return None

        # Extract company info from first result
        first = results[0]
        cik = first["cik"]
        company_name = first["company_name"]
        ticker = first["tickers"][0] if first.get("tickers") else None

        # Build event items (one filing can have multiple items)
        items = []
        all_persons = []
        for r in results:
            items.append({
                "item_number": r["item_number"],
                "item_name": r["item_name"] or FeedService.ITEM_NAMES.get(r["item_number"], ""),
                "signal_type": r["signal_type"],
                "raw_text": r["raw_text"] or "",
            })
            if r["persons_mentioned"]:
                all_persons.extend(r["persons_mentioned"])

        # Classify signal level from all items (with IPO detection)
        item_numbers = [r["item_number"] for r in results]
        raw_texts = [i["raw_text"] for i in items if i.get("raw_text")]
        signal_level, signal_summary = FeedService.classify_signal_level(item_numbers, raw_texts)

        event = {
            "accession_number": accession_number,
            "filing_date": first["filing_date"],
            "signal_level": signal_level,
            "signal_summary": signal_summary,
            "items": items,
            "item_numbers": item_numbers,
            "persons_mentioned": list(set(all_persons)),
        }

        # Get LLM analysis for the primary item (first/most significant)
        # Use the item with the most text, or the first one
        primary_item = max(items, key=lambda x: len(x.get("raw_text", "")))
        analysis = await LLMAnalysisService.get_or_analyze(
            accession_number=accession_number,
            item_number=primary_item["item_number"],
            raw_text=primary_item["raw_text"],
            company_name=company_name,
        )

        # Auto-link extracted parties to Company nodes (creates DEAL_WITH edges)
        if not analysis.get("cached"):
            await PartyLinkerService.link_event_parties(
                accession_number, primary_item["item_number"]
            )

        # Get deal connections for this company
        deals = await PartyLinkerService.get_company_deals(cik)

        # Collect counterparty CIKs for timeline
        counterparty_ciks = list({d["cik"] for d in deals})

        # Build company timeline (events + insider trades interleaved)
        timeline = await EventDetailService._build_timeline(
            cik, accession_number, counterparty_ciks
        )

        # Compute combined signal level with insider context
        combined_signal_level = signal_level
        insider_context_data = None
        try:
            dummy_signal = SignalItem(
                company_name=company_name,
                cik=cik,
                ticker=ticker,
                filing_date=first["filing_date"],
                signal_level=signal_level,
                signal_summary=signal_summary,
                items=item_numbers,
                item_names=[],
                persons_mentioned=list(set(all_persons)),
                accession_number=accession_number,
            )
            contexts = await FeedService.get_insider_context_batch([dummy_signal])
            key = f"{cik}|{first['filing_date']}|{accession_number}"
            ctx = contexts.get(key)
            if ctx:
                insider_context_data = ctx.to_dict()
                combined_signal_level = FeedService.compute_combined_signal(signal_level, ctx)
        except Exception as e:
            logger.warning(f"Failed to compute insider context for event detail: {e}")

        return {
            "event": event,
            "analysis": analysis,
            "timeline": timeline,
            "deals": deals,
            "company": {
                "cik": cik,
                "name": company_name,
                "ticker": ticker,
            },
            "combined_signal_level": combined_signal_level,
            "insider_context": insider_context_data,
        }

    @staticmethod
    async def _build_timeline(
        cik: str,
        current_accession: str,
        counterparty_ciks: list[str] | None = None,
    ) -> list[dict]:
        """
        Build an interleaved timeline of events and insider trades for a company.
        Includes counterparty insider trades if deal connections exist.
        """
        # Get all events for this company
        events_query = """
            MATCH (c:Company {cik: $cik})-[:FILED_EVENT]->(e:Event)
            RETURN e.accession_number as accession_number,
                   e.filing_date as date,
                   e.item_number as item_number,
                   e.item_name as item_name,
                   e.signal_type as signal_type,
                   e.raw_text as raw_text
            ORDER BY e.filing_date DESC
        """

        events = await Neo4jClient.execute_query(events_query, {"cik": cik})

        # Group events by accession number to avoid duplicates
        event_groups: dict[str, dict] = {}
        for e in events:
            acc = e["accession_number"]
            if acc not in event_groups:
                event_groups[acc] = {
                    "date": e["date"],
                    "type": "event",
                    "accession_number": acc,
                    "items": [],
                    "raw_texts": [],
                    "is_current": acc == current_accession,
                }
            item_name = e["item_name"] or FeedService.ITEM_NAMES.get(e["item_number"], "")
            event_groups[acc]["items"].append({
                "item_number": e["item_number"],
                "item_name": item_name,
            })
            if e.get("raw_text"):
                event_groups[acc]["raw_texts"].append(e["raw_text"])

        # Build descriptions for event groups
        timeline_entries = []
        for acc, group in event_groups.items():
            item_labels = [f"Item {i['item_number']}: {i['item_name']}" for i in group["items"]]
            # Classify the signal level for this group (with IPO detection)
            item_numbers = [i["item_number"] for i in group["items"]]
            level, summary = FeedService.classify_signal_level(item_numbers, group.get("raw_texts"))

            timeline_entries.append({
                "date": group["date"],
                "type": "event",
                "accession_number": acc,
                "description": summary,
                "detail": ", ".join(item_labels),
                "signal_level": level,
                "is_current": group["is_current"],
            })

        # Get insider trades for this company
        trades_query = """
            MATCH (c:Company {cik: $cik})-[:INSIDER_TRADE_OF]->(t:InsiderTransaction)
            RETURN t.transaction_date as date,
                   t.insider_name as insider_name,
                   t.insider_title as insider_title,
                   t.transaction_code as transaction_code,
                   t.transaction_type as transaction_type,
                   t.shares as shares,
                   t.price_per_share as price_per_share,
                   t.total_value as total_value
            ORDER BY t.transaction_date DESC
            LIMIT 50
        """

        trades = await Neo4jClient.execute_query(trades_query, {"cik": cik})

        # Collect event filing dates for proximity detection
        event_dates = set()
        for entry in timeline_entries:
            if entry.get("date"):
                event_dates.add(entry["date"])

        # C-suite titles that matter
        C_SUITE_KEYWORDS = ["ceo", "cfo", "coo", "chief", "president", "director", "officer"]

        def is_c_suite(title: str) -> bool:
            if not title:
                return False
            t = title.lower()
            return any(kw in t for kw in C_SUITE_KEYWORDS)

        def is_near_filing(trade_date: str, filing_dates: set, window_days: int = 30) -> bool:
            """Check if trade is within N days before a filing."""
            if not trade_date:
                return False
            try:
                td = datetime.strptime(trade_date, "%Y-%m-%d")
                for fd_str in filing_dates:
                    fd = datetime.strptime(fd_str, "%Y-%m-%d")
                    diff = (fd - td).days
                    if 0 <= diff <= window_days:
                        return True
            except ValueError:
                pass
            return False

        # Detect cluster buys: 3+ purchases within a 30-day window
        purchases_by_date = {}
        for t in trades:
            if (t["transaction_code"] or "") == "P" and t.get("date"):
                purchases_by_date.setdefault(t["date"], []).append(t["insider_name"])

        cluster_buy_dates = set()
        purchase_dates_sorted = sorted(purchases_by_date.keys())
        for i, date_str in enumerate(purchase_dates_sorted):
            try:
                d = datetime.strptime(date_str, "%Y-%m-%d")
                window_buyers = set()
                for other_str in purchase_dates_sorted:
                    od = datetime.strptime(other_str, "%Y-%m-%d")
                    if abs((od - d).days) <= 30:
                        window_buyers.update(purchases_by_date[other_str])
                if len(window_buyers) >= 3:
                    cluster_buy_dates.add(date_str)
            except ValueError:
                pass

        for t in trades:
            code = t["transaction_code"] or ""
            trade_type = "buy" if code == "P" else "sell" if code == "S" else "other"

            shares_str = f"{t['shares']:,.0f}" if t.get("shares") else "?"
            value_str = f"${t['total_value']:,.0f}" if t.get("total_value") else ""

            description = f"{t['insider_name']} - {t['transaction_type'] or code}"
            detail = f"{shares_str} shares"
            if value_str:
                detail += f" ({value_str})"
            if t.get("insider_title"):
                detail += f" - {t['insider_title']}"

            # Determine if this trade is notable
            notable = False
            notable_reasons = []
            total_value = t.get("total_value") or 0

            # Large discretionary purchase ($100K+) by C-suite
            if code == "P" and total_value >= 100000 and is_c_suite(t.get("insider_title", "")):
                notable = True
                notable_reasons.append("Large C-suite purchase")

            # Large purchase by anyone ($100K+)
            if code == "P" and total_value >= 100000 and not notable:
                notable = True
                notable_reasons.append("Large purchase")

            # Large sale ($500K+)
            if code == "S" and total_value >= 500000:
                notable = True
                notable_reasons.append("Large sale")

            # Large disposition ($500K+) by C-suite — often merger-related
            if code == "D" and total_value >= 500000 and is_c_suite(t.get("insider_title", "")):
                notable = True
                notable_reasons.append("Large C-suite disposition")

            # Cluster buy
            if code == "P" and t.get("date") in cluster_buy_dates:
                notable = True
                if "Cluster buy" not in " ".join(notable_reasons):
                    notable_reasons.append("Cluster buy pattern")

            # Unusual timing — trade within 30 days before a filing
            if code in ("P", "S") and is_near_filing(t.get("date", ""), event_dates):
                notable = True
                if "Pre-filing" not in " ".join(notable_reasons):
                    notable_reasons.append("Pre-filing activity")

            timeline_entries.append({
                "date": t["date"],
                "type": "trade",
                "trade_type": trade_type,
                "description": description,
                "detail": detail,
                "is_current": False,
                "notable": notable,
                "notable_reasons": notable_reasons,
            })

        # Fetch counterparty insider trades
        # Include if: within the event timeline window, OR high-value ($1M+) C-suite
        if counterparty_ciks:
            # Compute event timeline date range (with 60-day buffer on each side)
            all_event_dates = [e.get("date", "") for e in timeline_entries if e.get("date")]
            if all_event_dates:
                try:
                    earliest = min(all_event_dates)
                    latest = max(all_event_dates)
                    window_start = (datetime.strptime(earliest, "%Y-%m-%d") - timedelta(days=60)).strftime("%Y-%m-%d")
                    window_end = (datetime.strptime(latest, "%Y-%m-%d") + timedelta(days=60)).strftime("%Y-%m-%d")
                except ValueError:
                    window_start = "2000-01-01"
                    window_end = "2099-12-31"
            else:
                window_start = "2000-01-01"
                window_end = "2099-12-31"

            for cp_cik in counterparty_ciks:
                cp_query = """
                    MATCH (c:Company {cik: $cik})-[:INSIDER_TRADE_OF]->(t:InsiderTransaction)
                    WHERE t.transaction_code IN ['P', 'S'] AND t.total_value >= 100000
                    RETURN c.name as company_name,
                           t.transaction_date as date,
                           t.insider_name as insider_name,
                           t.insider_title as insider_title,
                           t.transaction_code as transaction_code,
                           t.transaction_type as transaction_type,
                           t.shares as shares,
                           t.price_per_share as price_per_share,
                           t.total_value as total_value
                    ORDER BY t.total_value DESC
                    LIMIT 50
                """
                cp_trades = await Neo4jClient.execute_query(cp_query, {"cik": cp_cik})

                for t in cp_trades:
                    trade_date = t.get("date", "")
                    total_value = t.get("total_value") or 0
                    title = t.get("insider_title", "") or ""

                    # Filter: within timeline window, or high-value C-suite trade
                    in_window = window_start <= trade_date <= window_end
                    high_value_csuite = total_value >= 1000000 and is_c_suite(title)

                    if not in_window and not high_value_csuite:
                        continue

                    code = t["transaction_code"] or ""
                    trade_type = "buy" if code == "P" else "sell"

                    shares_str = f"{t['shares']:,.0f}" if t.get("shares") else "?"
                    value_str = f"${total_value:,.0f}" if total_value else ""

                    cp_name = t["company_name"] or "Counterparty"
                    description = f"[{cp_name}] {t['insider_name']} - {t['transaction_type'] or code}"
                    detail = f"{shares_str} shares"
                    if value_str:
                        detail += f" ({value_str})"
                    if title:
                        detail += f" - {title}"

                    notable_reasons = ["Counterparty trade"]
                    if in_window:
                        notable_reasons.append("During deal period")
                    if code == "P" and total_value >= 100000:
                        notable_reasons.append("Large purchase")
                    if code == "S" and total_value >= 500000:
                        notable_reasons.append("Large sale")
                    if high_value_csuite and not in_window:
                        notable_reasons.append("High-value C-suite")

                    timeline_entries.append({
                        "date": trade_date,
                        "type": "trade",
                        "trade_type": trade_type,
                        "description": description,
                        "detail": detail,
                        "is_current": False,
                        "notable": True,
                        "notable_reasons": notable_reasons,
                    })

        # Sort by date descending
        timeline_entries.sort(key=lambda x: x.get("date", ""), reverse=True)

        return timeline_entries
