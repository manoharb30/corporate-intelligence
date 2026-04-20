---
phase: 13-xbrl-tier-candidates
plan: 01
status: APPLIED
started: 2026-04-20
completed: 2026-04-20
---

# Plan 13-01 — XBRL mcap backfill for tier candidates

## Outcome
**DONE.** Generated `tier_candidates_v1_5.csv` with 441 rows, 431 ground-truth mcap resolved (97.7%), 198 linked to existing SignalPerformance rows.

## Artifacts
- `backend/exports/tier_candidates_backfill.py` (new)
- `backend/exports/out/tier_candidates_v1_5.csv` (441 × 25)

## Tier distribution (by ground-truth mcap)
| Tier | Total | Matured + priced |
|---|---|---|
| Micro (<$100M) | 61 | — |
| Small ($100M–$300M) | 78 | 51 |
| Midcap ($300M–$5B) | 205 | 137 |
| Large (>$5B) | 87 | 61 |
| Null (unresolvable XBRL) | 10 | — |

## Caveats
- 10 rows have null ground-truth mcap — closed-end funds + late-XBRL issuers beyond the 90d fallback. Excluded from tier analysis.
- 198 existing-SP-linked rows reuse their Phase 9 mcap values (no redundant XBRL calls).

## Deviations
None.

## Files modified
- `backend/exports/tier_candidates_backfill.py` (new)
- `backend/exports/out/tier_candidates_v1_5.csv` (new)
No Neo4j mutations.
