# Signal Risk Scorer — Pre-trade Failure Filter

**Date:** 2026-04-16
**Goal:** Exclude likely-to-fail strong_buy signals before they reach hedge fund clients.
**Target:** 70%+ hit rate while retaining 100+ signals (from current 143 at 67%).

## Problem

143 concentrated strong_buy signals (top buyer >70%, midcap $300M-$10B, 2+ buyers, $100K+) have a 67% hit rate at 90 days. ~47 signals lost money. No pre-trade filter exists to identify and exclude likely failures.

## Approach: Multi-factor Risk Score

Each signal gets a risk score (0-33) computed from 11 factors. Signals above a calibrated threshold are excluded. Each factor is interpretable — hedge fund clients can see why a signal was excluded.

## Features (11 total)

### From price_series (already in Neo4j)

| Feature | Description | Source |
|---|---|---|
| `momentum_10d` | Stock return 10 trading days before signal date | price_series |
| `momentum_30d` | Stock return 30 trading days before signal date | price_series |
| `distance_52w_high` | % below 52-week high at signal date | price_series |
| `stock_volatility_30d` | Annualized 30-day price volatility before signal | price_series |

### From yfinance (new, fetched at signal time)

| Feature | Description | Source |
|---|---|---|
| `earnings_distance` | Trading days until next earnings report | yfinance `earnings_dates` |
| `sector_etf_30d` | 30d return of sector ETF (XLK, XLV, etc.) at signal date | yfinance |

### From Neo4j (already computed)

| Feature | Description | Source |
|---|---|---|
| `prior_insider_selling` | Count of insiders who SOLD same company in 60 days before buy cluster | InsiderTransaction (code=S) |
| `has_10pct_owner` | Whether cluster includes a 10% beneficial owner | InsiderTransaction |
| `cluster_value` | Total dollar value of cluster | InsiderTransaction |
| `num_buyers` | Number of distinct buyers in cluster | InsiderTransaction |
| `top_buyer_share` | Concentration — top buyer's % of cluster value | InsiderTransaction |

## Scoring Matrix

| Factor | 0 pts (low risk) | 1 pt | 2 pts | 3 pts (high risk) |
|---|---|---|---|---|
| momentum_10d | > +5% | 0% to +5% | -10% to 0% | < -10% |
| momentum_30d | > +10% | 0% to +10% | -15% to 0% | < -15% |
| distance_52w_high | < 10% off | 10-20% off | 20-35% off | > 35% off |
| earnings_distance | > 30 days | 15-30 days | 7-14 days | < 7 days |
| sector_etf_30d | > +5% | 0% to +5% | -5% to 0% | < -5% |
| stock_volatility_30d | < 20% ann. | 20-35% | 35-50% | > 50% |
| prior_insider_selling | None | — | 1 seller | 2+ sellers |
| has_10pct_owner | Yes (0 pts) | — | — | No (2 pts) |
| cluster_value | > $1M | $500K-$1M | $100K-$500K | — |
| num_buyers | 4+ | 3 | 2 | — |
| top_buyer_share | 90%+ | 70-90% | — | — |

**Risk score** = sum of all factor scores. Range: 0 (safest) to ~33 (riskiest).

**Exclusion rule:** `risk_score >= threshold` → signal excluded.

Threshold determined by backtesting (see Calibration section).

## Sector ETF Mapping

Determined from yfinance `sector` field or SIC code:

| Sector | ETF |
|---|---|
| Technology | XLK |
| Healthcare | XLV |
| Financial Services | XLF |
| Energy | XLE |
| Industrials | XLI |
| Consumer Cyclical | XLY |
| Consumer Defensive | XLP |
| Basic Materials | XLB |
| Real Estate | XLRE |
| Utilities | XLU |
| Communication Services | XLC |
| Unknown/Other | SPY (fallback) |

## Architecture

### New file: `backend/app/services/signal_risk_scorer.py`

```python
class SignalRiskScorer:
    score_signal(ticker, signal_date, cluster_data) -> dict
        # Returns {risk_score, risk_factors, risk_pass}

    _compute_momentum(price_series, signal_date, days) -> float
    _compute_52w_distance(price_series, signal_date) -> float
    _compute_earnings_proximity(ticker, signal_date) -> int
    _compute_sector_momentum(ticker, signal_date) -> float
    _compute_volatility(price_series, signal_date) -> float
    _check_prior_selling(cik, signal_date) -> int
```

All factor computations are pure functions (testable in isolation).

### Integration points

1. **merge_classifications.py** — after structured deal detector, before writing classified.json. Risk score computed for each GENUINE signal.
2. **classified.json** — `risk_score`, `risk_factors`, `risk_pass` fields added per signal.
3. **ingest_genuine_p_to_neo4j.py** — writes `risk_score` to InsiderTransaction node.
4. **Cluster detection service** — uses `risk_pass` to filter signals shown to clients.

### Data flow

```
Phase A (prefilter) → Phase B (LLM) → merge (structured detector) 
    → risk_scorer (NEW) → classified.json → ingest → Neo4j
```

## Backtesting & Threshold Calibration

### Step 1: Feature computation
Compute all 11 features for existing 143 signals (read-only analysis script).

### Step 2: Score distribution
Generate risk_score for each signal. Visualize distribution: winners vs losers.

### Step 3: Threshold sweep
For threshold T in [3, 4, 5, ..., 12]:
- Count signals with risk_score < T (pass filter)
- Compute hit rate on passing signals
- Compute alpha vs SPY on passing signals

### Step 4: Select threshold
Pick T where:
- hit_rate >= 70%
- signals_retained >= 100
- alpha improves vs unfiltered baseline

### Step 5: Validate
- Check that filter doesn't exclude entire months or sectors (overfitting)
- Check that filter works across different time periods (not just fitted to one quarter)

### Step 6: Alpha verification
Recompute alpha vs SPY on filtered subset. Confirm improvement over baseline +5.5%.

## Output Format

Each signal in classified.json:

```json
{
  "risk_score": 7,
  "risk_threshold": 8,
  "risk_pass": true,
  "risk_factors": {
    "momentum_10d": {"value": -3.2, "score": 2},
    "momentum_30d": {"value": +1.5, "score": 1},
    "distance_52w_high": {"value": -12.0, "score": 1},
    "earnings_distance": {"value": 5, "score": 3},
    "sector_etf_30d": {"value": +2.1, "score": 1},
    "stock_volatility_30d": {"value": 28.0, "score": 1},
    "prior_insider_selling": {"value": 0, "score": 0},
    "has_10pct_owner": {"value": true, "score": 0},
    "cluster_value": {"value": 450000, "score": 2},
    "num_buyers": {"value": 3, "score": 1},
    "top_buyer_share": {"value": 0.82, "score": 1}
  }
}
```

Fully transparent — hedge fund clients see every factor and its contribution.

## Testing Strategy

- Unit tests for each `_compute_*` function with known price series inputs
- Integration test: score a known winner and a known loser, verify scores differ
- Backtest validation: run on full 143-signal dataset, confirm hit rate improvement
- Edge cases: missing price data, no earnings dates, unknown sector

## Success Criteria

1. Hit rate on filtered signals ≥ 70% (from current 67%)
2. Signals retained ≥ 100 (from current 143)
3. Alpha vs SPY improves from +5.5% baseline
4. No month or sector entirely excluded by filter
5. Risk factors are interpretable and explainable to clients
