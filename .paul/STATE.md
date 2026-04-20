# STATE.md — Current Loop Position

## Current Position

Version: 1.1.0-dev
Milestone: v1.1 Hedge Fund Research Delivery — 🚧 In Progress
Phase: 5 of 6 (Research Brief PDF) — Plan 05-02 created, awaiting approval
Plan: 05-02 created (PDF rendering)
Status: PLAN created, ready for APPLY
Last activity: 2026-04-19 — Created .paul/phases/05-research-brief-pdf/05-02-PLAN.md

Progress:
- v1.1 Hedge Fund Research Delivery: [████░░░░░░] 40% (Phase 4 ✓, Phase 5 plan 05-01 ✓, 05-02 planning)
- Phase 5 (Research Brief PDF): [███████░░░] 70% (05-01 content done, 05-02 planning)

## Loop Position

```
PLAN ──▶ APPLY ──▶ UNIFY
  ✓        ○        ○     [Plan 05-02 created, awaiting approval]
```

## Session Continuity

Last session: 2026-04-20
Stopped at: Scoping-only session — confirmed next action is APPLY on Plan 05-02 (unchanged from 2026-04-19)
Next action: /paul:apply .paul/phases/05-research-brief-pdf/05-02-PLAN.md
Resume file: .paul/HANDOFF-2026-04-20.md
Resume context:
- No code changes this session — discussion only
- User chose Option A: finish v1.1 before opening any 2024-backfill work
- Post-v1.1 parking lot: new milestone "Data Coverage Expansion" → Phase 1 = Jan–May 2024 backfill (optionally 2023)
- DB earliest coverage confirmed: Jun 2024 – Apr 2026 (22 months, per PROJECT.md)

APPLY notes for UNIFY (plan 05-01):
- Tasks completed: 3 auto + 1 checkpoint (all PASS, user-approved)
- Significant spec changes during execution (user-directed, documented as scope additions):
  1. Section 2 reframed from "Background and Thesis" to confident "Thesis"
  2. Section 6 REPLACED: "Caveats" → "Academic Foundation" with 4 cited papers
  3. Section 4.1-4.6 each extended with academic citations (Jeng/Metrick/Zeckhauser 2003, Cohen/Malloy/Pomorski 2012, Lakonishok & Lee 2001, Seyhun 1986, Ke/Huddart/Petroni 2003)
  4. Section 5: added 5.5 high-conviction subset (signal_level), 5.6 hostile overlap (renumbered), 5.7 Signal-level performance log (month-grouped with "Month Year" subheadings, 17 months)
  5. signal_level added as 33rd column in Phase 4 CSV (scope-creep, user-approved option A) — DATA_DICTIONARY.md updated, verify_export still passes 0/5 mismatches
- New artifacts:
  - backend/exports/brief_stats.py (computes funnel, headline, CI, p-values, breakdowns)
  - backend/exports/brief_charts.py (3 PNG charts: funnel, return distribution, alpha waterfall)
  - backend/exports/brief_signal_table.py (month-grouped per-signal markdown emitter)
  - .paul/phases/05-research-brief-pdf/stats.json (machine-readable facts for the brief)
  - .paul/phases/05-research-brief-pdf/charts/*.png (3 files)
  - .paul/phases/05-research-brief-pdf/brief_v1_1.md (533 lines, 6477 words, 8 sections)
  - .paul/phases/05-research-brief-pdf/per_signal_table.md (generated intermediate, 261 lines)
- Dependencies added: scipy>=1.11, matplotlib>=3.8 (backend/requirements.txt)
- Data fact discovered: alpha p-value is 0.0022 (two-sided t-test), not <0.001 as PROJECT.md asserted; brief honors the computed value

### Git State

Last commit: 5f29237 — feat(exports): v1.1 Phase 4 — hedge fund signal data export
Branch: main
Feature branches merged: none (worked directly on main)
Pending untracked (deferred from 04-18 handoff cleanup):
  - backend/ pipeline scripts (backfill_*, run_*, prefilter_p, classify_p_with_prefilter, etc.)
  - .paul/phases/03-institutional-positioning/ (v1.0 phase dir never committed)
  - Root PDFs, create_ppt.py, export_neudata_samples.py, generate_data_catalog.py
  - Neo4j-*.txt files (likely credentials — needs inspection)
  - .design-review/, .jez/, docs/superpowers/, neo4j/*.md
  - backend/lookinsight-implementation-plan.md, lookinsight-roadmap.docx

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
