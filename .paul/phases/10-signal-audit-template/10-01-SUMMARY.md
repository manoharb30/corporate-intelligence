---
phase: 10-signal-audit-template
plan: 01
status: APPLIED
started: 2026-04-20
completed: 2026-04-20
---

# Plan 10-01 — Per-signal audit template

## Outcome

**APPLY: DONE** — all four acceptance criteria satisfied. 142-row × 33-column deterministic CSV generated; data dictionary complete; sanity analysis reveals that naive midcap-filter-on-true-mcap would LOSE alpha (Phase 11 territory).

## Task results

| Task | Status | Verify |
|---|---|---|
| 1. Build audit CSV generator (`exports/audit_v1_4.py`) | DONE | PASS — 142 rows, 33 cols, MD5 stable across re-runs |
| 2. Data dictionary | DONE | PASS — every column documented; caveats section covers xbrl_post_signal_approx + GAM nulls + split-adjusted price |
| 3. Sanity analysis (filter on true mcap → headline) | DONE | PASS — result surprising (tighter filter = worse performance); recorded, no decision |

## Artifacts

- `backend/exports/audit_v1_4.py` (new, ~330 lines)
- `backend/exports/AUDIT_V1_4_DATA_DICTIONARY.md` (new, complete column ref + caveats)
- `backend/exports/out/signal_audit_v1_4.csv` (142 × 33)
- `backend/exports/out/signal_audit_v1_4.parquet` (same)

## Verification evidence

**Determinism (AC-3):**
```
MD5 (signal_audit_v1_4.csv) = 35f57c2dacd76653d0121d8d5225b248
[re-run]
MD5 (signal_audit_v1_4.csv) = 35f57c2dacd76653d0121d8d5225b248   ← identical
```

**Spot checks (AC-2) against Phase 9 corrections:**

| Ticker | true_mcap | is_midcap | would_remain | return | hit |
|---|---|---|---|---|---|
| DNA (Ginkgo) | $1675M | true | true | -66.5% | False |
| ANDG | $202M | **false** | **false** | +11.3% | True |
| RPAY | $25M | **false** | **false** | +48.4% | True |
| ONDS | $49M | **false** | **false** | +3.5% | True |
| FNKO | $369M | true | true | -29.5% | False |
| GAM | null | false | false | +14.1% | True |
| SEI | $511M | true | true | +59.6% | True |
| MRVI | $531M | true | true | -1.6% | False |
| CRGY | $2820M | true | true | -17.2% | False |

## Key finding for Phase 11 (surprising, do NOT act on yet)

Applying the existing midcap filter ($300M–$5B) to the ground-truth `mcap_at_signal_true_usd` would:
- **Reduce** pool from 142 → 132 signals (10 would drop)
- **Reduce** hit rate: 66.9% → 65.9%
- **Reduce** avg return: +14.04% → +12.61%
- **Reduce** avg alpha: +8.72% → +7.42%

The 10 dropped signals had:
- **80% hit rate, +32.9% avg return** — better than the pool they'd be leaving
- 8 of 10 are winners: PHAT +172%, HUMA +60%, RPAY +48%, ANNX +27%, GAM +14%, ANDG +11%, TFX +11%, ONDS +3.5%
- 2 are losers: HXL −1%, COLD −18%

**Interpretation (provisional):** The old ratio-estimate mcap was, effectively, a different filter — not a worse one. Its noisy boundaries happened to admit small-cap and the occasional large-cap signals that performed well. Tightening to ground-truth midcap would remove profitable signals.

**Candidates Phase 11 should test** (not in scope for Phase 10):
1. Is midcap the right filter at all? What hit rate / alpha do the 8 below-midcap winners have vs. the 132 midcap-remaining pool?
2. Should the band widen (e.g., $100M–$5B) given small caps performed well?
3. Are the 2 above-midcap outliers (HXL, COLD) flukes, or does the large-cap band need revisiting?
4. What single factor (if any) distinguishes the winners from the losers in the small-cap subpool?

All of this needs p-value validation, not point estimates — Phase 11's job.

## Deviations from plan

None. All tasks executed as specified.

## Files modified

- `backend/exports/audit_v1_4.py` (new)
- `backend/exports/AUDIT_V1_4_DATA_DICTIONARY.md` (new)
- `backend/exports/out/signal_audit_v1_4.csv` (new)
- `backend/exports/out/signal_audit_v1_4.parquet` (new)

No changes to Neo4j, services, or any existing code.

## Next

`/paul:unify .paul/phases/10-signal-audit-template/10-01-PLAN.md` to close the loop. Phase 11 will consume `signal_audit_v1_4.csv` and the finding recorded above as its starting input.
