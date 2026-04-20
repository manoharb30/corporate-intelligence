---
phase: 14-per-tier-analysis
plan: 01
status: APPLIED
started: 2026-04-20
completed: 2026-04-20
---

# Plan 14-01 — Per-tier hit-rate + alpha analysis

## Outcome
**DONE — BOTH candidate tiers REJECTED.** Neither small-cap nor large-cap sub-pool clears p<0.05 Bonferroni vs the midcap baseline. Phase 15 closes v1.5 without new tier values.

## Task results

| Task | Status | Verify |
|---|---|---|
| 1. Compute per-tier stats + report | DONE | PASS — per-tier CSV + synthesis markdown both produced |

## Results

| Tier | n_mature | Hit rate | Avg return | Avg alpha | p_fisher | p_mannwhitney | p_bonferroni | Verdict |
|---|---|---|---|---|---|---|---|---|
| small | 51 | 52.94% | +11.77% | +7.79% | 0.1767 | 0.2221 | 0.5301 | **REJECT** |
| midcap (baseline) | 137 | 64.96% | +12.64% | +7.53% | — | — | — | baseline |
| large | 61 | 52.46% | +7.58% | +2.73% | 0.1148 | 0.2192 | 0.3443 | **REJECT** |
| small+large (combined) | 112 | 52.68% | +9.50% | +5.05% | 0.0529 | 0.1267 | 0.1587 | **REJECT** |

**Interpretation:**
- Both candidate tiers have hit rates ~53%, meaningfully below midcap's 65%.
- The combined pool misses the raw p<0.05 bar too (p_fisher=0.053 raw).
- Large-cap clusters in particular have noticeably weaker alpha (+2.73% vs +7.53% midcap).
- Honest read: insider conviction buying works best in midcap. Small-cap and large-cap insider buying patterns do exist, but they don't rise to the same signal quality in this 22-month pool.

## Artifacts
- `backend/exports/tier_analysis_v1_5.py` (new)
- `backend/exports/out/tier_analysis_v1_5_stats.csv` (4 rows × 11 cols)
- `backend/exports/TIER_ANALYSIS_V1_5_REPORT.md` (synthesis markdown)

## Phase 15 implication
Phase 15 does not extend `conviction_tier`. v1.5 closes with "no new tiers added; midcap remains the product."

## Deviations
None.

## Files modified
- `backend/exports/tier_analysis_v1_5.py` (new)
- `backend/exports/TIER_ANALYSIS_V1_5_REPORT.md` (new)
- `backend/exports/out/tier_analysis_v1_5_stats.csv` (new)
No Neo4j mutations.
