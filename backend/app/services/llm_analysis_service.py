"""Service for LLM-powered analysis of SEC filings using Claude Haiku."""

import json
import logging
from datetime import datetime

import anthropic

from app.config import settings
from app.db.neo4j_client import Neo4jClient

logger = logging.getLogger(__name__)

ANALYSIS_PROMPT = """You are analyzing an SEC 8-K filing for a company. Extract facts ONLY from the filing text below. Do not use outside knowledge. If the text does not contain enough information for a field, say "Not stated in filing."

Company: {company_name}
Filing Item: {item_number}

Filing Text:
{raw_text}

Return a JSON object with these fields:

- "agreement_type": A short label for what this filing covers (e.g., "Merger Agreement", "Credit Facility", "Asset Purchase", "Executive Appointment", "Bylaw Amendment"). Be specific.
- "summary": 2-3 sentence summary of what this filing discloses. Only state facts from the text.
- "parties_involved": Array of entity names mentioned as parties. Each entry should be an object with "name" (entity name) and "source_quote" (the exact phrase from the filing where this entity is mentioned).
- "key_terms": Array of notable terms/values/conditions. Each entry should be an object with "term" (the extracted term) and "source_quote" (exact phrase from the filing containing this term).
- "forward_looking": What concrete next steps are mentioned in the filing itself (regulatory approvals, closing conditions, shareholder votes). Only cite what the filing states. If nothing is stated, say "No forward-looking statements in filing."
- "forward_looking_source": The exact quote from the filing supporting the forward_looking field. Empty string if none.
- "market_implications": Brief factual note on what this means for the company based only on what the filing states. Do not speculate.
- "market_implications_source": The exact quote from the filing supporting market_implications. Empty string if none.

IMPORTANT: Every claim must be traceable to text in the filing. The "source_quote" fields must be exact substrings from the filing text above.

Return ONLY valid JSON, no markdown formatting."""


class LLMAnalysisService:
    """Analyzes SEC filings using Claude Haiku."""

    @staticmethod
    async def analyze_filing(raw_text: str, item_number: str, company_name: str) -> dict:
        """
        Analyze a filing's text using Claude Haiku.

        Returns dict with: agreement_type, summary, parties_involved,
        key_terms, forward_looking, market_implications
        """
        empty_result = {
            "agreement_type": "Unknown",
            "summary": "",
            "parties_involved": [],
            "key_terms": [],
            "forward_looking": "N/A",
            "forward_looking_source": "",
            "market_implications": "N/A",
            "market_implications_source": "",
        }

        if not settings.ANTHROPIC_API_KEY:
            empty_result["summary"] = "LLM analysis unavailable - no API key configured."
            return empty_result

        # Truncate text to avoid excessive token usage (~4000 chars is plenty)
        truncated_text = raw_text[:4000] if raw_text else ""

        if not truncated_text.strip():
            empty_result["summary"] = "No filing text available for analysis."
            return empty_result

        prompt = ANALYSIS_PROMPT.format(
            company_name=company_name,
            item_number=item_number,
            raw_text=truncated_text,
        )

        try:
            client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)
            message = client.messages.create(
                model="claude-haiku-4-5-20251001",
                max_tokens=1500,
                temperature=0,
                messages=[{"role": "user", "content": prompt}],
            )

            response_text = message.content[0].text.strip()

            # Strip markdown code fences if present
            if response_text.startswith("```"):
                lines = response_text.split("\n")
                lines = [l for l in lines if not l.strip().startswith("```")]
                response_text = "\n".join(lines)

            analysis = json.loads(response_text)

            # Normalize parties_involved — now expects [{name, source_quote}]
            raw_parties = analysis.get("parties_involved", [])
            parties = []
            for p in raw_parties:
                if isinstance(p, dict):
                    parties.append({
                        "name": p.get("name", ""),
                        "source_quote": p.get("source_quote", ""),
                    })
                elif isinstance(p, str):
                    # Fallback if LLM returns plain strings
                    parties.append({"name": p, "source_quote": ""})

            # Normalize key_terms — now expects [{term, source_quote}]
            raw_terms = analysis.get("key_terms", [])
            terms = []
            for t in raw_terms:
                if isinstance(t, dict):
                    terms.append({
                        "term": t.get("term", ""),
                        "source_quote": t.get("source_quote", ""),
                    })
                elif isinstance(t, str):
                    terms.append({"term": t, "source_quote": ""})

            return {
                "agreement_type": analysis.get("agreement_type", "Unknown"),
                "summary": analysis.get("summary", ""),
                "parties_involved": parties,
                "key_terms": terms,
                "forward_looking": analysis.get("forward_looking", ""),
                "forward_looking_source": analysis.get("forward_looking_source", ""),
                "market_implications": analysis.get("market_implications", ""),
                "market_implications_source": analysis.get("market_implications_source", ""),
            }

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse LLM response as JSON: {e}")
            empty_result["summary"] = "Analysis failed - could not parse response."
            return empty_result
        except Exception as e:
            logger.error(f"LLM analysis failed: {e}")
            empty_result["summary"] = f"Analysis failed: {str(e)}"
            return empty_result

    @staticmethod
    async def get_or_analyze(
        accession_number: str,
        item_number: str,
        raw_text: str,
        company_name: str,
    ) -> dict:
        """
        Get cached analysis from Neo4j or run a new analysis.

        Caches results on the Event node for future lookups.
        """
        # Check for cached analysis (v2 = has citation fields)
        cache_query = """
            MATCH (e:Event {accession_number: $accession_number, item_number: $item_number})
            WHERE e.llm_summary IS NOT NULL AND e.llm_version = 2
            RETURN e.llm_summary as summary,
                   e.llm_agreement_type as agreement_type,
                   e.llm_parties as parties,
                   e.llm_key_terms as key_terms,
                   e.llm_forward_looking as forward_looking,
                   e.llm_forward_looking_source as forward_looking_source,
                   e.llm_market_implications as market_implications,
                   e.llm_market_implications_source as market_implications_source
        """

        results = await Neo4jClient.execute_query(cache_query, {
            "accession_number": accession_number,
            "item_number": item_number,
        })

        if results and results[0].get("summary"):
            r = results[0]
            return {
                "agreement_type": r["agreement_type"] or "Unknown",
                "summary": r["summary"],
                "parties_involved": json.loads(r["parties"]) if r.get("parties") else [],
                "key_terms": json.loads(r["key_terms"]) if r.get("key_terms") else [],
                "forward_looking": r["forward_looking"] or "",
                "forward_looking_source": r["forward_looking_source"] or "",
                "market_implications": r["market_implications"] or "",
                "market_implications_source": r["market_implications_source"] or "",
                "cached": True,
            }

        # Run new analysis
        analysis = await LLMAnalysisService.analyze_filing(raw_text, item_number, company_name)

        # Cache on the Event node (v2 with citations)
        cache_store_query = """
            MATCH (e:Event {accession_number: $accession_number, item_number: $item_number})
            SET e.llm_summary = $summary,
                e.llm_agreement_type = $agreement_type,
                e.llm_parties = $parties,
                e.llm_key_terms = $key_terms,
                e.llm_forward_looking = $forward_looking,
                e.llm_forward_looking_source = $forward_looking_source,
                e.llm_market_implications = $market_implications,
                e.llm_market_implications_source = $market_implications_source,
                e.llm_analyzed_at = $analyzed_at,
                e.llm_version = 2
        """

        await Neo4jClient.execute_query(cache_store_query, {
            "accession_number": accession_number,
            "item_number": item_number,
            "summary": analysis["summary"],
            "agreement_type": analysis["agreement_type"],
            "parties": json.dumps(analysis["parties_involved"]),
            "key_terms": json.dumps(analysis["key_terms"]),
            "forward_looking": analysis["forward_looking"],
            "forward_looking_source": analysis["forward_looking_source"],
            "market_implications": analysis["market_implications"],
            "market_implications_source": analysis["market_implications_source"],
            "analyzed_at": datetime.now().isoformat(),
        })

        analysis["cached"] = False
        return analysis
