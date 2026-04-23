"""LEGACY LIBRARY MODULE — orchestration removed.

This file is no longer invoked as a standalone classifier. The pipeline now uses
the split architecture:
    prefilter_p.py → batch_llm_classify.py → merge_classifications.py

This module is retained as a library, exporting three shared primitives that
the new scripts import:
    - prefilter() — deterministic prefilter rules (used by prefilter_p.py)
    - CLASSIFIER_PROMPT — LLM classification prompt (used by batch_llm_classify.py)
    - build_payload() — legacy LLM payload builder (not used by new pipeline;
      new pipeline uses build_payload_dict() in prefilter_p.py)
    - classify_with_llm() — single-call LLM helper (not used by new pipeline)

The original two-stage orchestration (main()) has been removed — if you need
standalone single-day classification, use run_week.py --start DATE --days 1.

If this module is ever revived for direct use, also note that
backfill_quarterly.py and backfill_historical_form4.py still write YYYYMMDD to
filing_date — normalize those to YYYY-MM-DD before ingesting.
"""

import json
import os
import re
import sys

import anthropic
from dotenv import load_dotenv

sys.stdout.reconfigure(line_buffering=True)

load_dotenv()
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
if not ANTHROPIC_API_KEY:
    print("ERROR: ANTHROPIC_API_KEY not set")
    sys.exit(1)


# === Pre-filter rules (Python only — must be UNAMBIGUOUS) ===

def prefilter(filing: dict, txn: dict) -> tuple | None:
    """Apply deterministic NOT_GENUINE rules. Return (reason, rule_id) or None."""
    insider = filing.get("insider", {})
    insider_name = (insider.get("name") or "").upper()
    issuer_name = (filing.get("issuer_name") or "").upper()
    security = (txn.get("security_title") or "").lower()
    ownership_nature = (txn.get("ownership_nature") or "").lower()
    footnotes = (filing.get("footnotes") or "").lower()
    is_10b5_1 = filing.get("is_10b5_1", False)
    price = txn.get("price_per_share", 0) or 0
    shares = txn.get("shares", 0) or 0
    total_value = txn.get("total_value", 0) or 0

    # Rule 13 — too small
    if total_value < 500:
        return (f"Total value ${total_value:.2f} < $500 threshold", "Rule 13")

    # Rule 1 — price = 0
    if price == 0:
        return ("Price per share is 0 (compensation/transfer/SPAC)", "Rule 1")

    # Rule 11 — 10b5-1 plan
    if is_10b5_1:
        return ("Filed as 10b5-1 trading plan", "Rule 11")
    if "10b5-1 trading plan" in footnotes or "rule 10b5-1" in footnotes:
        return ("Footnote references 10b5-1 trading plan", "Rule 11")

    # Rule 12 — fractional shares + low value (DRIP indicator)
    has_fractional = (shares - int(shares)) > 0.0001
    if has_fractional and total_value < 50000:
        return (f"Fractional shares ({shares}) + value ${total_value:.2f} < $50K (DRIP indicator)", "Rule 12")

    # Rule 2 — insider is clearly an entity (not a person)
    # Use spaces/punctuation around markers to avoid false matches like "Lincoln" or "Corporation"
    entity_markers = [
        " LLC", " L.L.C.", " L.L.C ", " L.L.C,",
        " L.P.", " L.P,", ", LP", " LP,", " LP ",
        " INC.", " INC,", " INC ",
        " CORP.", " CORP,", " CORP ",
        " LTD.", " LTD,", " LTD ",
        " PLC.", " PLC,", " PLC ",
        " N.V.", " S.A.", " AG ",
        " HOLDINGS LLC", " GROUP LLC", " MANAGEMENT LP", " CAPITAL LLC", " CAPITAL LP",
        " PARTNERS LP", " PARTNERS LLC", " PARTNERS L.P.",
    ]
    # Add trailing space to insider_name to ensure end-of-string markers can match
    insider_padded = insider_name + " "
    if any(marker in insider_padded for marker in entity_markers):
        return (f"Insider name contains entity marker: {insider_name[:40]}", "Rule 2")

    # Rule 3 — issuer is L.P. or Fund (skip "Trust" — too many REIT false positives)
    issuer_padded = " " + issuer_name + " "
    if " L.P. " in issuer_padded or " L.P," in issuer_padded or " LP " in issuer_padded:
        return ("Issuer name contains L.P./LP", "Rule 3")
    fund_patterns = [" FUND ", " FUND,", " FUND.", "FUND, INC", "FUND INC.", "FUND, INC.", "FUND HOLDINGS"]
    if any(p in issuer_padded for p in fund_patterns) or issuer_name.endswith(" FUND"):
        return ("Issuer name contains 'Fund'", "Rule 3")

    # Rule 4 — non-equity security (skip "Preferred" — could be publicly traded)
    nonequity_terms = [
        "limited partnership units",
        "limited liability company interests",
        "shares of beneficial interest",
        "membership units",
        "rights to receive",
        "warrants",
    ]
    if any(t in security for t in nonequity_terms):
        return (f"Security title is non-equity: {security[:50]}", "Rule 4")

    # Rule 5 — DRIP
    if any(t in footnotes for t in ["reinvestment of dividends", "dividend reinvestment plan",
                                     "dividend reinvestment", "drip "]):
        return ("Footnote mentions dividend reinvestment", "Rule 5")

    # Rule 6 — ESPP / Director Stock Purchase Plan
    if any(t in footnotes for t in ["director stock purchase plan", "employee stock purchase plan",
                                     "employee share purchase plan"]):
        return ("Footnote mentions employee/director stock purchase plan", "Rule 6")

    # Rule 7 — SPAC indicators (only unambiguous SPAC-specific terms)
    if "initial business combination" in footnotes or "private units" in footnotes:
        return ("Footnote mentions SPAC (initial business combination/private units)", "Rule 7")

    # Rule 8 — fund commitment
    if any(t in footnotes for t in ["prior commitment", "seed investment", "seed capital",
                                     "investment company act"]):
        return ("Footnote mentions fund commitment / Investment Company Act", "Rule 8")

    # Rule 9 — option exercise settlement
    if any(t in footnotes for t in ["shares withheld to satisfy", "cashless exercise", "net exercise"]):
        return ("Footnote mentions cashless/net exercise or shares withheld", "Rule 9")

    # Rule 10 — RSU/PSU vesting
    if any(t in footnotes for t in ["restricted stock units will vest", "rsus vest", "psus vesting"]):
        return ("Footnote mentions RSU/PSU vesting", "Rule 10")
    if "settlement of" in footnotes and ("performance stock" in footnotes or "deferred share units" in footnotes):
        return ("Footnote mentions settlement of performance/deferred shares", "Rule 10")

    # Rule 14 — Phantom stock (deferred comp, not open-market equity)
    if "phantom stock" in security:
        return ("Security title is 'Phantom Stock' (deferred compensation)", "Rule 14")

    # Rule 15 — 409A deferred compensation plan in ownership nature
    # (check ownership_nature only — footnote check contaminated by multi-transaction filings)
    if "409a" in ownership_nature:
        return (f"Ownership nature is 409A deferred comp plan: {ownership_nature[:50]}", "Rule 15")

    # Rule 16 — Common Units (LP/LLC partnership interest, not common stock)
    if "common units" in security:
        return ("Security title is 'Common Units' (LP/LLC interest, not stock)", "Rule 16")

    # Rule 17 — Securities Purchase Agreement (private placement indicator)
    if "securities purchase agreement" in footnotes:
        return ("Footnote references Securities Purchase Agreement (private placement)", "Rule 17")

    # Rule 18 — Gift in private transaction
    if "gift" in footnotes and ("private transaction" in footnotes or "private placement" in footnotes):
        return ("Footnote describes gift in private transaction", "Rule 18")

    # Rule 19 — Capital call / committed investor (fund commitment)
    if "capital call" in footnotes or "committed investor" in footnotes:
        return ("Footnote references capital call / committed investor", "Rule 19")

    # === Tier 2 rules (added 2026-04-17) ===
    # Only rules with <5% false positive rate against LLM validation.
    # Rules 20 (RSU), 21 (micro-price), 24 (preferred) dropped — 9-10% FP rate.

    # Rule 20 — BDC / closed-end fund issuer (0% FP, 23 catches)
    bdc_patterns = [
        "capital corp", "capital corporation",
        "lending corp", "lending corporation",
        "credit corp", "credit corporation",
        "income corp", "income corporation",
        "investment corp", "investment corporation",
        "senior floating", "floating rate",
    ]
    is_officer_flag = insider.get("is_officer", False)
    is_director_flag = insider.get("is_director", False)
    if any(t in issuer_name.lower() for t in bdc_patterns):
        if not is_officer_flag and not is_director_flag:
            return (f"Issuer appears to be BDC/closed-end fund: {issuer_name[:40]}", "Rule 20")

    # Rule 21 — Underwritten / public offering in footnotes (2% FP, 208 catches)
    if any(t in footnotes for t in ["underwritten", "public offering", "offering price",
                                     "registered direct offering"]):
        return ("Footnote references underwritten/public offering", "Rule 21")

    return None  # No rule matched, defer to LLM


# === LLM classifier (only for cases that survived pre-filter) ===

CLASSIFIER_PROMPT = """You are an SEC Form 4 transaction classifier. Determine whether a "P" (Purchase) transaction is GENUINE or NOT_GENUINE.

This transaction has ALREADY passed deterministic pre-filter checks (price > 0, total > $500, not 10b5-1, no DRIP/ESPP/SPAC keywords, no obvious institutional name, no obvious non-equity security, no compensation footnotes). Your job is the nuanced judgment.

CLASSIFY into:
- GENUINE — Deliberate open market purchase of publicly traded equity by a person with potential information edge
- NOT_GENUINE — Subtle compensation, plan, fund, structured deal, or non-conviction transaction
- AMBIGUOUS — Cannot determine with confidence; needs manual review

KEY THINGS TO CHECK:
- Insider name with "Trust", "Bank", "Insurance", "Foundation" — could be person's last name OR entity. Determine from context (footnotes, ownership structure).
- Issuer with "Trust" in name — could be operating REIT (genuine target) OR closed-end investment trust (NOT_GENUINE).
- Security with "Preferred" — publicly traded preferred (genuine) OR private placement preferred (NOT_GENUINE).
- Multiple insiders same date same exact price = potential private placement (NOT_GENUINE)
- Footnote describes ownership through trust/LLC but the trade itself is broker-executed = GENUINE
- Footnotes contain "weighted average price" + "ranging from $X to $Y" = strong GENUINE signal
- Multiple fills same day at SLIGHTLY different prices (e.g., $32.33 and $32.371) = open-market execution = GENUINE. Market fills produce price variation; structured deals do not.
- Empty footnotes + ordinary common stock + direct ownership for a public company = most likely GENUINE open-market buy. Do not default to AMBIGUOUS just because there's no footnote — the absence of red-flag language is itself a positive signal when the other facts (price, security, role) look normal.
- "Reporting person disclaims beneficial ownership" footnote on small buys = yellow flag but not disqualifying alone; combine with other indicators.

OUTPUT FORMAT (JSON only, no other text):
{
  "classification": "GENUINE" | "NOT_GENUINE" | "AMBIGUOUS",
  "reason": "<one line explanation>"
}

When in doubt between GENUINE and AMBIGUOUS → choose AMBIGUOUS.
When in doubt between NOT_GENUINE and AMBIGUOUS → choose NOT_GENUINE.

Now classify:
"""


def build_payload(filing: dict, txn: dict) -> str:
    insider = filing.get("insider", {})
    return json.dumps({
        "issuer": filing.get("issuer_name", ""),
        "insider_name": insider.get("name", ""),
        "insider_is_officer": insider.get("is_officer", False),
        "insider_is_director": insider.get("is_director", False),
        "insider_is_ten_percent_owner": insider.get("is_ten_percent_owner", False),
        "is_10b5_1": filing.get("is_10b5_1", False),
        "security_title": txn.get("security_title", ""),
        "shares": txn.get("shares", 0),
        "price_per_share": txn.get("price_per_share", 0),
        "total_value": txn.get("total_value", 0),
        "ownership_type": txn.get("ownership_type", ""),
        "ownership_nature": txn.get("ownership_nature", ""),
        "footnotes": filing.get("footnotes", "")[:1500],  # truncate long footnotes
    }, indent=2)


def classify_with_llm(client, filing: dict, txn: dict) -> dict:
    payload = build_payload(filing, txn)
    msg = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=200,
        messages=[{"role": "user", "content": CLASSIFIER_PROMPT + payload}],
    )
    text = msg.content[0].text.strip()
    m = re.search(r'\{[^{}]*"classification"[^{}]*\}', text, re.DOTALL)
    if m:
        try:
            parsed = json.loads(m.group(0))
            return {
                "classification": parsed.get("classification", "PARSE_ERROR"),
                "reason": parsed.get("reason", ""),
                "rule_triggered": "LLM",
            }
        except json.JSONDecodeError:
            pass
    return {"classification": "PARSE_ERROR", "reason": "Failed to parse LLM JSON",
            "rule_triggered": "LLM", "raw": text[:200]}


# NOTE: The main() orchestration function was removed as part of the Phase A/B/C
# split refactor. To classify a single day end-to-end, use:
#     python run_week.py --start YYYY-MM-DD --days 1
