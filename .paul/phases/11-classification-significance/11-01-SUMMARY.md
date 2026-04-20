---
phase: 11-classification-significance
plan: 01
status: APPLIED
started: 2026-04-20
completed: 2026-04-20
---

# Plan 11-01 — Classification + significance testing

## Outcome

**APPLY: DONE** — all four acceptance criteria satisfied. Central finding: **zero filter candidates pass Bonferroni-adjusted p < 0.05** across 22 tested. The honest scientific conclusion: the 142-signal pool is too small to support new filter discovery under strict multiple-testing discipline. Phase 12 should *not* add new filters; Phase 10's "don't tighten midcap" recommendation is formally codified as REJECT with evidence.

## Task results

| Task | Status | Verify |
|---|---|---|
| 1. Statistical filter-candidate harness | DONE | PASS — 22 rows in output CSV, each with Fisher's exact + Mann-Whitney U + Bonferroni; sorted; deterministic |
| 2. Per-loser detail printer | DONE | PASS — 47 blocks (matches `(hit_90d == false).sum()`), each with `root_cause_tag: unclassified` placeholder |
| 3. Synthesis audit report | DONE | PASS — every recommendation cites p_bonferroni; adopt/reject/inconclusive classification made |

## Artifacts

- `backend/exports/audit_v1_4_stats.py` (new, ~290 lines)
- `backend/exports/audit_v1_4_loser_detail.py` (new, ~130 lines)
- `backend/exports/AUDIT_V1_4_REPORT.md` (new, hand-authored synthesis)
- `backend/exports/out/audit_v1_4_filter_candidates.csv` (22 × 15)
- `backend/exports/out/audit_v1_4_losers.md` (47 blocks)

## Headline finding

**Zero filters pass Bonferroni-adjusted p < 0.05.**

| Rank | Filter | Raw p_fisher | p_bonferroni | Verdict |
|---|---|---|---|---|
| 1 | industry bottom-quartile by hit rate | 0.0153 | 0.3364 | inconclusive (data-driven threshold) |
| 4 | mcap_at_signal_true < $300M | 0.0955 | 1.0000 | REJECT (excluded pool is 100% hits) |
| ... | all others | > 0.25 raw | 1.0000 | REJECT |

**Degenerate candidates:**
- `days_to_next_earnings > 60` → excludes 0 rows (v1.0 earnings filter already operational on every mature strong_buy — confirms correctness)
- 2 other candidates excluded 1 row → untestable (insufficient degrees of freedom)

## Per-loser qualitative review — status

47 loser blocks emitted. **All tagged `root_cause_tag: unclassified`** per plan (no auto-tagging). Manual review is a separate activity; Phase 11 provides the data, not the interpretation.

## Recommendations for Phase 12 (from the report)

1. **Do NOT adopt the naive true-mcap midcap filter.** Drops 10 winners (80% HR, +33% return).
2. **Do NOT adopt any new hard filter.** None cleared the p<0.05 Bonferroni bar.
3. **Keep v1.0 earnings rule** (confirmed operational).
4. **Keep `has_hostile_activist` as informational flag** (no filter-grade evidence).
5. **Methodology versioning:** still add the `methodology_version` column to SignalPerformance as planned. v1.4 value will be schema-only (no semantic filter change).
6. **Product implication:** growing the dataset (more backfilled months) is the next highest-leverage move for any future filter discovery — it's a statistical precondition, not a chore.

## Deviations from plan

None on acceptance criteria. The "headline" section of the report included a product-implication paragraph (section 5) that went beyond pure p-value reporting — included because Phase 12 needs guidance on what NOT to do, and "we need more data" is an honest, concrete prescription.

## Files modified

- `backend/exports/audit_v1_4_stats.py` (new)
- `backend/exports/audit_v1_4_loser_detail.py` (new)
- `backend/exports/AUDIT_V1_4_REPORT.md` (new)
- `backend/exports/out/audit_v1_4_filter_candidates.csv` (new)
- `backend/exports/out/audit_v1_4_losers.md` (new)

No changes to Neo4j. No changes to services. No mutations of existing exports.

## Next

`/paul:unify .paul/phases/11-classification-significance/11-01-PLAN.md` to close the loop. Phase 12 will be minimal — implement `methodology_version` column + decide display treatment of `mcap_at_signal_true_usd` vs `market_cap`. No new filters.
