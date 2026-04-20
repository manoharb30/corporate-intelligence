---
phase: 16-inline-xbrl-mcap
plan: 01
status: APPLIED
started: 2026-04-20
completed: 2026-04-20
---

# Plan 16-01 — Inline XBRL mcap at compute_all time (v1.6)

## Outcome

**DONE.** Forward-going mcap gap closed. New SignalPerformance nodes created by `compute_all` now populate `mcap_at_signal_true` + 5 provenance sidecars inline from SEC XBRL. Matured rows remain untouched.

## Verification evidence

```
Mature BEFORE: 142 rows, 141 with mcap_at_signal_true
compute_all result:
  preserved_mature: 142
  computed: 56 (immature + new)
  elapsed_seconds: 269.6
Immature AFTER: 56 rows, 55 with mcap_at_signal_true (1 unresolvable XBRL)
Mature AFTER: 142 rows, 141 with mcap_at_signal_true   ← UNCHANGED

PASS: matured rows unchanged; new immature rows carry inline XBRL mcap
```

## Code changes

`backend/app/services/signal_performance_service.py`:
- Imported `XBRLClient` + `SharesOutstandingEntry`.
- `_compute_one` is now `async`. Added `xbrl_cache: Optional[dict]` parameter.
- Inline XBRL fetch after the conviction_tier gate — per-CIK, cached across the compute_all run, 1s pacing between distinct CIK fetches.
- Uses `pick_shares_at_or_before` then falls back to `pick_nearest_post_signal(90d)`.
- Computes `mcap_at_signal_true = hist_price × picked.shares` + provenance.
- Returns 6 new fields in the result dict.
- `compute_all` awaits `_compute_one` and passes the shared `xbrl_cache`.
- `_store_batch` CREATE clause extended with 6 new properties.

`backend/tests/test_signal_performance_service.py`:
- Converted 7 existing `_compute_one` calls to `asyncio.run(...)` wrappers (function is async now).
- Added `import asyncio`.
- New class `TestComputeOneInlineXBRL` with 3 tests covering: populated cache, empty cache, cache=None backward compat.

`neo4j/schema-report.md`:
- Updated "Ground-truth market cap" section with population-paths table showing one-time backfill (v1.4 Phase 9) vs inline (v1.6 Phase 16).

## Tests

74 pass (71 prior + 3 new).

## Deliberate non-changes

- `estimate_historical_mcap` still populates the `market_cap` field (ratio estimate, kept for backward compat).
- `compute_conviction_tier` still reads `market_cap` (ratio estimate). Switching classification to `mcap_at_signal_true` is a separate decision beyond v1.6.
- v1.2 immutability invariant preserved: matured nodes untouched on recompute.
- v1.3 strong_buy-only invariant preserved.

## Files modified

- `backend/app/services/signal_performance_service.py`
- `backend/tests/test_signal_performance_service.py`
- `neo4j/schema-report.md`
