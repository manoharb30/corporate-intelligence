# Corporate Intelligence Graph - Project Context

## What This Project Does
A corporate intelligence tool that detects M&A signals from SEC 8-K filings by analyzing patterns in Material Agreements, executive changes, and governance changes.

## Key Insight (M&A Signal Detection)
- **HIGH Signal**: Item 1.01 (Material Agreement) + 5.02/5.03 (Exec/Governance changes) WITHOUT 2.01 = Deal in progress, actionable
- **MEDIUM Signal**: Item 1.01 alone = Potential deal, watch list
- **LOW Signal**: Item 2.01 + 5.01 = Deal already closed, too late to act
- **LOW Signal**: Single 5.02/5.03 = Routine executive/governance change

## Architecture
- **Backend**: FastAPI + Neo4j (port 8000)
- **Frontend**: React + TypeScript + Vite + Tailwind (port 5173)
- **Data Source**: SEC EDGAR 8-K filings

## Key Backend Files
- `/backend/app/services/feed_service.py` - Signal classification logic
- `/backend/app/services/company_profile_service.py` - Company profiles
- `/backend/app/api/routes/feed.py` - Feed API endpoints
- `/backend/app/api/routes/profile.py` - Profile API endpoints

## Key Frontend Files
- `/frontend/src/pages/Feed.tsx` - Signal feed (home page)
- `/frontend/src/pages/CompanyProfile.tsx` - Company detail view
- `/frontend/src/services/api.ts` - API client with types

## API Endpoints
- `GET /api/feed` - Signal feed with filtering
- `GET /api/profile/{cik}` - Company profile
- `GET /api/profile/search/companies?q=` - Search companies
- `POST /api/feed/scan/{cik}` - Scan company for signals

## Current State
- 259 events in database from ~50 companies
- Signal classification updated to prioritize predictive signals (1.01 combos) over completed deals (2.01)
- Frontend running at http://localhost:5173
- Backend running at http://localhost:8000

## Demo Story
1. Splunk example: 1.01+5.03 in Sep 2023 → Deal closed Mar 2024 (6 month warning)
2. Current watch list: Delta, Salesforce, PayPal with Material Agreements

## Architecture Governance (sentrux)

This project uses sentrux for structural quality scoring. Follow these rules in every session:

### Before making changes:
1. Run `sentrux gate --save .` to snapshot the current baseline

### During development:
- Use the sentrux MCP tools: call `scan()` after major changes to check structural health
- Never let architecture grade drop below B without explicit approval
- Zero dependency cycles allowed (max_cycles = 0)
- No god files — if any file exceeds 500 lines, refactor

### After completing changes:
1. Run `sentrux gate .` to compare against baseline
2. If grade degraded, identify the cause and fix before committing
3. Run `sentrux check .` — all rules must pass

### Layer architecture (do not violate):
- **data** (shared): Neo4j client, models — accessible from all layers
- **ingestion** (layer 0): SEC filing fetchers, parsers — must not depend on API or services
- **domain** (layer 1): Services, scanners — can access data + ingestion
- **api** (layer 2): FastAPI routes — can access domain + data
- **delivery** (layer 3): Frontend, CSV exports

Scanners must NOT depend on API layer. Ingestion must NOT depend on services or API.
