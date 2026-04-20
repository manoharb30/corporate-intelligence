# Milestones

Completed milestone log for this project.

| Milestone | Completed | Duration | Stats |
|-----------|-----------|----------|-------|
| v1.0 Signal Quality | 2026-04-18 | 3 phases | 3 phases, 14 plans, production deployment |
| v1.1 Hedge Fund Research Delivery | 2026-04-20 | 2 days | 2 phases shipped, 1 dropped; brief + data appendix |
| v1.2 Signal Integrity — matured immutability | 2026-04-20 | same-day | 1 phase, 1 plan; +4 regression tests |
| v1.3 Pipeline Simplification — strong_buy only | 2026-04-20 | same-day | 1 phase, 1 plan; +3 regression tests; 372 legacy rows deleted |
| v1.4 Signal Quality Audit — ground-truth mcap + per-signal post-mortem | 2026-04-20 | same-day | 4 phases, 4 plans; +11 tests; 141/142 mcap corrected; zero new filters (Bonferroni) |

---

## ✅ v1.4 Signal Quality Audit — ground-truth mcap + per-signal post-mortem

**Version:** 1.4.0
**Completed:** 2026-04-20
**Duration:** Same-day (single session, 4 phases)

### Stats

| Metric | Value |
|--------|-------|
| Phases | 4 (9, 10, 11, 12) |
| Plans | 4 (one per phase) |
| New tests | 11 XBRL client tests; total suite now 71 |
| Files created | 9 (XBRL client, backfill script, 3 audit scripts, 4 markdown docs) |
| XBRL API calls | 142 company-facts fetches (~1 per CIK, cached per run) |
| Signals with ground-truth mcap | 141 / 142 (99.3%) |
| Filter candidates tested | 22 |
| Filters adopted | 0 (none passed Bonferroni p<0.05) |

### Key Accomplishments

**Phase 9: Ground-truth market cap via SEC XBRL**
- `XBRLClient` with 5-concept fallback chain + sanity filter + post-signal fallback for late-XBRL issuers.
- `backfill_mcap_true.py` (checkpoint-resumable operational script).
- Top ratio-estimate errors revealed: ANDG −93%, RPAY −92%, ONDS −88%, SEI −86%, MRVI −60%, DNA −19%.

**Phase 10: Per-signal audit template**
- Deterministic 142 × 34 CSV + Parquet + comprehensive data dictionary.
- Surprising finding: naive midcap filter on true mcap drops 10 signals with 80% HR / +33% return.

**Phase 11: Classification + significance testing**
- 22 filter candidates × Fisher's exact + Mann-Whitney U + Bonferroni (n=22).
- Zero candidates pass. Honest scientific conclusion: 142 signals too small for multiple-testing filter discovery.
- Formally rejected: naive true-mcap midcap filter. Confirmed operational: v1.0 earnings rule.
- 47 per-loser detail blocks (root_cause_tag placeholders for manual review).

**Phase 12: Methodology versioning**
- `methodology_version` property added on SignalPerformance. All 142 tagged `'v1.1'`.
- No filter changes (per Phase 11). No display changes. Minimal mechanism for v1.5 tier extensions.

### Key Decisions

See `.paul/milestones/v1.4.0-ROADMAP.md` for the full table (7 decisions).

Top three:
1. Ground-truth mcap from SEC XBRL primary data, not ratio estimate.
2. No new filters adopted — Bonferroni discipline on 22 candidates.
3. "Leaked winners" are mislabeled midcaps, not feature of the filter. Tier extension (small_cap, large_cap) is the principled fix — deferred to v1.5.

### Headline numbers (unchanged)

**142 mature strong_buy · 66.9% hit rate · +14.04% avg return · +8.72% avg alpha.**

By design — v1.4 audited the methodology without altering classification.

### Commits

- `8fb4853` Phase 9
- `7743111` Phase 10
- `5d263eb` Phase 11
- `4dc1c22` Phase 12 / v1.4 complete

---

## ✅ v1.3 Pipeline Simplification — strong_buy only

**Version:** 1.3.0
**Completed:** 2026-04-20
**Duration:** Same-day (created and shipped 2026-04-20)

### Stats

| Metric | Value |
|--------|-------|
| Phases | 1 (Phase 8 — Strong_buy-only pipeline) |
| Plans | 1 (08-01) |
| Files changed | 6 (signal_performance_service.py, snapshot_service.py, signal_performance.py API route, test_signal_performance_service.py, frontend/api.ts, neo4j/schema-report.md) |
| New tests | 3 (TestComputeAllStrongBuyOnly) |
| Total tests | 41 pass |
| Legacy rows deleted | 372 (266 mature + 106 immature non-strong_buy) |
| Mature strong_buy preserved | 142 (byte-identical) |

### Key Accomplishments

**Phase 8: Strong_buy-only pipeline**
- `compute_all` no longer calls `detect_clusters(direction="sell")`; `_compute_one` short-circuits any cluster whose `conviction_tier != 'strong_buy'`. Sell + non-strong_buy tiers never enter SignalPerformance.
- `snapshot_service.get_signal_list` stripped of sell detection, `insider_sell_cluster` emission, `_compute_sell_stats`, and `sell_stats` / `pass_stats` blob fields.
- `signal_performance` API route `direction` regex tightened to `^(buy)$`.
- Frontend `signal_type` type union narrowed to `'insider_cluster'`.
- One-time Cypher migration deleted 372 legacy SignalPerformance rows.
- v1.2 matured-immutability invariant upheld (142 matured strong_buy byte-identical before/after migration).
- `InsiderClusterService` intentionally left parameterized for sell — unit tests still exercise it; only live callers changed.

### Key Decisions

| Decision | Rationale | Date |
|----------|-----------|------|
| Pipeline scope narrowed to strong_buy buy only | Sell + non-strong_buy tiers were legacy from pre-v1.0; never surfaced by product. Cleanup cuts compute cycles, storage, and confusion. | 2026-04-20 |
| Keep `direction` + `conviction_tier` columns on SignalPerformance | Future-proofs schema if tiers/directions reintroduced later. Always `'buy'` / `'strong_buy'` now. | 2026-04-20 |
| Keep InsiderClusterService parameterized for sell | Utility stays flexible (tests exercise it); only live callers changed — lower blast radius. | 2026-04-20 |

### Commit

`edf6a41` — feat(08-strong-buy-only): narrow pipeline to strong_buy buy only (v1.3 complete)

---

## ✅ v1.2 Signal Integrity — matured immutability

**Version:** 1.2.0
**Completed:** 2026-04-20
**Duration:** Same-day (created and shipped 2026-04-20)

### Stats

| Metric | Value |
|--------|-------|
| Phases | 1 (Phase 7 — mcap snapshot / matured immutability) |
| Plans | 1 (07-01) |
| Files changed | 4 (signal_performance_service.py, signal_filter.py, test_signal_performance_service.py, neo4j/schema-report.md) |
| New tests | 4 (TestComputeAllPreservesMatured) |
| Total tests | 38 pass |
| Matured rows preserved | 408 (byte-identical across recompute) |

### Key Accomplishments

**Phase 7: mcap snapshot (Matured-signal Immutability)**
- Initially proposed as "add `market_cap_at_signal` snapshot column"; during design the simpler root-cause fix emerged: **never recompute matured rows**. Dropped the snapshot field in favor of immutability.
- `compute_all` now reads matured `signal_id`s BEFORE any DELETE; the DELETE clause filters `WHERE is_mature = false OR is_mature IS NULL` so matured rows survive untouched.
- `_compute_one` short-circuits (returns `None`) when the cluster's prospective `signal_id` is already matured.
- New `_fetch_all_for_dashboard` helper reshapes the full SignalPerformance set (preserved matured + freshly computed) for `_save_dashboard_stats`.
- `signal_filter.py` TZ-suffix fix (`signal_date[:10]`) — surfaced by May 2024 backfill where some `transaction_date` values carry `-05:00`.
- Four new regression tests (AC-1 short-circuit, AC-2 new-cluster, AC-3 immature-refresh, backward-compat).

### Key Decisions

| Decision | Rationale | Date |
|----------|-----------|------|
| Matured SignalPerformance nodes are immutable | A matured signal is a frozen historical record; recompute should never drift classifications. | 2026-04-20 |
| Drop `market_cap_at_signal` field in favor of matured-preservation | Snapshot field was redundant once we stopped touching matured rows entirely. Simpler and respects the same invariant. | 2026-04-20 |

### Also Completed During Session

- May 2024 Form 4 backfill (first extended-coverage month).
- Hardened schema discipline: added `Before writing database queries` rule to `CLAUDE.md` + expanded SignalPerformance section in `neo4j/schema-report.md`.
- `.paul/backfill-log.md` scaffold for opportunistic monthly-backfill journaling.

### Commit

`df2bb8f` — feat(07-mcap-snapshot): matured-signal immutability invariant (v1.2 complete)

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
