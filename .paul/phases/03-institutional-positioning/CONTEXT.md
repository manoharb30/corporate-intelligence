# Phase 3 CONTEXT — Institutional Positioning

**Date:** 2026-04-16

## Vision

Rebuild the web dashboard as a **proof and accountability tool** — not an analysis platform. Quant analysts get CSV for analysis. The dashboard proves signals are real (SEC EDGAR links) and returns are real (daily tracking).

The dashboard IS the demo tool for hedge fund calls.

## Goals

1. **Signal List** — Show today's signals (or any day's). Ticker, company, conviction tier, cluster value, insiders. Clickable.
2. **Signal Detail** — Proof view. Who bought (name, title, shares, price, value). Direct link to SEC EDGAR Form 4 for verification.
3. **Performance Tracker** — Every signal tracked daily from signal date through 90 days. Daily closing price, cumulative return, alpha vs SPY. Aggregated HR, alpha, return distribution across all signals.

## Approach

- Completely new frontend design — do NOT anchor to current codebase (15 pages, mostly deprecated)
- Current tech stack: React + TypeScript + Vite + Tailwind (keep or change TBD)
- Start with 3 views, grow or shrink based on what we learn during implementation
- Backend already has most data: SignalPerformance nodes, price_series, primary_document for EDGAR links, cluster detection, conviction tiers

## What this is NOT

- NOT an analysis tool (quants use CSV)
- NOT a retail product (no pricing page, no marketing)
- NOT the old 8-K/M&A dashboard (all deprecated concepts removed)

## Key data already available in backend

- 164 strong_buy signals with full metrics
- Per-signal: buyers, titles, shares, price, value, Form 4 URLs
- Price series on Company nodes (daily closes)
- SignalPerformance: returns at day 0/1/2/3/5/7/90, SPY comparison
- Conviction tiers, market cap, industry
- Hostile activist flag, earnings proximity data
- CSV export endpoint exists

## Open questions (resolve during implementation)

- Keep React+Vite+Tailwind or switch framework?
- Dark theme vs light?
- How to handle signals still within 90d (daily price updates needed?)
- Navigation structure for 3 views
- Mobile support needed?

---
*CONTEXT.md — Phase 3 discussion handoff*
