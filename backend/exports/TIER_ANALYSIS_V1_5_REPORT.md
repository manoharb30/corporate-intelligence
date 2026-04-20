# v1.5 Signal Tier Extension — Phase 14 Report

*Generated: 2026-04-20*
*Input: `backend/exports/out/tier_candidates_v1_5.csv` (441 total candidate clusters).*
*Baseline: midcap tier's matured pool (n_mature = 137).*
*Bonferroni n = 3 (small + large + small+large combined).*

## Per-tier stats (matured pool)

| Tier | n_mat | Hit rate | Avg return | Avg alpha | p_fisher | p_mannwhitney | p_bonferroni | Verdict |
|---|---|---|---|---|---|---|---|---|
| **small** | 51 | 52.94% | +11.77% | +7.79% | 0.1767 | 0.2221 | 0.5301 | **REJECT** |
| **midcap** | 137 | 64.96% | +12.64% | +7.53% | — | — | — | **baseline** |
| **large** | 61 | 52.46% | +7.58% | +2.73% | 0.1148 | 0.2192 | 0.3443 | **REJECT** |
| **small+large (extended)** | 112 | 52.68% | +9.50% | +5.05% | 0.0529 | 0.1267 | 0.1587 | **REJECT** |

## Recommendations

### `small_cap_strong_buy` tier (ground-truth mcap $100M–$300M)
- n_mature = 51, hit rate = 52.94%, avg return = +11.77%, avg alpha = +7.79%
- vs baseline (midcap, 64.96% hr): p_fisher = 0.176688, p_bonferroni = 0.530064
- **Verdict: REJECT**

### `large_cap_strong_buy` tier (ground-truth mcap > $5B)
- n_mature = 61, hit rate = 52.46%, avg return = +7.58%, avg alpha = +2.73%
- vs baseline (midcap): p_fisher = 0.114778, p_bonferroni = 0.344334
- **Verdict: REJECT**

### Combined `small + large` (if we adopt both)
- n_mature = 112, hit rate = 52.68%, avg return = +9.50%
- vs baseline: p_fisher = 0.052894, p_bonferroni = 0.158682
- **Verdict: REJECT**

## Phase 15 guidance

*Adoption rule: a tier is adopted only if p_fisher_bonferroni < 0.05.*

**No tiers pass the p<0.05 Bonferroni bar. Phase 15 closes v1.5 without new tier values.** This is a defensible outcome — the signal quality data for candidate tiers is either similar-to or indistinguishable-from the midcap baseline.

The v1.1 headline remains the defining methodology. Growing the dataset further (additional months) is still the highest-leverage move for future tier or filter refinements.
