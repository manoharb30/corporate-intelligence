# Phase 2C: Attribute failures to activist filing patterns

## Goal
Understand WHY ~30 of our 85 filtered signals lost money. Can activist filing data explain or predict failures?

## Test Design (4 scenarios, single analysis)

### Scenario 1: Activist stake reduction (EXIT signal)
For losers with activist filings — did any 13D/A amendments show DECREASING ownership %?
If activist is reducing stake while insiders are buying → conflicting conviction → warning.

### Scenario 2: Hostile/negative purpose text
For losers with activist filings — does purpose_text contain hostile keywords?
("proxy fight", "remove", "replace board", "strategic alternatives", "inadequate", "underperform")
Hostile activist + insider buying = insider might be wrong (buying to defend position).

### Scenario 3: Loser distribution by activist group
We know from 02-04: NO_ACTIVIST has 18 losers, ACTIVIST_BEFORE has 6, ACTIVIST_AFTER has 2.
Deep dive into the 6 ACTIVIST_BEFORE losers: who was the activist, what stake, what happened?

### Scenario 4: Post-signal activist activity
For losers with NO activist at signal time — did an activist show up AFTER (within 180 days)?
If activist starts accumulating after insiders bought but stock dropped → the insider signal attracted the activist but too early.

## Approach
- Single read-only analysis on ~30 losers
- Query ActivistFiling for each loser's company
- Compare patterns in losers vs winners
- No code changes

---
*Created: 2026-04-16*
