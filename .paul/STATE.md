# STATE.md — Current Loop Position

## Current Position

Version: 1.7.0 (in progress)
Milestone: v1.7 Signal Pipeline Reconciliation (1 of 4 phases complete)
Phase: 18 of 4 — Cluster-detection correctness
Plan: 18-01 applied, awaiting UNIFY
Status: APPLY complete — all 5 ACs satisfied, SUMMARY.md written, ready to reconcile
Last activity: 2026-04-23 — Plan 18-01 APPLY complete. Four surgical edits to insider_cluster_service.py applied + verified via compile + test suite + compute_all rerun. Cohort now clean: 142 mature preserved, 32 immature (zero contaminated, down from 17 contaminated pre-fix). AVEX + BMI + 15 other FILTERED-backed rows absent from SignalPerformance.

Progress:
- v1.7 Signal Pipeline Reconciliation: [███░░░░░░] 35% (1 of 4 phases complete; Phase 18 applied, awaiting unify)

## Loop Position

```
PLAN ──▶ APPLY ──▶ UNIFY
  ✓        ✓        ○     [Plan 18-01 applied, awaiting unify to close the loop]
```

### Post-v1.6 point fixes (not milestones, tracked by commit only)
- `42bf05c` fix(frontend): conviction labels read backend signal_level (DNA no longer mislabeled "High Conviction"). Pushed.
- `08588b7` feat(backfill_signal_coverage): `--refresh-older-than N` flag for stale-price refresh without touching matured SP rows. Pushed.
- Ops run 2026-04-21: refreshed Company.price_series for 543 companies; compute_all re-derived 57 immature SP rows with Apr 20 prices. 142 matured untouched.

### v1.6 outcome (last milestone closed)
- `_compute_one` is async; fetches SEC XBRL inline; caches per-CIK per compute_all run.
- 55/56 immature rows carry ground-truth mcap at creation.
- Matured rows untouched throughout.

### Phase 10 UNIFY result
- 1 of 1 plans complete (10-01)
- Tasks: 3 of 3 DONE, all 4 ACs satisfied
- 142-row × 33-col CSV + Parquet + data dictionary produced. Byte-deterministic across re-runs (MD5 stable: 35f57c2d...).
- Key finding: midcap filter applied to TRUE mcap would drop 10 signals with 80% hit rate / +33% avg return — tightening the filter would HURT performance. Phase 11 to investigate why with p-values.
- No deviations. No Neo4j mutations. Deterministic output (no `exported_at`).

### Phase 9 UNIFY result
- 1 of 1 plans complete (09-01)
- Tasks: 3 of 3 DONE (all PASS)
- Coverage: 141/142 (99.3%) mcap_at_signal_true populated — 139 exact + 2 post-signal approx. 1 unresolved (GAM, closed-end fund, accepted).
- Unit tests: 71 (11 new xbrl + 41 sp + 19 sf) all pass. 2 pre-existing collection errors unrelated.
- Deviations (all resolved during iteration):
  1. Classification filter relaxed GENUINE → GENUINE|FILTERED|NULL.
  2. Post-signal fallback (≤90d) added for late-XBRL issuers (ANDG, CRGY).
  3. Fall-through on sanity filter (FNKO needed WeightedAvg fallback).
  4. XBRL concept list extended 3 → 5.
- Top ratio-estimate errors corrected: ANDG -93%, RPAY -92%, ONDS -88%, SEI -86%, MRVI -60%, DNA -19%.

### Git State
Last commit: 08588b7 — feat(backfill_signal_coverage): add --refresh-older-than flag for freshness ops
Branch: main (up to date with origin/main)
Tags local: v1.0.0 through v1.6.0
Tags pushed: v1.0.0, v1.1.0 only (v1.2–v1.6 are local-only; not blocking)
Feature branches merged: none

### Phase 8 UNIFY result
- 1 of 1 plans complete (08-01)
- Tasks: 3 of 3 DONE (all PASS)
- Unit tests: 41 pass (38 prior + 3 new TestComputeAllStrongBuyOnly)
- Live DB: 372 legacy rows deleted; 142 mature strong_buy preserved byte-identically.
- Post-code compute_all: all 198 rows are (buy, strong_buy); preserved_mature=142.
- Deviations (both benign): (1) deleted 372 not 266 — plan counted mature-only; WHERE swept immature too; (2) frontend/src/services/api.ts added (one-line type narrowing).

### Git State
Last commit: f23dc17 — chore(milestones): formalize v1.2 + v1.3 — entries, archives, version bump
Branch: main
Tags: v1.0.0, v1.1.0, v1.2.0, v1.3.0 (all local; not pushed)
Feature branches merged: none

### Git State
Last commit: df2bb8f — feat(07-mcap-snapshot): matured-signal immutability invariant (v1.2 complete)
Branch: main
Feature branches merged: none

## Session Continuity

Last session: 2026-04-22 evening → 2026-04-23 early morning (v1.7 milestone + Phase 17 closed + Phase 18 plan created)
Stopped at: Phase 18 APPLY complete but unresolved concerns. User paused to restart fresh because session accumulated confusion (Claude's 548-vs-14 framing + invented same-day-cluster methodology + inability to precisely explain why 23 old-dated signals surfaced). Phase 18 code changes are live; 23 newly-surfaced mature signals in DB; no git commits all session.
Next action: **Read .paul/HANDOFF-2026-04-23.md first.** Then ask user what to tackle — do NOT presume. Likely options: commit today's work, per-signal audit of the 23 surfaced signals, close Phase 18 via UNIFY, or rescope.
Resume file: .paul/HANDOFF-2026-04-23.md
Git strategy: main (nothing committed in the 2026-04-22 session — many untracked .py files + modified backfill_daily.py; commit before Phase 17 plan begins)
Resume context:
- v1.7 created to close multi-file drift in the signal pipeline — surfaced during 2026-04-22 audit session.
- ROOT BUG: `insider_cluster_service.detect_clusters` has no `classification` filter. Lets FILTERED + NOT_GENUINE transactions cluster. Explains why today's AEVEX override had to be paired with code change, and why 17/58 immature SP rows are contaminated.
- Phase 17 is a DECISION PHASE: user must choose option 1 (tighten earnings-proximity retroactively), option 2 (reframe as informational), or option 3 (drop rule entirely). Decision determines Phase 18 implementation branch.
- Untracked work from 2026-04-22 session:
  - `backend/audit_142_mature_2026-04-22.py` + `.json` — 142-mature verification vs fresh yfinance + XBRL (SOLID, 140/142 match).
  - `backend/override_aevex_booth_2026-04-22.py` — AEVEX Booth Todd flipped to NOT_GENUINE.
  - `backend/enrich_crt_2026-04-22.py` — CRT Company node enriched (mcap $63.75M, 502 price points).
  - `backend/run_compute_all_2026-04-22.py` — wrapper for SignalPerformanceService.compute_all.
  - `backend/hypothesis_no_earnings_2026-04-22.py` — 142-cohort scenarios (ratio-mcap / TRUE-mcap × earnings-gate / no-gate). **Reliable.**
  - `backend/hypothesis_full_cohort_2026-04-22.py` — **DISCARD OUTPUT**: used invented same-day clustering instead of 30-day sliding window. Numbers are not reliable.
  - `backend/audit_overrides_2026-04-22.py` — survey of classification_override rows (4 total, all AEVEX).
  - Edit in `backend/backfill_daily.py` — two dead imports removed (filter_investment_vehicles, filter_non_companies).
  - DB mutations applied this session (not reverted): Apr 21 ingest wrote 7 GENUINE rows; AEVEX Booth flipped to NOT_GENUINE; 548 companies had prices refreshed; CRT Company enriched; SignalPerformance recomputed (142 mature preserved; 58 immature — 17 of which are contaminated pre-fix).
- v1.1 brief shipped externally; 142 mature cohort contains ~58 FILTERED-backed signals + AEVEX; v1.2 invariant keeps them frozen. Future briefs (v1.2+) will use clean cohort.
- User state at end-of-session: engaged, frustrated earlier by my method-invention error (hypothesis_full_cohort same-day clustering) — corrected. Methodology decision for Phase 17 still pending.
- Neudata timing: open decision — pre-v1.7 with caveats, pre-v1.7 with tighter 80-signal GENUINE-only cohort (+11.35pp alpha), or delay until v1.7 ships.

## Accumulated Decisions

_v1.0 decisions archived in .paul/MILESTONES.md_
_v1.1 decisions archived in .paul/MILESTONES.md_

_Next milestone decisions will be recorded here as they're made._

## Cleanup Bucket (still pending — unresolved across sessions)

Unresolved items from session 2026-04-18 handoff:

1. Root `Insider Trading Signals_ Academic Validation...pdf` — delete or keep?
2. `backend/` live pipeline .py files — must be **committed** (v1.0 pipeline currently untracked)
3. `backend/lookinsight-implementation-plan.md` + `lookinsight-roadmap.docx` — likely stale
4. `neo4j/material-agreement-signal-profile.md`, `anomaly-detector.md`, `analysis-session-state.md` — likely stale (M&A deprecated)
5. `neo4j/schema-report.md` — referenced in README + now extended with SignalPerformance section; **commit**
6. `Neo4j-9c8213f6-*.txt` (root) + `neo4j/Neo4j-2aaa6269-*.txt` — **must inspect** (likely credentials); must NOT commit
7. `.design-review/`, `.jez/`, `docs/superpowers/specs/2026-04-17-dashboard-redesign-design.md` — user to explain
8. Helper scripts at root: `create_ppt.py`, `export_neudata_samples.py`, `generate_data_catalog.py` — keep or delete

---
*Last updated: 2026-04-23 — v1.7 milestone created (Signal Pipeline Reconciliation)*
