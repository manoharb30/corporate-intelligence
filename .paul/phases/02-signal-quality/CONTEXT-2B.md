# Phase 2B: Activist Compound Signal Validation — Discussion Context

## Goals

1. Validate ONE hypothesis: "activist files BEFORE insider cluster = stronger signal"
2. Test on existing 164 filtered strong_buy signals (no new data)
3. Pure research — no code changes, no production impact
4. Outcome drives next decision (build or don't build)

## Hypothesis

When a 13D activist filing exists BEFORE the insider cluster date, the signal performs better.

## Test Design

Split 164 signals into 3 groups:
1. **No activist** — no ActivistFiling for that company
2. **Activist BEFORE** — 13D filing_date < insider cluster date
3. **Activist AFTER** — 13D filing_date > insider cluster date

Measure for each group:
- 90d hit rate
- 90d alpha vs SPY
- Sample size

## Approach

- Single read-only query against Neo4j
- Join InsiderTransaction clusters with ActivistFiling by target_cik
- Compare filing_date vs cluster max(transaction_date)
- No code changes, no pipeline modifications

## What research says (context, not anchor)

- Duong et al 2025: insiders buying before 13D = +12% avg profits
- Our earlier test (ANY activist): inconsistent month-to-month
- Gap: we never tested temporal sequencing specifically

## Success criteria

- Test runs, 3 groups measured
- Results are what they are — if hypothesis fails, we don't build
- No commitment to any implementation

---
*Created: 2026-04-16*
