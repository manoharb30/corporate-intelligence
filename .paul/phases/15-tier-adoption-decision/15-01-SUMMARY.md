---
phase: 15-tier-adoption-decision
plan: 01
status: APPLIED
started: 2026-04-20
completed: 2026-04-20
---

# Plan 15-01 — Tier adoption decision gate

## Outcome
**DONE — NO ADOPTION.** Both candidate tiers (small-cap, large-cap) rejected by Phase 14's statistical analysis. v1.5 closes with the midcap product definition intact.

## Decision

No change to `conviction_tier` enum. Only value remains `'strong_buy'`. Confirmed live.

### Evidence from Phase 14

| Candidate tier | n_mature | Hit rate | p_fisher vs midcap | p_bonferroni | Verdict |
|---|---|---|---|---|---|
| small-cap ($100M–$300M) | 51 | 52.94% | 0.1767 | 0.5301 | **REJECT** |
| large-cap (>$5B) | 61 | 52.46% | 0.1148 | 0.3443 | **REJECT** |
| combined (small + large) | 112 | 52.68% | 0.0529 | 0.1587 | **REJECT** |
| midcap (baseline) | 137 | 64.96% | — | — | stays the product |

None cleared the p<0.05 Bonferroni bar. Raw p for combined was 0.053 — close, but multiple-testing discipline says we stop there.

## Interpretation

The midcap filter isn't arbitrary — it's load-bearing. Small-cap and large-cap insider buying DOES happen, and individual signals can be winners, but the aggregate hit rate in those size bands is ~12 percentage points lower than midcap in our 22-month pool. That's substantive, not noise; the Bonferroni adjustment just says we don't have enough sample to distinguish "systematic ~12pp gap" from "variance within the same distribution."

## What this means

- **Product stays as is.** 142 mature strong_buy, 66.9% HR, +9.0% alpha, methodology_version='v1.1'.
- **Future-proof mechanism still exists.** `methodology_version` column introduced in v1.4 Phase 12 remains ready for when we DO have enough data to adopt tiers (likely after extended coverage backfill adds more months).
- **Extended coverage backfill is now the critical path** for any future tier adoption. The ~112-row combined small+large pool is already at raw p=0.053 — with another ~200 signals of similar quality, we'd likely cross the bar.

## AC Status
- AC-1 ✅ No tier adopted. Live DB verified: only `'strong_buy'` conviction_tier.
- AC-2 ✅ Decision documented with Phase 14 evidence.

## Deviations
None.

## Files modified
None. Phase 15 is decision-only.
