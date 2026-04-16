# ROADMAP.md — Phase Breakdown

## Phase 1: Data Pipeline ✅ COMPLETE
**Goal:** Clean, classified insider signal data across 17+ months
- Form 4 P transaction pipeline (fetch → classify → ingest)
- Split architecture (prefilter → batch LLM → merge)
- Structured deal detector
- Market cap + price coverage backfill
- Monthly/quarterly batch processing

## Phase 2: Signal Quality 🔄 IN PROGRESS
**Goal:** Push hit rate from 67% to 70%+ with pre-trade risk filter
- [x] Hit rate analysis across FY 2025 (309 signals)
- [x] Alpha vs SPY computation (+5.5% baseline)
- [x] Filter stacking exploration (concentration, 10%-owner, sectors)
- [x] Risk scorer design spec (11 factors, score-based)
- [ ] Risk scorer implementation + backtest
- [ ] Threshold calibration (target: 70% hit, 100+ signals retained)
- [ ] Alpha verification on filtered subset

## Phase 3: Institutional Positioning 📋 PLANNED
**Goal:** Product ready for hedge fund evaluation
- [ ] Neudata research brief (1-pager)
- [ ] Sample data CSV with alpha metrics
- [ ] Data delivery API (CSV/JSON/Parquet)
- [ ] Bridgewater proposal
- [ ] Dashboard repositioned around insider signals (remove 8-K references)

## Phase 4: Operations 📋 PLANNED
**Goal:** Daily automated signal generation
- [ ] Daily auto-ingest (cron/scheduler)
- [ ] Signal alert system (new strong_buy → notify)
- [ ] Price/market cap freshness automation
- [ ] Monitoring/health checks

## Phase 5: Scale 📋 PLANNED
**Goal:** Revenue + growth
- [ ] First paid institutional client
- [ ] Neudata marketplace listing
- [ ] Historical data licensing
- [ ] Extended coverage (2023-2024 backfill)

---
*ROADMAP.md — Updated when phases complete or scope changes*
*Last updated: 2026-04-16*
