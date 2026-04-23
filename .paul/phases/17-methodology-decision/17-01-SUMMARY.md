# Plan 17-01 — Earnings-proximity methodology decision

**Status:** Complete
**Date:** 2026-04-23
**Track:** Compressed (decision-only, no code change per Option 1)

## Decision

**Option 1 selected:** The earnings-proximity rule (`≤60d to next earnings`) applies as a hard filter to all unmatured signals (current 58 immature + every future signal). Matured 142 cohort is frozen per v1.2 invariant — not re-classified against the enforced rule.

## Implementation

**No code change in Phase 17.** `merge_classifications.py` already demotes `GENUINE → FILTERED` when earnings are beyond 60 days. That behavior stays.

**Phase 18 delivers the enforcement** by adding `AND t.classification = 'GENUINE'` to the `detect_clusters` Cypher query in `insider_cluster_service.py`. Without that filter, the `FILTERED` demotion has no effect — which is the root cause of the 17 contaminated immature signals surfaced on 2026-04-22.

## Expected cohort impact (once Phase 18 ships)

- Matured 142: unchanged (v1.2 + "frozen at methodology level" principle)
- Immature: drops from 58 → ~41 (the 17 FILTERED-backed rows stop emerging as signals)
- Future signals: only those within ≤60d of earnings enter SignalPerformance

## `classification_override` role

Deferred — not addressed explicitly during Phase 17. Default assumption: read-only audit tag (since Phase 18 enforces classification directly, no active consumer of `classification_override` is needed). Can be revisited if a use case emerges.

## Next

Phase 18: Cluster-detection correctness (classification filter + $10B→$5B + 10b5-1 buy exclusion + yfinance logging).
