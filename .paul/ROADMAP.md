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
- [ ] **03-01** Frontend cleanup (remove 15+ deprecated pages, strip to clean shell)
- [ ] **Visual design discussion** (brainstorming skill — page layouts before building)
- [ ] **03-02** Signal List + Signal Detail (proof layer — buyers, EDGAR links) + backend date filter
- [ ] **03-03** Performance Tracker (accountability — daily P&L through 90d lifecycle)
- [ ] Sample data CSV with alpha metrics
- [ ] S3 bucket signal delivery
- [ ] Dashboard stripped of all deprecated 8-K/M&A references

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
