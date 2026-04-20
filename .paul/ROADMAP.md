# ROADMAP.md — Milestone & Phase Breakdown

## Version Overview

| Version | Milestone | Status | Date |
|---------|-----------|--------|------|
| v1.0 | Signal Quality | ✅ Complete | 2026-04-18 |
| v1.1 | Hedge Fund Research Delivery | ✅ Complete | 2026-04-20 |
| v1.2 | Signal Integrity — matured immutability | ✅ Complete | 2026-04-20 |
| v1.3 | Pipeline Simplification — strong_buy only | ✅ Complete | 2026-04-20 |
| v1.4 | Signal Quality Audit — ground-truth mcap + per-signal post-mortem | 🚧 In Progress | Started 2026-04-20 |

## Current Milestone

**v1.4 Signal Quality Audit — ground-truth mcap + per-signal post-mortem** (1.4.0-dev)
Status: 🚧 In Progress
Started: 2026-04-20
Phases: 0 of 4 complete

**Theme:** Stop relying on price-ratio estimates for historical market cap; ground-truth every signal against primary-source SEC data, then analyze each signal individually and redesign filters only where the data supports it (p<0.05 vs baseline). Trigger: reviewing DNA (Ginkgo Bioworks 2024-05-15) exposed that a distressed post-reverse-split penny stock had been mis-labeled `$1B–$3B midcap` — the ratio estimate folded a 40-for-1 reverse split and dilution into a single wrong number.

**Scope anchors:**
- Replace `current_mcap × (signal_price / current_price)` with SEC EDGAR XBRL-sourced shares outstanding × raw Form 4 execution price.
- Per-signal audit CSV for all 142 mature strong_buy signals (one row each, deterministic fields, no human interpretation yet).
- Per-loser root-cause tagging + p-value-tested filter candidates.
- Implement validated filters with a `methodology_version` column; keep v1.1 numbers tagged as such; respect v1.2 immutability.
- No client correction note in this milestone (deferred to v1.5).

### Phases

| Phase | Name | Plans | Status | Completed |
|-------|------|-------|--------|-----------|
| 9 | Ground-truth market cap (SEC XBRL) | 1/1 | ✅ Complete | 2026-04-20 |
| 10 | Per-signal audit template | 1/1 | ✅ Complete | 2026-04-20 |
| 11 | Classification + significance testing | 1/1 | ✅ Complete | 2026-04-20 |
| 12 | Filter redesign + re-export | TBD | Not started | — |

### Phase 9: Ground-truth market cap (SEC XBRL)

**Focus:** Build a small EDGAR XBRL client to fetch `dei:EntityCommonStockSharesOutstanding` per CIK from `data.sec.gov/api/xbrl/companyfacts/CIK{padded}.json`. For each of the 142 mature strong_buy signals, pick the shares-outstanding value reported in the quarter containing or closest-prior-to `signal_date`. Store as immutable `mcap_at_signal_true` (= `raw_execution_price × shares_outstanding`). Backfill existing 142 signals; add idempotency test.
Plans: TBD (defined during /paul:plan)

### Phase 10: Per-signal audit template

**Focus:** Produce `signal_audit_v1_4.csv` — 142 rows × 20+ columns. All fields computed from stored data (ingest, price_series, SPY, XBRL shares). Deterministic; zero human judgment in Phase 10. Columns include per-signal earnings proximity, pre-cluster officer sells (180d), post-signal officer sells (90d), volatility at signal, SPY return during hold, raw and adjusted returns, industry, true mcap. Output ready for Phase 11 pattern mining.
Plans: TBD (defined during /paul:plan)

### Phase 11: Classification + significance testing

**Focus:** For each of the ~47 losing signals, tag root-cause categories. Then for each candidate filter, compute hit rate and alpha of the excluded sub-pool + the remaining sub-pool; p-value vs baseline (66.9% HR, +8.72% alpha). Reject filters that don't clear p<0.05. Output: audit report markdown with validated filter candidates and per-signal tags.
Plans: TBD (defined during /paul:plan)

### Phase 12: Filter redesign + re-export

**Focus:** Implement validated filters (only those that passed Phase 11). Add `methodology_version` column to SignalPerformance ('v1.1' for existing matured, 'v1.4' for new). Regenerate exported CSV/Parquet with both methodology versions represented. Update DATA_DICTIONARY.md. v1.2 matured-immutability invariant holds: no existing matured row mutates.
Plans: TBD (defined during /paul:plan)

## Backlog (not scheduled)

### Operations
- [ ] Daily auto-ingest (cron/scheduler)
- [ ] Signal alert system (new strong_buy → notify)
- [ ] Price/market cap freshness automation
- [ ] Monitoring/health checks

### Scale
- [ ] First paid institutional client
- [ ] Neudata marketplace listing
- [ ] Historical data licensing
- [ ] Extended coverage (Jan–Apr 2024 next; 2023 after)
- [ ] S3 bucket signal delivery
- [ ] Per-fund delivery / outreach (was v1.1 Phase 6, dropped; revisit when cadence is defined)

### Correctness / Research
- [ ] Window size experiment (30d vs 40d) — needs non-destructive analysis approach
- [ ] Industry enrichment beyond SEC SIC (24% SIC-null rate in Phase 4 export)

## Completed Milestones

<details>
<summary>v1.3 Pipeline Simplification — strong_buy only — 2026-04-20 (1 phase, 1 plan)</summary>

| Phase | Name | Plans | Status |
|-------|------|-------|--------|
| 8 | Strong_buy-only pipeline | 1/1 | ✅ Complete |

**Outcome:** SignalPerformance now only holds strong_buy buy rows. 372 legacy rows deleted. 142 mature strong_buy preserved byte-identically. `compute_all`, `snapshot_service`, and signal_performance API route all cleaned. 3 new regression tests.

Commit: `edf6a41`
Archive: `.paul/milestones/v1.3.0-ROADMAP.md`

</details>

<details>
<summary>v1.2 Signal Integrity — matured immutability — 2026-04-20 (1 phase, 1 plan)</summary>

| Phase | Name | Plans | Status |
|-------|------|-------|--------|
| 7 | mcap snapshot (matured immutability) | 1/1 | ✅ Complete |

**Outcome:** `compute_all` now preserves matured `SignalPerformance` nodes byte-identically. 408 matured rows verified unchanged across a live recompute. 4 new regression tests.

Commit: `df2bb8f`
Milestone log: `.paul/MILESTONES.md`

</details>

<details>
<summary>v1.1 Hedge Fund Research Delivery — 2026-04-20 (2 phases shipped, 1 dropped)</summary>

| Phase | Name | Plans | Status |
|-------|------|-------|--------|
| 4 | Signal Data Export | 1/1 | ✅ Complete |
| 5 | Research Brief (Content) | 1/1 (05-02 PDF closed) | ✅ Complete |
| 6 | Per-Fund Delivery | — | Dropped from scope |

**Artifacts:** 141-signal CSV + Parquet + data dictionary; 533-line methodology brief with academic foundation; 3 charts + stats.json.

Full archive: `.paul/milestones/v1.1.0-ROADMAP.md`
Milestone log: `.paul/MILESTONES.md`

</details>

<details>
<summary>v1.0 Signal Quality — 2026-04-18 (3 phases, 14 plans)</summary>

| Phase | Name | Plans | Status |
|-------|------|-------|--------|
| 1 | Data Pipeline | (pre-PAUL) | ✅ Complete |
| 2 | Signal Quality | 6/6 | ✅ Complete |
| 3 | Institutional Positioning | 8/8 | ✅ Complete |

**Headline result:** 141 mature strong_buy signals, 67.4% HR, +9.0% alpha vs SPY (p<0.001).
Data range: Jun 2024 – Apr 2026 (22 months). Production deployed at ci.lookinsight.ai.

Full archive: `.paul/milestones/v1.0.0-ROADMAP.md`
Milestone log: `.paul/MILESTONES.md`

</details>

---
*ROADMAP.md — Updated when phases complete or scope changes*
*Last updated: 2026-04-20 — v1.4 created (Signal Quality Audit)*
