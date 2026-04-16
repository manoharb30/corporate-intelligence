# LookInsight — Insider Conviction Signal Platform

## What This Is

An alternative data product that surfaces high-conviction insider buying signals from SEC Form 4 filings for institutional hedge fund clients. The platform classifies "genuine" open-market purchases (filtering out 90% noise — RSU vesting, DRIP, private placements, structured deals), detects multi-insider clusters, scores signal quality, and delivers pre-filtered signals with proven alpha vs SPY.

## Core Value

Hedge funds get pre-filtered insider conviction signals with 67% hit rate and +5.5% alpha vs SPY at 90 days, eliminating months of data engineering on raw SEC filings.

## Current State

| Attribute | Value |
|-----------|-------|
| Type | Application (Data Product) |
| Version | Signal pipeline v2 (split architecture) |
| Status | Production (ci.lookinsight.ai) + Active research |
| Last Updated | 2026-04-16 |

**Production URLs:**
- https://ci.lookinsight.ai: Web dashboard (Vercel + Railway)
- Neo4j Aura: Graph database (shared local + prod)

## Requirements

### Core Features

- Genuine P transaction classifier (LLM + 19 prefilter rules)
- Multi-insider cluster detection (2+ buyers, $100K+, midcap)
- Structured deal detector (5+ same-price exclusions)
- Forward return analysis (90d vs SPY alpha)
- Signal risk scorer (pre-trade failure filter) — IN PROGRESS

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

### Active (In Progress)

- [ ] Signal risk scorer — multi-factor pre-trade filter targeting 70%+ hit rate
- [ ] Product repositioning for institutional hedge fund clients

### Planned (Next)

- [ ] Daily auto-ingest automation (cron)
- [ ] Data delivery API (CSV/JSON/Parquet) for hedge fund clients
- [ ] Alpha vs SPY in signal output
- [ ] Neudata article / research brief

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
- Founder: Manohar (solo, based in India, markets are US)

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

- Solo founder — no dev team
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
| Score-based risk filter (not hard rules or ML) | Tunable, explainable, transparent for institutional clients | 2026-04-16 | Active |

## Success Metrics

| Metric | Target | Current | Status |
|--------|--------|---------|--------|
| Strong_buy hit rate (90d) | 70%+ | 67.1% | At risk |
| Alpha vs SPY (90d) | +7%+ | +5.5% | At risk |
| Monthly signal count | 15-30 | ~20 avg | On track |
| Data coverage | 18+ months | 17 months | On track |
| Neudata article | Published | Call scheduled | In progress |
| First paid institutional client | Signed | In discussions | In progress |

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
*Last updated: 2026-04-16*
