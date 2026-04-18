# ROADMAP.md — Phase Breakdown

## Phase 1: Data Pipeline ✅ COMPLETE
**Goal:** Clean, classified insider signal data across 17+ months
- Form 4 P transaction pipeline (fetch → classify → ingest)
- Split architecture (prefilter → batch LLM → merge)
- Structured deal detector
- Market cap + price coverage backfill
- Monthly/quarterly batch processing

## Phase 2: Signal Quality ✅ COMPLETE
**Goal:** Evidence-based signal filtering + failure attribution
**Result:** 164 signals, 65.9% HR (+4.4pp), +8.0% alpha (+2.7pp), data verified for institutional delivery

### Plans executed (6 loops)
- [x] **02-01 Signal Quality Filter** — Earnings proximity rule (earn<=60d, p=0.003). Single strong rule beats 3 weak stacked rules. TDD: 12 tests. Integrated into merge pipeline with CIK→ticker Neo4j mapping (4,012 pairs).
- [x] **02-02 Data Integrity Verification** — 20% random sample (18/92) against live yfinance. 0.000% max discrepancy. Data trustworthy for hedge fund presentation.
- [x] **02-03 Retroactive Filter Application** — Applied earnings filter to 263 days of historical data. 3,433 transactions → FILTERED. Neo4j now reflects clean signal universe.
- [x] **02-04 Activist Temporal Hypothesis** — Tested 3 groups (no activist / before / after insiders). Activist-AFTER = 80% HR, activist-BEFORE = +27.2% alpha. Not actionable as filter (n=16/10).
- [x] **02-05 Failure Attribution** — Hostile purpose text predicts failure: 88% of losers-with-activist vs 33% winners (2.6× ratio). Aligned with Brav 2008, Klein & Zur 2009, Greenwood & Schor 2009.
- [x] **02-06 Hostile Activist Flag** — Informational `has_hostile_activist` tag on signals (not a filter). Stored in classified.json + Neo4j. TDD: 7 new tests (19 total).

### Research findings
- Parallel agent research: momentum, earnings, sector, volatility, insider behavior, cluster composition
- Earnings cycle = dominant predictor (mid-quarter insiders see internal data before market)
- Sector identity matters (Basic Materials 50%, Comms 33%) but sample too small for hard rule
- Prior selling, buyer count, volatility — not significant predictors
- 11-factor risk scorer designed then abandoned in favor of single clean rule (data-driven decision)

### Key metrics
| Metric | Before (Phase 1) | After (Phase 2) | Change |
|---|---|---|---|
| Signals | 309 | **164** | -145 |
| Hit rate (90d) | 61.5% | **65.9%** | +4.4pp |
| Alpha vs SPY | +5.25% | **+8.0%** | +2.75pp |
| Alpha hit rate | 50.2% | **56.1%** | +5.9pp |
| Mean return | +9.8% | **+12.4%** | +2.6pp |

## Phase 3: Institutional Positioning 🔄 IN PROGRESS
**Goal:** Dashboard as proof + accountability tool for hedge fund demo calls
**Numbers:** 141 strong_buy, 67.4% HR, +9.0% alpha (p<0.001), $300M-$5B midcap

### Completed
- [x] **03-01** Frontend cleanup — deleted 14 pages, 14 components, stripped to clean shell
- [x] **03-02** Backend cleanup — deleted 17 routes, 15 services (14K lines removed)
- [x] **Visual design** — brainstorming with mockups (Minimal/Modern style)
- [x] **03-03** Signal pattern research — buy/mcap, insider count, value buckets
- [x] **03-04** Backfill Jun-Nov 2024 — full pipeline, 6 months, earnings filter applied
- [x] **03-05** Data verification — coverage 94.5%, Oct-Nov 2025 patched, all months verified
- [x] **03-06** Signal performance service rewrite (TDD, 34 tests, stored data, historical mcap)
- [x] **03-07** Frontend pages built — Signal List (hero+cards), Signal Detail (buyers+SEC), Performance Tracker
- [x] **03-08** Dead code cleanup — 6 more services deleted, event_detail stripped, api.ts cleaned
- [x] Filing date fix — returns from actionable date, not transaction date
- [x] Midcap cap $5B (was $10B, p=0.018)
- [x] Precomputed dashboard stats blob
- [x] Signal riders — High Conviction / Standard with pattern profile

### Remaining
- [ ] Hostile activist flag in Signal Detail (API needs to return it)
- [ ] Precompute snapshot data (avoid live cluster detection on dashboard load)
- [ ] S3 bucket signal delivery
- [ ] Sample data CSV with alpha metrics

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
