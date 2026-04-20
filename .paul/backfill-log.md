# Backfill Log — Historical Month-by-Month

Ops log for opportunistic historical backfills. Not a PAUL phase — just a
running journal so we can watch the thesis evolve as coverage grows.

## Philosophy

Numbers are a moving target. Every publication states "as of [date]" and the
underlying dataset refreshes as the daily scanner ingests new filings and
backfills add history. Model improvements and broader coverage only strengthen
the product. Do not freeze anything.

## Publication snapshot (v1.1 brief — as of 2026-04-19)

| Metric | Value |
|---|---|
| Coverage | Jun 2024 – Apr 2026 (22 months) |
| Mature strong_buy signals | 141 |
| Hit rate (90d) | 67.4% |
| Alpha vs SPY (90d) | +9.0% (p=0.0022) |

This is what the v1.1 brief cites. When a future brief is published, that one
will cite its own "as of" snapshot.

## ⚠️ Technical gotcha: 730-day window

`SignalPerformanceService.compute_all(days=730)` re-detects clusters only
within the last 730 days. Today (2026-04-20) → cutoff ~2024-04-21.

- Backfilling **May 2024 → fine** (inside window).
- Backfilling **Apr 2024 or earlier** → raw `InsiderTransaction` ingested, but
  signals silently excluded from `SignalPerformance`. Must bump `days` param
  (or call sites) before running recompute for older months to count.

## Process per month

1. `cd backend && source venv/bin/activate`
2. Ingest: `python run_month.py YYYY-MM` (or equivalent)
3. Recompute: trigger `SignalPerformanceService.compute_all(days=N)` where
   `N` >= days from oldest signal to today.
4. Verify: row counts, new mature signals for that month.
5. Append a row to the log below.
6. If the cumulative HR/alpha shifts materially, note it under "Observations".

## Running totals (append one row per month)

| Date run | Month backfilled | Txns ingested | New strong_buy signals | Mature in month | Cumulative signals | Cumulative HR (90d) | Cumulative alpha | `days` used | Notes |
|---|---|---|---|---|---|---|---|---|---|
| _pending_ | 2024-05 | — | — | — | — | — | — | 730 | first backfill target; still inside default window |

## Target queue (work backwards from Jun 2024)

- [ ] 2024-05 (still inside 730d window at time of planning)
- [ ] 2024-04 (edge of window — may need `days=760+`)
- [ ] 2024-03 (needs `days=790+`)
- [ ] 2024-02 (needs `days=820+`)
- [ ] 2024-01 (needs `days=850+`)
- [ ] 2023-12 and earlier — decide after 2024 done

## Observations

_(Append free-form notes here as data accumulates: sector concentration, HR drift,
surprising clusters, regime differences, etc.)_

---

*Created 2026-04-20 — append-only running log.*
