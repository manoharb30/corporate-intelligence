# Phase 2: Signal Quality — Discussion Context

## Goals

1. Achieve 70%+ hit rate (90d) on strong_buy signals
2. Retain 100+ signals (80 minimum acceptable)
3. Use ONLY statistically significant findings — no overfitting
4. Few strong exclusion rules, NOT a weighted score
5. Research insight becomes Neudata deliverable as byproduct

## Approach: 3 Evidence-Based Exclusion Rules

Based on research phase findings (3 agents, 6 sub-questions analyzed):

### Rule 1: Exclude post-earnings buys
- **Evidence:** Earnings proximity p=0.003 (strongest predictor)
- **Logic:** Insiders buying 60-90d before next earnings = right AFTER last earnings = buying on public info, no edge
- **Sweet spot:** Mid-quarter buys (30-60d before next earnings) = 91% HR
- **Threshold:** Exclude when distance_to_next_earnings > 60 days (to be validated in backtest)

### Rule 2: Exclude price purgatory zone
- **Evidence:** Stocks 20-50% below 52w high have 58-63% HR
- **Logic:** U-shaped — near highs (momentum) and deeply crashed (mean reversion) both work. Middle = no catalyst, drifting.
- **Threshold:** Exclude when distance_52w_high is between -20% and -50% (to be validated)

### Rule 3: Exclude worst sectors
- **Evidence:** Basic Materials 50% HR, Communication Services 33% HR
- **Logic:** Commodity-driven and media sectors have external factors that override insider conviction
- **Threshold:** Exclude Basic Materials + Communication Services (to be validated — check signal count impact)

## What the research REJECTED (do NOT implement)

| Factor | Why rejected |
|---|---|
| Linear momentum filter | U-shaped — threshold would cut good extremes |
| Sector ETF momentum | p=0.52, no predictive power |
| Volatility | p=0.55, no predictive power |
| Prior insider selling (60d) | Too rare (0.8% of signals) |
| Buyer count / officer % / concentration | Not significant once 2+ threshold met |
| Weighted multi-factor score | Unnecessary complexity — 3 rules achieve the goal |

## Open Questions (resolve in backtest)

- Exact earnings distance threshold: 60d? 55d? 65d?
- Purgatory zone boundaries: -20% to -50%? Or -15% to -45%?
- Sector exclusion impact: how many signals lost? Can we afford it?
- Test rules individually AND stacked
- Confirm no month or sub-segment is entirely wiped out

## Success Criteria

| Metric | Target | Minimum |
|---|---|---|
| Hit rate (90d) | 70%+ | 68% |
| Signals retained | 100+ | 80 |
| Alpha vs SPY | > +5.5% baseline | Maintain |
| Rules count | 3 | Max 4 |

## Source Research

- `.paul/phases/02-signal-quality/research/momentum-patterns.md`
- `.paul/phases/02-signal-quality/research/earnings-sector-patterns.md`
- `.paul/phases/02-signal-quality/research/insider-volatility-patterns.md`

---
*CONTEXT.md — Persists across /clear for session continuity*
*Created: 2026-04-16*
