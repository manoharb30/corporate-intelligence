# Plan 02-06 SUMMARY — Hostile Activist Flag

**Status:** Complete
**Date:** 2026-04-16

## What Was Built

Informational `has_hostile_activist` flag on signals. NOT a filter — signals stay GENUINE, just tagged.

- `signal_filter.py`: added `check_hostile_activist(cik)` → `HostileCheckResult(has_hostile, keywords)`
- Searches ActivistFiling.purpose_text for hostile keywords (proxy, remove, replace, etc.)
- `merge_classifications.py`: flags GENUINE signals after earnings filter
- `ingest_genuine_p_to_neo4j.py`: writes `has_hostile_activist` property to InsiderTransaction node
- 7 new tests (19 total, all passing)

## Research Backing

- 88% of losers-with-activist had hostile keywords vs 33% winners (2.6× ratio)
- Aligned with Brav 2008, Klein & Zur 2009, Greenwood & Schor 2009
- Small sample (8 losers) — directional, not conclusive → hence flag, not filter

## Key Decision

Informational flag (not filter) because:
- Small sample size doesn't justify hard exclusion
- Hedge fund clients should see the flag and decide themselves
- Preserves signal count (164 unchanged)

---
*02-06-SUMMARY.md — 2026-04-16*
