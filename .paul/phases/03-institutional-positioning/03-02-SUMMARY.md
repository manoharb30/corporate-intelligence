# Plan 03-02 SUMMARY — Backend Cleanup

**Status:** Complete
**Date:** 2026-04-17

## What Was Done

Stripped backend from 24 routes to 7. Deleted unused route files and orphaned services.

### Routes removed (17)
companies, persons, citations, events, feed, profile, insider_trades, stock_price, officers, alerts, accuracy, dashboard, anomalies, signal_context, company_intelligence, person_intelligence, signal_returns

### Routes kept (7)
- `/api/health` — health check
- `/api/snapshot` — Signal List (strong_buy clusters with returns)
- `/api/event-detail` — Signal Detail (buyers, Form 4 URLs, decision card)
- `/api/signal-performance` — Performance Tracker
- `/api/explorer` — cross-company connections
- `/api/scanner` — Form 4 + activist scanning (operational)
- `/api/activist` — activist filing data

### Service files deleted (11)
company_intelligence_service.py, company_intelligence_service_legacy.py, company_service.py, dashboard_precompute_service.py, dashboard_service.py, event_service.py, person_intelligence_service.py, person_service.py, signal_return_service.py, signal_context_service.py, signal_reason_service.py

### Services kept (19)
Transitively required by kept routes, scanners, or pipeline: insider_cluster_service, snapshot_service, event_detail_service, signal_performance_service, explorer_service, activist_filing_service, accuracy_service, feed_service, stock_price_service, compound_signal_service, trade_classifier, signal_filter, alert_service, insider_trading_service, llm_analysis_service, party_linker_service, company_profile_service, officer_scan_service, + __init__

## Deviation from original plan

Plan was revised twice during this session:
1. Original 03-02: Signal List + backend date filter (reusing snapshot API)
2. Revision 1: New signal_list_service showing all conviction tiers
3. Final revision: Backend cleanup first — user decided to clean before building

The Signal List page exists with rolling 30d/60d/90d toggles using the snapshot API (strong_buy only, 9 signals in 30 days). User confirmed: only show validated signals, not unvalidated tiers.

## Verification

- `from app.main import app` — loads without errors
- 7 include_router lines in main.py
- All kept services import cleanly
- No orphaned imports

---
*03-02-SUMMARY.md — 2026-04-17*
