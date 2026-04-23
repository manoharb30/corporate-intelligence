# Plan 03-05 SUMMARY — Data Verification & Final Numbers

**Status:** Complete
**Date:** 2026-04-17

## Verified Dataset

**Coverage:** Jun 2024 – Apr 2026 (22 months)
**Pipeline:** fetch → prefilter (21 rules) → LLM classify → earnings filter (≤60d) → ingest
**SignalPerformance:** Rewritten from scratch (TDD, 33 tests), uses stored data only

### Transaction counts
- Total classified P transactions: 24,262
- GENUINE: 7,386 (passed all filters)
- FILTERED: 5,452 (failed earnings proximity)
- AMBIGUOUS: 296
- Coverage for strong_buy candidates: 94.5%

### Signal Performance Service — Rewrite
Old service had critical flaws (stale nodes, live yfinance, current market cap for historical signals). New service:
- Uses stored Company.price_series (zero yfinance calls during compute)
- Estimates historical market cap: current_mcap × (signal_price / current_price)
- Deletes all SignalPerformance before recompute (no stale nodes)
- Batch UNWIND storage
- 33 TDD tests, all passing
- Compute time: 3.3 min (was 15-30 min)

### Data integrity verified
- 163/163 mature strong_buy signals verified individually
- 5/5 random spot checks: prices match series, returns match formula, historical mcap matches
- Zero NULL price_day0, zero NULL spy_return, zero NULL market_cap
- SPY stored as Company node with 755 days of prices

---

## Final Numbers (verified, defensible)

### Baseline — what we sell

| Metric | Value | Statistical significance |
|--------|-------|------------------------|
| Mature strong_buy signals | **163** | — |
| Hit Rate (90d return > 0) | **65.6%** | **p < 0.001** (vs 50%) |
| Alpha Hit (beat SPY) | **58.9%** | **p = 0.012** (vs 50%) |
| Avg Return (90d) | **+13.0%** | — |
| Avg SPY Return (90d) | +5.1% | — |
| Avg Alpha vs SPY | **+7.8%** | **p < 0.001** (vs 0%) |

### Signal Riders — informational tiers on each signal

When a signal is generated, tag it with one of these based on retrospective analysis:

**HIGH CONVICTION** badge — when signal matches:
- ≤5 insiders AND
- cluster value <$1M AND
- buy/mcap ≥0.01%

| Metric | Value |
|--------|-------|
| Signals | 94 of 163 (58%) |
| Hit Rate | **71.3%** |
| Alpha Hit (beat SPY) | **66.0%** |
| Avg Alpha | **+11.8%** |

**STANDARD** badge — signals that don't match high conviction criteria:

| Metric | Value |
|--------|-------|
| Signals | 69 of 163 (42%) |
| Hit Rate | 58.0% |
| Alpha Hit | 49.3% |
| Avg Alpha | +2.4% |

**⚠ HOSTILE ACTIVIST** warning — overlay on any signal where company has 13D filing with hostile keywords (proxy, remove, replace, etc.):

| Metric | Value |
|--------|-------|
| Signals with hostile flag | 3 of 163 |
| Hit Rate | 33.3% |
| Avg Alpha | -0.6% |

Note: High Conviction vs Standard is directional (p=0.11), not statistically proven. Presented as informational tier, not a hard filter.

### What the dashboard shows per signal

Every signal on the Signal List and Signal Detail page shows:
1. **Conviction badge** — "High Conviction" (green) or "Standard" (gray)
2. **Hostile warning** — "⚠ Hostile Activist" (red) if applicable
3. **Track record context** — "Historically, signals matching these criteria have X% hit rate"
4. **90-day return** — tracked daily from signal date to day 90
5. **Alpha vs SPY** — signal return minus SPY return for same period
6. **SEC EDGAR link** — every buyer has a "Verify on SEC" link

### Performance Tracker shows
- All signals with daily P&L through 90-day lifecycle
- Winners (green) and losers (red) shown transparently
- Filter by period (30d/90d/year/month)
- Dynamic header stats recalculate per filter
- CSV download

---

## Conviction Tier Breakdown (by month)

| Month | n | HR | Notes |
|-------|---|-----|-------|
| 2024-05 | 7 | 42.9% | Early data, pre-backfill |
| 2024-06 | 3 | 66.7% | |
| 2024-08 | 9 | 100% | Strong summer |
| 2024-09 | 2 | 100% | |
| 2024-10 | 1 | 0.0% | Single signal |
| 2024-11 | 1 | 100% | |
| 2024-12 | 4 | 50.0% | |
| 2025-01 | 1 | 0.0% | Earnings blackout |
| 2025-02 | 5 | 40.0% | |
| 2025-03 | 25 | 64.0% | |
| 2025-04 | 6 | 83.3% | |
| 2025-05 | 15 | 73.3% | |
| 2025-06 | 11 | 90.9% | |
| 2025-07 | 2 | 50.0% | |
| 2025-08 | 20 | 50.0% | |
| 2025-09 | 7 | 71.4% | |
| 2025-10 | 4 | 25.0% | |
| 2025-11 | 21 | 61.9% | |
| 2025-12 | 18 | 72.2% | |
| 2026-01 | 1 | 100% | |

---

## Decisions Recorded

| Decision | Rationale |
|----------|-----------|
| Historical mcap via price ratio | More accurate than current mcap for conviction tier |
| DELETE before recompute | Prevents stale node accumulation |
| Stored data only (no yfinance) | Consistent, reproducible, fast |
| Signal riders are informational | p=0.11 for combo H — directional, not proven |
| Hostile flag is informational | Only 3 signals — too small for hard rule |
| NFE at -62.4% stays in dataset | Legitimate strong_buy loser, correctly classified |
| Performance page shows all signals | Losers visible — transparency builds credibility |

---
*03-05-SUMMARY.md — 2026-04-17*
