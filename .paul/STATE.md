# STATE.md — Current Loop Position

## Current Position

Version: 1.1.0-dev
Milestone: v1.1 Hedge Fund Research Delivery — 🚧 In Progress
Phase: 5 of 6 (Research Brief PDF) — Ready to plan
Plan: Not started
Status: Phase 4 complete; ready to plan Phase 5
Last activity: 2026-04-19 — Phase 4 transition complete (PROJECT.md evolved, ROADMAP marked complete, git commit pending user approval)

Progress:
- v1.1 Hedge Fund Research Delivery: [███░░░░░░░] 33% (1/3 phases complete)
- Phase 5 (Research Brief PDF): [░░░░░░░░░░] 0%

## Loop Position

```
PLAN ──▶ APPLY ──▶ UNIFY
  ○        ○        ○     [Ready for Phase 5 PLAN]
```

## Session Continuity

Last session: 2026-04-19
Stopped at: Phase 4 transitioned; git commit for the phase pending user approval
Next action: Approve Phase 4 commit, then /paul:plan for Phase 5 (Research Brief PDF)
Resume file: .paul/ROADMAP.md

APPLY notes for UNIFY:
- Tasks completed: 2 of 2
- Qualify results: 2 PASS
- Deviations:
  1. Added 32nd column `hostile_flag` (plan's conditional clause — v1.0 decision established it as informational)
  2. Added `"midcap-large"` as 6th market_cap_tier bucket for $5B–$10B band (zero rows in this bucket, but tier label defensible)
- Concerns (DONE_WITH_CONCERNS):
  - sentrux gate: coupling degraded 0.29 → 0.52 from new `backend/exports/` module; Quality improved 5181 → 5356; cycles unchanged (1→1 pre-existing); no new CC/god-file violations
  - sentrux check: 2 violations, both pre-existing (feed_service ↔ insider_cluster_service cycle + 12 CC>25 functions, none in new files)
- Artifacts produced:
  - backend/exports/__init__.py (new module)
  - backend/exports/export_signals_v1_1.py (240 lines)
  - backend/exports/verify_export.py (197 lines)
  - backend/exports/DATA_DICTIONARY.md (118 lines)
  - backend/exports/out/signals_v1_1_2026-04-19.csv (141 rows × 32 cols)
  - backend/exports/out/signals_v1_1_2026-04-19.parquet (141 rows × 32 cols)
  - backend/requirements.txt (pyarrow>=15.0 added)
  - .gitignore (backend/exports/out/ added)

Context carried forward:
- Milestone scoping answers (2026-04-19):
  - Q1 (signal scope): 141 mature strong_buy — but the methodology funnel is the story
  - Q2 (PDF format): One master PDF, not per-fund customized
  - Q3 (fresh vs refresh): Fresh write, no reference to deprecated hypotheses
- v1.0 headline numbers (verified, defensible): 141 signals, 67.4% HR, +9.0% alpha vs SPY, p<0.001
- Delivery targets: Citadel, Squarepoint, Final
- Narrative frame: funnel is the product — raw Form 4 → P classification → cluster → midcap → earnings proximity → hostile filter → maturity
- Deprecated frameworks to exclude from brief: 8-K M&A combinations, congressional trades, ownership-network hypotheses

## Accumulated Decisions

_v1.0 decisions archived in `.paul/MILESTONES.md`. Only v1.1-specific decisions tracked here._

| Decision | Milestone | Impact |
|---|---|---|
| Story-first framing for research brief | v1.1 | Methodology funnel emphasized over the 141 headline number |
| One master PDF, not per-fund | v1.1 | Simpler delivery, consistent narrative across recipients |
| Fresh write, no deprecated-framework references | v1.1 | Clean signal thesis for institutional readers |
| v1.1 phases = 4/5/6 globally (continuing sequence) | v1.1 | Preserves phase-directory convention from v1.0 |

## Cleanup Bucket (pending user decisions from handoff)

Unresolved items from session 2026-04-18 handoff — may block v1.1 if files need to ship as artifacts:

1. Root `Insider Trading Signals_ Academic Validation...pdf` — delete or keep?
2. `backend/` live pipeline .py files — must be **committed** (this is v1.0 pipeline, currently untracked)
3. `backend/lookinsight-implementation-plan.md` + `lookinsight-roadmap.docx` — likely stale
4. `neo4j/material-agreement-signal-profile.md`, `anomaly-detector.md`, `analysis-session-state.md` — likely stale (M&A deprecated)
5. `neo4j/schema-report.md` — referenced in README; keep + commit
6. `Neo4j-9c8213f6-*.txt` (root) + `neo4j/Neo4j-2aaa6269-*.txt` — **must inspect** (likely credentials); must NOT commit
7. `.design-review/`, `.jez/`, `docs/superpowers/specs/2026-04-17-dashboard-redesign-design.md` — user to explain
8. Helper scripts at root: `create_ppt.py`, `export_neudata_samples.py`, `generate_data_catalog.py` — keep or delete

---
*Last updated: 2026-04-19 — v1.1 Hedge Fund Research Delivery created*
