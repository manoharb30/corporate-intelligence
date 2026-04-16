# Plan 02-03 SUMMARY — Retroactive Earnings Filter

**Plan:** .paul/phases/02-signal-quality/02-03-PLAN.md
**Status:** Complete
**Date:** 2026-04-16

## Result

Earnings filter applied retroactively to 263 of 282 processed days. Neo4j now reflects filtered signal universe.

## Before vs After

| Metric | Before | After |
|---|---|---|
| GENUINE transactions | 9,574 | 6,137 |
| FILTERED transactions | 0 | 3,433 |
| Strong_buy clusters | 309 | **164** |
| Hit rate (90d) | 61.5% | **65.9%** |
| Mean return | +9.8% | **+12.4%** |
| Alpha vs SPY | +5.25% | **+8.0%** |
| Alpha hit rate | 50.2% | **56.1%** |

## Deviations

- 19 days had merge errors (missing queue files from old architecture) — skipped
- Strong_buy count is 164, not 92 as backtest predicted — because filter runs per-transaction, clusters with partial member survival still qualify with 2+ remaining GENUINE buyers. This is correct behavior.

## What Hedge Funds See Now

164 strong_buy signals at 65.9% hit rate with +8.0% alpha vs SPY. All in Neo4j as GENUINE. Cluster detection queries automatically exclude FILTERED.

---
*02-03-SUMMARY.md — Loop closed 2026-04-16*
