# Earnings Proximity & Sector Momentum: Impact on Strong Buy Signal Outcomes

**Generated:** 2026-04-16
**Dataset:** 131 mature strong_buy signals from SignalPerformance (midcap $300M-$10B, 2+ buyers, $100K+, GENUINE)
**Baseline:** 94/131 = 71.8% win rate, avg 90d return +19.9%, avg alpha vs SPY +14.5%

---

## Key Findings

1. **Earnings proximity is a statistically significant predictor of failure (p=0.003).** Signals where insiders buy 30-60 days before next earnings have 90.9% hit rate vs 64.4% when 60+ days out. This is counterintuitive -- the pattern suggests insiders who buy closer to an earnings date they know is coming have stronger conviction.

2. **Sector ETF momentum is NOT statistically significant (p=0.52).** Insiders buying into sector headwinds actually perform slightly better (81% HR) than the baseline. Sector context does not predict failure.

3. **Sector identity matters more than sector momentum.** Financial Services (83.3% HR), Consumer Cyclical (82.4%), and Real Estate (85.7%) are the best sectors. Communication Services (33.3%) and Basic Materials (50%) are danger zones.

4. **The worst losers cluster in Healthcare and Industrials** -- high volume sectors with moderate hit rates but some severe drawdowns (BIOA -72%, DNA -67%).

---

## Q1: EARNINGS PROXIMITY (statistically significant)

| Metric | Winners (n=92) | Losers (n=36) |
|--------|---------------|--------------|
| Mean days to next earnings | 68.6 | 78.9 |
| Median | 66.0 | 80.0 |
| Std dev | 24.1 | 22.5 |

**Mann-Whitney U = 1102.5, p = 0.0034 (highly significant)**

Direction: Winners buy CLOSER to earnings than losers. This makes sense -- insiders buying 1-2 months before an earnings date they presumably know about signals stronger conviction (they expect the report to be good, or a catalyst before it).

### Earnings distance buckets

| Bucket | Winners | Losers | Hit Rate | Delta vs baseline |
|--------|---------|--------|----------|-------------------|
| < 7 days | 1 | 1 | 50.0% | -21.8pp |
| 7-14 days | 0 | 0 | N/A | -- |
| 14-30 days | 3 | 0 | 100.0% | +28.2pp |
| 30-60 days | 30 | 3 | 90.9% | +19.1pp |
| 60+ days | 58 | 32 | 64.4% | -7.4pp |

**Actionable filter:** Signals with next earnings 30-60 days away are the sweet spot (90.9% HR, +19pp above baseline). Signals with next earnings 60+ days out have 64.4% HR -- materially below baseline.

### Interpretation
- 30-60 day window = insider has visibility into upcoming quarter results
- 60+ day window = insider may be buying on longer-term thesis (more uncertain)
- The < 7d bucket is too small (n=2) to draw conclusions

---

## Q2: SECTOR ETF 30-DAY MOMENTUM (not significant)

| Metric | Winners (n=93) | Losers (n=31) |
|--------|---------------|--------------|
| Mean 30d sector ETF return | +1.22% | +0.53% |
| Median | +1.13% | +0.90% |
| Std dev | 3.57% | 3.23% |

**Mann-Whitney U = 1554.0, p = 0.5181 (not significant)**

### Momentum buckets

| Sector Momentum | Winners | Losers | Hit Rate | Avg 90d Return |
|-----------------|---------|--------|----------|----------------|
| < -5% (deep weakness) | 3 | 1 | 75.0% | +8.8% |
| -5% to -2% | 14 | 3 | 82.4% | +15.2% |
| -2% to 0% | 15 | 5 | 75.0% | +17.4% |
| 0% to 2% | 23 | 12 | 65.7% | +25.3% |
| 2% to 5% | 26 | 9 | 74.3% | +15.2% |
| > 5% (strong tailwind) | 12 | 1 | 92.3% | +46.4% |

**Unexpected pattern:** Buying into sector headwinds (<-2%) has 81.0% HR, slightly above baseline. Insiders buying during sector weakness may represent contrarian value plays that work.

Strong sector tailwind (>+5%) has the best results: 92.3% HR and +46.4% avg return -- but this is likely momentum effect, not the insider signal itself.

**Conclusion:** Sector momentum is noise for filtering purposes. Do not add as a filter.

---

## SECTOR BREAKDOWN

| Sector | Count | Wins | Losses | Hit Rate | Avg Ret | Median Ret |
|--------|-------|------|--------|----------|---------|------------|
| Real Estate | 7 | 6 | 1 | 85.7% | +11.1% | +9.1% |
| Financial Services | 18 | 15 | 3 | 83.3% | +9.4% | +9.8% |
| Consumer Cyclical | 17 | 14 | 3 | 82.4% | +26.6% | +20.9% |
| Energy | 12 | 9 | 3 | 75.0% | +16.0% | +11.5% |
| Healthcare | 30 | 21 | 9 | 70.0% | +24.0% | +12.0% |
| Technology | 13 | 9 | 4 | 69.2% | +60.3% | +4.2% |
| Industrials | 22 | 14 | 8 | 63.6% | +8.7% | +8.8% |
| Consumer Defensive | 5 | 3 | 2 | 60.0% | +6.0% | +2.9% |
| Basic Materials | 4 | 2 | 2 | 50.0% | -1.7% | -3.0% |
| Communication Services | 3 | 1 | 2 | 33.3% | -2.1% | -17.7% |

**Top tier (>80% HR):** Financial Services, Consumer Cyclical, Real Estate
**Danger zone (<60%):** Basic Materials, Communication Services (combined 2/7 = 29% HR)
**High variance:** Technology -- 69% HR but huge avg return (+60%) driven by outlier winners (median only +4.2%)

---

## INTERACTION: Earnings x Sector Momentum

| Scenario | N | Wins | HR | Avg Return |
|----------|---|------|----|------------|
| Near earnings (<14d) + Weak sector (<-2%) | 0 | 0 | N/A | N/A |
| Near earnings (<14d) + Strong sector (>+2%) | 1 | 0 | 0.0% | -13.6% |
| Far from earnings (>30d) + Weak sector (<-2%) | 19 | 15 | 78.9% | +14.5% |
| Far from earnings (>30d) + Strong sector (>+2%) | 46 | 37 | 80.4% | +20.6% |

Small sample sizes in the near-earnings buckets make interaction analysis inconclusive.

---

## WORST LOSERS (pattern inspection)

| Ticker | Date | Return 90d | Sector | Earnings Dist | Sector Mom |
|--------|------|-----------|--------|---------------|------------|
| BIOA | 2024-09-27 | -72.0% | Healthcare | N/A | -1.4% |
| DNA | 2024-05-15 | -66.5% | Healthcare | 85d | N/A |
| IART | 2024-05-23 | -26.2% | Healthcare | 67d | +2.5% |
| ARX | 2025-12-08 | -26.2% | Financial Services | 100d | +1.3% |
| AMRC | 2024-11-15 | -25.1% | Industrials | 104d | -0.1% |
| UUUU | 2024-05-13 | -23.9% | Energy | 81d | N/A |
| KODK | 2025-12-05 | -21.5% | Industrials | 153d | +0.9% |
| HRTG | 2024-08-16 | -20.8% | Financial Services | 82d | -0.1% |
| WBTN | 2024-08-21 | -20.8% | Communication Services | 78d | +2.4% |
| PROK | 2024-06-13 | -19.2% | Healthcare | 57d | +1.3% |

**Pattern in worst losers:** Nearly all have earnings distance 60+ days. No sector momentum pattern (mix of positive and negative). Healthcare over-represented (4 of top 10 losers).

---

## ALPHA vs SPY

| Group | Mean Alpha | Median Alpha |
|-------|-----------|-------------|
| Winners | +27.95% | +11.91% |
| Losers | -19.54% | -18.66% |
| Overall | +14.54% | +3.57% |

---

## Recommendations for Signal Scoring

### Implement (evidence-based)
1. **Earnings proximity bonus:** Signals with next earnings 14-60 days away should get +5 conviction points. This is the only statistically significant predictor found (p=0.003).
2. **Sector penalty:** Basic Materials and Communication Services signals should get -5 conviction points (combined 29% HR on n=7). Monitor as sample grows.

### Do NOT implement
- Sector ETF momentum filter -- p=0.52, no predictive power
- Sector tailwind bonus -- the >5% bucket looks good but it is momentum, not insider alpha

### Monitor (need more data)
- Near-earnings (<14d) bucket -- only 2 signals total, too small
- Real Estate sector -- 85.7% HR but only n=7
- Consumer Defensive -- 60% HR on n=5
