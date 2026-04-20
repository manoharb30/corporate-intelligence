---
phase: 12-filter-redesign-reexport
plan: 01
status: APPLIED
started: 2026-04-20
completed: 2026-04-20
---

# Plan 12-01 — Methodology versioning (narrow scope)

## Outcome

**APPLY: DONE** — all three acceptance criteria satisfied. Minimal, additive methodology-version mechanism in place. No new filters (per Phase 11 Bonferroni evidence). No display changes. v1.4 milestone ready to close.

## Task results

| Task | Status | Verify |
|---|---|---|
| 1. Backfill methodology_version on 142 existing mature strong_buy | DONE | PASS — 142/142 tagged 'v1.1' |
| 2. Update _store_batch + _compute_one to set methodology_version on new signals | DONE | 71 tests pass |
| 3. Extend audit_v1_4.py COLUMNS list + schema-report.md | DONE | PASS — 34-col CSV, schema doc updated |

## Changes

**Neo4j data:**
- 142 mature strong_buy nodes: `SET sp.methodology_version = 'v1.1'`. No other property touched.

**Code:**
- `backend/app/services/signal_performance_service.py`:
  - `_store_batch` CREATE clause adds `methodology_version: COALESCE(row.methodology_version, 'v1.1')` — future-safe with default.
  - `_compute_one` return dict adds `"methodology_version": "v1.1"`.
- `backend/exports/audit_v1_4.py`:
  - COLUMNS list adds `("methodology_version", pa.string())`.
  - `fetch_signals` query returns `sp.methodology_version`.
  - `build_row` passes it through with `'v1.1'` default.

**Docs:**
- `neo4j/schema-report.md`: new "Methodology version (v1.4 Phase 12)" subsection under SignalPerformance.

## Verification evidence

```
Before: 142 mature strong_buy, 0 with methodology_version
Set methodology_version on 142 rows
After: 142 mature strong_buy, 142 with methodology_version

Audit CSV regenerated: 142 rows × 34 cols (was 33)
methodology_version counts: {'v1.1': 142}

Test suite: 71 passed (10 xbrl + 41 sp + 19 sf + 1 — unchanged)
```

## Deliberately NOT done (deferred to v1.5)

- No new filters. Phase 11's Bonferroni finding is definitive for this pool size.
- No swapping of `market_cap` → `mcap_at_signal_true_usd` on dashboard. UX decision deferred.
- No tier extension (small_cap / large_cap). That's v1.5's scope.
- No per-fund delivery, no client correction notes.

## Files modified

- `backend/app/services/signal_performance_service.py`
- `backend/exports/audit_v1_4.py`
- `neo4j/schema-report.md`
- Neo4j: 142 nodes gained 1 additive property each.

## Next

`/paul:unify` to close the loop. Phase 12 closes v1.4 cleanly. Next: `/paul:complete-milestone` for v1.4, then open v1.5 "Signal Tier Extension."
