---
phase: 07-mcap-snapshot
plan: 01
status: APPLIED
started: 2026-04-20
completed: 2026-04-20
---

# Plan 07-01 — mcap snapshot (Matured-signal Immutability)

## Outcome

**APPLY: DONE** — all three acceptance criteria verified end-to-end on the live DB.

## Task results

| Task | Status | Verify |
|---|---|---|
| 1. Make `compute_all` skip matured nodes | DONE | PASS (live DB: 408 mature preserved, 0 diffs, 0 missing) |
| 2. Three regression tests | DONE | PASS (38 tests pass — 34 existing + 4 new) |
| 3. Update schema-report.md + run verification compute_all | DONE | PASS (schema doc updated; live compute_all reports `preserved_mature: 408`) |

## Code changes

`backend/app/services/signal_performance_service.py`:
- `compute_all()` — now reads matured `signal_id`s before DELETE, deletes only `is_mature = false OR IS NULL`, threads `mature_ids` into `_compute_one`, and re-fetches the full SignalPerformance set for dashboard stats. Return dict adds `preserved_mature: int`.
- `_compute_one()` — new `mature_ids: Optional[set] = None` parameter. Short-circuits with `return None` at the top when `cluster.accession_number in mature_ids`.
- `_fetch_all_for_dashboard()` — new helper returning every SignalPerformance reshaped for `_save_dashboard_stats`.

`backend/tests/test_signal_performance_service.py`:
- New class `TestComputeAllPreservesMatured` with 4 tests:
  - `test_compute_one_short_circuits_when_signal_id_in_mature_ids` (AC-1)
  - `test_compute_one_proceeds_for_new_cluster_not_in_mature_ids` (AC-2)
  - `test_compute_one_proceeds_when_mature_ids_is_none` (backward-compat)
  - `test_compute_one_proceeds_for_immature_signal_even_if_prior_immature_existed` (AC-3)

`neo4j/schema-report.md`:
- Added "Immutability invariant (enforced 2026-04-20, v1.2)" subsection under SignalPerformance section, documenting the new contract and pointing to the enforcement tests.

## Pure functions — untouched

`estimate_historical_mcap`, `compute_returns`, `compute_conviction_tier`, `compute_alpha`, `compute_pct_of_mcap`, `check_maturity`, `find_price` — all unchanged, as required.

## Deviations from plan

None. Scope executed as planned. Specifically:
- No `market_cap_at_signal` field was added — the approach shifted during planning (based on user's design input) from "add a snapshot field" to "don't touch matured rows at all", which makes a snapshot field redundant.
- `_store_batch` CREATE clause unchanged (no new properties).

## Verification evidence

**Unit tests:**
```
38 passed in 0.85s
  (34 pre-existing + 4 new TestComputeAllPreservesMatured tests)
```

**Live DB verification:**
```
Before: 408 mature rows
compute_all result:
  preserved_mature: 408
  total_clusters: 699
  computed: 162 (immature + new)
  stored: 162
  elapsed_seconds: 202.1
After: 408 mature rows
Common: 408, Diffs: 0, Missing: 0, Extra: 0
PASS: matured rows unchanged and preserved
```

## Concerns

None flagged.

## Files modified

- `backend/app/services/signal_performance_service.py`
- `backend/tests/test_signal_performance_service.py`
- `neo4j/schema-report.md`

## Next

`/paul:unify .paul/phases/07-mcap-snapshot/07-01-PLAN.md` to close the loop.
