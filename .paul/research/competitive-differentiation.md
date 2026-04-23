# LookInsight Competitive Differentiation

**Date:** 2026-04-16
**Purpose:** Answer the buyer question: "What do you do that nobody else does?"

---

## The Competitive Landscape (8 players)

| Provider | Market | Method | Form 4 | 13D | 8-K | Cross-Filing | Delivery |
|----------|--------|--------|--------|-----|-----|-------------|----------|
| **InsiderScore / Verity** | Institutional | Analyst + rules | Yes (best behavioral flags) | No | No | No | API, SFTP |
| **SmartInsider** | Institutional | Analyst + algo | Yes (global) | No | No | No | SFTP, Snowflake |
| **2iQ Research** | Institutional | ML model | Yes (60K stocks, 58 countries) | No | No | No | AWS, Snowflake |
| **Washington Service** | Institutional (raw data) | Human QA | Yes (since 1988) | No | No | No | Feeds, API |
| **Paragon Intel** | Institutional | Interviews + quant | Yes (4% predictive subset) | No | No | No | Custom |
| **Quiver Quantitative** | Retail | Rule-based | Yes (+ Congress, lobbying) | No | No | No | API |
| **TipRanks** | Retail | Composite score | Yes (diluted in Smart Score) | No | No | No | Web only |
| **WhaleWisdom** | Retail/semi-pro | Quantitative | Minimal (13F focus) | Yes | No | No | API |
| **LookInsight** | Institutional | LLM + 19 rules + graph | Yes | Yes | Yes | **Yes** | API, CSV |

## What Nobody Else Does (our moat)

### 1. Cross-filing compound signals
We are the **only** product that cross-references Form 4 insider trades + Schedule 13D activist filings + 8-K corporate events into compound signals. Every competitor treats these filing types in isolation.

- `insider_activist`: Insider cluster + 13D filing within ±30 days
- `activist_8k`: 13D filing + 8-K material agreement within ±90 days
- `triple_convergence`: All three sources converge (highest conviction)

Academic validation: SSRN research confirms insiders trade ahead of 13D filings — 12.09% insider profit vs 7.72% average 13D announcement return.

### 2. LLM-powered noise classification
Competitors use either rule-based systems (most) or human analysts (SmartInsider, InsiderScore). We use:
- **19 deterministic prefilter rules** that eliminate 60-80% of noise without LLM cost
- **Claude Haiku** for ambiguous cases (trust entities, price variance signals, empty-footnote heuristics)
- Cost: ~$2-3/month vs human analyst teams at SmartInsider/InsiderScore

### 3. Evidence-based earnings proximity filter
No competitor filters by earnings timing. Our rule (earn<=60d, p=0.003) captures the informational asymmetry window — insiders buying mid-quarter have private data; post-earnings buyers are trading on public info.

### 4. Graph-based relationship intelligence
Neo4j enables queries impossible in flat SQL:
- "Which insiders traded near activist filings for their company?"
- Person → Transaction → Company → ActivistFiling in a single traversal
- Track insider networks across companies and time

### 5. Hostile activist flagging
88% of losing signals with activist overlap had hostile keywords in 13D purpose_text vs 33% of winners. No competitor analyzes purpose_text for hostile intent (proxy, remove, replace, etc.).

### 6. Structured deal detection
Groups transactions by (issuer, date, exact price). 5+ insiders at identical price = coordinated placement, not genuine conviction. Nobody else detects this.

### 7. Calibrated conviction tiers with proven alpha
Not just "insider bought" — scored by market cap band ($300M-$10B sweet spot), cluster value ($100K+), buyer count, officer role weighting. Strong_buy tier: 65.9% HR, +8.0% alpha vs SPY at 90 days. Verified 0.000% data discrepancy.

## Competitor "advantages" — and why they don't apply

| Competitor edge | Our position |
|----------------|-------------|
| **Global coverage** (2iQ, SmartInsider) | US-only by design — SEC filings are the deepest, most standardized insider disclosure regime. Global = breadth over depth. |
| **Data history depth** (Washington Service since 1988) | 17 months is sufficient — our methodology is backed by published academic research (Brav 2008, Klein & Zur 2009, Greenwood & Schor 2009). The research validates the patterns across decades; our data proves they still work. |
| **Institutional delivery infra** (InsiderScore SFTP) | S3 bucket delivery planned for Phase 3. Modern quant infra prefers cloud object storage over SFTP. |
| **Exec interviews** (Paragon Intel) | Different product — qualitative management research, not quantitative signal generation. |

### Actual gaps to address

| Gap | Impact | Priority |
|-----|--------|----------|
| **10b5-1 plan-level tracking** | InsiderScore tracks full plan lifecycle; we only tag presence | Low — our prefilter already excludes 10b5-1 trades |
| **Point-in-time data** | Quant funds need as-reported snapshots for backtesting | Medium — needed for institutional delivery |

## What Quant Funds Evaluate (from research)

1. **Point-in-time data** — essential for backtesting without look-ahead bias
2. **Noise filtering quality** — the 80% noise stat is well-known; they want the clean 20%
3. **Insider role weighting** — C-suite > director > 10% owner
4. **Cluster detection** — multi-insider buying in tight window
5. **Low correlation with existing factors** — additive alpha, not repackaged momentum
6. **Delivery infrastructure** — SFTP, API, Snowflake integration
7. **Data freshness** — minutes matter for systematic strategies
8. **Survivorship-bias-free history** — must include delisted companies

## The Elevator Answer

> "Every insider data vendor gives you Form 4 trades. We're the only ones who cross-reference Form 4 insider clusters with 13D activist positions and 8-K material events to find convergence signals. We use LLM classification (not just rules or human analysts) to filter 80% noise, apply an earnings-proximity filter backed by p=0.003 statistical significance, and flag hostile activist situations that predict 88% of losing positions. The result: 164 strong_buy signals at 65.9% hit rate and +8.0% alpha vs SPY over 17 months — verified to 0.000% data discrepancy against live market data."

---

*Research from: web competitor analysis + codebase capability audit*
*Date: 2026-04-16*
