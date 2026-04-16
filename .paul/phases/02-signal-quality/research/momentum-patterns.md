# Momentum Pattern Analysis: Winners vs Losers in Strong Buy Signals

**Date**: 2026-04-15
**Research question**: Does pre-signal price momentum predict failure in strong_buy insider cluster signals?

## Dataset

- **Source**: Neo4j — GENUINE open-market purchases, midcap ($300M-$10B), 2+ buyers, $100K+ cluster value
- **Date range**: 2024-12-01 to 2026-04-15
- **Raw transactions**: 2,917 from 435 companies
- **Clusters detected**: 190 (after applying strong_buy filters)
- **Analyzable signals** (with 90-day maturity + price data): **123**
- **Winners (>0% 90d return)**: 84 (68.3%)
- **Losers (<=0% 90d return)**: 39 (31.7%)
- **Average 90-day return**: +15.06%
- **Median 90-day return**: +11.74%

## Headline Finding

**Pre-signal price momentum does NOT statistically distinguish winners from losers.** None of the three momentum features tested reached p<0.05 significance. However, the quintile and extreme-momentum analyses reveal non-linear patterns worth incorporating.

## Statistical Tests: Winners vs Losers

| Feature | Winners Mean | Losers Mean | Diff | t-test p | Mann-Whitney p | Significant? |
|---|---|---|---|---|---|---|
| 10-Day Momentum (%) | -4.39 | -4.76 | +0.37 | 0.9135 | 0.9156 | No |
| 30-Day Momentum (%) | -6.88 | -12.23 | +5.34 | 0.2173 | 0.3920 | No |
| Distance from 52W High (%) | -38.37 | -39.54 | +1.16 | 0.7395 | 0.7218 | No |

**Interpretation**: Both winners and losers enter at roughly similar momentum. The average insider is buying after a decline (negative momentum), which aligns with academic literature (insiders are contrarian value buyers). Losers show slightly worse 30-day momentum (-12.2% vs -6.9%) but the difference is not statistically reliable.

## Non-Linear Patterns (Quintile Analysis)

While the linear tests show no significance, quintile analysis reveals a U-shaped pattern:

### 30-Day Momentum Quintiles

| Quintile | Range | N | Win Rate |
|---|---|---|---|
| Q1 (most negative) | -65.0% to -28.6% | 24 | **70.8%** |
| Q2 | -28.5% to -18.5% | 24 | 58.3% |
| Q3 | -18.3% to -8.0% | 24 | 62.5% |
| Q4 | -7.7% to +5.9% | 24 | **70.8%** |
| Q5 (most positive) | +6.3% to +114.8% | 27 | **77.8%** |

### Distance from 52-Week High Quintiles

| Quintile | Range | N | Win Rate |
|---|---|---|---|
| Q1 (deepest discount) | -85.3% to -54.6% | 24 | **75.0%** |
| Q2 | -54.4% to -43.2% | 24 | 58.3% |
| Q3 | -42.4% to -33.4% | 24 | 62.5% |
| Q4 | -33.3% to -24.5% | 24 | 66.7% |
| Q5 (near high) | -24.1% to 0.0% | 27 | **77.8%** |

**Key observation**: The worst performing zone is the MIDDLE — stocks down 20-50% from their high or with -10% to -30% prior momentum. This "purgatory zone" has ~58-63% win rates vs 70-78% at the extremes.

## Extreme Momentum: The Real Signal

### 30-Day Momentum Extremes

| Bucket | N | Win Rate | Avg 90d Return | Median 90d Return |
|---|---|---|---|---|
| Rising (>+20%) | 13 | **92%** | **+39.7%** | +23.9% |
| Falling (<-20%) | 45 | 67% | +19.5% | +15.4% |
| Neutral (-20% to +20%) | 65 | 65% | +7.1% | +8.8% |

**Rising momentum + insider buying = 92% win rate.** When insiders buy into upward momentum (>+20% in 30 days), they're almost always right. This is a small sample (N=13) but the signal is strong. These may be insiders buying ahead of confirmatory news.

### 52-Week High Distance

| Bucket | N | Win Rate | Avg 90d Return | Median 90d Return |
|---|---|---|---|---|
| Near high (>-10%) | 8 | **87.5%** | +16.3% | +13.2% |
| Moderate (-10% to -30%) | 33 | 66.7% | +12.0% | +8.8% |
| Deep discount (-30% to -50%) | 49 | 65.3% | +9.1% | +11.1% |
| Crash (< -50%) | 33 | **69.7%** | **+26.6%** | +22.6% |

**Crashed stocks with insider buying have the highest average returns (+26.6%)** — classic mean reversion with insider information edge. Stocks near their high also outperform (87.5% win rate), likely because insiders are buying into continued strength.

## Worst Losers: What Went Wrong?

| Ticker | Date | MCap $M | Buyers | Mom 10d | Mom 30d | 52W High | 90d Return |
|---|---|---|---|---|---|---|---|
| RPD | 2025-11-25 | 353 | 3 | +8.0% | -17.1% | -65.1% | **-60.1%** |
| PTLO | 2025-08-11 | 401 | 4 | -23.2% | -31.9% | -49.0% | **-39.8%** |
| CLVT | 2025-11-10 | 1,509 | 2 | -6.0% | -8.2% | -40.2% | **-39.1%** |
| RCKT | 2025-04-10 | 397 | 2 | -37.3% | -47.5% | -80.9% | **-35.2%** |
| HP | 2025-02-18 | 3,468 | 3 | -15.0% | -20.0% | -35.6% | **-35.1%** |

**Worst losers tend to cluster in the "purgatory zone"**: moderate declines (-15% to -50% from 52W high) with continued negative momentum. They're not crashed enough for mean reversion, and not near enough to the high for momentum continuation.

## Best Winners

| Ticker | Date | MCap $M | Buyers | Mom 30d | 52W High | 90d Return |
|---|---|---|---|---|---|---|
| EU | 2025-04-03 | 381 | 2 | -56.9% | -76.1% | **+144.1%** |
| TLRY | 2025-07-31 | 805 | 3 | +52.6% | -71.4% | **+134.5%** |
| MATV | 2025-06-06 | 508 | 5 | +20.2% | -66.1% | **+96.7%** |
| SVRA | 2025-06-20 | 1,242 | 2 | -32.7% | -59.4% | **+74.8%** |
| HRTG | 2025-03-14 | 819 | 2 | +26.1% | -17.6% | **+74.0%** |

Best winners are either (a) deeply crashed stocks with insider buying (mean reversion) or (b) stocks already in uptrend with insiders adding (momentum confirmation).

## Actionable Conclusions

### 1. Rising momentum + insider buying is a strong confirmation signal
- 30-day momentum > +20% at time of signal: **92% win rate, +39.7% avg return** (N=13)
- Consider a "momentum-confirmed" flag for these signals

### 2. The danger zone is the MIDDLE, not the extremes
- Stocks down 20-50% from 52W high with mild negative momentum: **58-65% win rate**
- These are "falling knife" situations where insiders may be early or wrong
- The purgatory zone (Q2-Q3 in quintile tables) consistently underperforms both extremes

### 3. Raw momentum is NOT a reliable linear filter
- t-test p-values all >0.20 — no statistically significant linear relationship
- Do not use momentum as a simple threshold filter (e.g., "skip if momentum < X")

### 4. Potential composite filter for future testing
- **Boost score** when: 30d momentum > +20% OR distance from 52W high > -10% OR distance from 52W high < -50%
- **Penalize score** when: stock is in purgatory zone (distance from 52W high between -20% and -50%) AND 30d momentum is mildly negative (-5% to -25%)
- This would need validation on out-of-sample data before implementation

## Methodology Notes

- Cluster detection: 30-day sliding window from latest trade, grouped by company CIK
- Entry price: close on or first trading day after signal date
- Exit price: close on or first trading day after signal_date + 90 calendar days
- 65 signals excluded as immature (signal too recent for 90-day return)
- 2 signals excluded for missing momentum data (insufficient price history)
- Statistical tests: Welch's t-test (unequal variance) and Mann-Whitney U (non-parametric)
- All prices from Company.price_series stored in Neo4j (sourced from yfinance)
