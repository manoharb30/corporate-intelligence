# Milestones

Completed milestone log for this project.

| Milestone | Completed | Duration | Stats |
|-----------|-----------|----------|-------|
| v1.0 Signal Quality | 2026-04-18 | 3 phases | 3 phases, 14 plans, production deployment |
| v1.1 Hedge Fund Research Delivery | 2026-04-20 | 2 days | 2 phases shipped, 1 dropped; brief + data appendix |

---

## ✅ v1.1 Hedge Fund Research Delivery

**Version:** 1.1.0
**Completed:** 2026-04-20
**Duration:** 2 days (2026-04-19 → 2026-04-20)

### Stats

| Metric | Value |
|--------|-------|
| Phases | 2 shipped (4, 5), 1 dropped (6 — Per-Fund Delivery, out of scope) |
| Plans | 3 (04-01 export ✓, 05-01 content ✓, 05-02 PDF closed by user) |
| New modules | `backend/exports/` (layer-3 delivery) |
| Artifacts shipped | 141-signal CSV + Parquet (33 cols), DATA_DICTIONARY.md, verify_export.py, 533-line research brief (8 sections, 6477 words), 3 PNG charts, stats.json |

### Key Accomplishments

**Phase 4: Signal Data Export**
- 32-column schema locked for reproducible delivery (later expanded to 33 with signal_level)
- CSV + Parquet outputs with pyarrow type enforcement
- DATA_DICTIONARY.md covering cohort, derived formulas, caveats, reproducibility
- verify_export.py Neo4j-live audit (row count + null audit + 5-signal spot-check, 0 mismatches)
- `backend/exports/` module respecting layer-3 boundary (imports domain+data only, never api)
- Reused `InsiderClusterService.get_cluster_detail` for buyer provenance — avoided re-implementing cluster-window logic

**Phase 5: Research Brief (Content)**
- 533-line methodology-first brief with 8 sections (Thesis, Methodology, Funnel, Performance, Signal-level log, Academic Foundation, Caveats, Appendix)
- Funnel-as-product framing validated
- Academic citations added (Jeng/Metrick/Zeckhauser 2003, Cohen/Malloy/Pomorski 2012, Lakonishok & Lee 2001, Seyhun 1986, Ke/Huddart/Petroni 2003)
- 17-month per-signal performance log (month-grouped)
- Statistical reality check: alpha p-value computed at 0.0022 (two-sided t-test), not <0.001 as previously asserted — brief honors the computed value
- Phase 5 Plan 02 (PDF rendering) created but closed by user — markdown output deemed sufficient

**Phase 6: Per-Fund Delivery** — dropped from v1.1 scope by user decision. Hedge fund outreach is not a code-milestone activity.

### Key Decisions

| Decision | Rationale | Date |
|----------|-----------|------|
| Story-first framing for research brief | Methodology funnel emphasized over the 141 headline number | 2026-04-19 |
| One master PDF, not per-fund | Simpler delivery, consistent narrative across recipients | 2026-04-19 |
| Fresh write, no deprecated-framework references | Clean signal thesis for institutional readers | 2026-04-19 |
| v1.1 phases = 4/5/6 globally (continuing sequence) | Preserves phase-directory convention from v1.0 | 2026-04-19 |
| 32-column signal schema locked | Reproducible delivery format with type-enforced Parquet + self-referencing CSV | 2026-04-19 |
| hostile_flag exported as informational column (3/141 true) | v1.0 classification preserved; buyer can weight independently | 2026-04-19 |
| Numbers are "as of [publication date]", not frozen | Institutional alt-data norm; updates strengthen the product | 2026-04-20 |
| Phase 6 (Per-Fund Delivery) dropped from scope | Email outreach is an ops activity, not a code milestone | 2026-04-20 |

### Work Also Completed

- **May 2024 backfill** — first month of extended coverage (Jun 2024 baseline extended backward). Found a TZ-suffix bug in `signal_filter.py` (missing `[:10]` slice on `signal_date`); fixed in-session.
- **Hardened schema discipline** — added `Before writing database queries` rule to `CLAUDE.md` + expanded `SignalPerformance` section in `neo4j/schema-report.md` after property-name guessing caused repeated query failures.
- **Identified mcap snapshot design gap** — `compute_all` re-derives historical market_cap from current state each run; should snapshot at signal creation. Carried forward as first phase of v1.2.

### Headline Numbers (as of 2026-04-20, post-May 2024 backfill)

| Metric | Value |
|--------|-------|
| Mature strong_buy signals | 142 (Apr 2024 – Apr 2026) |
| Hit rate (90d > 0) | 66.9% |
| Avg 90d return | +14.04% |
| Alpha vs SPY (90d) | +8.72% |

(v1.1 brief was written against the frozen 2026-04-19 snapshot: 141 / 67.4% / +9.0% / p=0.0022.)

### Delivery Artifacts

- `.paul/phases/05-research-brief-pdf/brief_v1_1.md` (533 lines, 6477 words, 8 sections)
- `backend/exports/out/signals_v1_1_2026-04-19.csv` (141 rows × 33 cols)
- `backend/exports/out/signals_v1_1_2026-04-19.parquet` (same)
- `backend/exports/DATA_DICTIONARY.md`
- `.paul/phases/05-research-brief-pdf/charts/` (funnel.png, return_distribution.png, alpha_waterfall.png)
- `.paul/phases/05-research-brief-pdf/stats.json`

### Next Milestone Input

- mcap snapshot fix (matured signals should be immutable on recompute)
- Extended coverage backfill (Jan–Apr 2024 next, optionally 2023)
- Revisit Phase 6 if/when outreach cadence is defined

---

## ✅ v1.0 Signal Quality

**Version:** 1.0.0
**Completed:** 2026-04-18
**Duration:** Phases 2-3 executed Apr 16-18 (Phase 1 data pipeline predates PAUL framework, spans Feb–Apr 2026)

### Stats

| Metric | Value |
|--------|-------|
| Phases | 3 (Data Pipeline, Signal Quality, Institutional Positioning) |
| Plans | 14 (6 in Phase 2, 8 in Phase 3; Phase 1 predates plan tracking) |
| Tests | 34 TDD tests on signal_performance + 19 on signal_filter |
| Code removed | ~14,000 lines (17 routes, 15 services, 14 pages, 14 components) |
| Data processed | 67,346 transactions → 7,386 GENUINE → 141 mature strong_buy |
| Data range | Jun 2024 – Apr 2026 (22 months) |

### Headline Numbers (verified, defensible)

| Metric | Value | Significance |
|--------|-------|--------------|
| Mature strong_buy signals | 141 | — |
| Hit Rate (90d return > 0) | 67.4% | p < 0.001 vs 50% coin flip |
| Avg Alpha vs SPY | +9.0% | p < 0.001 vs 0% |
| Avg Return (90d) | +14.2% | — |
| Data integrity | 0.000% max discrepancy | Verified 20% sample vs live yfinance |

### Key Accomplishments

**Phase 1: Data Pipeline**
- Form 4 P-transaction pipeline with split architecture (prefilter → batch LLM → merge)
- 21 prefilter rules + Claude Haiku 4.5 batch classifier (10 parallel workers)
- Structured deal detector (5+ buyers at same price → AMBIGUOUS)
- Monthly/quarterly batch processing (run_month.py, run_multiple_months.py)
- Market cap + price coverage backfill across 17 months

**Phase 2: Signal Quality**
- Earnings proximity filter (earn ≤60d, p=0.003) — single evidence-based rule beats stacked 3-rule scorer
- Data integrity verification: 20% random sample, 0.000% discrepancy vs live yfinance
- Retroactive filter: 3,433 transactions → FILTERED; 309 → 164 strong_buy clusters
- Activist temporal hypothesis tested (before/after/none) — directional, not actionable
- Hostile activist informational flag (88% loser predictor, small sample)
- 19 TDD tests on signal_filter

**Phase 3: Institutional Positioning**
- Frontend stripped to 3-page clean shell (Signal List, Signal Detail, Performance Tracker)
- Backend stripped from 24 routes to 7; 15 services deleted (14K lines)
- Signal Performance Service rewritten (TDD, 34 tests, stored data only, 130s compute vs 15-30 min)
- Historical market cap via price ratio, SPY stored as Company node (755 days)
- Midcap definition tightened to $300M–$5B (was $10B, p=0.018)
- Filing-date returns (avoids look-ahead bias vs transaction date)
- Precomputed dashboard stats + snapshot blobs (zero yfinance at query time)
- Cascading year/month dropdowns, hostile activist warning banner
- Jun–Nov 2024 backfilled through full pipeline

### Key Decisions

| Decision | Rationale | Date |
|----------|-----------|------|
| P transactions only (no S/A/M) | Conviction buying is the cleaner signal; sells noisy | 2026-04-15 |
| Single earnings rule over 3-rule scorer | p=0.003 significance; stacking weak rules lost signals for <1pp gain | 2026-04-16 |
| Hostile activist = informational flag, not filter | 88% predictor but n=8 too small for hard exclusion | 2026-04-16 |
| 8-K M&A signals deprecated | Insider clusters proved more predictive than 8-K combos | 2026-04-15 |
| AMBIGUOUS written to DB | Preserves data for review without polluting GENUINE | 2026-04-15 |
| Midcap cap $5B (was $10B) | $5B–$10B: 38.1% HR vs <$5B: 67.4% (p=0.018) | 2026-04-17 |
| Returns from filing date | 1-3 day gap avoids look-ahead bias | 2026-04-17 |
| Historical market cap estimation | current_mcap × (signal_price / current_price); 5/5 spot checks | 2026-04-17 |
| Confidence tiers informational, not filters | p=0.11 for High vs Standard — directional, not proven | 2026-04-17 |
| US-only by design | SEC is deepest insider disclosure; global = breadth over depth | Phase 2 |
| 17-22 mo history sufficient | Academic papers validate patterns across decades | Phase 2 |
| S3 bucket for signal delivery | Modern quant infra preference over SFTP | Phase 3 |

### Production Artifacts

- https://ci.lookinsight.ai — Vercel (frontend) + Railway (backend), GoDaddy DNS
- Neo4j Aura — shared local + prod instance
- 3 pages, 7 API routes, 12 services, 34 TDD tests (signal performance) + 19 (signal filter)
- Commit `8cf77b0` on main

### Research Foundation

- Brav 2008, Klein & Zur 2009, Greenwood & Schor 2009 — activist hostile patterns
- Earnings cycle as dominant predictor of insider alpha
- 11-factor risk scorer designed then abandoned (data-driven single-rule decision)
- Parallel agent research: momentum, earnings, sector, volatility, cluster composition

---

*MILESTONES.md — Updated when milestones complete*
