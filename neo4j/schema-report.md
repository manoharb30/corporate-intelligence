# Neo4j Schema Report

**Generated**: 2026-03-05
**Database**: Neo4j Aura (neo4j+s://2aaa6269.databases.neo4j.io)

---

## Node Types & Counts

| Node Label           | Count  |
|----------------------|--------|
| InsiderTransaction   | 89,341 |
| Person               | 15,192 |
| Company              | 8,953  |
| Event                | 2,112  |
| ActivistFiling       | 667    |
| Alert                | 389    |
| Filing               | 385    |
| Jurisdiction         | 172    |
| ScannerState         | 2      |
| **Total**            | **117,213** |

---

## Relationship Types & Counts

| Relationship     | Pattern                        | Count  | Has Properties? |
|------------------|--------------------------------|--------|-----------------|
| INSIDER_TRADE_OF | Company → InsiderTransaction   | 91,021 | No              |
| TRADED_BY        | Person → InsiderTransaction    | 89,640 | No              |
| FILED_EVENT      | Company → Event                | 2,140  | No              |
| MENTIONED_IN     | Person → Filing                | 1,635  | No              |
| OFFICER_OF       | Person → Company               | 845    | Yes             |
| TARGETS          | ActivistFiling → Company       | 667    | No              |
| DIRECTOR_OF      | Person → Company               | 606    | Yes             |
| ALERT_FOR        | Alert → Company                | 389    | No              |
| FILED            | Company → Filing               | 360    | No              |
| COUNTERPARTY_IN  | Company → Event                | 22     | Yes             |
| DEAL_WITH        | Company → Company              | 11     | Yes             |
| OWNS             | Company → Company              | 8      | Yes             |
| INCORPORATED_IN  | Company → Jurisdiction         | 4      | No              |
| **Total**        |                                | **187,348** |            |

---

## Node Properties

### Company (12 properties)

| Property               | Type     | Notes                              |
|------------------------|----------|------------------------------------|
| id                     | str      | UUID, unique constraint            |
| name                   | str      | Official company name              |
| normalized_name        | str      | Uppercased for matching            |
| cik                    | str      | SEC CIK number (10-digit), unique  |
| sic                    | str      | Standard Industrial Classification |
| sic_description        | str      | Human-readable SIC label           |
| tickers                | list     | Stock ticker symbols               |
| entity_type            | str      | e.g. "operating"                   |
| source                 | str      | e.g. "sec_edgar"                   |
| state_of_incorporation | str      | U.S. state code (e.g. "DE")        |
| created_at             | DateTime | Native Neo4j DateTime (105/8,953)  |
| updated_at             | DateTime | Native Neo4j DateTime              |

### Person (3 properties)

| Property        | Type | Notes                          |
|-----------------|------|--------------------------------|
| id              | str  | UUID, unique constraint        |
| name            | str  | Full name as filed             |
| normalized_name | str  | Lowercased for matching        |

### Event (9 properties)

| Property          | Type | Notes                                    |
|-------------------|------|------------------------------------------|
| accession_number  | str  | SEC accession number                     |
| company_name      | str  | Company name at time of filing           |
| filing_date       | str  | Date string (YYYY-MM-DD)                 |
| is_ma_signal      | bool | Whether event is an M&A signal           |
| item_name         | str  | SEC 8-K item description                 |
| item_number       | str  | SEC 8-K item number (e.g. "5.02")        |
| persons_mentioned | list | Extracted person names (currently empty)  |
| raw_text          | str  | Full text of the filing item             |
| signal_type       | str  | Classification (e.g. "executive_change") |

### InsiderTransaction (15 properties)

| Property                 | Type  | Notes                                   |
|--------------------------|-------|-----------------------------------------|
| id                       | str   | Composite key, unique constraint        |
| accession_number         | str   | SEC filing accession number             |
| filing_date              | str   | Date string (YYYY-MM-DD)                |
| transaction_date         | str   | Date string (YYYY-MM-DD)                |
| transaction_code         | str   | SEC code (P=Purchase, S=Sale, A=Award)  |
| transaction_type         | str   | Human-readable (e.g. "Award")           |
| insider_name             | str   | Name of insider                         |
| insider_title            | str   | Title/role at company                   |
| security_title           | str   | Description of security traded          |
| shares                   | float | Number of shares transacted             |
| price_per_share          | float | Price per share                         |
| total_value              | float | shares × price_per_share                |
| shares_after_transaction | float | Insider's holdings post-transaction     |
| is_derivative            | bool  | Whether security is derivative          |
| ownership_type           | str   | D=Direct, I=Indirect                    |

### ActivistFiling (16 properties)

| Property              | Type  | Notes                                    |
|-----------------------|-------|------------------------------------------|
| accession_number      | str   | SEC accession number, unique constraint  |
| filing_date           | str   | Date string (YYYY-MM-DD)                 |
| filing_type           | str   | e.g. "SCHEDULE 13D/A"                    |
| filing_url            | str   | SEC EDGAR URL                            |
| filer_cik             | str   | CIK of activist filer                    |
| filer_name            | str   | Name of activist filer                   |
| target_cik            | str   | CIK of target company                    |
| percentage            | float | Ownership percentage                     |
| shares_owned          | int   | Total shares beneficially owned          |
| purpose_text          | str   | Stated purpose of filing                 |
| signal_level          | str   | HIGH / MEDIUM / LOW                      |
| signal_summary        | str   | One-line summary of the filing           |
| is_amendment          | bool  | Whether this is an amendment (13D/A)     |
| amendment_number      | int   | Amendment sequence number                |
| reporting_person_type | str   | IN=Individual, other codes for entities  |
| citizenship           | str   | Filer's citizenship/jurisdiction         |

### Alert (11 properties)

| Property     | Type | Notes                                   |
|--------------|------|-----------------------------------------|
| id           | str  | UUID, unique constraint                 |
| alert_type   | str  | e.g. "insider_cluster"                  |
| severity     | str  | high / medium / low                     |
| company_cik  | str  | CIK of relevant company                 |
| ticker       | str  | Stock ticker                            |
| title        | str  | Alert headline                          |
| description  | str  | Alert detail text                       |
| signal_id    | str  | Links to signal (e.g. CLUSTER-cik-date) |
| dedup_key    | str  | Prevents duplicate alerts               |
| acknowledged | bool | Whether user has seen/dismissed it      |
| created_at   | str  | ISO timestamp string                    |

### Filing (7 properties)

| Property          | Type     | Notes                          |
|-------------------|----------|--------------------------------|
| id                | str      | UUID, unique constraint        |
| accession_number  | str      | SEC accession number, unique   |
| form_type         | str      | e.g. "DEF 14A"                 |
| filing_url        | str      | SEC EDGAR URL                  |
| extraction_method | str      | e.g. "llm"                     |
| created_at        | DateTime | Native Neo4j DateTime          |
| extracted_at      | DateTime | Native Neo4j DateTime          |

### Jurisdiction (3 properties)

| Property | Type | Notes                         |
|----------|------|-------------------------------|
| code     | str  | Unique key (e.g. "HONG_KONG") |
| country  | str  | Country name                  |
| name     | str  | Display name                  |

### ScannerState (8 properties)

| Property             | Type | Notes                          |
|----------------------|------|--------------------------------|
| scanner_id           | str  | Unique key                     |
| last_run_at          | str  | ISO timestamp string           |
| last_checkpoint      | str  | Date string (YYYY-MM-DD)       |
| last_status          | str  | e.g. "success"                 |
| total_runs           | int  | Cumulative run count           |
| companies_scanned    | int  | Count from last run            |
| transactions_stored  | int  | Count from last run            |
| alerts_created       | int  | Count from last run            |

---

## Relationship Properties

### OFFICER_OF (Person → Company) — 6 properties

| Property          | Type     | Notes                       |
|-------------------|----------|-----------------------------|
| title             | str      | Role title                  |
| is_executive      | bool     | Whether role is C-suite     |
| confidence        | float    | Extraction confidence score |
| extraction_method | str      | e.g. "llm"                  |
| source_filing     | str      | UUID of source Filing node  |
| updated_at        | DateTime | Native Neo4j DateTime       |

### DIRECTOR_OF (Person → Company) — 4 properties

| Property          | Type     | Notes                       |
|-------------------|----------|-----------------------------|
| confidence        | float    | Extraction confidence score |
| extraction_method | str      | e.g. "llm"                  |
| source_filing     | str      | UUID of source Filing node  |
| updated_at        | DateTime | Native Neo4j DateTime       |

### COUNTERPARTY_IN (Company → Event) — 2 properties

| Property   | Type     | Notes                  |
|------------|----------|------------------------|
| role       | str      | e.g. "counterparty"    |
| created_at | DateTime | Native Neo4j DateTime  |

### DEAL_WITH (Company → Company) — 5 properties

| Property         | Type     | Notes                      |
|------------------|----------|----------------------------|
| agreement_type   | str      | e.g. "Merger Agreement"    |
| accession_number | str      | Source filing accession     |
| filing_date      | str      | Date string (YYYY-MM-DD)   |
| source_quote     | str      | Extracted text evidence     |
| updated_at       | DateTime | Native Neo4j DateTime      |

### OWNS (Company → Company) — 7 properties

| Property          | Type     | Notes                        |
|-------------------|----------|------------------------------|
| confidence        | float    | Extraction confidence score  |
| extraction_method | str      | e.g. "rule_based"            |
| is_wholly_owned   | bool     | Whether 100% owned           |
| raw_text          | str      | Source text evidence          |
| source_filing     | str      | UUID of source Filing node   |
| source_section    | str      | e.g. "Exhibit 21"            |
| updated_at        | DateTime | Native Neo4j DateTime        |

### Propertyless Relationships

INSIDER_TRADE_OF, TRADED_BY, FILED_EVENT, MENTIONED_IN, TARGETS, ALERT_FOR, FILED, INCORPORATED_IN — all carry no properties.

---

## Temporal Data Summary

### Filing/Transaction Dates (stored as strings)

| Field                               | Earliest   | Latest     | Count  |
|-------------------------------------|------------|------------|--------|
| Event.filing_date                   | 2017-12-18 | 2026-02-25 | 2,112  |
| InsiderTransaction.transaction_date | 2004-03-17 | 2027-01-25 | 89,341 |
| InsiderTransaction.filing_date      | 2005-02-14 | 2026-03-02 | 89,341 |
| ActivistFiling.filing_date          | 2025-12-16 | 2026-03-02 | 667    |
| DEAL_WITH.filing_date               | present    | present    | 11     |

### System Timestamps (native DateTime or ISO string)

| Field                   | Type     | Earliest   | Latest     | Coverage       |
|-------------------------|----------|------------|------------|----------------|
| Company.created_at      | DateTime | 2026-01-21 | 2026-02-02 | 105 / 8,953    |
| Filing.created_at       | DateTime | 2026-01-22 | 2026-02-25 | 385 / 385      |
| Alert.created_at        | str      | 2026-02-21 | 2026-03-03 | 389 / 389      |
| OFFICER_OF.updated_at   | DateTime | present    | present    | on all 845     |
| DIRECTOR_OF.updated_at  | DateTime | present    | present    | on all 606     |
| COUNTERPARTY_IN.created | DateTime | present    | present    | on all 22      |

### Scanner State

| Scanner           | Last Run            | Checkpoint |
|-------------------|---------------------|------------|
| form4_scanner     | 2026-03-03 04:41:15 | 2026-03-03 |
| activist_scanner  | 2026-03-03 04:52:26 | 2026-03-03 |

---

## Notable Observations

1. **Date storage inconsistency**: Filing/transaction dates are stored as strings (`YYYY-MM-DD`), while system timestamps use a mix of native `DateTime` and ISO strings.
2. **Missing temporal properties**: `OFFICER_OF`, `DIRECTOR_OF`, and `OWNS` relationships have no `start_date` or `end_date` despite the schema defining indexes for them.
3. **Sparse `created_at` on Company**: Only 105 of 8,953 companies have a `created_at` timestamp — the rest were bulk-ingested without it.
4. **Future-dated transaction**: `InsiderTransaction.transaction_date` max is `2027-01-25`, likely a pre-scheduled vesting or exercise entry.
5. **Relationship count mismatch**: `INSIDER_TRADE_OF` (91,021) exceeds `InsiderTransaction` nodes (89,341), suggesting some transactions are linked to multiple companies.

---

## SignalPerformance (added 2026-04-20)

Computed nodes produced by `SignalPerformanceService.compute_all()` (delete-then-insert, stored via `_store_batch()`).

### Properties (authoritative: `backend/app/services/signal_performance_service.py:435-493`)

| Property              | Type    | Notes                                                   |
|-----------------------|---------|---------------------------------------------------------|
| `signal_id`           | string  | Primary key, e.g. `CLUSTER-{cik}-{signal_date}`         |
| `ticker`              | string  | Resolved at compute time                                |
| `company_name`        | string  |                                                         |
| `cik`                 | string  | Zero-padded 10 chars                                    |
| `signal_date`         | string  | `YYYY-MM-DD` — transaction date of cluster start        |
| `actionable_date`     | string  | `YYYY-MM-DD` — earliest filing_date in cluster          |
| `direction`           | string  | `'buy' | 'sell'`                                        |
| `signal_level`        | string  | `'high' | 'medium'` — cluster size/value tier           |
| `conviction_tier`     | string  | `'strong_buy' | 'buy' | 'watch' | ...` — use this for strong_buy filter |
| `num_insiders`        | int     | Distinct buyers in cluster                              |
| `total_value`         | float   | Sum of `total_value` across cluster                     |
| `market_cap`          | float   | Historical (signal-date) market cap                     |
| `pct_of_mcap`         | float   | `total_value / market_cap`                              |
| `industry`            | string  | SEC SIC-derived                                         |
| `price_day0`          | float   | Price on actionable_date                                |
| `price_day1`–`day7`   | float   | Prices at offsets 1, 2, 3, 5, 7 trading days            |
| `price_day90`         | float   | Price at 90 calendar days                               |
| `price_current`       | float   | Most recent observed price                              |
| `price_current_date`  | string  | Date of `price_current`                                 |
| `return_day0`–`day7`  | float   | Returns at each offset                                  |
| `return_current`      | float   | Return from day0 → `price_current` (for matured signals, this is the 90d return) |
| `spy_return_90d`      | float   | SPY return over the 90d window **(not `spy_return_day90`)** |
| `is_mature`           | bool    | True when `price_day90` is available                    |
| `computed_at`         | string  | ISO timestamp                                           |

### Ground-truth market cap (v1.4, Phase 9)

`mcap_at_signal_true` is the primary-source market cap at signal date:
- **Source:** SEC EDGAR XBRL company-facts API (`data.sec.gov/api/xbrl/companyfacts/`)
- **Formula:** `avg_raw_Form4_price × shares_outstanding_from_nearest_prior_10Q_or_10K`
- Survives reverse splits, dilution, buybacks because it uses the primary-source shares count, not a yfinance ratio.
- Introduced in v1.4 Phase 9 and populated on the 142 mature strong_buy rows **without mutating any existing field**.
- Provenance sidecar properties:
  - `mcap_at_signal_true_source` — always `'xbrl'` for v1.4
  - `mcap_at_signal_true_shares` — the shares-outstanding integer used
  - `mcap_at_signal_true_shares_end_date` — end date of the 10-Q/10-K that reported this value
  - `mcap_at_signal_true_avg_raw_px` — value-weighted avg Form 4 `price_per_share` for the cluster's buys
  - `mcap_at_signal_true_computed_at` — ISO timestamp of the backfill run

**Don't replace `market_cap` with this field yet.** Phase 12 decides whether to use it for classification. Forward-going ingest-time capture (populating this field for new signals at creation time) is explicitly scoped OUT of v1.4 — will be its own phase/milestone.

### Scope invariant (enforced 2026-04-20, v1.3)

`SignalPerformance` only stores rows where `direction = 'buy' AND conviction_tier = 'strong_buy'`.
Sell-side direction and non-strong_buy tiers (`buy`, `watch`) were removed in v1.3 as legacy-architecture remnants never surfaced by the product.
- `compute_all` short-circuits any cluster that would not classify as `strong_buy` — non-strong_buy clusters are never stored.
- `snapshot_service` no longer detects sell clusters; `insider_sell_cluster` signals are no longer emitted.
- The `signal_performance` API route's `direction` regex is tightened to `^(buy)$`.
- One-time delete migration on 2026-04-20 removed **372 legacy rows** (266 mature + 106 immature). The 142 mature strong_buy rows were preserved byte-identically.
- `InsiderClusterService` remains parameterized for sell (unit tests still exercise it) — the utility is unchanged, only its live callers changed.

Enforced by tests in `backend/tests/test_signal_performance_service.py::TestComputeAllStrongBuyOnly`.

### Immutability invariant (enforced 2026-04-20, v1.2)

A `SignalPerformance` node with `is_mature = true` is a frozen historical record.
- `compute_all()` MUST NOT delete, overwrite, or regenerate matured nodes.
- On each run, `compute_all` reads the set of matured `signal_id`s BEFORE any DELETE, and the DELETE clause filters `WHERE is_mature = false OR is_mature IS NULL` so matured rows survive untouched.
- `_compute_one` short-circuits (returns `None`) when the cluster's prospective `signal_id` is in the pre-collected matured set.
- The only path that may modify a matured node is an explicit migration script — those are rare, reviewed changes.
- Live display reads (e.g. current price on Signal Detail) are informational only — never persisted back to the node.

Enforced by tests in `backend/tests/test_signal_performance_service.py::TestComputeAllPreservesMatured`.

### Common query templates

```cypher
-- All mature strong_buy signals
MATCH (sp:SignalPerformance)
WHERE sp.direction = 'buy'
  AND sp.conviction_tier = 'strong_buy'
  AND sp.is_mature = true
RETURN sp.ticker, sp.signal_date, sp.return_current, sp.spy_return_90d

-- Hit rate + alpha (compute in Python from rows; Cypher AVG / SUM can trigger div-by-zero on empty sets)
```

### Pitfalls

- `return_day90` **does not exist.** Use `return_current` for matured signals (equivalent), or compute `(price_day90 - price_day0) / price_day0` explicitly.
- SPY alpha property is **`spy_return_90d`**, not `spy_return_day90`.
- `signal_level` = `'high' | 'medium'`. There is NO `signal_level = 'strong_buy'` — strong_buy is encoded in `conviction_tier`.
- Cypher `count(sp) * 1.0 / count(sp)` can throw `/ by zero` if the WHERE clause filters to 0 rows. Return the raw rows and compute aggregates in Python, or guard with a conditional.

