# LookInsight v1.1 — Signal Data Appendix

This file documents the columns in `signals_v1_1_{YYYY-MM-DD}.csv` and `.parquet`, the research artifact attached to the v1.1 institutional brief.

## Preamble

- **Cohort:** 141 mature *strong_buy* signals identified by LookInsight's Form 4 pipeline.
- **Data range:** June 2024 – April 2026 (22 months).
- **Universe:** US-listed equities with SEC Form 4 filings. Non-US issuers are out of scope by design.
- **Return anchor:** Returns are measured from **filing date (day 0)**, not transaction date. This avoids look-ahead bias since the filing is the earliest moment a third party could act.
- **Horizon:** 90 calendar days.
- **Signal construction:** See the v1.1 Research Brief for the full methodology funnel.

## Cohort Definition

A row appears in this file if and only if *all* of the following hold on the `SignalPerformance` node in Neo4j:

- `direction = 'buy'`
- `is_mature = true` (filing is ≥97 days old and the day-90 price is available)
- `conviction_tier = 'strong_buy'`

`strong_buy` itself requires:
- ≥2 distinct insiders in the cluster (`num_insiders >= 2`)
- Total cluster value ≥ $100K (`total_value_usd >= 100_000`)
- Historical market cap in the midcap band: $300M ≤ `market_cap_usd` ≤ $5B
- Cluster reported within 60 days of next earnings (`earn<=60d` filter, p=0.003)

The hostile-activist overlap is captured as an informational flag (`hostile_flag`), not used as a hard filter — it is a known but unproven predictor of under-performance and is left to the reader to weight.

## Column Reference

| # | Name | Type | Nullable | Units | Definition | Source |
|---|------|------|----------|-------|------------|--------|
| 1 | signal_id | string | no | — | Unique identifier for the cluster signal, format `CLUSTER-{cik}-{YYYY-MM-DD}` | Neo4j `SignalPerformance.signal_id` |
| 2 | cik | string | no | — | SEC Central Index Key (zero-padded to 10 digits) | Neo4j `SignalPerformance.cik` |
| 3 | ticker | string | no | — | Primary trading ticker at time of signal | Neo4j `SignalPerformance.ticker` |
| 4 | company_name | string | no | — | Issuer legal name | Neo4j `SignalPerformance.company_name` |
| 5 | industry | string | yes | — | SIC industry description (may be empty where SEC metadata is incomplete) | Neo4j `Company.sic_description` |
| 6 | signal_date | string (ISO date) | no | — | Last transaction date in the cluster window (cluster end) | Neo4j `SignalPerformance.signal_date` |
| 7 | filing_date | string (ISO date) | no | — | Date the Form 4 was filed with SEC; returns anchor to this date | Neo4j `SignalPerformance.actionable_date` |
| 8 | age_days | int32 | no | days | Days since `filing_date` as of export run | Derived: `today − filing_date` |
| 9 | is_mature | bool | no | — | Always `true` in this cohort (filter condition) | Neo4j `SignalPerformance.is_mature` |
| 10 | direction | string | no | — | Always `buy` in this cohort | Neo4j `SignalPerformance.direction` |
| 11 | conviction_tier | string | no | — | Always `strong_buy` in this cohort | Neo4j `SignalPerformance.conviction_tier` |
| 12 | num_insiders | int32 | no | count | Distinct insider names in the cluster window | Neo4j `SignalPerformance.num_insiders` |
| 13 | total_value_usd | float64 | no | USD | Aggregate dollar value of all cluster buys | Neo4j `SignalPerformance.total_value` |
| 14 | market_cap_usd | float64 | yes | USD | Estimated market cap at `signal_date` (price ratio × current_mcap) | Neo4j `SignalPerformance.market_cap` |
| 15 | market_cap_tier | string | no | — | `microcap` <$50M, `smallcap` $50M–$300M, `midcap` $300M–$5B (inclusive), `midcap-large` $5B–$10B, `largecap` >$10B, `unknown` if mcap null | Derived from `market_cap_usd` |
| 16 | pct_of_mcap | float64 | yes | % | `total_value_usd` as a percentage of `market_cap_usd` | Neo4j `SignalPerformance.pct_of_mcap` |
| 17 | price_day0 | float64 | yes | USD | Closing price on `filing_date` (or first trading day ≤5 days after) | Neo4j `SignalPerformance.price_day0` |
| 18 | price_day90 | float64 | yes | USD | Closing price 90 calendar days after `filing_date` | Neo4j `SignalPerformance.price_day90` |
| 19 | price_current | float64 | yes | USD | Most recently stored closing price | Neo4j `SignalPerformance.price_current` |
| 20 | return_day0 | float64 | no | % | 90-day return entering on `filing_date` close: `(price_day90 − price_day0) / price_day0 × 100` — this is the headline signal return | Neo4j `SignalPerformance.return_day0` |
| 21 | return_day1 | float64 | yes | % | 90-day return entering 1 trading day after filing (for slippage sensitivity) | Neo4j `SignalPerformance.return_day1` |
| 22 | return_day2 | float64 | yes | % | 90-day return entering 2 trading days after filing | Neo4j `SignalPerformance.return_day2` |
| 23 | return_day3 | float64 | yes | % | 90-day return entering 3 trading days after filing | Neo4j `SignalPerformance.return_day3` |
| 24 | return_day5 | float64 | yes | % | 90-day return entering 5 trading days after filing | Neo4j `SignalPerformance.return_day5` |
| 25 | return_day7 | float64 | yes | % | 90-day return entering 7 trading days after filing | Neo4j `SignalPerformance.return_day7` |
| 26 | return_current | float64 | yes | % | Return from `price_day0` to `price_current` (open-ended; useful for post-90d tracking) | Neo4j `SignalPerformance.return_current` |
| 27 | spy_return_90d | float64 | no | % | SPY's 90-day return over the same window as the signal | Neo4j `SignalPerformance.spy_return_90d` |
| 28 | alpha_90d | float64 | no | pp | `return_day0 − spy_return_90d`, in percentage points | Derived |
| 29 | cluster_members | string | no | — | Pipe-delimited sorted list of distinct insider names in the cluster window | Derived via `InsiderClusterService.get_cluster_detail` |
| 30 | primary_form4_url | string | yes | — | Direct link to the first Form 4 filing in the cluster (SEC EDGAR URL). Empty if the cluster has no accessible primary document | Derived: `https://www.sec.gov/Archives/edgar/data/{cik}/{accession_no_dashes}/{primary_document}` |
| 31 | hostile_flag | bool | no | — | `true` if the issuer has any associated Schedule 13D filing with hostile-activist language; informational only, not a filter | Derived via `InsiderClusterService.get_cluster_detail.has_hostile_activist` |
| 32 | computed_at | string (ISO datetime) | no | — | When the SignalPerformance node was computed in Neo4j | Neo4j `SignalPerformance.computed_at` |

## Derived Formulas

- **alpha_90d** = `round(return_day0 − spy_return_90d, 2)`; null if either input is null.
- **market_cap_tier** = bucketed from `market_cap_usd`:
  - `microcap`: < $50M
  - `smallcap`: $50M – $300M
  - `midcap`: $300M – $5B (inclusive) — the strong_buy target band
  - `midcap-large`: $5B – $10B (intentional gap: v1.0 analysis showed $5B–$10B had 38.1% HR vs 67.4% for <$5B, p=0.018)
  - `largecap`: > $10B
  - `unknown`: `market_cap_usd` is null
- **age_days** = `today − filing_date`, in calendar days (export-run relative).
- **cluster_members** = `" | ".join(sorted(distinct_insider_names))` from the cluster detail buyers list.
- **primary_form4_url** = first buyer's `form4_url` in the cluster detail (sorted by total value). Format:
  - `https://www.sec.gov/Archives/edgar/data/{cik}/{accession_no_dashes}/{primary_document}` when primary_document is available
  - `https://www.sec.gov/Archives/edgar/data/{cik}/{accession_no_dashes}/{accession}-index.htm` as fallback

## Caveats

- **Survivorship.** Delisted or acquired tickers may have `price_current` as null and `return_current` undefined. `price_day90` is still valid since it is stored at signal maturity. No signals have been removed from the cohort for being delisted.
- **Maturity window.** `is_mature = true` means the signal is ≥97 days old with `price_day90` populated. Younger signals and those missing day-90 data are excluded from this cohort.
- **Market regime.** The data covers June 2024 – April 2026. Readers should note the prevailing market environment when interpreting alpha.
- **Industry coverage.** `industry` is derived from SEC SIC metadata, which is not populated for every issuer. Empty values are expected for some rows.
- **Form 4 URL availability.** A small number of filings do not expose a `primary_document` field (older filings, amendments). In those cases the URL falls back to the accession-level index page. Empty strings are rare but possible.
- **Cluster detection vs export.** The cluster members list is recomputed at export time via `InsiderClusterService.get_cluster_detail`. The `num_insiders` stored on `SignalPerformance` is authoritative for the count used in cohort filtering; the members list may diverge in rare cases where Person nodes have been renamed or deduplicated after signal computation.

## Reproducibility

To regenerate the export:

```bash
cd backend
venv/bin/python -m exports.export_signals_v1_1 \
    --output-dir exports/out \
    --date-suffix $(date +%Y-%m-%d)
```

To verify the output:

```bash
cd backend
venv/bin/python -m exports.verify_export \
    --csv exports/out/signals_v1_1_$(date +%Y-%m-%d).csv \
    --parquet exports/out/signals_v1_1_$(date +%Y-%m-%d).parquet
```

**Environment (at export time):**
- Python 3.13
- Neo4j Aura (managed; version held constant for this release)
- pyarrow ≥ 15.0
- No pandas dependency

The `SignalPerformance` nodes are recomputed by `SignalPerformanceService.compute_all()` before export runs — see `backend/app/services/signal_performance_service.py` for the TDD-locked contract.
