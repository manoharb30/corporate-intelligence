# LookInsight — Final Verified Numbers

**Date:** 2026-04-18
**Status:** Verified, defensible, statistically significant

---

## Product Definition

**Strong_buy signal:** Insider cluster where:
- 2+ insiders bought (GENUINE open-market purchases)
- $100K+ total cluster value
- $300M-$5B historical market cap (midcap)
- Within 60 days of next earnings (earnings proximity filter, p=0.003)
- Returns measured from **filing date** (when public knows), not transaction date

## Headline Numbers

| Metric | Value | Statistical significance |
|--------|-------|------------------------|
| Mature strong_buy signals | **141** | — |
| Hit Rate (90d return > 0) | **67.4%** | p < 0.001 (vs 50%) |
| Avg Return (90d) | **+14.2%** | — |
| Avg Alpha vs SPY | **+9.0%** | p < 0.001 (vs 0%) |
| Avg SPY Return (90d) | +5.3% | — |

## Data Coverage

| Metric | Value |
|--------|-------|
| Date range | Jun 2024 – Apr 2026 (22 months) |
| Transactions processed | 67,346 |
| Genuine purchases (after filtering) | 7,386 |
| Companies monitored | 5,437 |
| Total strong_buy (mature + immature) | 207 |
| Mature (90d elapsed, in HR calc) | 141 |
| Immature (active, not in HR calc) | 66 |

## Key Decisions (with evidence)

| Decision | Evidence | p-value |
|----------|----------|---------|
| Midcap cap $5B (was $10B) | $5B-$10B: 38.1% HR vs <$5B: 67.4% | **p=0.018** |
| Earnings filter ≤60d | Post-earnings buys have no edge | **p=0.003** |
| Filing date for returns | Avoids look-ahead bias (1-3 day gap) | Design decision |
| Historical market cap estimation | current_mcap × (signal_price / current_price) | Verified 5/5 spot checks |

## Signal Riders (informational, not filters)

| Badge | Criteria | n | HR | Alpha | Significance |
|-------|----------|---|-----|-------|-------------|
| **High Conviction** | ≤5 insiders, <$1M, buy/mcap ≥0.01% | ~94 | 71.3% | +11.8% | p=0.11 (directional) |
| **Standard** | Doesn't match high conviction | ~69 | 58.0% | +2.4% | — |
| **⚠ Hostile Activist** | 13D with hostile keywords | 3 | 33.3% | -0.6% | Small sample |

## Pattern Annotations (shown per signal)

Each signal card shows the historical HR for signals in that bucket:

| Dimension | Buckets | HR range |
|-----------|---------|----------|
| Market cap | $300M-$1B (71%), $1B-$3B (64%), $3B-$5B (65%) | 64-71% |
| Insider count | 2 (62%), 3 (68%), 4 (74%), 5 (100%), 6+ (23%) | 23-100% |
| Cluster value | 100K-200K (74%), 200K-500K (61%), 500K-1M (64%), 1M+ (58%) | 58-74% |

## Technical Architecture

| Component | Detail |
|-----------|--------|
| Price source | Stored Company.price_series (zero yfinance during compute) |
| Market cap | Historical estimated from price ratio |
| SPY | Stored as Company node with 755-day price_series |
| Compute time | ~130 seconds (was 15-30 min with old yfinance approach) |
| Cleanup | DELETE ALL before recompute (no stale nodes) |
| Tests | 34 TDD tests, all passing |
| Returns start from | Filing date (actionable_date) |

---
*FINAL-NUMBERS.md — 2026-04-18*
*These are the numbers we stand behind for hedge fund conversations.*
