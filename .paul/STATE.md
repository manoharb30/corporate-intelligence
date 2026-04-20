# STATE.md — Current Loop Position

## Current Position

Version: 1.4.0-dev
Milestone: v1.4 Signal Quality Audit — ground-truth mcap + per-signal post-mortem
Phase: 9 of 12 (Ground-truth market cap) — ✅ Complete
Plan: 09-01 UNIFIED
Status: Ready to plan Phase 10 (Per-signal audit template)
Last activity: 2026-04-20 — Phase 9 complete; 141/142 mcap_at_signal_true resolved

Progress:
- v1.4 Signal Quality Audit: [██░░░░░░░░] 16% (phase 9 apply done, 3 phases pending)
- Phase 9 (Ground-truth mcap): [███████░░░] 70%

## Loop Position

```
PLAN ──▶ APPLY ──▶ UNIFY
  ✓        ✓        ✓     [Phase 9 complete — ready to plan Phase 10]
```

APPLY notes for UNIFY (plan 09-01):
- Tasks 1, 2, 3 all executed. Status DONE_WITH_CONCERNS due to AC-2 at 96.5% (137/142).
- Unit tests: 70 relevant (10 new xbrl + 41 sp + 19 sf) all pass. 2 pre-existing collection errors in unrelated deprecated-service test files.
- Code / data:
  - NEW: `backend/ingestion/sec_edgar/xbrl_client.py` (XBRLClient async HTTP client, ~160 lines)
  - NEW: `backend/backfill_mcap_true.py` (checkpoint-resumable operational script, ~290 lines)
  - NEW: `backend/tests/test_xbrl_client.py` (10 tests)
  - MOD: `neo4j/schema-report.md` — added "Ground-truth market cap (v1.4, Phase 9)" subsection
  - DATA: 137 SignalPerformance nodes gained 6 additive properties each (`mcap_at_signal_true` + 5 provenance sidecars). NO existing property mutated.
- Deviations:
  1. Classification filter relaxed from `GENUINE` only to `GENUINE|FILTERED|NULL` — matured strong_buy signals often have underlying P txns that were later reclassified to FILTERED by the earnings filter. The real price the insiders paid is independent of classification.
  2. AC-2 is 96.5% (137/142), not 100%. 5 signals have no retrievable XBRL shares-outstanding (closed-end fund, late-IPO'd issuers, missing XBRL).
  3. FNKO shows mcap_new=$0M — likely a near-zero avg_px artifact. Logged as concern for Phase 10 pre-check.
- Top ratio-estimate errors corrected: RPAY -92.5%, ONDS -88.1%, DNA -18.7%, ANNX -75.6%, XRN -50.0% (all old estimate → true primary-source).

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
Stopped at: v1.4 milestone created, Phase 9 awaiting plan
Next action: /paul:plan (plan Phase 9: Ground-truth market cap)
Resume file: .paul/ROADMAP.md
Resume context:
- Trigger: DNA (Ginkgo Bioworks 2024-05-15) exposed that our price-ratio mcap estimate folds reverse-splits + dilution into a single wrong number. Signal was mis-classified as $1B–$3B midcap.
- Ad-hoc audit (same session) found my DNA-derived hypotheses (pre-cluster selling, low raw price) don't generalize across the 142 pool. Need systematic per-signal audit, not one-off tests.
- Plan: 4 phases. Phase 9 = ground-truth mcap from SEC XBRL; Phase 10 = per-signal CSV; Phase 11 = classify + p-value filters; Phase 12 = implement + re-export.
- Constraint: v1.2 immutability invariant holds; new fields are additive.
- Deferred to v1.5: client-facing correction note.

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
