# Phase 21 — Control-Vehicle Exclusion Gate

Milestone: v1.7 Signal Pipeline Reconciliation
Status: ✅ **COMPLETE (reduced scope)** — 2026-06-09
Created: 2026-06-09

> **OUTCOME — we deliberately did NOT build the automated gate.** On expert/accounting
> re-review the buyer-attribute heuristic was too fragile (self-reported 10% checkbox;
> indirect ownership collides with legitimate family LPs/trusts; brittle fund regex;
> $-dominance is a weak control proxy), and we'd be generalizing an automated rule from
> **n = 1** — overfitting, with the downside that a false positive prunes a good signal
> from the core cohort. RLI + GSHD (the other recent clusters) were vetted as legitimate.
>
> **DELIVERED:** (1) deterministic CIK blocklist — `EXCLUDED_CIKS = {"0002064307"}` +
> guard in `process_incremental` + filter in `detect_clusters`; (2) removed the LOGC
> SP node `CLUSTER-0002064307-2026-06-03` (immature; cohort 173 mature unchanged,
> immature 24->23; underlying Form 4 tx left GENUINE). Committed with `MIN_AGE_DAYS`
> 97->90 fix. **Still outstanding: backend image redeploy for the blocklist to go live.**
>
> **DEFERRED to backlog (revisit at >=3-4 examples):** the automated control-vehicle gate
> (sound form = 13D-control + >=30% shares-outstanding, fail-open) and primary-issuance
> prefilter Rule 23. The design notes below are retained for that future work.

Original scope: Workstreams **B + D** (A deferred) — B/C now deferred; only D + blocklist shipped.

## Trigger
LOGC (ContextLogic Holdings, `CLUSTER-0002064307-2026-06-03`) entered the cohort as a strong_buy when its day-90... no — entered as an immature strong_buy via the `v1.7-incremental` path (computed 2026-06-07). It is a genuine 2-insider open-market cluster:
- **Raja Bobbili** (Abrams Capital, director + 10% owner) — 6 buys 5/19–5/28, ~$2.45M, indirect via estate-planning vehicle / Abrams + Riva funds.
- **Paul S. Levy** (JLL Partners founder, director) — 5 buys 6/1–6/5, ~$1.13M.
- Cluster total **$3.58M**, mcap **~$400M** (verified: 45.7M sh × ~$9; stored `market_cap` $380M, not inflated).

It passes every mechanical filter (2+ insiders, $100K+, $300M–$5B midcap, genuine P). But it is an **Abrams-controlled permanent-capital vehicle**: post-US-Salt ($907.5M) reverse-merger holdco, ~$2.7–2.9B NOLs, affiliated funds hold ~40% of shares, concurrent **$115M rights offering at $8**.

## Why neither the LLM nor SIC catches it (empirically confirmed)
- Live Haiku classifier (`claude-haiku-4-5`) returns **GENUINE** for Bobbili's buy **even with the Abrams/Riva fund-control footnote in the payload** — rubric treats weighted-avg-range fills as a strong GENUINE signal and disclaimed-beneficial-ownership as "yellow flag, not disqualifying." The transaction genuinely *is* open-market.
- SEC SIC is still `5961 – Retail-Catalog & Mail-Order Houses`, entityType `operating` — never reclassified after the Wish sale. A blank-check/SIC gate would miss it.
- Conclusion: the disqualifier is **company-level control**, not transaction mechanics → requires a deterministic eligibility gate, not a classifier change.

## Workstream B — Control-vehicle eligibility gate

> **Active-path finding (2026-06-09, verified):** the LIVE writer is `InsiderClusterService.process_incremental()` (line 584; called by `ingest_genuine_p_to_neo4j.py:293`, stamps `methodology_version='v1.7-incremental'` = the LOGC record). It forms clusters **itself** — NOT via `detect_clusters` — through `_cluster_state_for_window()` (line 749), which currently returns only `{n, v}`. The strong_buy gate is at lines **666–683**. So the gate MUST live in the path `process_incremental` uses; editing only `detect_clusters` would miss the live ingest entirely. `detect_clusters` still feeds `feed_service` + `scanner` + `signal_performance_service`, so both need it.

- **Design:** a shared helper `_control_vehicle_exclusion(cik, anchor_date, today, from_anchor, total_value) -> (excluded: bool, reason: str|None)`, called by **both** `process_incremental` (before the line-682 strong_buy write) **and** `detect_clusters`. It reuses the same window logic as `_cluster_state_for_window` and projects per-insider aggregates (`insider_name`, `sum(total_value)`, `is_ten_percent_owner`, `ownership_type`, `footnotes`) — all already persisted by `ingest_genuine_p_to_neo4j.py`.
- **"Control-affiliated fund insider"** = `is_ten_percent_owner == true` AND `ownership_type == 'I'` AND footnote/nature matches `(Capital Partners|Capital Management|L\.?P\.?|general partner|managing member|Partners [IVX]+|\bfund\b)` (case-insensitive).
- **Exclude cluster** if: control-affiliated fund insiders ≥ **50% of cluster $ value** (Bobbili = 68%), OR all distinct buyers are control-affiliated.
- **Confirmation layer** (reduce false positives): affiliated funds ≥ **~30% of shares outstanding** (shares ≈ `market_cap / price`); source preference 13D/13G `ActivistFiling` → footnote share-sum → role-heuristic-with-log.
- **Guardrail:** direct (`ownership_type='D'`) 10% owners (founder/CEO conviction) are NEVER flagged.
- **Backstop:** CIK exclusion-list constant, seeded with LOGC `0002064307`.
- **Output:** structured skip-reason logged for audit.
- **Tests:** LOGC-shaped synthetic cluster → excluded; founder direct-10%-owner cluster → retained.
- **Config:** thresholds + fund-language regex + exclusion-list CIKs in a tunable constants block.

## Workstream C — Validation backtest (mandatory gate before D commits)
Read-only run of gate B against all **197** existing `SignalPerformance` (173 mature + 24 immature). List every signal it *would* exclude; review for false positives with founder. Tighten thresholds if anything good is threatened. **Matured cohort frozen — gate is forward-only; no retroactive reclassification. Backtest is analysis only, zero mutation.**

## Workstream D — Remove the live immature LOGC signal
- Add CIK `0002064307` to exclusion list (prevents re-formation).
- `DETACH DELETE` `SignalPerformance {signal_id:'CLUSTER-0002064307-2026-06-03'}` + the `InsiderCluster` node.
- Refresh snapshot/feed so the Signal List drops it.
- **Do NOT** set `classification_override='NOT_GENUINE'` on Bobbili/Levy transactions — they are genuine open-market buys. This is a **company-eligibility** exclusion, a deliberate divergence from the `invalidate_codi_*.py` precedent (which relabels transactions).
- It is **immature** → the 173 mature dashboard stats are unaffected; only the immature feed/count changes.
- Dry-run (print what will be deleted) → commit on explicit approval.

## Deferred — Workstream A
Primary-issuance prefilter **Rule 23** in `classify_p_with_prefilter.py → prefilter()`: footnote scan for `rights offering / subscription / private placement / PIPE / backstop / registered direct / securities purchase agreement / standby purchase` → `NOT_GENUINE`. Hygiene only; does NOT catch LOGC (footnotes silent on the offering). Separate future phase.

## Deployment note
Backend runs as a Docker image on the Hetzner box (`lookinsight-backend` + `lookinsight-neo4j` containers; Neo4j bolt localhost-only — run scripts via `docker exec -w /app/backend lookinsight-backend`). Gate B takes effect only after image rebuild/redeploy. **Confirm the active incremental entry point that calls `detect_clusters` first** (`compute_all` is deprecated; this signal was written by the `v1.7-incremental` path).

## Sequencing & safety
1. B (+ unit tests) — code only, no DB writes → `pytest`.
2. C backtest — read-only → review with founder.
3. Deploy — rebuild/redeploy backend image after confirming active entry point.
4. D removal — dry-run → commit.

Every DB-affecting step: dry-run + explicit approval. Frozen 170/173 never mutated.
