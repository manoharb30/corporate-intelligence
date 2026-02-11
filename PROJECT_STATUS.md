# Corporate Intelligence Graph - Project Status

**Last Updated:** January 24, 2026

## What Was Built

### Backend (FastAPI + Neo4j) - Working

1. **Company Search API** (`/api/companies/search`)
   - Searches both Neo4j graph AND SEC EDGAR
   - Returns `in_graph: true/false` to indicate if company needs ingestion
   - Prioritizes SEC-registered companies (with CIK) first

2. **Company Intelligence API** (`/api/companies/{id}/intelligence`)
   - Returns officers, directors, subsidiaries, beneficial owners
   - Detects **red flags** (conflicts of interest, sanctions, PEPs)
   - Tracks `other_companies_count` for each person (cross-company connections)
   - Found real finding: **Cathy McCarthy** - Director at both Nikola and Romeo Power

3. **SEC EDGAR Integration**
   - Company search via SEC's company_tickers.json
   - Filing ingestion (DEF 14A, 10-K, 13D/G)
   - LLM extraction for officers/directors/subsidiaries

### Frontend (React + Vite + Tailwind) - Partially Working

1. Search page with graph visualization (react-force-graph-2d)
2. Node colors: Blue=company, Purple=officers, Green=directors, Orange=subsidiaries, Red=connected to other companies
3. **Issue**: Node click handler not triggering properly

---

## How to Run

```bash
# Backend (port 8000)
cd /Users/shreshta/Documents/corporate_intelligence/corporate-intelligence-graph/backend
source venv/bin/activate
uvicorn app.main:app --reload --port 8000

# Frontend (port 3000)
cd /Users/shreshta/Documents/corporate_intelligence/corporate-intelligence-graph/frontend
npm run dev
```

**Open:** http://localhost:3000/

---

## Test the APIs Directly

```bash
# Search for a company
curl "http://localhost:8000/api/companies/search?q=Nikola"

# Get company intelligence (Nikola Corp)
curl "http://localhost:8000/api/companies/58b510b6-aaf6-4e8e-a8c7-ae5cf2fef594/intelligence"

# Search company not in database (shows SEC EDGAR result)
curl "http://localhost:8000/api/companies/search?q=Palantir"
```

---

## What Needs Fixing

1. **Graph node clicks** - The `onNodeClick` handler in `frontend/src/pages/Intelligence.tsx` isn't firing. Likely a react-force-graph-2d event issue.

2. **Person expansion** - When clicking a person with `other_companies_count > 0`, should fetch and display their other companies. Backend endpoint needed.

3. **Company ingestion** - When user clicks a company with `in_graph: false`, should trigger SEC EDGAR ingestion.

---

## Key Files

| File | Purpose |
|------|---------|
| `backend/app/services/company_service.py` | Search + Intelligence logic |
| `backend/app/api/routes/companies.py` | API endpoints |
| `backend/app/models/responses.py` | Response models (CompanyIntelligence, RedFlag, etc.) |
| `backend/ingestion/sec_edgar/` | SEC filing parsers |
| `frontend/src/pages/Intelligence.tsx` | Main UI with graph |
| `frontend/src/services/api.ts` | API client types |

---

## Database (Neo4j Aura)

- **URI:** `neo4j+s://2aaa6269.databases.neo4j.io`
- **User:** neo4j
- **Password:** (see backend/.env)
- **Contents:** Nikola Corp, Romeo Power, Apple, + subsidiaries (~47 companies, ~100+ persons)

---

## Tests

```bash
cd /Users/shreshta/Documents/corporate_intelligence/corporate-intelligence-graph/backend
source venv/bin/activate
pytest tests/ -v
# 25 tests passing
```

---

## Product Vision

1. User types company name (single text input)
2. System searches graph + SEC EDGAR
3. User clicks result → sees network graph with officers, directors, subsidiaries
4. Red flags automatically detected (conflicts of interest, sanctions)
5. Click on person with connections → expand to see their other companies
6. Everything clickable, no more typing after initial search

---

## Key Finding from Investigation

**Cathy McCarthy** was found to be a Director at BOTH:
- Nikola Corp
- Romeo Power, Inc.

This is a conflict of interest during the Romeo Power acquisition by Nikola. The system detects this automatically as a red flag.
