# LookInsight — Insider Conviction Signal Platform

## What This Is

An alternative data product that surfaces high-conviction insider buying signals from SEC Form 4 filings for institutional hedge fund clients. The platform classifies "genuine" open-market purchases (filtering out 90% noise — RSU vesting, DRIP, private placements, structured deals), detects multi-insider clusters, scores signal quality, and delivers pre-filtered signals with proven alpha vs SPY.

## Core Value

Hedge funds get pre-filtered insider conviction signals with 67.4% hit rate and +9.0% alpha vs SPY at 90 days, eliminating months of data engineering on raw SEC filings.

## Current State

| Attribute | Value |
|-----------|-------|
| Type | Application (Data Product) |
| Version | 1.3.0 |
| Status | Production (ci.lookinsight.ai) — v1.3 complete; awaiting v1.4 definition |
| Last Updated | 2026-04-20 |

**Production URLs:**
- https://ci.lookinsight.ai: Web dashboard (Vercel + Railway)
- Neo4j Aura: Graph database (shared local + prod)

## Requirements

### Core Features

- Genuine P transaction classifier (LLM + 19 prefilter rules)
- Multi-insider cluster detection (2+ buyers, $100K+, midcap)
- Structured deal detector (5+ same-price exclusions)
- Forward return analysis (90d vs SPY alpha)
### Validated (Shipped)

- [x] Form 4 pipeline (fetch → filter → parse → classify → ingest) — split architecture
- [x] Batch LLM classification (10 parallel workers)
- [x] Structured deal detector (5+ buyers same price → AMBIGUOUS)
- [x] AMBIGUOUS records persisted in Neo4j
- [x] Market cap + price coverage backfill (backfill_signal_coverage.py)
- [x] 17 months backfilled (Dec 2024 – Apr 2026)
- [x] Monthly/quarterly/multi-month batch processing (run_month.py, run_multiple_months.py)
- [x] ISO filing_date normalization
- [x] primary_document capture for Form 4 direct URLs
- [x] Hit rate analysis across full FY 2025 (309 matured signals)
- [x] Earnings proximity filter (earn<=60d, p=0.003) — single evidence-based rule
- [x] Retroactive filter applied to 17 months (3,433 txns → FILTERED)
- [x] Data integrity verified (20% sample, 0.000% discrepancy vs live yfinance)
- [x] Hostile activist flag (informational tag, not filter) — 88% loser predictor
- [x] Activist temporal hypothesis tested (before/after/none — directional, not actionable)
- [x] Failure attribution research (momentum, earnings, sector, volatility, cluster composition)
- [x] Product repositioning for institutional hedge fund clients — v1.0 Signal Quality
- [x] Frontend clean shell (3 pages) + backend strip (24→7 routes) — v1.0 Signal Quality
- [x] Signal Performance Service rewrite (TDD, 34 tests, stored data) — v1.0 Signal Quality
- [x] Precomputed dashboard + snapshot blobs — v1.0 Signal Quality
- [x] 22 months backfilled (Jun 2024 – Apr 2026) — v1.0 Signal Quality
- [x] 141-signal CSV + Parquet export with 32-column provenance schema — v1.1 Phase 4
- [x] DATA_DICTIONARY.md with cohort definition, derived formulas, caveats, reproducibility — v1.1 Phase 4
- [x] verify_export.py — Neo4j-live audit tool (row count + null audit + 5-signal spot-check) — v1.1 Phase 4
- [x] backend/exports/ as layer-3 delivery module — v1.1 Phase 4

### Validated (v1.1, shipped 2026-04-20)

- [x] Methodology-first research brief (533 lines, 8 sections, academic foundation)
- [x] Research brief charts (funnel, return distribution, alpha waterfall)
- [x] May 2024 extended-coverage backfill (first of several planned extensions)
- [x] TZ-suffix fix in signal_filter.py (May 2024 surfaced it)
- [x] Schema discipline — CLAUDE.md rule + neo4j/schema-report.md SignalPerformance section

### Validated (v1.2, shipped 2026-04-20)

- [x] Matured-signal immutability invariant — `compute_all()` never touches SignalPerformance nodes where `is_mature = true` (Phase 7)

### Validated (v1.3, shipped 2026-04-20)

- [x] Pipeline scope narrowed to strong_buy buy only — legacy sell direction + non-strong_buy tiers (buy, watch) removed from compute_all, snapshot_service, and API route. 372 legacy rows deleted; 142 mature strong_buy preserved byte-identically (Phase 8)

### In progress (v1.4, Phase 9 shipped 2026-04-20)

- [x] Ground-truth market cap via SEC EDGAR XBRL — `mcap_at_signal_true` backfilled on 141/142 mature strong_buy signals (99.3%). XBRL client + backfill script + 11 unit tests. Top ratio-estimate errors revealed: ANDG/RPAY/ONDS/SEI each off by 60–93%. (Phase 9)

### Active (In Progress)

_No milestone currently defined. Run `/paul:discuss-milestone` to scope next._

### Deferred (Backlog)

- [ ] Daily auto-ingest automation (cron/scheduler)
- [ ] Signal alert system (new strong_buy → notify)
- [ ] Price/market cap freshness automation
- [ ] Monitoring/health checks
- [ ] S3 bucket signal delivery (hedge-fund delivery channel)
- [ ] First paid institutional client
- [ ] Neudata marketplace listing
- [ ] Extended coverage backfill (Jan–Apr 2024 next; 2023 after)
- [ ] Industry enrichment beyond SEC SIC metadata (24% SIC-null rate observed in Phase 4)
- [ ] Window size experiment (30d vs 40d) — non-destructive analysis
- [ ] Per-fund delivery / outreach (was v1.1 Phase 6, dropped from scope; revisit when cadence defined)

### Out of Scope

- 8-K / M&A signal framework — DEPRECATED, not used
- Congressional trades — dead APIs, 45-day lag
- Retail SaaS pricing — repositioned to institutional

## Target Users

**Primary:** Quantitative hedge funds (Citadel, Squarepoint, Bridgewater)
- Systematic strategies seeking alpha signals
- Want: historical backtest data, daily feed, factor transparency
- Evaluate on: alpha, information ratio, signal decay, breadth

**Secondary:** Data scouts / marketplaces (Neudata, Eagle Alpha)
- Curate alternative data for their hedge fund clients
- Want: research methodology, provenance, unique angle
- Evaluate on: novelty, coverage, academic backing

## Context

**Business Context:**
- Calls completed with Citadel, Squarepoint, Final
- Proposal pending for Bridgewater
- Neudata scout call scheduled (research article opportunity)
- Founder: Manohar (based in India, markets are US)

**Technical Context:**
- Backend: FastAPI + Neo4j Aura (Python 3.13)
- Frontend: React + TypeScript + Vite + Tailwind
- Data: SEC EDGAR (Form 4, Schedule 13D), yfinance (prices, market cap)
- LLM: Anthropic Claude Haiku 4.5 for P transaction classification
- Deployment: Vercel (FE) + Railway (BE), GoDaddy DNS

## Constraints

### Technical Constraints

- SEC EDGAR rate limit: 10 req/sec (8 workers with 1s pacing)
- Anthropic API quota: upgraded, ~$2-3/month for classification
- yfinance: free tier, 1.5s pacing per ticker
- Neo4j Aura: shared instance for local + prod

### Business Constraints

- Limited engineering capacity (no dev team)
- Institutional sales cycle: 3-6 months typical
- Need research credibility for Neudata article
- Time zone: India (user) vs US (markets, clients)

### Compliance Constraints

- SEC data is public — no compliance issues on source
- Signal delivery to clients must include data provenance documentation

## Key Decisions

| Decision | Rationale | Date | Status |
|----------|-----------|------|--------|
| P transactions only (no S/A/M) | Conviction buying is cleaner signal than selling | 2026-04-15 | Active |
| 8-K signals deprecated | Insider clusters proved more predictive than 8-K combos | 2026-04-15 | Active |
| Concentration >70% as primary filter | 67% hit rate, +10.7% return, counterintuitive but validated | 2026-04-15 | Active |
| AMBIGUOUS written to DB | Preserves data for review without polluting GENUINE signals | 2026-04-15 | Active |
| Structured deals flagged at 5+ buyers same price | Catches IPO allocations, private placements | 2026-04-15 | Active |
| Strong_buy = midcap + $100K + 2+ buyers | Academic-backed + our data validates | 2026-04-15 | Active |
| Single earnings rule over multi-factor scorer | p=0.003 significance; stacking 3 weak rules lost signals for <1pp gain | 2026-04-16 | Active |
| Hostile activist = informational flag, not filter | Small sample (8 losers), 88% predictor ratio — directional, not conclusive | 2026-04-16 | Active |
| Midcap cap $5B (was $10B) | $5B-$10B: 38.1% HR vs <$5B: 67.4% (p=0.018) | 2026-04-17 | Active |
| Returns from filing date (not transaction date) | 1-3 day gap avoids look-ahead bias | 2026-04-17 | Active |
| Historical market cap via price ratio | current_mcap × (signal_price / current_price); 5/5 spot checks | 2026-04-17 | Active |
| Confidence tiers informational, not filters | p=0.11 for High vs Standard — directional, not proven | 2026-04-17 | Active |
| v1.0 Signal Quality closed with 3 phases | Pivoting to marketing + operations; Phases 4-5 deferred to new milestone | 2026-04-18 | Active |
| v1.1 milestone = Hedge Fund Research Delivery (3 phases) | Methodology story is the product; one master PDF; fresh write excluding deprecated frameworks | 2026-04-19 | Active |
| 32-column signal schema locked for v1.1 data appendix | Reproducible delivery format with type-enforced Parquet + self-referencing CSV | 2026-04-19 | Active |
| hostile_flag exported as informational column (3/141 true) | v1.0 classification preserved; data freely available; buyer can weight the flag independently | 2026-04-19 | Active |
| backend/exports/ as layer-3 delivery module | Keeps export scripts out of backend/ root; imports only from domain+data, never api | 2026-04-19 | Active |
| Reuse InsiderClusterService.get_cluster_detail for buyer provenance | Avoids reimplementing cluster-window logic; 100% semantically aligned with v1.0 cluster definition | 2026-04-19 | Active |
| Matured SignalPerformance nodes are immutable | A matured signal is a frozen historical record; recompute should never drift classifications. `compute_all` now preserves `is_mature=true` nodes byte-identically — only immature/new signals are refreshed. | 2026-04-20 | Active |
| Drop `market_cap_at_signal` field in favor of matured-preservation | A snapshot field was planned but made redundant once we stopped touching matured rows entirely. Simpler and respects the same invariant. | 2026-04-20 | Active |
| Pipeline scope narrowed to strong_buy buy only | Sell direction and non-strong_buy tiers (buy, watch) were legacy from pre-v1.0 architecture; never surfaced by product. Removing them cuts compute cycles, storage, and confusion (e.g., 408 vs 142 mismatch that caused user friction). | 2026-04-20 | Active |
| Keep `direction` + `conviction_tier` columns on SignalPerformance | Even though both fields will always be `'buy'` / `'strong_buy'` now, keeping them future-proofs the schema if tiers/directions are reintroduced later. | 2026-04-20 | Active |
| Keep InsiderClusterService parameterized for sell | Utility stays flexible (unit tests exercise it); only live callers changed. Lower blast radius than ripping out the lower layer. | 2026-04-20 | Active |
| Ground-truth mcap sourced from SEC XBRL primary data | Price-ratio estimate (`current_mcap × signal_price/current_price`) breaks on reverse splits, dilution, buybacks. SEC EDGAR XBRL company-facts is free, official, dated quarterly — the only trustworthy source. | 2026-04-20 | Active |
| XBRL client tries 5 concepts as fallback chain | Different filers tag shares outstanding differently. Dual-class issuers (MRVI), post-IPO entities (FNKO), closed-end funds all need different concepts or fail. `WeightedAverageNumberOfSharesOutstandingBasic` is within <2% of point-in-time for stable issuers. | 2026-04-20 | Active |
| Post-signal XBRL fallback (within 90d) for late-XBRL issuers | 2 signals (ANDG, CRGY) had no pre-signal XBRL because the first 10-Q/10-K XBRL filing postdates signal_date. Using nearest-quarter-after is <5% different for stable issuers and preferred over null. Labeled distinctly as `xbrl_post_signal_approx` in provenance. | 2026-04-20 | Active |

## Success Metrics

| Metric | Target | Current | Status |
|--------|--------|---------|--------|
| Strong_buy hit rate (90d) | 70%+ | **67.4%** | Improved (+5.9pp from 61.5%), close to target |
| Alpha vs SPY (90d) | +7%+ | **+9.0%** | **Met** ✓ (p<0.001) |
| Signal count | 100+ matured | **141** | **Met** ✓ |
| Data coverage | 18+ months | **22 months** | **Met** ✓ (Jun 2024 – Apr 2026) |
| Data integrity | Verified | **0.000% discrepancy** | **Met** ✓ |
| Neudata article | Published | Call scheduled | Carried to next milestone |
| First paid institutional client | Signed | In discussions | Carried to next milestone |

## Tech Stack

| Layer | Technology | Notes |
|-------|------------|-------|
| Backend | FastAPI (Python 3.13) | Port 8000 |
| Database | Neo4j Aura | Graph model: Company → InsiderTransaction ← Person |
| Frontend | React + TypeScript + Vite | Port 3000/5173 |
| LLM | Claude Haiku 4.5 | P transaction classification |
| Prices | yfinance | Market cap + 2y daily closes |
| Data Source | SEC EDGAR | Form 4 + Schedule 13D |
| Hosting FE | Vercel | ci.lookinsight.ai |
| Hosting BE | Railway | corporate-intelligence-production |
| DNS | GoDaddy | CNAME to Vercel |

## Links

| Resource | URL |
|----------|-----|
| Production | https://ci.lookinsight.ai |
| Repository | (local) |

---
*PROJECT.md — Updated when requirements or context change*
*Last updated: 2026-04-20 after v1.4 Phase 9 (ground-truth mcap)*
