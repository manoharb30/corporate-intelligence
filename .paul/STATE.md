# STATE.md — Current Loop Position

## Current Position

Version: 1.6.0 (complete)
Milestone: None active. Next candidate: v1.7 Neudata Research Presentation (not yet scoped).
Phase: None active.
Plan: None active.
Status: Idle — user paused for machine shutdown 2026-04-21. Everything committed + pushed.
Last activity: 2026-04-21 — Frontend conviction-label fix deployed; price refresh for 543 companies applied; compute_all ran, 57 immature SP rows now carry Apr 20 close prices. Matured 142 unchanged.

Progress:
- v1.4 Signal Quality Audit: [██░░░░░░░░] 16% (phase 9 apply done, 3 phases pending)
- Phase 9 (Ground-truth mcap): [███████░░░] 70%

## Loop Position

```
PLAN ──▶ APPLY ──▶ UNIFY
  ○        ○        ○     [Idle — ready for v1.7 scoping]
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

Last session: 2026-04-21 (paused before machine shutdown)
Stopped at: Post-v1.6 ops (frontend fix + price refresh) complete, idle
Next action: User has Neudata call today. Likely start with /paul:discuss-milestone for v1.7 (Neudata presentation pack).
Resume file: .paul/HANDOFF-2026-04-21.md
Resume context:
- 6 milestones complete (v1.0 through v1.6). All tagged locally. v1.2-v1.6 tags unpushed (not blocking).
- Product state verified: 142 mature strong_buy + 57 immature = 199 total SP rows. Headline unchanged at 142/66.9%/+14.04%/+8.72% alpha.
- Frontend conviction labels aligned with backend signal_level. Dashboard honest for Neudata review.
- Prices refreshed as of Apr 20 close. BETR was showing stale $34.34 / +6.5%; now shows $46.33 / +43.7%.
- v1.1 research brief PDF (ci.lookinsight.ai Citadel/Squarepoint/Final package) is frozen: 141 / 67.4% / +9.0% / p<0.001. Do not regenerate.
- Open item for v1.7: Methodology Update PDF showing v1.4-v1.6 work (XBRL mcap, 22-filter Bonferroni audit, tier rejection).

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
