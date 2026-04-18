# ROADMAP.md — Milestone & Phase Breakdown

## Version Overview

| Version | Milestone | Status | Date |
|---------|-----------|--------|------|
| v1.0 | Signal Quality | ✅ Complete | 2026-04-18 |
| v1.1 | _TBD (marketing + operations)_ | 📋 Pending scope | — |

## Current Milestone

**v1.0 Signal Quality** (1.0.0)
Status: ✅ Complete
Completed: 2026-04-18
See: .paul/MILESTONES.md · .paul/milestones/v1.0.0-ROADMAP.md

## Next Milestone

_To be scoped — focus will be marketing + operational work._
Run `/paul:discuss-milestone` to explore and articulate the vision,
or `/paul:milestone` to create one directly.

## Deferred Phases (carried from v1.0, available for next milestone)

### Phase 4: Operations 📋 DEFERRED
**Goal:** Daily automated signal generation
- [ ] Daily auto-ingest (cron/scheduler)
- [ ] Signal alert system (new strong_buy → notify)
- [ ] Price/market cap freshness automation
- [ ] Monitoring/health checks

### Phase 5: Scale 📋 DEFERRED
**Goal:** Revenue + growth
- [ ] First paid institutional client
- [ ] Neudata marketplace listing
- [ ] Historical data licensing
- [ ] Extended coverage (2023-2024 backfill)
- [ ] S3 bucket signal delivery
- [ ] Sample data CSV with alpha metrics

### Other Deferred Items
- [ ] Window size experiment (30d vs 40d) — needs non-destructive analysis approach

## Completed Milestones

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
*Last updated: 2026-04-18 after v1.0 Signal Quality*
