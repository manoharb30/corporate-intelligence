# ROADMAP.md — Milestone & Phase Breakdown

## Version Overview

| Version | Milestone | Status | Date |
|---------|-----------|--------|------|
| v1.0 | Signal Quality | ✅ Complete | 2026-04-18 |
| v1.1 | Hedge Fund Research Delivery | ✅ Complete | 2026-04-20 |
| v1.2 | Signal Integrity — matured immutability | ✅ Complete | 2026-04-20 |
| v1.3 | Pipeline Simplification — strong_buy only | ✅ Complete | 2026-04-20 |
| v1.4 | Signal Quality Audit — ground-truth mcap + per-signal post-mortem | ✅ Complete | 2026-04-20 |
| v1.5 | Signal Tier Extension — small_cap + large_cap (investigated, REJECTED) | ✅ Complete | 2026-04-20 |
| v1.6 | Forward-going mcap capture at signal creation | ✅ Complete | 2026-04-20 |
| v1.7 | Signal Pipeline Reconciliation | 🚧 In Progress | 2026-04-23 |

## Current Milestone

**v1.7 Signal Pipeline Reconciliation** (1.7.0)
Status: 🚧 In Progress
Started: 2026-04-23
Phases: 2 of 5 complete

**Theme:** Reconcile the multiple "sources of truth" across the signal pipeline. `detect_clusters` currently ignores the `classification` tag (letting `FILTERED` and `NOT_GENUINE` transactions cluster), uses an outdated `$10B` midcap cap, and duplicates logic with `get_cluster_detail` which has a conflicting `strong_buy` definition. Close the multi-file drift that has silently produced contaminated cohorts since the earnings-proximity rule was introduced.

**Scope anchors:**
- 17 of 58 current immature SignalPerformance rows are backed by non-GENUINE underlying transactions (16 FILTERED-backed + 1 NOT_GENUINE-override-backed — AEVEX, surfaced 2026-04-22).
- Phase 17 is a decision phase: option 1 / 2 / 3 on earnings-proximity must be chosen before implementation begins.
- v1.2 matured-immutability preserved throughout. 142 mature rows untouched.
- v1.4 `methodology_version` mechanism reused; new work tagged `'v1.7'`.

### Phases

| Phase | Name | Plans | Status | Completed |
|-------|------|-------|--------|-----------|
| 17 | Methodology decision + earnings-proximity implementation | 1/1 | ✅ Complete | 2026-04-23 |
| 18 | Cluster-detection correctness | 1 (18-01) | Planning | - |
| 19 | Conviction-tier unification | TBD | Not started | - |
| 20 | Mcap source reconciliation | TBD | Not started | - |
| 21 | Control-Vehicle Exclusion (LOGC removal + CIK blocklist) | 1/1 | ✅ Complete (reduced scope; auto-gate deferred) | 2026-06-09 |

### Phase 17: Methodology decision + earnings-proximity implementation

**Focus:** Decide between option 1 (tighten retroactively — keep earnings-proximity as hard filter), option 2 (reframe as informational — FILTERED becomes a tag, not a gate), or option 3 (drop the rule entirely). Implement the consequence in `merge_classifications.py` and downstream. Resolve `classification_override` role (active tag consumed by pipeline, or read-only audit). **Decision pause for user review before implementation.**
Plans: TBD (defined during /paul:plan)

### Phase 18: Cluster-detection correctness

**Focus:** Bug-fix phase on `insider_cluster_service.py`. (a) Add `AND t.classification = 'GENUINE'` to `detect_clusters` Cypher query — the root defect from the 2026-04-22 session. (b) Change midcap upper cap `$10B → $5B` in `detect_clusters:417` to align with `signal_performance_service.compute_conviction_tier` and the v1.0 decision dated 2026-04-17 (p=0.018). (c) Exclude `is_10b5_1` from the buy branch (line 276-279) for symmetry with the sell branch (line 273). (d) Replace silent exception fallback (line 432-437) with `logger.warning(...)` on yfinance failures.
Plans: TBD (defined during /paul:plan)

### Phase 19: Conviction-tier unification

**Focus:** Extract `_build_cluster_from_trades(trades, cik, window_start, window_end, direction) → ClusterResult` helper shared by `detect_clusters` and `get_cluster_detail` — collapses the duplication flagged in the 2026-04-22 architectural review. Align `get_cluster_detail`'s conviction-tier rule (currently `num_traders ≥ 3 AND officer_count ≥ 2`) with `detect_clusters`'s rule (mcap + value). Single rule everywhere. Optionally centralize thresholds into a `ClusterThresholds` dataclass.
Plans: TBD (defined during /paul:plan)

### Phase 20: Mcap source reconciliation

**Focus:** `detect_clusters` currently calls `StockPriceService.get_market_cap(ticker)` for live yfinance mcap. v1.6's `mcap_at_signal_true` field already stores XBRL-truth mcap on immature SignalPerformance rows but `detect_clusters` doesn't read it. Decide: (a) prefer stored `mcap_at_signal_true` when available, fall back to ratio-estimate; or (b) accept the drift with documented rationale. Decide during plan phase.
Plans: TBD (defined during /paul:plan)

### Phase 21: Control-Vehicle Exclusion Gate

**Trigger:** LOGC (ContextLogic Holdings, `CLUSTER-0002064307-2026-06-03`) entered the cohort as a strong_buy on 2026-06-08. Investigation showed it is a genuine 2-insider open-market cluster (Raja Bobbili / Abrams Capital $2.45M + Paul Levy $1.13M) at ~$400M midcap — passing every mechanical filter — but the company is an **Abrams-controlled permanent-capital vehicle** (post-US-Salt reverse-merger holdco, ~40% fund-controlled, concurrent $115M rights offering). The disqualifying facts are company-level, not transaction-level: the LIVE Haiku classifier returns GENUINE for Bobbili's buy even with the Abrams/Riva fund-control footnote in the payload, and SEC SIC is still `5961` (operating). So neither the LLM classifier nor a SIC gate catches it — a deterministic control-vehicle eligibility gate is required.

**OUTCOME (2026-06-09): DESCOPED — auto-gate deliberately NOT built.** On expert/accounting re-review the buyer-attribute heuristic proved fragile (self-reported 10% checkbox; indirect ownership collides with legitimate family LPs/trusts; brittle fund regex; $-dominance is a weak control proxy), and we are generalizing from **n = 1** (LOGC is the only confirmed instance) — an automated rule from one example overfits, and a false positive prunes a good signal from the core cohort. RLI and GSHD (the other two recent clusters) were vetted and confirmed legitimate, so there is no wave to gate against. Shipped only the certain, deterministic part.

**DELIVERED:**
- **Deterministic CIK blocklist** in `insider_cluster_service.py`: `EXCLUDED_CIKS = {"0002064307"}` constant, guard in the live writer `process_incremental`, and filter in `detect_clusters` (feed/scanner). Exact CIK match, zero false-positive risk. Live after next backend redeploy.
- **LOGC signal removed** via `remove_logc_2026-06-09.py` (deleted immature SP node `CLUSTER-0002064307-2026-06-03`). Cohort 173 mature unchanged, immature 24 -> 23. Underlying Form 4 transactions left GENUINE (company-eligibility exclusion, NOT a transaction relabel — deliberate divergence from `invalidate_codi`).

**DEFERRED to Backlog -> Correctness/Research:**
- **B/C — automated control-vehicle gate + backtest.** Revisit only when >= 3-4 control-vehicle examples accumulate. Economically sound form = 13D-control (`ActivistFiling`) + >= 30% of shares outstanding, fail-open when ownership can't be confirmed. Not n=1.
- **A — primary-issuance prefilter Rule 23.** Hygiene only; would NOT have caught LOGC.

**Deploy note:** the blocklist guard is committed but only live after image rebuild/redeploy; until then a re-ingest of CIK `0002064307` could recreate the signal (Bobbili/Levy buys stay inside a 30-day window into early July).

---
*Original design (B/C now deferred — kept for reference):*

**Scope: Workstreams B + D (defer A).**

- **B — Control-vehicle eligibility gate** in `insider_cluster_service.detect_clusters` (beside the $300M–$5B mcap gate, ~line 411; extend the cluster query ~line 221 to project `is_ten_percent_owner`, `ownership_type`, `footnotes`). A buyer is a "control-affiliated fund insider" if `is_ten_percent_owner=true` AND `ownership_type='I'` AND footnote/nature matches investment-fund language (`Capital Partners|Capital Management|L\.?P\.?|general partner|managing member|Partners [IVX]+|fund`). **Exclude the cluster** if such insiders are ≥50% of cluster $ value OR all distinct buyers are control-affiliated. **Confirmation layer:** affiliated funds ≥~30% of shares outstanding (prefer linked 13D/13G `ActivistFiling`, else footnote share-sum, else role-heuristic with log). **Guardrail:** direct (`ownership_type='D'`) 10% owners (founder/CEO conviction) are never flagged. **Backstop:** CIK exclusion-list constant, seeded with LOGC `0002064307`. Structured skip-reason logged for audit. Unit tests: LOGC-shaped cluster excluded; founder direct-10%-owner retained.
- **C (mandatory gate before D commits)** — read-only backtest of gate B against all 197 existing `SignalPerformance` (173 mature + 24 immature). Review what it would exclude for false positives; tighten thresholds if anything good is threatened. Matured cohort frozen — gate is forward-only, no retroactive reclassification.
- **D — Remove the live immature LOGC signal.** Add CIK to exclusion list, `DETACH DELETE` the `SignalPerformance` + `InsiderCluster` nodes, refresh snapshot/feed. **Do NOT** mark Bobbili/Levy transactions `NOT_GENUINE` — they are genuine open-market buys; this is a company-eligibility exclusion, not a transaction relabel (deliberate divergence from the `invalidate_codi` precedent). Immature → 173 mature dashboard stats unaffected. Dry-run → commit on approval.

**Deferred — Workstream A** (primary-issuance prefilter Rule 23: footnote scan for rights offering / subscription / private placement / backstop → NOT_GENUINE). Hygiene only; does NOT catch LOGC (its footnotes are silent on the offering). Separate future phase.

**Deployment note:** backend runs as a Docker image on the Hetzner box (`lookinsight-neo4j` + `lookinsight-backend` containers; Neo4j bolt is localhost-only). Gate B only takes effect after an image rebuild/redeploy, and the active incremental entry point that calls `detect_clusters` must be confirmed first (`compute_all` is deprecated; this signal was written by the `v1.7-incremental` path).

Sequencing: B (+tests) → C backtest → D (dry-run → commit). Every DB-affecting step is dry-run + explicit approval. Frozen 170/173 never mutated.
Plans: TBD (defined during /paul:plan)

**v1.6 Forward-going mcap capture** (1.6.0)
Status: ✅ Complete
Completed: 2026-04-20
Phases: 1 of 1 complete

**Outcome:** `_compute_one` now fetches SEC XBRL shares outstanding inline at signal creation; new SignalPerformance nodes carry `mcap_at_signal_true` + 5 provenance sidecars. 55/56 immature rows populated on first recompute (1 unresolvable XBRL). Matured rows unchanged. All mcap gaps from v1.4 are now closed.

### v1.6 Phase

| Phase | Name | Plans | Status | Completed |
|-------|------|-------|--------|-----------|
| 16 | Inline XBRL mcap at compute_all time | 1/1 | ✅ Complete | 2026-04-20 |

**v1.5 Signal Tier Extension — small_cap + large_cap** (1.5.0)
Status: ✅ Complete (tier adoption REJECTED; midcap remains sole strong_buy tier)
Completed: 2026-04-20
Phases: 3 of 3 complete

**Theme:** Extend strong_buy classification to recognize small-cap and large-cap insider clusters as distinct tiers, IF the data supports it under p<0.05 Bonferroni. Reuses v1.4's XBRL mcap + audit infrastructure.

**Scope anchors:**
- 299 qualifying clusters exist in raw pool beyond the 142 current strong_buys (2+ buyers, ≥$100K, GENUINE P).
- Rough breakdown by ratio-estimate mcap: 44 micro (skip), 60 small, 50 immature midcap (auto-mature over time), 92 large, 53 null.
- Adoption gate: p<0.05 Bonferroni, same discipline as v1.4 Phase 11.
- v1.2 matured-immutability preserved throughout; new tiers are additive via `methodology_version='v1.5'`.

### Phases

| Phase | Name | Plans | Status | Completed |
|-------|------|-------|--------|-----------|
| 13 | XBRL mcap backfill for tier candidates | 1/1 | ✅ Complete | 2026-04-20 |
| 14 | Per-tier hit-rate + alpha analysis | 1/1 | ✅ Complete | 2026-04-20 |
| 15 | Tier adoption + methodology tag (decision gate) | 1/1 | ✅ Complete (no adoption) | 2026-04-20 |

### Phase 13: XBRL mcap backfill for tier candidates

**Focus:** Reuse Phase 9's `XBRLClient` and `backfill_mcap_true.py` pattern to fetch ground-truth shares-outstanding × raw Form 4 avg price for the ~299 additional clusters. Output: a staging table / CSV (not SignalPerformance nodes yet — those would imply classification).

### Phase 14: Per-tier hit-rate + alpha analysis

**Focus:** Extended audit CSV over all 441 qualifying clusters (142 existing + 299 candidates). Per-tier (small-cap $100M-$300M, large-cap >$5B, null-mcap) statistical analysis via Fisher's exact + Mann-Whitney U + Bonferroni. Concrete recommendation per tier: adopt or reject.

### Phase 15: Tier adoption decision gate

**Focus:** If Phase 14 shows a tier clears significance, extend `conviction_tier` enum and re-run compute_all to materialize new SignalPerformance nodes tagged `methodology_version='v1.5'`. If no tier clears, document and close v1.5 without new tiers. **Decision pause for user review** before any product-defining enum extension.

**v1.4 Signal Quality Audit — ground-truth mcap + per-signal post-mortem** (1.4.0)
Status: ✅ Complete
Completed: 2026-04-20
Phases: 4 of 4 complete

**Theme:** Stop relying on price-ratio estimates for historical market cap; ground-truth every signal against primary-source SEC data, then analyze each signal individually and redesign filters only where the data supports it (p<0.05 vs baseline). Trigger: reviewing DNA (Ginkgo Bioworks 2024-05-15) exposed that a distressed post-reverse-split penny stock had been mis-labeled `$1B–$3B midcap` — the ratio estimate folded a 40-for-1 reverse split and dilution into a single wrong number.

**Scope anchors:**
- Replace `current_mcap × (signal_price / current_price)` with SEC EDGAR XBRL-sourced shares outstanding × raw Form 4 execution price.
- Per-signal audit CSV for all 142 mature strong_buy signals (one row each, deterministic fields, no human interpretation yet).
- Per-loser root-cause tagging + p-value-tested filter candidates.
- Implement validated filters with a `methodology_version` column; keep v1.1 numbers tagged as such; respect v1.2 immutability.
- No client correction note in this milestone (deferred to v1.5).

### Phases

| Phase | Name | Plans | Status | Completed |
|-------|------|-------|--------|-----------|
| 9 | Ground-truth market cap (SEC XBRL) | 1/1 | ✅ Complete | 2026-04-20 |
| 10 | Per-signal audit template | 1/1 | ✅ Complete | 2026-04-20 |
| 11 | Classification + significance testing | 1/1 | ✅ Complete | 2026-04-20 |
| 12 | Filter redesign + re-export (methodology_version) | 1/1 | ✅ Complete | 2026-04-20 |

### Phase 9: Ground-truth market cap (SEC XBRL)

**Focus:** Build a small EDGAR XBRL client to fetch `dei:EntityCommonStockSharesOutstanding` per CIK from `data.sec.gov/api/xbrl/companyfacts/CIK{padded}.json`. For each of the 142 mature strong_buy signals, pick the shares-outstanding value reported in the quarter containing or closest-prior-to `signal_date`. Store as immutable `mcap_at_signal_true` (= `raw_execution_price × shares_outstanding`). Backfill existing 142 signals; add idempotency test.
Plans: TBD (defined during /paul:plan)

### Phase 10: Per-signal audit template

**Focus:** Produce `signal_audit_v1_4.csv` — 142 rows × 20+ columns. All fields computed from stored data (ingest, price_series, SPY, XBRL shares). Deterministic; zero human judgment in Phase 10. Columns include per-signal earnings proximity, pre-cluster officer sells (180d), post-signal officer sells (90d), volatility at signal, SPY return during hold, raw and adjusted returns, industry, true mcap. Output ready for Phase 11 pattern mining.
Plans: TBD (defined during /paul:plan)

### Phase 11: Classification + significance testing

**Focus:** For each of the ~47 losing signals, tag root-cause categories. Then for each candidate filter, compute hit rate and alpha of the excluded sub-pool + the remaining sub-pool; p-value vs baseline (66.9% HR, +8.72% alpha). Reject filters that don't clear p<0.05. Output: audit report markdown with validated filter candidates and per-signal tags.
Plans: TBD (defined during /paul:plan)

### Phase 12: Filter redesign + re-export

**Focus:** Implement validated filters (only those that passed Phase 11). Add `methodology_version` column to SignalPerformance ('v1.1' for existing matured, 'v1.4' for new). Regenerate exported CSV/Parquet with both methodology versions represented. Update DATA_DICTIONARY.md. v1.2 matured-immutability invariant holds: no existing matured row mutates.
Plans: TBD (defined during /paul:plan)

## Backlog (not scheduled)

### Operations
- [ ] Daily auto-ingest (cron/scheduler)
- [ ] Signal alert system (new strong_buy → notify)
- [ ] Price/market cap freshness automation
- [ ] Monitoring/health checks

### Scale
- [ ] First paid institutional client
- [ ] Neudata marketplace listing
- [ ] Historical data licensing
- [ ] Extended coverage (Jan–Apr 2024 next; 2023 after)
- [ ] S3 bucket signal delivery
- [ ] Per-fund delivery / outreach (was v1.1 Phase 6, dropped; revisit when cadence is defined)

### Correctness / Research
- [ ] **Automated control-vehicle gate (deferred from Phase 21)** — exclude controlled permanent-capital vehicles / holdco shells from cluster formation. Revisit only at >=3-4 confirmed examples (currently n=1, LOGC). Sound design = 13D-control (`ActivistFiling`) + >=30% of shares outstanding (XBRL), fail-open on unconfirmed ownership. Optional companion: primary-issuance prefilter Rule 23 (rights offering/subscription/PIPE/backstop footnote scan).
- [ ] Window size experiment (30d vs 40d) — needs non-destructive analysis approach
- [ ] Industry enrichment beyond SEC SIC (24% SIC-null rate in Phase 4 export)

## Completed Milestones

<details>
<summary>v1.3 Pipeline Simplification — strong_buy only — 2026-04-20 (1 phase, 1 plan)</summary>

| Phase | Name | Plans | Status |
|-------|------|-------|--------|
| 8 | Strong_buy-only pipeline | 1/1 | ✅ Complete |

**Outcome:** SignalPerformance now only holds strong_buy buy rows. 372 legacy rows deleted. 142 mature strong_buy preserved byte-identically. `compute_all`, `snapshot_service`, and signal_performance API route all cleaned. 3 new regression tests.

Commit: `edf6a41`
Archive: `.paul/milestones/v1.3.0-ROADMAP.md`

</details>

<details>
<summary>v1.2 Signal Integrity — matured immutability — 2026-04-20 (1 phase, 1 plan)</summary>

| Phase | Name | Plans | Status |
|-------|------|-------|--------|
| 7 | mcap snapshot (matured immutability) | 1/1 | ✅ Complete |

**Outcome:** `compute_all` now preserves matured `SignalPerformance` nodes byte-identically. 408 matured rows verified unchanged across a live recompute. 4 new regression tests.

Commit: `df2bb8f`
Milestone log: `.paul/MILESTONES.md`

</details>

<details>
<summary>v1.1 Hedge Fund Research Delivery — 2026-04-20 (2 phases shipped, 1 dropped)</summary>

| Phase | Name | Plans | Status |
|-------|------|-------|--------|
| 4 | Signal Data Export | 1/1 | ✅ Complete |
| 5 | Research Brief (Content) | 1/1 (05-02 PDF closed) | ✅ Complete |
| 6 | Per-Fund Delivery | — | Dropped from scope |

**Artifacts:** 141-signal CSV + Parquet + data dictionary; 533-line methodology brief with academic foundation; 3 charts + stats.json.

Full archive: `.paul/milestones/v1.1.0-ROADMAP.md`
Milestone log: `.paul/MILESTONES.md`

</details>

<details>
<summary>v1.0 Signal Quality — 2026-04-18 (3 phases, 14 plans)</summary>

| Phase | Name | Plans | Status |
|-------|------|-------|--------|
| 1 | Data Pipeline | (pre-PAUL) | ✅ Complete |
| 2 | Signal Quality | 6/6 | ✅ Complete |
| 3 | Institutional Positioning | 8/8 | ✅ Complete |

**Headline result:** 141 mature strong_buy signals, 67.4% HR, +9.0% alpha vs SPY (p<0.001).
Data range: Jun 2024 – Apr 2026 (22 months). Production deployed at ci.lookinsight.ai.

Full archive: `.paul/milestones/v1.0.0-ROADMAP.md`
Milestone log: `.paul/MILESTONES.md`

</details>

---
*ROADMAP.md — Updated when phases complete or scope changes*
*Last updated: 2026-06-09 — Phase 21 complete (reduced scope): LOGC removed + CIK blocklisted. Automated control-vehicle gate (B/C) descoped to backlog — n=1, revisit at >=3-4 examples.*
