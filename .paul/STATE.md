# STATE.md — Current Loop Position

## Current Position

Version: 1.3.0
Milestone: v1.3 Pipeline Simplification — strong_buy only ✅ Complete
Phase: 8 of 8 (Strong_buy-only pipeline) — ✅ Complete
Plan: 08-01 UNIFIED
Status: Loop closed; milestone complete — ready for next milestone
Last activity: 2026-04-20 — Phase 8 and v1.3 milestone complete

Progress:
- v1.3 Pipeline Simplification: [██████████] 100% ✅
- Phase 8 (Strong_buy-only): [██████████] 100% ✅

## Loop Position

```
PLAN ──▶ APPLY ──▶ UNIFY
  ✓        ✓        ✓     [Loop complete — milestone v1.3 closed]
```

### Phase 8 UNIFY result
- 1 of 1 plans complete (08-01)
- Tasks: 3 of 3 DONE (all PASS)
- Unit tests: 41 pass (38 prior + 3 new TestComputeAllStrongBuyOnly)
- Live DB: 372 legacy rows deleted; 142 mature strong_buy preserved byte-identically.
- Post-code compute_all: all 198 rows are (buy, strong_buy); preserved_mature=142.
- Deviations (both benign): (1) deleted 372 not 266 — plan counted mature-only; WHERE swept immature too; (2) frontend/src/services/api.ts added (one-line type narrowing).

### Git State
Last commit: df2bb8f — feat(07-mcap-snapshot): matured-signal immutability invariant (v1.2 complete)
Branch: main
Feature branches merged: none

## Session Continuity

Last session: 2026-04-20
Stopped at: v1.3 milestone created, Phase 8 awaiting plan
Next action: /paul:plan  (plan Phase 8: Strong_buy-only pipeline)
Resume file: .paul/ROADMAP.md
Resume context:
- Single-concern milestone: remove legacy signal tiers + sell direction.
- Today 408 mature rows → 142 strong_buy (surfaced) + 266 legacy (never shown).
- Scope: compute_all stops sell detection; _compute_one gates on strong_buy; delete 266 legacy rows; audit dead code in frontend/API/exports/feed.
- Constraint: v1.2 matured-immutability invariant holds — the 142 matured strong_buy rows must remain byte-identical.

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
