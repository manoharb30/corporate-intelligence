# LookInsight

**Insider conviction signals for institutional alpha seekers.**

LookInsight surfaces high-conviction insider buying signals from SEC Form 4 filings. We classify genuine open-market purchases (filtering out RSU vesting, DRIP, private placements, and structured deals), detect multi-insider clusters, apply an evidence-based earnings-proximity filter, and deliver pre-filtered signals with measured alpha vs SPY.

🔗 **Production:** https://ci.lookinsight.ai

## Performance (v1.0)

| Metric | Value | Significance |
|--------|-------|--------------|
| Mature strong_buy signals | **141** | — |
| Hit Rate (90d return > 0) | **67.4%** | p < 0.001 |
| Avg Alpha vs SPY (90d) | **+9.0%** | p < 0.001 |
| Avg Return (90d) | +14.2% | — |
| Data integrity | 0.000% discrepancy | Verified 20% sample |
| Data coverage | 22 months | Jun 2024 – Apr 2026 |

## What a Signal Looks Like

A **strong_buy** is emitted when, on a given date for a given company:

- 2+ distinct insiders made GENUINE open-market P purchases
- $100K+ total cluster value
- $300M–$5B historical market cap (midcap)
- Within 60 days of next earnings (`earn≤60d`)
- Returns tracked from filing date (actionable), not transaction date

Each signal is tagged with an informational rider:
- **High Conviction** (≤5 insiders, <$1M, buy/mcap ≥0.01%) — 71.3% HR, +11.8% alpha
- **Standard** (does not match High Conviction)
- **⚠ Hostile Activist** — overlay when the company has a 13D with hostile keywords

## Tech Stack

| Layer | Technology |
|-------|------------|
| Backend | FastAPI (Python 3.13) |
| Database | Neo4j Aura (graph) |
| Frontend | React 18 + TypeScript + Vite + Tailwind |
| LLM | Claude Haiku 4.5 (P-transaction classification, batch) |
| Prices | yfinance (market cap + 2y daily closes) |
| Data Sources | SEC EDGAR (Form 4, Schedule 13D) |
| Hosting | Vercel (frontend) + Railway (backend) |
| DNS | GoDaddy |

## Project Structure

```
corporate-intelligence-graph/
├── backend/
│   ├── app/
│   │   ├── main.py                     # FastAPI app entry (7 routes)
│   │   ├── config.py                   # Settings (env-driven)
│   │   ├── api/routes/                 # activist, event_detail, explorer, health, scanner, signal_performance, snapshot
│   │   ├── services/                   # signal_filter, signal_performance_service, insider_cluster_service, snapshot_service, trade_classifier, ...
│   │   ├── models/                     # Pydantic models
│   │   └── db/neo4j_client.py          # Neo4j connection (with reconnect)
│   ├── ingestion/sec_edgar/            # EDGAR fetchers + parsers (Form 4, 13D)
│   ├── scanner/                        # form4_scanner, activist_scanner (8k_scanner deprecated)
│   ├── run_month.py, run_multiple_months.py, run_week.py    # pipeline entry points
│   ├── prefilter_p.py, classify_p_with_prefilter.py,
│   │   batch_llm_classify.py, merge_classifications.py       # split-architecture pipeline
│   ├── backfill_*.py                   # operational backfills
│   ├── tests/                          # test_signal_filter (19), test_signal_performance (34), ...
│   ├── requirements.txt
│   └── .env.example
├── frontend/
│   ├── src/
│   │   ├── pages/                      # SignalList, SignalDetail, PerformanceTracker
│   │   ├── components/                 # Layout + shared UI
│   │   ├── services/api.ts             # typed API client
│   │   ├── App.tsx, main.tsx
│   │   └── index.css
│   ├── package.json
│   └── tailwind.config.js
├── neo4j/
│   ├── constraints.cypher              # database constraints
│   ├── indexes.cypher                  # database indexes
│   └── schema-report.md                # current schema reference
├── .paul/                              # PAUL framework: milestones, plans, state
└── README.md
```

## Prerequisites

- Python 3.11+ (3.13 recommended)
- Node.js 18+
- Neo4j 5.x (Aura recommended) or local install
- Anthropic API key (required for P-transaction classification)
- yfinance works over public endpoints (no key)

## Setup

### 1. Neo4j

**Option A — Neo4j Aura (recommended):** create a free account, create an instance, note the bolt URI + credentials.

**Option B — Local:** download from https://neo4j.com/download/, start it, set a password.

Apply schema:

```bash
cat neo4j/constraints.cypher | cypher-shell -u neo4j -p <password>
cat neo4j/indexes.cypher | cypher-shell -u neo4j -p <password>
```

### 2. Backend

```bash
cd backend
python -m venv venv
source venv/bin/activate              # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
# Edit .env with your credentials
```

**Environment variables** (`backend/.env`):

```env
# Neo4j
NEO4J_URI=neo4j+s://<your-aura-host>:7687    # or bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=your_password

# LLM classification (required)
ANTHROPIC_API_KEY=sk-ant-...

# SEC EDGAR (required by SEC)
SEC_EDGAR_USER_AGENT=YourName your-email@example.com

# CORS
CORS_ORIGINS=["http://localhost:3000", "http://localhost:5173"]
```

Run the backend:

```bash
uvicorn app.main:app --reload --port 8000
# API: http://localhost:8000   |   Docs: http://localhost:8000/docs
```

### 3. Frontend

```bash
cd frontend
npm install
npm run dev
# UI: http://localhost:3000 (or 5173)
```

## Pipeline Usage

The insider-signal pipeline is split into stages for cost and throughput:

```bash
cd backend && source venv/bin/activate

# Run a single month through the full pipeline
python run_month.py 2026-03

# Backfill a quarter / multi-month range
python run_multiple_months.py 2025-10 2025-12

# Individual stages
python prefilter_p.py <input.json> <output.json>
python classify_p_with_prefilter.py <input.json> <output.json>
python batch_llm_classify.py <input.json> <output.json>
python merge_classifications.py <dir> <output.json>

# Operational backfills
python backfill_signal_coverage.py
python backfill_market_cap.py
python backfill_company_prices.py
```

Daily incremental ingest is on the v1.1 roadmap (Operations milestone — cron/scheduler, not yet wired).

## API Endpoints

All routes are under `/api/*`. The surface is deliberately small — 7 routes total.

### Health
- `GET /api/health` — service + DB health

### Signals
- `GET /api/snapshot` — Signal List (strong_buy clusters with returns)
- `POST /api/snapshot/precompute` — rebuild precomputed blobs
- `GET /api/signal-performance/dashboard-stats` — precomputed dashboard stats
- `GET /api/signal-performance/...` — performance tracker data (all signals, winners + losers)
- `GET /api/event-detail/{accession_number}` — Signal Detail (buyers, Form 4 URLs, decision card, hostile flag)

### Exploration + Scanning
- `GET /api/explorer/...` — cross-company connections + graph exploration
- `GET /api/activist/...` — Schedule 13D data
- `POST /api/scanner/form4/scan` — trigger Form 4 scan
- `POST /api/scanner/activist/scan` — trigger 13D scan

See `/docs` (Swagger UI) for live endpoint details.

## Neo4j Schema

### Node Types

| Node | Key Properties |
|------|----------------|
| Company | cik, ticker, name, market_cap, price_series (stored), has_hostile_activist |
| Person | id, normalized_name, is_officer, is_director |
| InsiderTransaction | accession, filing_date, transaction_date, shares, price, value, classification (GENUINE / FILTERED / AMBIGUOUS), rule_triggered |
| ActivistFiling | cik, filing_date, purpose_text, stake_percent, has_hostile_keywords |
| SignalPerformance | cluster_id, signal_date, day0_price, spy_return, return_90d, alpha_90d |
| Event | (8-K events — legacy, not used in v1.0 signals) |

### Relationship Types

| Relationship | From → To | Purpose |
|--------------|-----------|---------|
| INSIDER_TRADE_OF | (Company)→(InsiderTransaction) | Transaction ownership |
| TRADED_BY | (Person)→(InsiderTransaction) | Actor on transaction |
| FILED_EVENT | (Company)→(Event) | 8-K events (legacy) |
| FILED_ACTIVIST | (Company)→(ActivistFiling) | 13D filings |

The SPY ETF is stored as a Company node with 755 days of price_series so return/alpha computations run without live yfinance calls.

## Development

### Tests

```bash
cd backend && venv/bin/python -m pytest tests/ -v
```

Key suites: `test_signal_filter.py` (19 tests), `test_signal_performance.py` (34 tests).

### Architecture Governance

This project uses **sentrux** for structural quality scoring:

```bash
sentrux gate --save .      # snapshot baseline
# ... make changes ...
sentrux gate .             # compare vs baseline
sentrux check .            # all rules must pass
```

Rules:
- Architecture grade ≥ B
- Zero dependency cycles
- No files > 500 lines
- Layer order enforced (ingestion → domain → api → delivery)

### Formatting & Typing

```bash
cd backend
black .
ruff check .
mypy app
```

## Roadmap

**v1.0 Signal Quality — ✅ Complete (2026-04-18)**
Clean insider cluster pipeline, earnings filter, verified data, production dashboard.

**v1.1 — 📋 Pending scope** (marketing + operations)
Daily auto-ingest, alert system, monitoring, S3 signal delivery, Neudata article, first paid institutional client, extended backfill.

See `.paul/ROADMAP.md` for detail and `.paul/MILESTONES.md` for history.

## License

Proprietary — © LookInsight. Contact the author for licensing terms.
