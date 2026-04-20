# ROADMAP.md — Milestone & Phase Breakdown

## Version Overview

| Version | Milestone | Status | Date |
|---------|-----------|--------|------|
| v1.0 | Signal Quality | ✅ Complete | 2026-04-18 |
| v1.1 | Hedge Fund Research Delivery | ✅ Complete | 2026-04-20 |
| v1.2 | Signal Integrity — matured immutability | ✅ Complete | 2026-04-20 |

## Current Milestone

**v1.2 Signal Integrity — matured immutability** (1.2.0)
Status: ✅ Complete
Completed: 2026-04-20
Phases: 1 of 1 complete

**Outcome:** Matured `SignalPerformance` nodes are now byte-immutable across recompute. `compute_all` reads the set of matured signal_ids before any DELETE and skips them entirely. Implementation shifted from the originally-planned "snapshot column" to the simpler "don't touch matured rows" approach — same invariant, less code.

Verification: 408 matured rows preserved byte-identically across a live `compute_all(days=760)` run. 38 unit tests pass (34 existing + 4 new).

### Phases

| Phase | Name | Plans | Status | Completed |
|-------|------|-------|--------|-----------|
| 7 | mcap snapshot (matured immutability) | 1/1 | ✅ Complete | 2026-04-20 |

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
- [ ] **mcap snapshot at signal creation** — matured signals should be immutable on recompute (`compute_all` currently re-derives historical mcap from current state each run)
- [ ] Window size experiment (30d vs 40d) — needs non-destructive analysis approach
- [ ] Industry enrichment beyond SEC SIC (24% SIC-null rate in Phase 4 export)

## Completed Milestones

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
*Last updated: 2026-04-20 — v1.2 complete*
