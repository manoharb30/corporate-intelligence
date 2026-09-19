# LookInsight — Project Context

## ⛔ HARD RULES — read before every tool call

These rules override anything else in this file. Violating them wastes the user's time and money.

### 1. Never run anything without explicit permission
Before any `Bash` command that mutates state — `kill`, `pkill`, `rm`, `mv`, `git push`, `git commit`, run scripts, run backfills, db writes, broker orders, etc. — STOP and explicitly check:

- Did the user say *for this specific action* "yes / run it / do it / execute / kill it / commit it"?
- If no → do NOT run. State what would be done; wait.
- "Want me to X?" or "should we X?" from the user is a question, not permission.
- Frustration / all-caps / sharp tone from the user means I already violated this. Stop and wait.

Memory rule: `feedback_no_auto_actions.md`. Violated multiple times in 2026-04-27 / 2026-04-28 sessions.

### 2. Precise answers only — no long stories
- 1–3 sentences default. Tables/code blocks only when the data IS the answer.
- "Yes" or "No" + one sentence of context is usually enough.
- Don't enumerate options unless asked. Don't pre-write implementations unless asked.

Memory rule: `feedback_precise_answers_only.md`.

### 3. Apply domain rules before suggesting designs
- **Cluster window = 30 days, FROZEN at formation.** 90d is for return calculation only — don't extend cluster membership to 90d. (Memory: `cluster_window_rule.md`.)
- **Matured signals are frozen.** Once `is_mature = true` a row is immutable. Never retroactively recompute, reclassify or expand the matured cohort; new rules apply forward only. (Memory: `feedback_matured_signals_frozen.md`.)
- **Don't name buyside firms in external artifacts** without explicit written approval. (Memory: `feedback_no_naming_funds.md`.)
- **Verify DB schema from write-path** before writing Cypher queries — never guess property names.
- **The $300M–$5B mcap band is deliberate.** Out-of-band names are out of universe — never frame them as missed coverage or propose widening.

### 4. Verify "fixes" before claiming them as verified
- "Verified" / "all good" / "checked" must mean an actual test was run (read-only query, manual recompute, or sample inspection).
- Don't say "this should work" and call it verified. If the verification was just reading code, say so.
- Prefer verifying against the **live deployed system**, not the script's own stdout.

### Pre-tool-call checklist (run mentally before every Bash mutation, Edit, Write)
1. Did the user say "yes/run/do" for THIS exact action?
2. Which memory rule applies? (Cluster window, no-auto-actions, precise-answers, frozen-cohort)
3. Is this read-only or mutating? Mutating = stricter check.
4. If unsure → ask, don't act.

---

## What This Is

**LookInsight** is an alternative-data product that surfaces high-conviction insider buying signals from SEC Form 4 filings for institutional hedge fund clients. The platform classifies genuine open-market purchases (filtering out RSU vesting, DRIP, private placements, structured deals), detects multi-insider clusters, applies an earnings-proximity filter, and delivers pre-filtered signals with measured alpha vs SPY.

**Production:** https://ci.lookinsight.ai (frontend) · https://api.lookinsight.ai (backend)

## Core Signal Model

A **strong_buy** signal is emitted when all of the following hold on a given date for a given company:
- 2+ distinct insiders made GENUINE open-market P transactions
- $100K+ total cluster value
- $300M–$5B historical market cap (midcap)
- Within 60 days of next earnings (`earn<=60d`, p=0.003)
- Returns measured from **filing date** (actionable), not transaction date

Gates live in ONE place — `insider_cluster_service.py` (`MIN_CLUSTER_INSIDERS`, `MIN_CLUSTER_VALUE_USD`, `MIN_MARKET_CAP_USD`, `MAX_MARKET_CAP_USD`, `CLUSTER_WINDOW_DAYS`, `EXCLUDED_CIKS`). Other services import them; never redeclare a gate. **The thresholds above are mirrored here for readability — the constants in that file are authoritative.** If they ever disagree, the code is right and this file is stale.

### ⚠️ NEVER write headline numbers into this file, or any doc
Cohort size, hit rate, alpha, avg return and beat-SPY all change every time a signal
matures. A number written down here is wrong within weeks and will be quoted to a client.
**Discover them when they are actually needed:**

```
GET https://ci.lookinsight.ai/api/signal-performance/dashboard-stats
```

Always quote results as "as of [date]". Same applies to open-signal counts, blocklist
size, promise-ledger tallies and research-queue depth — query, don't remember.
(Memory: `feedback_moving_numbers.md`.)

Deprecated signal frameworks (DO NOT reintroduce):
- 8-K M&A material-agreement combinations (Items 1.01/5.02/5.03/2.01) — replaced by insider clusters
- S/A/M transaction types — only P transactions are used
- Congressional trades — dead APIs, 45-day lag
- `buy` / `watch` conviction tiers — **strong_buy only** since v1.3. Never surface deprecated tier counts.

## Quality control is a HUMAN, PER-ARRIVAL process — not a gate

This is settled and should not be re-litigated. The 2026-06-15 pressure tests concluded that **no fundamental filter improves the cohort**, and the 52-week-range test reached the same conclusion. The resolution: **no automated quality gate; review each arriving signal qualitatively.**

- Signals are read by hand — 10-Q/10-K, peer comps, insider detail — because they are few.
- A name that fails review is dropped by adding its CIK to `EXCLUDED_CIKS` (with a documented comment explaining why) and removing its open `SignalPerformance` row. Precedent: YEXT, FULC, REI, RHLD, AIAI, AXIA3, PWRL, LUCK.
- The blocklist is also **prophylactic** — a weak name can be blocked BEFORE a cluster forms.
- This does NOT conflict with the frozen-cohort rule, which protects **matured** rows. Live signals are reviewable.
- Findings are written to a `ResearchNote` on the Company so the reasoning survives.

### Check buyer INDEPENDENCE, not just buyer count
`MIN_CLUSTER_INSIDERS` counts **heads, not decisions**. It assumes several insiders
independently concluded the stock is cheap. It cannot see that the buyers are one family,
one fund, or one control block — so a single decision can present as a multi-insider
cluster and clear the gate cleanly. Two ways this has actually happened:

- **Token buy** (`token_buy_cluster`) — one buyer barely participated. LUCK (2026-09-16):
  founder/CEO $175,800 alongside a director's $3,268, 1.8% of his size. KRMN (2026-09-18):
  $1,007,648 — 97.2% of the cluster — alongside $18,720 and $10,117. In both, removing the
  token leaves a single buyer that would not have qualified at all.
  Rules of thumb: largest buy ≥ ~90% of cluster value, or any buyer ≤ ~2% of the lead.
- **Control block** (`control_block_buyers`) — the buyers are the same people. BWMX
  (2026-09-17): a director who is also a 10% owner plus his two sons, buying on the same
  two days, with insiders already holding 63.2%. Look for a shared surname, a common
  holding vehicle in the Form 4 footnotes, one fund or sponsor, or already-high insider
  ownership.

For contrast, clusters that are genuinely two decisions: DFH $120,700 / $20,205 (17%),
TH $250,166 / $124,992 (50%), MCFT $75,016 / $48,745 (65%).

On every arriving cluster, look at the buyer list before anything else and ask: are these
independent? Signals worth checking for: a shared surname or disclosed family
relationship; a common holding vehicle named in the Form 4 footnotes ("voting and
investment power over shares held directly by <entity>"); the same fund or sponsor;
holder-appointed board seats; already-high insider ownership; or one buy dwarfing the
others. Tag it `control_block_buyers` on the ResearchNote.

Neither is an automatic reject — concentrated family buying can be a real signal, and the
flag is informational. It is a prompt to judge independence during review, never a gate.

## Architecture

- **Backend:** FastAPI (Python 3.13), port 8000
- **Database:** Neo4j 5 Community, running as the `lookinsight-neo4j` Docker container on Hetzner. **Neo4j Aura is PAUSED** — the `NEO4J_URI` in local `backend/.env` points at the dead Aura instance and will fail DNS resolution.
- **Frontend:** React + TypeScript + Vite + Tailwind (`npm run dev`, port 5173)
- **Data Sources:** SEC EDGAR (Form 4, Schedule 13D), yfinance (prices + market cap)
- **LLM:** Claude Haiku 4.5 for P-transaction classification (batch, 10 parallel workers)
- **Broker:** Alpaca **paper** account for the $100K tracking portfolio
- **Deploy:** Vercel (frontend, via Git integration on push to `main`) + Hetzner CPX21 Ashburn (backend + DB, Caddy + Let's Encrypt TLS) + GoDaddy DNS. **Railway is cancelled.**

### Layer architecture (sentrux-enforced)
- **data** (shared): Neo4j client, models — accessible from all layers
- **ingestion** (layer 0): SEC filing fetchers, parsers — must NOT depend on API or services
- **domain** (layer 1): Services, scanners — can access data + ingestion
- **api** (layer 2): FastAPI routes — can access domain + data
- **delivery** (layer 3): Frontend, CSV exports

Scanners must NOT depend on API layer. Ingestion must NOT depend on services or API.

## 🖥️ Operating the live system (READ THIS BEFORE ANY DB WORK)

**You cannot query the database locally.** Local `.env` points at paused Aura. Everything goes through the box.

```bash
ssh lookinsight@178.156.152.231          # root disabled
```

**Read-only Cypher** (credentials come from the running container, never from the local .env):

```bash
ssh lookinsight@178.156.152.231 'U=$(docker exec lookinsight-backend printenv NEO4J_USER); \
  P=$(docker exec lookinsight-backend printenv NEO4J_PASSWORD); \
  docker exec -i lookinsight-neo4j cypher-shell -u "$U" -p "$P" --format plain "MATCH ... RETURN ...;"'
```

**The backend container has NO bind mounts** — the image bakes in `backend/` at build time, so `/srv/lookinsight/backend` is only the build source. To run a new operator script without a full rebuild:

```bash
scp backend/my_script.py lookinsight@178.156.152.231:/srv/lookinsight/backend/
ssh lookinsight@178.156.152.231 'docker cp /srv/lookinsight/backend/my_script.py lookinsight-backend:/app/backend/ \
  && docker exec lookinsight-backend python my_script.py'          # add --commit / -d as needed
```

**Full backend deploy** (needed for any code change to take effect):

```bash
rsync -az --exclude 'venv/' --exclude '__pycache__/' --exclude '*.pyc' --exclude '.pytest_cache/' \
  --exclude '.env' --exclude '*.log' --exclude 'backfill_checkpoints/' --exclude 'backfill_errors/' \
  backend/ lookinsight@178.156.152.231:/srv/lookinsight/backend/
ssh lookinsight@178.156.152.231 'cd /srv/lookinsight/compose && docker compose build backend && docker compose up -d backend'
```

**ALWAYS exclude `.env`** — pushing the local one would point the box at dead Aura.

**Frontend deploy** is automatic: Vercel builds on push to `main`. Run `npx vite build` locally first to avoid pushing a broken build; confirm the live bundle hash matches by grepping `assets/index-*.js` from the served HTML.

**Operator script conventions:** default to DRY-RUN, require `--commit` to write; abort on anomaly rather than pressing on; assert before/after counts; write a log to a stable path. Name them `<verb>_<subject>_<YYYY-MM-DD>.py` in `backend/`.

**After ANY price refresh or ingest**, check `GET /api/snapshot/weekly` returns **200** — NaN values have broken the feed before.

## Key Backend Files

### Services (`backend/app/services/`)
- `insider_cluster_service.py` — cluster detection, all gates, `EXCLUDED_CIKS`, `build_form4_url()`, signal detail
- `signal_filter.py` — earnings proximity filter + hostile activist check
- `signal_performance_service.py` — returns, alpha, maturation, dashboard stats
- `near_miss_service.py` — Research Queue (clusters dropped on earnings timing alone)
- `research_note_service.py` — `(:Company)-[:HAS_RESEARCH_NOTE]->(:ResearchNote)`, written reviews
- `signal_watch_service.py` — `Promise` / `SignalEvent` promise-vs-delivery ledger
- `alpaca_portfolio_service.py` — paper portfolio positions, P&L, implementation shortfall
- `snapshot_service.py` — precomputed signal list blobs
- `trade_classifier.py` — trade-type utility (exercise-hold vs exercise-sell, etc.)
- `activist_filing_service.py` — Schedule 13D data
- `stock_price_service.py` — yfinance wrapper (used during ingest, not at query time)
- `feed_service.py`, `alert_service.py`, `explorer_service.py`, `insider_trading_service.py`, `officer_scan_service.py` — supporting

### Routes (`backend/app/api/routes/`)
`health.py` · `snapshot.py` · `event_detail.py` · `signal_performance.py` · `explorer.py` · `scanner.py` · `activist.py` · `near_miss.py` (`/api/near-miss`) · `portfolio.py` (`/api/portfolio`) · `signal_watch.py` (`/api/signal-watch`)

### Scanners (`backend/scanner/`)
- `form4_scanner.py` — daily Form 4 discovery + cluster detection
- `activist_scanner.py` — Schedule 13D discovery
- `8k_scanner.py` — LEGACY, deprecated; not used in signal generation

### Pipeline scripts (`backend/`)
- `run_week.py` — the daily/weekly entry point. `--start YYYY-MM-DD --days N`, where **N counts TRADING days**; weekends and `SEC_HOLIDAYS` are skipped automatically.
- `run_month.py`, `run_multiple_months.py` — batch backfills
- `prefilter_p.py`, `classify_p_with_prefilter.py`, `batch_llm_classify.py` — split-architecture steps
- `backfill_*.py` — operational backfills (market cap, prices, historical signals, etc.)
- `refresh_immature_current_price.py` — refresh `price_current` / `return_current` on open signals

## Key Frontend Files

- `frontend/src/pages/SignalList.tsx` — strong_buy feed (home)
- `frontend/src/pages/SignalDetail.tsx` — buyers, Form 4 links, decision card, Research Note, Signal Watch
- `frontend/src/pages/PerformanceTracker.tsx` — full signal P&L (winners + losers)
- `frontend/src/pages/NearMiss.tsx` — Research Queue at `/research-queue` (no nav link, no auth, by decision)
- `frontend/src/pages/Portfolio.tsx` — Alpaca paper portfolio, equity curve vs SPY, implementation shortfall
- `frontend/src/components/SignalWatch.tsx` — promise ledger on the signal page
- `frontend/src/services/api.ts` — typed API client
- Also present: `McpDocs.tsx`, `Privacy.tsx`, `Terms.tsx`

## Before writing database queries (HARD RULE)

**Never guess Cypher property names.** Before writing any Cypher that references specific properties, confirm the schema:

1. **Always-current sources of truth (read these first):**
   - `SignalPerformance` → `signal_performance_service.py`, `_store_batch()` — the CREATE clause lists every property.
   - `InsiderTransaction` / `Company` / `Person` → `backend/ingest_genuine_p_to_neo4j.py` `ingest_transaction()`.
   - `ActivistFiling` → `activist_filing_service.py`.
   - `ResearchNote` → `research_note_service.py` `record_note()` (closed vocabularies: `VERDICTS`, `RISK_FLAGS`).
   - `Promise` / `SignalEvent` → `signal_watch_service.py` `record_promises()` / `record_event()`.
   - `Event` → `feed_service.py` (there is **no** `event_store_service.py`).
2. **Cached reference:** `neo4j/schema-report.md` — generated snapshot from 2026-04, useful for orientation but validate against the write path.
3. **If a query fails with "property does not exist":** STOP. Re-read the write path. Do not iterate by trial-and-error — one schema mismatch often hides others.

**Common gotchas (record, don't rediscover):**
- `SignalPerformance` has `price_day90` but **no** `return_day90` — use `return_day0` for the matured headline return, or compute from prices.
- SPY alpha property is `spy_return_90d`, **not** `spy_return_day90`, and it is stored in **PERCENT points**.
- `signal_level` = `'high' | 'medium'`. The strong_buy distinction lives in `conviction_tier`.
- `transaction_date` may have a TZ suffix (`-05:00`). Truncate via `substring(dt, 0, 10)` in Cypher or `dt[:10]` in Python.
- `signal_date` is the cluster **window end**, not the first buy date.
- `detect_clusters(days=N)` filters TRANSACTIONS, not signal_date — pass `days=N+30` when scoping to the last N days.
- `compute_all` is DEPRECATED; the live path is `process_incremental`.
- `Company.market_cap` is frequently **stale**, sometimes by tens of percent. Recompute shares × price before trusting it near a gate boundary, and never quote it as the company's market cap.

## Testing

```bash
cd backend && venv/bin/python -m pytest tests/ -q
```

**The suite is green.** There are no known-failing tests, so any red is yours — do not assume a failure is pre-existing.

**Gotcha worth remembering:** these unit tests patch `Neo4jClient` *in the module under test*. If a service reaches the DB through a COLLABORATOR's import (e.g. `ResearchNoteService.get_notes()` from inside `insider_cluster_service`), the patch does not apply and the test hits the real, unconnected client. Compose across services at the **route** layer instead.

Core suites: `test_signal_filter.py`, `test_signal_performance_service.py`, `test_near_miss_service.py`, `test_near_miss_route.py`, `test_signal_watch_service.py`, `test_research_note_service.py`.

## Architecture Governance (sentrux)

`sentrux` CLI is installed at `~/bin/sentrux`; baseline lives in `.sentrux/baseline.json`.

- Before changes: `sentrux gate --save .` to snapshot the baseline
- After changes: `sentrux gate .` to compare; `sentrux check .` — all rules must pass
- Never let architecture grade drop below B without explicit approval
- Zero dependency cycles (max_cycles = 0); no file over 500 lines

## Paper Portfolio (Alpaca)

$100K Alpaca **paper** account trading LookInsight's own signals, so the published alpha has an auditable P&L behind it. Methodology is pre-registered on `/portfolio` and changes go in a dated changelog — never retroactively.

- **Entry:** $5,000 fixed per position (5% of the INITIAL $100K, not compounding), 3 same-day market tranches at 10:00 / 12:30 / 15:30 ET, max 20 slots.
- **Entry day is the day the signal SURFACES** (detection + review), never the signal date. Never backdate. `day0_price` is the implementation-shortfall BASIS only.
- **Every kept signal gets entered** — that is part of finishing a signal, not a separate request. Dropped signals are not entered.
- **Exit:** day 90, sold in 3 same-day tranches.
- **Idle cash** sits in SGOV above a $1,000 buffer; every entry after the launch must first liquidate ~$5K of SGOV to fund the slice.
- No recurring executor exists yet — each entry/exit is a one-off operator script cloned from `enter_dfh_2026-09-16.py`. Run multiple same-day entries in SEQUENCE so the funding sales cannot race.

## Context for Future Sessions

- Founder: Manohar (based in India); markets are US — use **US Eastern** dates for anything market- or scanner-related.
- Ingest cadence is **occasional operator catchup**, not daily automation. A catchup run carries maturation + price refresh + dashboard.
- Institutional sales cycle has been active since early 2026; the Neudata engagement concluded 2026-04-23.
- Next milestone: marketing + operational (daily auto-ingest, alerts, S3 delivery, paid clients).
