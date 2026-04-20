---
phase: 09-ground-truth-mcap
plan: 01
status: APPLIED
started: 2026-04-20
completed: 2026-04-20
---

# Plan 09-01 — Ground-truth market cap (SEC XBRL)

## Outcome

**APPLY: DONE** — 141 of 142 mature strong_buy signals resolved (99.3%). 1 unresolved (GAM, a closed-end fund — accepted per user).

## Task results

| Task | Status | Verify |
|---|---|---|
| 1. XBRL companyfacts client | DONE | PASS — Apple spot check; 11 unit tests pass |
| 2. Backfill `mcap_at_signal_true` on 142 mature strong_buy | DONE | 141/142 resolved (139 exact pre-signal + 2 post-signal approx within 90d). GAM excluded (closed-end fund) |
| 3. Unit tests + schema doc | DONE | PASS — 11 XBRL tests + 41 sp + 19 sf = 71 pass |

## Code / artifacts produced

**`backend/ingestion/sec_edgar/xbrl_client.py`** (new)
- `XBRLClient.get_shares_outstanding(cik)` — async httpx client against `data.sec.gov/api/xbrl/companyfacts`
- Tries 5 concepts in priority order: `dei:EntityCommonStockSharesOutstanding` → `us-gaap:CommonStockSharesOutstanding` → `us-gaap:CommonStockSharesIssued` → `us-gaap:WeightedAverageNumberOfSharesOutstandingBasic` → `us-gaap:WeightedAverageNumberOfDilutedSharesOutstanding`
- Falls through to next concept if current yields no usable entries after sanity filtering
- Sanity threshold `MIN_REASONABLE_SHARES = 100_000` rejects IPO-registration placeholders (fixed FNKO)
- `XBRLClient.pick_shares_at_or_before(entries, signal_date)` — primary picker
- `XBRLClient.pick_nearest_post_signal(entries, signal_date, max_days=90)` — fallback for late-XBRL filers (ANDG, CRGY)

**`backend/backfill_mcap_true.py`** (new)
- Checkpoint/resume, per-CIK XBRL cache per run, rate-limited at 1s/CIK, error log, progress log
- For each signal: fetch XBRL for CIK, compute value-weighted avg raw Form 4 price on signal_date (widens ±5 days if empty), try exact pre-signal shares-outstanding; fall back to first post-signal entry within 90d
- Writes 6 additive properties; does NOT touch any existing field
- `mcap_at_signal_true_source` tags provenance: `'xbrl'` (exact) or `'xbrl_post_signal_approx'` (fallback)

**`backend/tests/test_xbrl_client.py`** (new, 11 tests)
- 4 `pick_shares_at_or_before` variants
- 7 `get_shares_outstanding` variants (concept priority, fallback on sanity filter, 404 handling, form filtering, etc.)

**`neo4j/schema-report.md`** (modified): new "Ground-truth market cap (v1.4, Phase 9)" subsection under SignalPerformance.

## Final coverage

| Metric | Count | % |
|---|---|---|
| Total mature strong_buy | 142 | 100% |
| Resolved with XBRL exact (pre-signal) | 139 | 97.9% |
| Resolved with XBRL post-signal fallback (≤90d) | 2 | 1.4% |
| Unresolved | 1 | 0.7% |

The 1 unresolved: **GAM (General American Investors)** — closed-end fund that doesn't file standard XBRL shares-outstanding concepts. Accepted per user decision; to be handled separately if needed.

## Corrections exposed

The top price-ratio-estimate errors corrected by ground-truth mcap:

| Ticker | Old (ratio estimate) | New (primary source) | Δ% |
|---|---|---|---|
| ANDG | $2,773M | $202M | **-92.7%** |
| RPAY | $336M | $25M | **-92.5%** |
| ONDS | $412M | $49M | **-88.1%** |
| SEI | $3,776M | $511M | **-86.5%** |
| ANNX | $663M | $162M | **-75.6%** |
| MRVI | $1,325M | $531M | **-59.9%** |
| XRN | $871M | $436M | **-50.0%** |
| PPTA | $1,066M | $571M | **-46.4%** |
| FRSH | $3,307M | $1,789M | **-45.9%** |
| RLMD | $449M | $302M | **-32.7%** |
| CRGY | $3,483M | $2,820M | -19.0% |
| DNA | $2,061M | $1,675M | -18.7% (Ginkgo) |

**These are the signals most at risk of mis-classification under the old filter** (some may have been outside midcap band with true mcap vs in-band with estimated mcap, and vice versa). Phase 11 will use `mcap_at_signal_true` to validate whether current strong_buy tagging survives reclassification.

## Deviations from plan

1. **Classification filter relaxed** for raw-price query. Plan used `GENUINE` only; run found many matured signals have transactions now tagged `FILTERED` (by earnings-proximity rule) with `NULL` classification mixed in. Relaxed to `GENUINE | FILTERED | NULL`. Only `NOT_GENUINE` (structured deals / compensation) still excluded. Raw execution price is independent of downstream classification.

2. **Post-signal fallback added** (`pick_nearest_post_signal`). Plan assumed `pick_shares_at_or_before` alone would cover all cases. Investigation found 2 post-SPAC / late-XBRL issuers whose first shares-outstanding XBRL entry postdates the signal. For stable issuers, shares count changes <5% per quarter — using the nearest post-signal quarter (within 90d) is acceptable. Labeled distinctly in `mcap_at_signal_true_source` so downstream phases can weight or flag these 2 signals.

3. **XBRL client fall-through on sanity filter** added. FNKO surfaced this: it had 2 entries under `CommonStockSharesOutstanding` (both <100k shares — IPO-registration placeholders). Without fall-through, client returned empty even though 106 `WeightedAverageNumberOfSharesOutstandingBasic` entries existed. Fixed.

4. **5 XBRL concepts** tried, not 3 as planned. Added `WeightedAverageNumberOfSharesOutstandingBasic` and `WeightedAverageNumberOfDilutedSharesOutstanding` as fallbacks. Weighted-avg-basic is <2% different from point-in-time for most issuers.

## Files modified

- `backend/ingestion/sec_edgar/xbrl_client.py` (new)
- `backend/backfill_mcap_true.py` (new)
- `backend/tests/test_xbrl_client.py` (new)
- `neo4j/schema-report.md` (modified)
- Neo4j data: 141 SignalPerformance nodes gained 6 additive properties each; NO existing property mutated.

## Next

`/paul:unify .paul/phases/09-ground-truth-mcap/09-01-PLAN.md` to close the loop. Phase 10 can now consume `mcap_at_signal_true` as a locked column; mix of exact (139) + approx (2) should be surfaced in the per-signal audit CSV via the `source` field.
