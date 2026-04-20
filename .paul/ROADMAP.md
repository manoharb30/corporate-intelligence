# ROADMAP.md — Milestone & Phase Breakdown

## Version Overview

| Version | Milestone | Status | Date |
|---------|-----------|--------|------|
| v1.0 | Signal Quality | ✅ Complete | 2026-04-18 |
| v1.1 | Hedge Fund Research Delivery | ✅ Complete | 2026-04-20 |
| v1.2 | Signal Integrity — matured immutability | ✅ Complete | 2026-04-20 |
| v1.3 | Pipeline Simplification — strong_buy only | ✅ Complete | 2026-04-20 |

## Current Milestone

**v1.3 Pipeline Simplification — strong_buy only** (1.3.0)
Status: ✅ Complete
Completed: 2026-04-20
Phases: 1 of 1 complete

**Outcome:** `SignalPerformance` now holds only `direction='buy' AND conviction_tier='strong_buy'` rows. Sell-side detection and non-strong_buy tiers (`buy`, `watch`) were removed from `compute_all`, `snapshot_service`, and the signal_performance API route. 372 legacy rows (266 mature + 106 immature) deleted in a one-time migration. 142 mature strong_buy rows preserved byte-identically (v1.2 invariant upheld). 41 tests pass (3 new).

### Phases

| Phase | Name | Plans | Status | Completed |
|-------|------|-------|--------|-----------|
| 8 | Strong_buy-only pipeline | 1/1 | ✅ Complete | 2026-04-20 |

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

Milestone log: `.paul/MILESTONES.md`

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
*Last updated: 2026-04-20 — v1.3 complete*
