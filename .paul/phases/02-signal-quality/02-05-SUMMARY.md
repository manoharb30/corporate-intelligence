# Plan 02-05 SUMMARY — Failure Attribution to Activist Patterns

**Status:** Complete
**Date:** 2026-04-16

## Result

Of 4 scenarios tested, ONE yielded actionable insight:

**Hostile purpose text predicts failure:**
- 88% of losers-with-activist had hostile keywords (proxy, remove, change, etc.)
- 33% of winners-with-activist had hostile keywords
- 2.6× ratio, consistent with 3 academic papers (Brav 2008, Klein & Zur 2009, Greenwood & Schor 2009)

Other scenarios: stake reduction (no pattern), post-signal arrival (too rare).

## Decision

Add hostile-activist flag as INFORMATIONAL tag (not a filter). Store in both classified.json and Neo4j InsiderTransaction node. Signal stays GENUINE — just tagged with `has_hostile_activist: true/false`.

---
*02-05-SUMMARY.md — 2026-04-16*
