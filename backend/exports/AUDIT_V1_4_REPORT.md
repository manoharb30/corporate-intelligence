# v1.4 Signal Quality Audit — Phase 11 Report

*Generated: 2026-04-20*
*Input: `backend/exports/out/signal_audit_v1_4.csv` (142 mature strong_buy signals)*
*Statistical tests: Fisher's exact (hit rate), Mann-Whitney U (return distribution), Bonferroni correction for multiple testing (n=22).*

---

## 1. Headline comparison

| Methodology | Signals | Hit rate | Avg return | Avg alpha |
|---|---|---|---|---|
| v1.1 (current, ratio-estimate mcap) | 142 | 66.90% | +14.04% | +8.72% |
| v1.4 naive (true-mcap midcap filter) | 132 | 65.94% | +12.61% | +7.42% |

The naive swap underperforms. Phase 10 established that the 10 dropped signals had 80.0% hit rate / +32.9% avg return — alpha contributors, not drag.

---

## 2. Filter candidates tested

22 candidates across 8 axes. Bonferroni denominator: 22. Adoption bar: `p_fisher_bonferroni < 0.05`.

### Top 10 by Bonferroni-adjusted p-value

| Rank | Axis | Threshold | Direction | n_excl | HR retained | HR excluded | Δpp | p_fisher | p_mw | p_bonf |
|---|---|---|---|---|---|---|---|---|---|---|
| 1 | industry | — (bottom quartile by hit rate) | exclude bottom-q | 6 | 69.12% | 16.67% | +52.45 | **0.0153** | **0.0081** | 0.3364 |
| 2 | mcap_at_signal_true_usd | $100M | exclude_below | 3 | 66.19% | 100.00% | −33.81 | 0.5508 | 0.5992 | 1.0000 |
| 3 | mcap_at_signal_true_usd | $200M | exclude_below | 4 | 65.94% | 100.00% | −34.06 | 0.3020 | 0.3791 | 1.0000 |
| 4 | mcap_at_signal_true_usd | $300M | exclude_below | 7 | 65.19% | 100.00% | −34.81 | 0.0955 | 0.0584 | 1.0000 |
| 5 | mcap_at_signal_true_usd | $500M | exclude_below | 34 | 66.67% | 67.65% | −0.98 | 1.0000 | 0.9143 | 1.0000 |
| 6 | mcap_at_signal_true_usd | $3B | exclude_above | 17 | 66.40% | 70.59% | −4.19 | 1.0000 | 0.9149 | 1.0000 |
| 7 | mcap_at_signal_true_usd | $5B | exclude_above | 3 | 67.63% | 33.33% | +34.29 | 0.2545 | 0.2829 | 1.0000 |
| 8 | pre_cluster_sellers_count_180d | 1 | exclude if ≥ | 9 | 66.17% | 77.78% | −11.61 | 0.7178 | 0.1339 | 1.0000 |
| 9 | pre_cluster_sellers_count_180d | 2 | exclude if ≥ | 3 | 67.63% | 33.33% | +34.29 | 0.2545 | 0.6873 | 1.0000 |
| 10 | post_signal_sells_count_90d | 1 | exclude if ≥ | 3 | 67.63% | 33.33% | +34.29 | 0.2545 | 0.3368 | 1.0000 |

*Full table: `backend/exports/out/audit_v1_4_filter_candidates.csv`.*

### Degenerate / untestable candidates

- `days_to_next_earnings_at_signal > 60` → **excludes 0 signals**. Confirms the v1.0 earnings filter is already applied to every mature strong_buy row.
- `days_from_last_earnings_at_signal < 7` → **excludes 0 signals**.
- `pre_cluster_sellers_count_180d ≥ 3` → excludes 1 signal (DNA). Can't compute Fisher on 1-row contingency.
- `post_signal_sells_count_90d ≥ 2` → excludes 1 signal. Untestable.

---

## 3. Recommendations

**Adoption bar:** `p_fisher_bonferroni < 0.05`.

### Adopt
**None.** Zero candidates passed the Bonferroni bar.

### Reject (evidence-backed)
- **Naive true-mcap midcap filter ($300M–$5B)** — Phase 10 showed it drops 10 signals with 80% HR / +33% return. Bonferroni tests on its lower and upper bounds separately (ranks 4 and 7 above) show p_bonferroni = 1.0 for both. **Do not tighten the midcap filter using ground-truth mcap.**
- **Exclude small caps** (`mcap_at_signal_true_usd < $100M/$200M/$300M`) — excluded sub-pools are 100% hits (ranks 2–4). Small-cap signals in our pool are perfect winners. Tightening would remove winners.
- **`has_hostile_activist` as hard filter** — raw `p_fisher = 0.73`. No signal. Keep as informational flag, not a filter.
- **`days_to_next_earnings > 60`** — redundant. Every mature strong_buy already has `days_to_next_earnings ≤ 60` (confirms v1.0 rule is operational).

### Inconclusive (raw significance, Bonferroni-fails — worth revisiting with more data)
- **Industry bottom-quartile exclusion** — raw `p_fisher = 0.015`, `p_mannwhitney = 0.008`. Bonferroni-adjusted = 0.336. Excluded pool of 6 signals had 16.7% HR vs 69.1% retained. *Caveat: this threshold is data-driven (bottom quartile computed from the same 142 pool); interpret with skepticism. The large raw-p delta suggests industry concentration may matter, but multiple-testing discipline says we need independent validation.*
- **Volatility > 75% annualized** — raw `p_mannwhitney = 0.015` (distribution difference), but `p_fisher = 0.475` (hit rate similar). Volatility affects return *spread* more than win/loss flip. Not actionable as a binary filter.
- **Volatility > 50%** — raw `p_mannwhitney = 0.021`, `p_fisher = 1.0`. Same story as above.

---

## 4. Per-loser root-cause distribution

`backend/exports/out/audit_v1_4_losers.md` contains one block per losing signal (47 total, sorted worst → best by return_90d_pct). Every block has `root_cause_tag: unclassified` as a placeholder for manual review.

**Automated tag distribution is NOT populated in this report** — per plan, Phase 11 does not auto-fill root-cause tags. Human review required to validate DNA-like patterns on a per-signal basis before any filter built from them can be trusted.

---

## 5. Implications for Phase 12

### Concrete guidance
1. **Do NOT implement the naive midcap filter on `mcap_at_signal_true_usd`.** Evidence is clear: dropping small-caps removes winners (rank 4 excluded pool = 100% hits). The current `market_cap` ratio estimate, flawed as it is on individual signals, is empirically a no-worse filter at the pool level.

2. **Do NOT implement any new hard filter** from the tested set. None cleared the adoption bar, and multiple-testing discipline prevents cherry-picking the few with low raw p-values.

3. **Keep the v1.0 earnings-proximity rule** — confirmed operational (zero mature strong_buy signals violate it).

4. **Keep `has_hostile_activist` as informational flag** — no filter-grade evidence.

5. **Methodology versioning recommendation:** add the `methodology_version` column to SignalPerformance as planned. Because Phase 11 did not identify any new filter to adopt, v1.4's `methodology_version` value for new signals will be `'v1.4'` in schema only — semantically identical to `'v1.1'` until/unless a filter is adopted in a later milestone.

### What this means for the product
- **The current signal quality IS the signal quality** on this dataset size. 142 signals is too small to support new filter discovery under strict multiple-testing discipline.
- **Growing the dataset is the next highest-leverage move.** Extended coverage (Jan–Apr 2024 backfill + 2023) is not a clerical task — it's a statistical precondition for any filter refinement.
- **Use the audit CSV + loser detail as customer documentation.** The transparency of this audit (142 signals reviewed, 47 losers itemized, 22 filters tested) is itself a product asset. Can be referenced in future client conversations.

### What this does NOT mean
- The ratio-estimate `market_cap` field is still wrong on individual signals (ANDG, RPAY, ONDS, etc. are off by 60–93%). `mcap_at_signal_true_usd` remains the correct data point for display and reporting, even if we don't use it for filtering. Phase 12 will need to decide: swap display values, or keep both with clear labeling.

---

## 6. Reproducibility

```bash
cd backend
venv/bin/python -m exports.audit_v1_4_stats
venv/bin/python -m exports.audit_v1_4_loser_detail
```

Outputs:
- `backend/exports/out/audit_v1_4_filter_candidates.csv` (22 rows × 15 cols; deterministic)
- `backend/exports/out/audit_v1_4_losers.md` (47 blocks; deterministic order)

This report is hand-authored, citing the above outputs. No machine-generated facts in this markdown that aren't in the CSVs.
