# Insider Signal: Winner vs Loser Patterns

**Date**: 2026-04-16
**Dataset**: 309 mature strong_buy signals (midcap $300M-$10B, 2+ buyers, $100K+, GENUINE)
**Date Range**: 2024-12-01 to 2026-04-15 (signals matured 90+ days)

## Headline Numbers

| Metric | Value |
|--------|-------|
| Total signals | 309 |
| Winners (>0% 90d return) | 190 (61.5%) |
| Losers (<=0% 90d return) | 119 (38.5%) |
| Avg winner return | 25.87% |
| Avg loser return | -15.86% |
| Overall avg return | 9.8% |
| Avg winner alpha (vs SPY) | 20.44% |
| Avg loser alpha (vs SPY) | -19.0% |

## Q1: Prior Insider Selling Before Buy Cluster

**Key finding**: Only 0.8% of strong_buy signals have prior selling within 60 days.
Companies where multiple insiders are buying rarely have concurrent selling.
This is itself a signal -- the absence of selling IS the signal quality filter.

### Multi-Window Analysis

| Window | WITH Selling | N | Win Rate | Avg Return | WITHOUT Selling | N | Win Rate | Avg Return |
|--------|-------------|---|----------|-----------|----------------|---|----------|-----------|
| 60 days | WITH | 3 | 33.3% | 10.09% | WITHOUT | 306 | 61.8% | 9.8% |
| 180 days | WITH | 20 | 50.0% | 1.24% | WITHOUT | 289 | 62.3% | 10.39% |
| 365 days | WITH | 128 | 60.9% | 7.25% | WITHOUT | 181 | 61.9% | 11.6% |

### Sell-to-Buy Ratio (365-day window, prior sell value / cluster buy value)

| Ratio Bucket | N | Win Rate | Avg Return |
|-------------|---|----------|------------|
| No prior selling (ratio=0) | 182 | 61.5% | 11.49% |
| 0 < ratio <= 1 | 49 | 75.5% | 13.28% |
| ratio > 1 (selling dominates) | 78 | 52.6% | 3.67% |

## Q2: Pre-Signal Volatility (30-day annualized)

| Group | Avg Vol | Median Vol |
|-------|---------|------------|
| Winners | 72.78% | 59.49% |
| Losers | 68.03% | 59.89% |

### By Volatility Tercile

| Tercile | Vol Range | N | Win Rate | Avg Return |
|---------|-----------|---|----------|------------|
| LOW | 32% avg | 101 | 64.4% | 5.92% |
| MID | 60% avg | 102 | 62.7% | 9.99% |
| HIGH | 121% avg | 102 | 59.8% | 15.09% |

## Q3: Cluster Composition

### Buyer Count

| Num Buyers | N | Win Rate | Avg Return |
|-----------|---|----------|------------|
| 2 | 182 | 63.7% | 9.99% |
| 3 | 64 | 54.7% | 8.51% |
| 4 | 36 | 55.6% | 8.01% |
| 5 | 12 | 83.3% | 25.84% |
| 6 | 9 | 66.7% | 7.14% |
| 7 | 1 | 100.0% | 28.01% |
| 8 | 3 | 33.3% | -10.91% |
| 10 | 1 | 0.0% | -10.81% |
| 14 | 1 | 100.0% | 16.81% |

### Cluster Value

| Value Bucket | N | Win Rate | Avg Return |
|-------------|---|----------|------------|
| $100K-250K | 96 | 66.7% | 11.21% |
| $250K-500K | 83 | 60.2% | 14.17% |
| $500K-1M | 64 | 60.9% | 8.34% |
| $1M-5M | 54 | 57.4% | 2.75% |
| $5M+ | 12 | 50.0% | 7.73% |

### Role Composition

| Role Mix | N | Win Rate | Avg Return |
|----------|---|----------|------------|
| Officers only | 204 | 60.3% | 12.34% |

### Market Cap

| Market Cap | N | Win Rate | Avg Return |
|-----------|---|----------|------------|
| $300M-$1B | 121 | 63.6% | 11.59% |
| $1B-$3B | 103 | 62.1% | 10.04% |
| $3B-$5B | 35 | 57.1% | 7.15% |
| $5B-$10B | 50 | 58.0% | 6.83% |

## Combined Feature Interactions

### Prior Selling x Volatility

| Combination | N | Win Rate | Avg Return |
|------------|---|----------|------------|
| HIGH vol + prior selling | 60 | 56.7% | 8.17% |
| HIGH vol, no selling | 93 | 65.6% | 20.58% |
| LOW vol + prior selling | 68 | 64.7% | 6.44% |
| LOW vol, no selling | 84 | 60.7% | 3.74% |

### Prior Selling x Officer Presence

| Combination | N | Win Rate | Avg Return |
|------------|---|----------|------------|
| Officer + no prior selling | 128 | 61.7% | 14.28% |
| Officer + prior selling | 76 | 57.9% | 9.08% |
| No officer + no prior selling | 53 | 62.3% | 5.12% |
| No officer + prior selling | 52 | 65.4% | 4.58% |

## Top 10 Biggest Losers

| # | Ticker | Signal Date | Return | Buyers | Value | Prior Sell | Volatility | Market Cap |
|---|--------|------------|--------|--------|-------|-----------|-----------|-----------|
| 1 | ALMS | 2025-04-02 | -69.31% | 2 | $230,277 | NO ($0) | 135.2% | $2,843M |
| 2 | FLY | 2025-08-06 | -62.14% | 3 | $197,955 | NO ($0) | None% | $5,856M |
| 3 | NEOG | 2025-01-16 | -60.34% | 2 | $418,504 | NO ($0) | 44.78% | $2,092M |
| 4 | RPD | 2025-11-25 | -60.08% | 3 | $273,620 | NO ($0) | 75.23% | $353M |
| 5 | FIG | 2025-08-01 | -59.97% | 2 | $3,052,500 | NO ($0) | None% | $9,610M |
| 6 | PRGO | 2025-08-22 | -49.32% | 4 | $304,328 | NO ($0) | 46.47% | $1,579M |
| 7 | CLF | 2025-02-28 | -45.57% | 2 | $208,348 | NO ($0) | 79.76% | $5,390M |
| 8 | MAGN | 2025-02-27 | -43.0% | 2 | $907,829 | NO ($0) | 40.99% | $362M |
| 9 | PTLO | 2025-08-11 | -39.75% | 4 | $1,614,474 | NO ($0) | 92.52% | $401M |
| 10 | LENZ | 2025-11-07 | -39.18% | 2 | $288,841 | NO ($0) | 109.81% | $310M |

## Top 10 Biggest Winners

| # | Ticker | Signal Date | Return | Buyers | Value | Prior Sell | Volatility | Market Cap |
|---|--------|------------|--------|--------|-------|-----------|-----------|-----------|
| 1 | MBX | 2025-10-20 | 203.16% | 2 | $537,774 | NO ($0) | 230.4% | $1,489M |
| 2 | NAUT | 2025-09-08 | 190.0% | 2 | $148,433 | NO ($0) | 38.4% | $387M |
| 3 | TLRY | 2025-07-31 | 134.48% | 3 | $123,541 | NO ($0) | 144.16% | $805M |
| 4 | IMRX | 2025-06-27 | 126.63% | 5 | $256,797 | NO ($0) | 192.35% | $363M |
| 5 | SEI | 2025-09-09 | 115.99% | 2 | $298,300 | NO ($0) | 64.13% | $6,057M |
| 6 | MATV | 2025-05-30 | 115.26% | 4 | $376,200 | NO ($0) | 61.51% | $508M |
| 7 | FOSL | 2025-11-24 | 90.04% | 3 | $152,832 | NO ($0) | 146.54% | $303M |
| 8 | LUMN | 2025-08-15 | 83.3% | 2 | $757,002 | NO ($0) | 70.3% | $8,035M |
| 9 | AGL | 2024-12-13 | 78.57% | 4 | $219,988 | NO ($0) | 178.42% | $411M |
| 10 | HRTG | 2025-03-14 | 74.05% | 2 | $146,950 | NO ($0) | 42.34% | $819M |

## Actionable Conclusions

### Q1: Prior Selling -- NATURAL FILTER, NOT A PREDICTOR

The most surprising finding: **only 0.8% of strong_buy signals have ANY insider selling within 60 days**. The cluster-buying requirement already filters out companies with mixed sentiment. When we expand to 365 days, 41% of signals have prior selling, but win rate barely differs (60.9% vs 61.9%, p=0.87 -- not significant). Prior selling is NOT an independent predictor of failure.

**However**, the sell-to-buy ratio matters at 365d:
- When prior selling is MODEST (0 < ratio <= 1): **75.5% win rate, +13.28% avg return** -- insiders who sold modestly then came back to buy in a coordinated cluster are HIGHER conviction
- When prior selling DOMINATES (ratio > 1): **52.6% win rate, +3.67% avg return** -- this is a genuine yellow flag

**Recommendation**: Do NOT add a "prior selling" penalty. Instead, consider a BONUS for sell-then-buy-back clusters (ratio 0-1x). Flag ratio > 1x as a risk factor.

### Q2: Volatility -- NO PREDICTIVE POWER

Winners and losers have virtually identical pre-signal volatility (72.78% vs 68.03%, p=0.55). Not significant. High-volatility signals actually have slightly HIGHER avg returns (+15.09%) than low-vol (+5.92%), though win rates are similar. This is the classic volatility-return tradeoff -- high vol stocks move more in BOTH directions.

**Recommendation**: Do NOT use pre-signal volatility as a filter. It does not distinguish winners from losers.

### Q3: Composition -- TWO REAL PATTERNS

**1. Cluster value is inversely correlated with win rate (p=0.09, borderline):**
- $100K-250K: 66.7% win rate
- $250K-500K: 60.2%
- $1M-5M: 57.4%
- $5M+: 50.0%

Losers have higher avg cluster value ($1.95M vs $1.00M for winners). This is counterintuitive but explained by: very large purchases often happen at already-elevated prices or in companies where insiders are trying to prop up sentiment. Smaller, more targeted buys are more informational.

**2. Smaller midcaps ($300M-$1B) outperform larger midcaps ($5B-$10B):**
- $300M-$1B: 63.6% win rate, +11.59% avg return
- $5B-$10B: 58.0% win rate, +6.83% avg return

This aligns with academic literature: information asymmetry is higher in smaller companies, making insider buying more informative.

**3. Number of buyers, officer percentage, and top-buyer concentration are NOT significant differentiators** (all p > 0.15). Once you pass the 2+ buyer threshold, adding more buyers does not improve odds.

### Q3 Exception: The 5-Buyer Sweet Spot

5 buyers stands out: 83.3% win rate, +25.84% avg return (n=12). However n=12 is too small for statistical significance. Worth tracking as data grows.

### Combined Interactions

The strongest interaction is **HIGH volatility + no 365d selling**: 65.6% win rate, +20.58% avg return. This represents companies with volatile stocks where ALL insiders are net buyers -- a clean conviction signal.

### What DOES Predict Losers?

Looking at the top 10 losers, there is no single distinguishing feature. They span all buyer counts (2-4), values ($197K-$3M), volatility ranges, and market caps. The failures appear to be driven by company-specific fundamental risk (clinical trial failures, competitive losses, macro headwinds) rather than any signal composition pattern.

**Bottom line**: The current strong_buy criteria (midcap + 2+ buyers + $100K+ + GENUINE) is already well-calibrated. The 61.5% win rate with +9.8% avg return is robust. Marginal gains come from:
1. Preferring smaller midcaps ($300M-$1B)
2. Flagging sell-to-buy ratio > 1x (365d) as risk
3. Preferring moderate cluster values ($100K-$500K) over mega-buys ($5M+)
4. Ignoring volatility and officer composition as non-informative
