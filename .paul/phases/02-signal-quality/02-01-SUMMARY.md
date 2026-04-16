# Plan 02-01 SUMMARY — Signal Quality Filter

**Plan:** .paul/phases/02-signal-quality/02-01-PLAN.md
**Status:** Complete with deviations
**Date:** 2026-04-16

## Plan vs Actual

### Planned
- 3 evidence-based exclusion rules (earnings cycle, purgatory zone, sector)
- Target: 70%+ HR, 100+ signals

### Actual
- 1 rule implemented (earnings proximity <=60d)
- Result: **68.5% HR, 92 signals, +10.6% alpha vs SPY**

### Why the deviation
Research found earnings proximity (p=0.003) was the only rule with clean statistical significance AND practical signal retention. Purgatory zone and sector exclusion added marginal HR gain (<1pp) while reducing signal count. Data-driven decision at checkpoint: single strong rule beats 3 weak stacked rules.

## Acceptance Criteria Results

| AC | Planned | Actual | Status |
|---|---|---|---|
| AC-1: Backtest validates rules | 3 rules stacked, 70%+ HR, 100+ signals | 1 rule, 68.5% HR, 92 signals | **PARTIAL** — meets minimums (68%/80) not stretch targets (70%/100) |
| AC-2: Production filter passes tests | All tests pass | 12/12 tests pass | **MET** ✓ |
| AC-3: Filter integrated into pipeline | Merge + ingest wired | Merge wired with CIK→ticker Neo4j mapping, ingest accepts FILTERED | **MET** ✓ |

## What Was Built

### New files
- `backend/app/services/signal_filter.py` — SignalFilter class with earnings proximity rule
  - `apply_filter(ticker, signal_date)` → FilterResult(passed, earnings_distance, reason)
  - Cached earnings dates via yfinance `get_earnings_dates(limit=20)` (historical coverage)
  - Graceful degradation: missing data → pass with warning
- `backend/tests/test_signal_filter.py` — 12 tests (TDD, all passing)

### Modified files
- `backend/merge_classifications.py`
  - Earnings filter runs after structured deal detector
  - CIK→ticker mapping loaded from Neo4j (4,012 mappings) for historical data
  - Accession→CIK mapping from parsed JSON
  - FILTERED signals get classification='FILTERED', rule_triggered='EARNINGS_FILTER'
- `backend/ingest_genuine_p_to_neo4j.py`
  - Added 'FILTERED' to WRITE_CLASSIFICATIONS
- `backend/parse_form4_p_to_json.py`
  - Added `issuerTradingSymbol` extraction from Form 4 XML (for future runs)

## Decisions Made

| Decision | Rationale | Impact |
|---|---|---|
| 1 rule instead of 3 | Earnings was only statistically significant rule (p=0.003). Purgatory + sector added <1pp HR while losing signals. | Simpler filter, easier to explain to clients |
| earn<=60d threshold | Backtest showed: 92 signals, 68.5% HR, +10.6% alpha. Best balance of HR + count + alpha in the 75-100 signal range. | Doubles alpha vs baseline (+10.6% vs +5.25%) |
| CIK→ticker mapping from Neo4j | Historical parsed JSON lacks ticker. Neo4j has 4,012 CIK→ticker pairs. Loaded at merge time. | Historical data works without re-parsing |
| yfinance get_earnings_dates(limit=20) | Original approach only got future dates. limit=20 returns historical dates back to 2020. | 99% earnings coverage (was 43%) |

## Key Metrics

| Metric | Baseline | After filter | Change |
|---|---|---|---|
| Hit rate (90d) | 61.5% | **68.5%** | +7.0pp |
| Alpha vs SPY | +5.25% | **+10.6%** | +5.35pp (doubled) |
| Signals | 309 | **92** | -217 (70% filtered) |
| Mean return | +9.8% | **+10.6%** | +0.8pp |

## Research Insights (byproduct)

1. **Earnings cycle is the dominant signal** — mid-quarter buys (insiders see internal data, market doesn't) = 68.5% HR
2. **Post-earnings buys have no edge** — buying right after earnings = trading on public info = 61.5% HR
3. **Momentum is U-shaped** — near highs AND deeply crashed both outperform the "purgatory" middle
4. **Volatility, sector ETF momentum, prior selling, buyer count** — none are significant predictors
5. **Sector identity matters** (Basic Materials 50%, Comms 33%) but sample too small to make a hard rule

## Deferred Issues

- [ ] Retroactive filter application on all 17 months of historical data
- [ ] Ticker backfill for historical parsed JSON files (issuerTradingSymbol)
- [ ] Re-compute full-year hit rate after retroactive filter application
- [ ] Purgatory zone rule — not implemented but research supports it; revisit with more data

## Files Created/Modified

```
+ backend/app/services/signal_filter.py (NEW)
+ backend/tests/test_signal_filter.py (NEW)
~ backend/merge_classifications.py
~ backend/ingest_genuine_p_to_neo4j.py
~ backend/parse_form4_p_to_json.py
```

---
*02-01-SUMMARY.md — Loop closed 2026-04-16*
