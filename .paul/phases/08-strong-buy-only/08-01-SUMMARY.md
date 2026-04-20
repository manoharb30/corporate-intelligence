---
phase: 08-strong-buy-only
plan: 01
status: APPLIED
started: 2026-04-20
completed: 2026-04-20
---

# Plan 08-01 — Strong_buy-only pipeline (v1.3 complete)

## Outcome

**APPLY: DONE** — all four acceptance criteria verified end-to-end on the live DB.

## Task results

| Task | Status | Verify |
|---|---|---|
| 1. Gate compute_all + snapshot_service + API route to strong_buy buy only | DONE | PASS |
| 2. One-time delete of 372 legacy SignalPerformance rows (266 mature + 106 immature) | DONE | PASS (142 strong_buy preserved) |
| 3. Regression tests for non-strong_buy tiers + strong_buy classification | DONE | PASS (41 tests pass) |

## Code changes

`backend/app/services/signal_performance_service.py`:
- `compute_all`: removed `detect_clusters(direction="sell")` call and `sell_clusters` loop; simplified `all_clusters` construction; simplified logger message to "Detected N buy clusters".
- `_compute_one`: added short-circuit `return None` immediately after `compute_conviction_tier` when `conviction_tier != "strong_buy"`.
- `get_summary`: removed the `is_sell` case, `sell_count` field, and sell aggregate branches. Query simplified to buy-only aggregates.

`backend/app/services/snapshot_service.py`:
- `get_signal_list`: removed sell-side `detect_clusters` call, removed the `for c in sell_clusters:` loop emitting `insider_sell_cluster` signals, removed `sell_signals` split, removed `_compute_sell_stats` function, removed `sell_stats` and `pass_stats` from the output blob.

`backend/app/api/routes/signal_performance.py`:
- `direction` query regex tightened from `^(buy|sell)$` to `^(buy)$` on both `get_signal_performances` and `download_csv`.

`frontend/src/services/api.ts`:
- `signal_type` type union narrowed from `'insider_cluster' | 'insider_sell_cluster'` to `'insider_cluster'`.

`backend/tests/test_signal_performance_service.py`:
- New class `TestComputeAllStrongBuyOnly` with 3 tests covering watch-tier skip, buy-tier skip, and strong_buy passthrough.

`neo4j/schema-report.md`:
- New "Scope invariant (enforced 2026-04-20, v1.3)" subsection under SignalPerformance section.

## Intentionally untouched

- `backend/app/services/insider_cluster_service.py` — stays parameterized for `direction='sell'` (unit tests exercise it). Only the live callers changed.
- Pure computation functions in `signal_performance_service.py` — unchanged.
- `direction` and `conviction_tier` columns on SignalPerformance — kept (always `'buy'` / `'strong_buy'` now; future-proof).
- `feed_service.py` — its `net_direction` describes within-cluster insider behavior, unrelated to signal direction.

## Verification evidence

**Unit tests:**
```
41 passed in 0.80s
  (34 legacy + 4 v1.2 TestComputeAllPreservesMatured + 3 new TestComputeAllStrongBuyOnly)
```

**One-time migration (Task 2):**
```
Mature strong_buy BEFORE: 142
Total SignalPerformance BEFORE: 570
Deleted (legacy rows): 372
Mature strong_buy AFTER: 142
Total SignalPerformance AFTER: 198
PASS: legacy rows cleaned, strong_buy preserved
```

**Live compute_all after code changes:**
```
compute_all result:
  preserved_mature: 142
  total_clusters: 583  (buy only; was 699 with sells)
  computed: 56         (non-strong_buy short-circuited)
  stored: 56
  buy_count: 56
  sell_count: 0
  mature_count: 0

All SignalPerformance rows by (direction, tier):
  direction=buy, tier=strong_buy: 198
AC-1 PASS: only strong_buy buy rows exist
AC-2 PASS: matured strong_buy byte-identical (142 preserved)
```

## Deviations from plan

- Task 2 deleted **372** rows (266 mature + 106 immature non-strong_buy), not 266 as the plan estimate stated. The plan's "266" count was mature-only; the WHERE clause correctly targets both mature and immature non-strong_buy. Net effect matches plan intent.
- Minor: also narrowed `frontend/src/services/api.ts` `signal_type` union (not in original plan's files_modified list). One-line type narrowing, additive clarity; no runtime impact.

## Concerns

None flagged.

## Files modified

- `backend/app/services/signal_performance_service.py`
- `backend/app/services/snapshot_service.py`
- `backend/app/api/routes/signal_performance.py`
- `backend/tests/test_signal_performance_service.py`
- `frontend/src/services/api.ts`
- `neo4j/schema-report.md`

## Next

`/paul:unify .paul/phases/08-strong-buy-only/08-01-PLAN.md` to close the loop.
