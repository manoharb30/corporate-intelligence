# LookInsight — Project Context

## What This Is

**LookInsight** is an alternative-data product that surfaces high-conviction insider buying signals from SEC Form 4 filings for institutional hedge fund clients. The platform classifies genuine open-market purchases (filtering out RSU vesting, DRIP, private placements, structured deals), detects multi-insider clusters, applies an earnings-proximity filter, and delivers pre-filtered signals with measured alpha vs SPY.

**Production:** https://ci.lookinsight.ai
**Version:** 1.0.0 (v1.0 Signal Quality milestone shipped 2026-04-18)

## Core Signal Model

A **strong_buy** signal is emitted when all of the following hold on a given date for a given company:
- 2+ distinct insiders made GENUINE open-market P transactions
- $100K+ total cluster value
- $300M–$5B historical market cap (midcap)
- Within 60 days of next earnings (`earn<=60d`, p=0.003)
- Returns measured from **filing date** (actionable), not transaction date

Current numbers (verified, defensible): **141 mature signals, 67.4% HR, +9.0% alpha vs SPY (p<0.001)** across Jun 2024 – Apr 2026 (22 months).

Deprecated signal frameworks (DO NOT reintroduce):
- 8-K M&A material-agreement combinations (Items 1.01/5.02/5.03/2.01) — replaced by insider clusters
- S/A/M transaction types — only P transactions are used
- Congressional trades — dead APIs, 45-day lag

## Architecture

- **Backend:** FastAPI + Neo4j Aura (Python 3.13), port 8000
- **Frontend:** React + TypeScript + Vite + Tailwind, port 3000/5173
- **Data Sources:** SEC EDGAR (Form 4, Schedule 13D), yfinance (prices + market cap)
- **LLM:** Claude Haiku 4.5 for P-transaction classification (batch, 10 parallel workers)
- **Deploy:** Vercel (frontend) + Railway (backend) + GoDaddy DNS

### Layer architecture (sentrux-enforced)
- **data** (shared): Neo4j client, models — accessible from all layers
- **ingestion** (layer 0): SEC filing fetchers, parsers — must NOT depend on API or services
- **domain** (layer 1): Services, scanners — can access data + ingestion
- **api** (layer 2): FastAPI routes — can access domain + data
- **delivery** (layer 3): Frontend, CSV exports

Scanners must NOT depend on API layer. Ingestion must NOT depend on services or API.

## Key Backend Files

### Services (`backend/app/services/`)
- `signal_filter.py` — earnings proximity filter + hostile activist check
- `signal_performance_service.py` — returns, alpha, performance tracker (TDD, 34 tests)
- `insider_cluster_service.py` — cluster detection (2+ buyers, $100K+, midcap)
- `snapshot_service.py` — precomputed signal list blobs
- `trade_classifier.py` — trade-type utility (exercise-hold vs exercise-sell, etc.)
- `activist_filing_service.py` — Schedule 13D data
- `stock_price_service.py` — yfinance wrapper (used during ingest, not at query time)
- `feed_service.py`, `alert_service.py`, `explorer_service.py`, `insider_trading_service.py`, `officer_scan_service.py` — supporting

### Routes (`backend/app/api/routes/`)
- `health.py` → `/api/health`
- `snapshot.py` → `/api/snapshot` (Signal List)
- `event_detail.py` → `/api/event-detail` (Signal Detail)
- `signal_performance.py` → `/api/signal-performance` (Performance Tracker)
- `explorer.py` → `/api/explorer` (cross-company connections)
- `scanner.py` → `/api/scanner` (Form 4 + activist scanning)
- `activist.py` → `/api/activist`

### Scanners (`backend/scanner/`)
- `form4_scanner.py` — daily Form 4 discovery + cluster detection
- `activist_scanner.py` — Schedule 13D discovery
- `8k_scanner.py` — LEGACY, deprecated; not used in signal generation

### Pipeline scripts (`backend/`)
- `run_month.py`, `run_multiple_months.py`, `run_week.py` — batch pipeline entry points
- `prefilter_p.py`, `classify_p_with_prefilter.py`, `batch_llm_classify.py` — split-architecture steps
- `backfill_*.py` — operational backfills (market cap, prices, historical signals, etc.)

## Key Frontend Files

- `frontend/src/pages/SignalList.tsx` — strong_buy feed (home)
- `frontend/src/pages/SignalDetail.tsx` — buyers, Form 4 links, decision card
- `frontend/src/pages/PerformanceTracker.tsx` — full signal P&L (winners + losers)
- `frontend/src/services/api.ts` — typed API client (snapshotApi, eventDetailApi, signalPerfApi, healthApi)

## Before writing database queries (HARD RULE)

**Never guess Cypher property names.** Before writing any Cypher query that references specific properties, confirm the schema:

1. **Always-current sources of truth (read these first):**
   - `SignalPerformance` → `backend/app/services/signal_performance_service.py` — see `_store_batch()` for the exact CREATE clause listing every property.
   - `InsiderTransaction` / `Company` / `Person` → `backend/ingest_genuine_p_to_neo4j.py` `ingest_transaction()` — authoritative MERGE/SET clauses.
   - `ActivistFiling` → `backend/app/services/activist_filing_service.py`.
   - `Event` → `backend/app/services/event_store_service.py`.
2. **Cached reference:** `neo4j/schema-report.md` — generated snapshot, updated periodically. Use for quick lookup but validate against the write path if unsure.
3. **If a query fails with "property does not exist":** STOP. Re-read the write path. Do not iterate by trial-and-error — one schema mismatch often hides others.

**Common gotchas (record, don't rediscover):**
- `SignalPerformance` has `price_day90` but **no** `return_day90` — compute from `(price_day90 - price_day0)/price_day0`, or use `return_current` for mature signals.
- SPY alpha property is `spy_return_90d`, **not** `spy_return_day90`.
- `signal_level` = `'high' | 'medium'`. The strong_buy distinction lives in `conviction_tier` = `'strong_buy' | ...`.
- `transaction_date` may have a TZ suffix (`-05:00`). Truncate via `substring(dt, 0, 10)` in Cypher or `dt[:10]` in Python before parsing.

## PAUL Framework

This project uses PAUL (Plan → Apply → Unify loop). See `.paul/`:
- `STATE.md` — current loop position
- `PROJECT.md` — requirements and constraints
- `ROADMAP.md` — current + upcoming phases
- `MILESTONES.md` — completed milestone log
- `milestones/v1.0.0-ROADMAP.md` — archived v1.0 state

## Architecture Governance (sentrux)

This project uses sentrux for structural quality scoring. In every session:

### Before making changes:
- Run `sentrux gate --save .` to snapshot the current baseline

### During development:
- Use the sentrux MCP tools: call `scan()` after major changes to check structural health
- Never let architecture grade drop below B without explicit approval
- Zero dependency cycles allowed (max_cycles = 0)
- No god files — if any file exceeds 500 lines, refactor

### After completing changes:
- Run `sentrux gate .` to compare against baseline
- If grade degraded, identify the cause and fix before committing
- Run `sentrux check .` — all rules must pass

## Running the Stack

```bash
# Backend
cd backend && source venv/bin/activate
uvicorn app.main:app --reload --port 8000

# Frontend
cd frontend && npm run dev
```

## Testing

```bash
cd backend && venv/bin/python -m pytest tests/ -v
```

Core test suites: `test_signal_filter.py` (19), `test_signal_performance.py` (34).

## Context for Future Sessions

- Founder: Manohar (India); markets are US
- Institutional sales cycle active (Citadel/Squarepoint/Final done, Bridgewater proposal pending, Neudata call scheduled)
- Next milestone: marketing + operational (daily auto-ingest, alerts, S3 delivery, Neudata article, paid clients)
- Defer detailed product decisions to `.paul/PROJECT.md` — this file is the agent-facing summary
