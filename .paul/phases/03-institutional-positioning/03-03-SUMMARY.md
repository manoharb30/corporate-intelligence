# Plan 03-03 SUMMARY — Signal Pattern Deep Dive

**Status:** Complete — findings documented, decision pending backfill
**Date:** 2026-04-17

## Findings

### Pattern 1: $1M+ total value underperformance — DIRECTIONAL
- 40 signals at 60% HR vs 91 signals <$1M at 76.9% HR
- 5 of 16 losers are likely structured deals (buy/mcap >1%: KODK 30%, PROK 13%, BIOA 4.5%)
- 11 losers are genuine buys that lost — $1M cap is too blunt
- Time consistency: weak (54% H1-2024, 88% H3-2025, 56% H4-2025)
- Verdict: partly an artifact of buy/mcap — not a standalone filter

### Pattern 2: 6+ insider clusters — DIRECTIONAL, TOO SMALL
- 9 signals at 44% HR vs 122 signals ≤5 at 73.8% HR
- NOT structured deals — genuine clusters that lost (low buy/mcap)
- UUUU (15 insiders, 0.009% buy/mcap) = board-wide buy program
- Sample size too small (9) for a hard rule
- Capping at ≤5 only gains 2pp HR on 9 fewer signals
- Verdict: flag, don't filter

### Pattern 3: buy/mcap sweet spot — VALIDATED (pending statistical proof)
- 0.005-0.01%: 58.8% HR — board programs, no skin in game
- 0.01-0.2%: ~78% HR (83 signals) — meaningful conviction
- ≥0.2%: drops to ~50% — structured/private placements
- Logical backing: buy/mcap = skin in game, academically supported
- p=0.112 (directional, not yet significant at p<0.05)
- Projected: p=0.048 at ~195 signals (2 quarters backfill)

## Key Discovery: buy/mcap distribution

| Bucket | n | HR | Alpha | Interpretation |
|--------|---|-----|-------|----------------|
| <0.005% | 7 | 100% | +21.4% | Tiny sample, confounding |
| 0.005-0.01% | 17 | 58.8% | -1.5% | Board programs, no conviction |
| 0.01-0.05% | 24 | 79.2% | +8.2% | Sweet spot — meaningful |
| 0.02-0.05% | 28 | 78.6% | +31.8% | Sweet spot — highest alpha |
| 0.05-0.1% | 17 | 70.6% | +13.6% | Sweet spot — decent |
| 0.1-0.2% | 14 | 78.6% | +19.8% | Still good |
| 0.2-0.5% | 11 | 45.5% | -2.4% | Drops — structured risk |
| 0.5%+ | 13 | 61.5% | +8.2% | Mixed — small sample |

## Statistical Tests

- Overall 71.8% HR is highly significant vs coin flip (p<0.001)
- Sweet spot vs flagged: p=0.112 (not yet significant)
- At 1.5x data (~195 signals): projected p=0.048 ✓
- At 2.0x data (~262 signals): projected p=0.017 ✓

## Decision: Confidence Tiers (not hard filters)

User decided: keep all 131 signals visible, add confidence tiers:
- **High:** buy/mcap 0.01-0.2%, ≤5 insiders (79.2% HR)
- **Medium:** outside sweet spot but not flagged (71.8% HR)
- **Flagged:** buy/mcap <0.01% OR ≥0.2% OR 6+ insiders (~53% HR)

Implementation deferred until after backfill (03-04) proves the pattern statistically.

## Next Step

Backfill Jun-Nov 2024 through full pipeline (Plan 03-04) to reach ~195 mature signals and cross p<0.05 threshold.

---
*03-03-SUMMARY.md — 2026-04-17*
