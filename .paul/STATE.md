# STATE.md — Current Loop Position

## Current Position

Version: 1.4.0
Milestone: v1.4 Signal Quality Audit — ✅ Complete (all 4 phases)
Phase: 12 of 12 — ✅ Complete
Plan: 12-01 UNIFIED
Status: v1.4 milestone complete. Ready for milestone close + v1.5 planning.
Last activity: 2026-04-20 — Phase 12 complete; methodology_version tagged on all 142 mature strong_buy

Progress:
- v1.4 Signal Quality Audit: [██░░░░░░░░] 16% (phase 9 apply done, 3 phases pending)
- Phase 9 (Ground-truth mcap): [███████░░░] 70%

## Loop Position

```
PLAN ──▶ APPLY ──▶ UNIFY
  ✓        ✓        ✓     [Phase 11 complete — ready to plan Phase 12]
```

### Phase 11 UNIFY result
- 1 of 1 plans complete (11-01)
- Tasks: 3 of 3 DONE, all 4 ACs satisfied
- Zero filter candidates pass Bonferroni p<0.05.
- Naive true-mcap midcap filter formally REJECTED with evidence.
- v1.0 earnings rule confirmed operational (0 mature rows violate it).
- 47 loser blocks emitted with `root_cause_tag: unclassified` placeholders.
- Phase 12 guidance: NO new filters. Just methodology_version column + display decision.
- Product implication: dataset growth is the next highest-leverage move.
- Scope carved out for v1.5: tier extension (small_cap + large_cap) — 299 clusters out of pool; user granted autonomous-mode execution.

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
Last commit: 7743111 — feat(10-signal-audit-template): per-signal audit CSV (v1.4 Phase 10)
Branch: main
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

Last session: 2026-04-20
Stopped at: Phase 10 complete (commit 7743111); ready to plan Phase 11
Next action: /paul:plan (plan Phase 11: Classification + significance testing)
Resume file: .paul/phases/10-signal-audit-template/10-01-SUMMARY.md
Resume context:
- Phases 9-10 shipped. Audit CSV at backend/exports/out/signal_audit_v1_4.csv (142 × 33).
- Unexpected Phase 10 finding: naive midcap filter on TRUE mcap DROPS 10 signals with 80% HR / +33% return — making the filter worse, not better. Phase 11 must investigate with p-values, not intuition.
- Phase 11 consumes the audit CSV. Its output: per-loser root-cause tagging + validated filter candidates (p<0.05).
- Constraint: v1.2 immutability holds; audit CSV is the only input to Phase 11 (no re-queries during analysis).

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
*Last updated: 2026-04-20 — v1.1 milestone complete*
