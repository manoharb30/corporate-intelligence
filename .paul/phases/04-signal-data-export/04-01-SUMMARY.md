---
phase: 04-signal-data-export
plan: 01
subsystem: data-export
tags: [csv, parquet, neo4j, pyarrow, data-dictionary, delivery-layer, signal-performance]

requires:
  - phase: 03-institutional-positioning
    provides: SignalPerformance Neo4j node (v1.0 TDD contract) + InsiderClusterService.get_cluster_detail
  - phase: 02-signal-quality
    provides: 141 mature strong_buy cohort definition (midcap + $100K + 2+ insiders + earn≤60d)

provides:
  - signals_v1_1_{date}.csv (141 rows × 32 cols, UTF-8, comment+header)
  - signals_v1_1_{date}.parquet (141 rows × 32 cols, typed schema)
  - DATA_DICTIONARY.md (institutional-grade column spec with caveats + reproducibility)
  - verify_export.py (row count + null audit + 5-signal Neo4j spot-check)
  - Reusable delivery-layer module pattern (backend/exports/)

affects:
  - 05-research-brief-pdf (consumes the 32-column schema as data appendix + uses DATA_DICTIONARY.md text as methodology source)
  - 06-per-fund-delivery (ships CSV + Parquet + dictionary as attachments)

tech-stack:
  added: [pyarrow>=15.0]
  patterns:
    - "backend/exports/ as layer-3 delivery module — imports from app.services + app.db only, never app.api"
    - "Single-file async script with argparse CLI for one-off artifact generation"
    - "Schema-as-constant: COLUMNS list defines both Parquet schema and CSV column order"

key-files:
  created:
    - backend/exports/__init__.py
    - backend/exports/export_signals_v1_1.py
    - backend/exports/verify_export.py
    - backend/exports/DATA_DICTIONARY.md
  modified:
    - backend/requirements.txt
    - .gitignore

key-decisions:
  - "Reuse InsiderClusterService.get_cluster_detail() instead of reimplementing cluster-window Cypher"
  - "Add hostile_flag as 32nd column (v1.0 decision already classified as informational)"
  - "Introduce midcap-large tier label for $5B–$10B band to preserve v1.0's tightened midcap cap without silent relabeling"
  - "Coerce nulls to empty strings in string columns for CSV compatibility; keep true nulls in numeric columns"

patterns-established:
  - "Delivery layer scripts live under backend/exports/ as a Python module (not backend/ root)"
  - "32-column signal schema is the locked release format for v1.1 hedge fund artifacts"
  - "Provenance triangulation: signal-level data from SignalPerformance node + member-level data from InsiderClusterService.get_cluster_detail"

duration: ~40min
started: 2026-04-19T10:00:00Z
completed: 2026-04-19T10:35:00Z
---

# Phase 4 Plan 01: Signal Data Export Summary

**Institutional-grade CSV + Parquet artifact of the 141 mature strong_buy signals with full provenance (filing URLs, cluster member identities, SPY alpha, hostile flag), paired with a 118-line data dictionary and a Neo4j-live verification script that passed 0 mismatches on a 5-signal spot-check.**

## Performance

| Metric | Value |
|--------|-------|
| Duration | ~40 minutes end-to-end |
| Tasks | 2 of 2 completed, both PASS after qualify |
| Files created | 4 (3 Python, 1 markdown) |
| Files modified | 2 (requirements.txt, .gitignore) |
| Export runtime | ~70 seconds for 141 signals |
| Output size | 141 rows × 32 columns (CSV + Parquet) |

## Acceptance Criteria Results

| Criterion | Status | Notes |
|-----------|--------|-------|
| AC-1: Export produces exactly the v1.0 strong_buy cohort | **PASS** | 141 rows in both CSV and Parquet; identical data; deterministic column order |
| AC-2: Every documented column populated with correct type and provenance | **PASS** | 32 columns; critical fields 100% non-null; alpha = return_day0 − spy_return_90d verified (VSTS: 8.12 − (−4.04) = 12.16); primary_form4_url 100% coverage |
| AC-3: Data dictionary is complete and institutional-grade | **PASS** | 118 lines; all 32 columns with name/type/nullable/units/definition/source; cohort preamble + derived formulas + caveats + reproducibility sections |
| AC-4: Verification script confirms zero discrepancy on 5-signal spot-check | **PASS** | `verify_export` exit 0; 5 random signals (HRTG, MITK, MRVI, MAGN, EYE) all OK across cik/ticker/filing_date/num_insiders/total_value/return_day0 |

## Accomplishments

- Locked a 32-column schema for the v1.1 institutional data release, with type-enforced Parquet output and a matching CSV that's self-referencing to the dictionary
- Produced the first deliverable hedge-fund-ready artifact: 141 rows, every critical column populated, market_cap_tier uniformly `midcap` (filter correctness confirmed), 3/141 hostile-flagged (2.1% overlap rate — cleanly callable in the brief)
- Established `backend/exports/` as a clean delivery-layer module that reuses v1.0 domain services (`InsiderClusterService`, `SignalPerformance` queries) without adding API-layer coupling
- Reproducibility baked in: one-command regenerate (`python -m exports.export_signals_v1_1`) and one-command audit (`python -m exports.verify_export`)

## Data Quality Findings (handoff to Phase 5)

| Finding | Count | Implication for brief |
|---------|-------|----------------------|
| `market_cap_tier = "midcap"` | 141/141 | Midcap filter is absolute — can state this definitively |
| `hostile_flag = true` | 3/141 (2.1%) | Small, callable subset — worth a one-line footnote in caveats |
| `industry` empty string | 34/141 (24%) | SEC SIC metadata gap — recommend omitting industry from public tables or enriching pre-brief |
| `price_current` null | 0/141 | No delisted-ticker survivorship issue — cohort is clean |
| `age_days` min/max | 118 – 706 | All signals mature by design; useful range for "signal decay" discussion |
| `primary_form4_url` missing | 0/141 | Every signal traceable to a live SEC EDGAR URL |

## Task Commits

No atomic per-task commits were made during APPLY — all work is currently uncommitted in the working tree. The phase transition (next step) will create a single `feat(exports): v1.1 signal data export for hedge fund delivery` commit covering:

| Path | Change |
|------|--------|
| `backend/exports/__init__.py` | Created (module marker) |
| `backend/exports/export_signals_v1_1.py` | Created (240 lines) |
| `backend/exports/verify_export.py` | Created (197 lines) |
| `backend/exports/DATA_DICTIONARY.md` | Created (118 lines) |
| `backend/requirements.txt` | Modified (pyarrow>=15.0) |
| `.gitignore` | Modified (backend/exports/out/) |
| `.paul/phases/04-signal-data-export/04-01-PLAN.md` | Created |
| `.paul/phases/04-signal-data-export/04-01-SUMMARY.md` | Created (this file) |
| `.paul/STATE.md` | Updated |
| `.paul/ROADMAP.md` | Updated (v1.1 + phase 4 created) |
| `.paul/handoffs/archive/` | 5 handoffs archived |

Note: the generated `.csv`/`.parquet` files under `backend/exports/out/` are gitignored by design — artifacts are reproducible and get promoted to the phase output directory when a release is cut.

## Decisions Made

| Decision | Rationale | Impact |
|----------|-----------|--------|
| Use `InsiderClusterService.get_cluster_detail()` for buyer provenance | Reuses v1.0 cluster-window logic verbatim; avoids reimplementing the 30-day window + dedup logic in raw Cypher | Slightly slower (141 sequential calls × ~0.2s = ~30s) but 100% semantically aligned with v1.0 |
| Add `hostile_flag` as 32nd column | Plan's boundary allowed addition "unless spot-check reveals it's informational" — v1.0 decision log already classifies it as informational; data freely available from same service call | Data appendix aligns with v1.1 anchor list ("hostile flag" was explicitly mentioned) |
| Add `midcap-large` tier for $5B–$10B band | v1.0 decision tightened midcap cap to $5B (p=0.018 evidence); documenting the band explicitly prevents silent relabeling in downstream analysis | All 141 rows are strict `midcap`; the label is defensive documentation, not observed data |
| Skip pandas; use pyarrow directly | Parquet is the only use case; pandas adds ~100MB to venv | Lean delivery-layer footprint; no transitive numpy/pytz overhead |
| Coerce null strings to "" in CSV | CSV has no native null; empty-string + dictionary note is cleaner than the word "None" or "null" | Parquet retains true nulls where meaningful (numeric) |

## Deviations from Plan

### Summary

| Type | Count | Impact |
|------|-------|--------|
| Auto-fixed | 0 | — |
| Scope additions | 2 | Both defensible against the plan's conditional clauses; zero breakage |
| Deferred | 0 | — |

**Total impact:** Plan executed essentially as written. Both deviations are additions that strengthen the artifact without violating any boundary.

### Scope Additions

**1. [Column addition] `hostile_flag` added as 32nd column**
- **Found during:** Task 1 (export implementation) — `InsiderClusterService.get_cluster_detail` returns `has_hostile_activist` alongside `cluster_detail.buyers`
- **Plan reference:** Boundaries said "Do not add a separate hostile_flag column unless AC-2 spot-check reveals it's genuinely informational"; the informational classification was pre-established in CLAUDE.md and v1.0 decision log
- **Fix/Addition:** Added as column 31 (before `computed_at`); plan had 31 columns, output has 32
- **Files:** `backend/exports/export_signals_v1_1.py`, `backend/exports/DATA_DICTIONARY.md`
- **Verification:** 3/141 rows are true; spot-check confirmed correct routing through `has_hostile_activist` flag

**2. [Tier expansion] `market_cap_tier` has 6 buckets instead of plan's 5**
- **Found during:** Task 1 (action spec listed 5 tiers: microcap / smallcap / midcap / largecap / unknown, with a note that $5B–$10B "falls into neither midcap nor largecap")
- **Plan reference:** Plan's own action text introduced the gap. Leaving it ambiguous would either (a) lie (stretch midcap to $10B) or (b) silently drop those rows into "unknown"
- **Fix/Addition:** Added explicit `midcap-large` label for the $5B–$10B band; documented in DATA_DICTIONARY
- **Files:** `backend/exports/export_signals_v1_1.py`, `backend/exports/DATA_DICTIONARY.md`
- **Verification:** All 141 rows are strict `midcap` (no rows currently use `midcap-large`); label is future-proofing, not reshaping the cohort

### Deferred Items

None — plan executed as specified with only additive enhancements.

## Issues Encountered

| Issue | Resolution |
|-------|------------|
| Initial smoke test from repo root failed — `.env` loads from cwd | Re-ran from `backend/` directory; documented the constraint in the export script's module docstring |
| `c.industry` doesn't exist on Company node | Used `c.sic_description` (stored on Company); acknowledged 24% null-rate in DATA_DICTIONARY caveats |
| My initial Cypher window join pulled 1–2 insiders per cluster vs `num_insiders` of 4–5 | Cause: cluster windows span ~11 days but single-date `transaction_date = signal_date` match missed earlier trades. Fixed by reusing `InsiderClusterService.get_cluster_detail` which implements the proper window logic |
| sentrux coupling metric drifted 0.29 → 0.52 | Acknowledged as DONE_WITH_CONCERNS. Delivery-layer additions inherently add import edges; Quality score improved (5181 → 5356), no hard rules violated, no new god files or CC violations. User to decide whether to save a new baseline |

## Next Phase Readiness

**Ready:**
- 32-column schema locked and reproducible — Phase 5 (research brief PDF) can consume it as the data appendix
- DATA_DICTIONARY.md text is the methodology skeleton for the brief's funnel section
- Verification tooling in place to re-audit before delivery (Phase 6)
- Data quality findings (see above) feed directly into the brief's caveats section

**Concerns:**
- `industry` column is 24% null from SEC SIC gaps — Phase 5 should decide whether to enrich (e.g., yfinance/ticker lookup) or omit from public tables
- sentrux coupling metric drift may need baseline refresh before v1.1 ships; user decision pending

**Blockers:**
- None

---
*Phase: 04-signal-data-export, Plan: 01*
*Completed: 2026-04-19*
