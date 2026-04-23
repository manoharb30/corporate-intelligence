# Plan 18-01 Summary — Cluster-detection correctness

**Status:** Complete
**Date:** 2026-04-23
**Track:** Standard
**File modified:** `backend/app/services/insider_cluster_service.py` (only)

## Changes applied

| # | Location | Change |
|---|---|---|
| 1 | `detect_clusters` Cypher (line 218) | Added `AND t.classification = 'GENUINE'` — classification now governs cluster detection |
| 2 | `detect_clusters` tier logic (line 423) | Changed midcap upper cap: `<= 10_000_000_000` → `<= 5_000_000_000`. Comment updated to cite the 2026-04-17 decision (p=0.018) |
| 3 | `detect_clusters` buy branch (line 281) | Added `and not t.get("is_10b5_1", False)` — symmetric with sell branch |
| 4 | `detect_clusters` exception handler (line 438-442) | Replaced silent `except Exception:` with `except Exception as e:` + `logger.warning(...)` including ticker, exception type, and message |

## Verification

**Syntax:** `py_compile` passes.

**Tests:** 239 pass, 4 pre-existing failures (confirmed by running against unmodified code via `git stash` — failures are not regressions from this plan). Pre-existing failures:
- `test_company_search::test_combined_search_graph_only` — imports missing `app.services.company_service` module
- `test_insider_cluster_service::TestOfficerPromotion::test_two_officers_promoted_to_high` — asserts signal_summary contains `"Officer Cluster"` (that string lives only in `get_cluster_detail`, not `detect_clusters`)
- `test_insider_cluster_service::TestConvictionTiers::test_three_buyers_two_officers_strong_buy` — assertion mismatches production code (expected `strong_buy`, gets `buy`)
- `test_insider_cluster_service::TestConvictionTiers::test_two_buyers_no_officers_watch` — assertion mismatches production code (expected `watch`, gets `buy`)

These are candidates for cleanup in Phase 19 (conviction-tier unification) where `_build_cluster_from_trades` gets extracted and proper test coverage can be added.

**compute_all post-fix:**

```
preserved_mature          142          (unchanged — v1.2 invariant held)
total_clusters            347          (down from 567 pre-fix: classification filter excluded 220 non-GENUINE-backed clusters)
computed                  55
stored                    55
buy_count                 55           (v1.3 strong_buy-only)
sell_count                0
mature_count              23           (newly-matured since last compute)
elapsed_seconds           202.2
```

Cohort composition now:
- 142 preserved mature + 23 newly mature = 165 mature total
- 32 immature
- 197 total SP rows (down from 200 pre-fix)

**Cross-check:**

`audit_overrides_2026-04-22.py` post-fix output:

> *Cross-check: SP rows whose underlying txns are NOT all GENUINE*
> **None — every immature strong_buy SP row is backed by all-GENUINE txns (post-fix view).**

The 17 contaminated rows that existed pre-fix (16 FILTERED-backed + 1 NOT_GENUINE-backed including AEVEX) are gone. BMI (the Badger Meter signal that was FILTERED for earnings >60d), VSCO, MTN, MLAB, TPC, GPK, SKWD, ACIW, CMTG, TNC, SXC, ASST, QDEL, LUCK, MMS, RAL, and AVEX are all absent from SignalPerformance.

## Acceptance criteria

- **AC-1 (classification filter):** ✅ — 220 non-GENUINE clusters excluded; zero contaminated SP rows
- **AC-2 (midcap cap $5B):** ✅ — line 423 verified via grep
- **AC-3 (10b5-1 buy exclusion):** ✅ — line 281 verified via grep (symmetric with line 274 sell branch)
- **AC-4 (yfinance logging):** ✅ — line 440 verified via grep
- **AC-5 (cohort composition):** ✅ — 142 mature preserved; zero non-GENUINE-backed immature; AVEX absent

## Deviations

None.

## Boundaries honored

- `get_cluster_detail` — not touched (Phase 19 scope)
- `merge_classifications.py` — not touched (Phase 17 decision: keep earnings rule)
- `signal_performance_service.py` — not touched (Phase 20 scope for mcap)
- `ingest_genuine_p_to_neo4j.py` — not touched
- All matured SignalPerformance rows — byte-identical (v1.2 immutability)

## Next

Phase 19: Conviction-tier unification — extract `_build_cluster_from_trades` helper; align `get_cluster_detail`'s conviction-tier rule with `detect_clusters`. This is also where the 3 pre-existing failing cluster-service tests can be repaired (either updated to match production behavior or marked as intentional invariants in the refactor).
