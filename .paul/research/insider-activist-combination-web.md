# Insider Trading + Activist Investor Compound Signal: Web Research

**Date:** 2026-04-15
**Context:** LookInsight has 65.9% hit rate / +8.0% alpha on insider buying clusters (Form 4) at 90 days on midcap US equities. We have 7,463 Schedule 13D activist filing records. This document synthesizes academic research, competitor analysis, and practical implementation guidance for combining these two signal sources.

---

## 1. Academic Research: Combining Insider Trading + Activist Investor Signals

### 1A. The Landmark Paper: "Betting on My Enemy"

**Duong, Pi, and Sapp (2025).** "Betting on my enemy: Insider trading ahead of hedge fund 13D filings." *Journal of Corporate Finance*, Vol. 93, July 2025.

This is the single most relevant academic paper for LookInsight's compound signal engine. Key findings:

| Metric | Value |
|--------|-------|
| Sample period | 1994-2016 |
| 13D announcement abnormal returns | **7.72%** |
| Insider buy profits (average) | **12.09%** |
| Insider buy profits (no prior talks with activist) | **14.49%** |
| Insider buy profits (prior talks with activist) | ~4.8% |

**Critical findings for our product:**
- Insiders engage in **abnormal buying activity in the months leading up to 13D filings**. This is not random -- corporate insiders become aware of hedge fund attention before the 13D is filed.
- When insiders buy WITHOUT having formal discussions with the activist, their profits are **triple** those of insiders who had early talks. This implies insiders are detecting activist interest through indirect channels (unusual trading volume, share register changes, industry gossip).
- The pre-13D insider buying is concentrated in the **20-day window before the filing**, with the strongest signal in the final 10 days.
- **This directly validates LookInsight's compound signal architecture**: insider cluster + 13D = stronger signal than either alone.

**Source:** [ScienceDirect](https://www.sciencedirect.com/science/article/abs/pii/S0929119925000628) | [ResearchGate](https://www.researchgate.net/publication/390666701)

### 1B. Hedge Fund Activism Returns (Brav, Jiang, Partnoy, Thomas)

**Brav, Jiang, Partnoy, and Thomas (2008).** "Hedge Fund Activism, Corporate Governance, and Firm Performance." *Journal of Finance*.

| Metric | Value |
|--------|-------|
| Sample | ~2,000 interventions, 1994-2007 |
| Abnormal return at 13D announcement | **~7%** |
| Long-term reversal | **None** (gains persist) |
| Success rate (full or partial) | **67%** |
| Median monthly 4-factor alpha (activist funds) | **63 bps** |
| Median monthly alpha (all equity hedge funds) | 39 bps |

**Target company characteristics:**
- "Value" firms: low market value relative to book value
- Profitable with sound operating cash flows and ROA
- Smaller than non-target firms (few large-caps targeted due to cost of amassing a stake)
- Higher institutional ownership and trading liquidity
- More takeover defenses, higher CEO pay vs peers
- Lower payout before intervention
- 59.5% of campaigns cite "general undervaluation / maximize shareholder value"

**Source:** [Columbia Business School](https://business.columbia.edu/sites/default/files-efs/pubfiles/4132/jiang_activism.pdf) | [Duke Law](https://law.duke.edu/sites/default/files/centers/gfmc/session_3/2_brav_et_al-hedge_fund_activism-2008.pdf)

### 1C. Long-Term Effects (Bebchuk, Brav, Jiang 2015)

**Bebchuk, Brav, and Jiang (2015).** "The Long-Term Effects of Hedge Fund Activism." *Columbia Law Review / NBER Working Paper 21227*.

- Examined **five-year window** following activist interventions.
- Found **no evidence** that activism produces short-term gains at the expense of long-term performance.
- Initial positive stock-price spike reflects **long-term value creation**, not a pump-and-dump.
- Klein and Zur report **additional 11.4% abnormal return** during the year following the 13D filing.

**Implication for LookInsight:** The 13D signal is not a short-term artifact. Companies targeted by activists genuinely improve, making the compound signal (insider + activist) a valid long-duration thesis.

**Source:** [NBER](https://www.nber.org/system/files/working_papers/w21227/w21227.pdf) | [Columbia Law Review](https://columbialawreview.org/wp-content/uploads/2016/04/Bebchuk-Brav-Jiang.pdf)

### 1D. Insider Cluster Trading (Alldredge 2019)

**Alldredge (2019).** "Do Insiders Cluster Trades with Colleagues? Evidence from Daily Insider Trading." *Journal of Financial Research*.

| Metric | Value |
|--------|-------|
| Sample period | 1986-2014 |
| Monthly abnormal return (clustered buys) | **2.1%** |
| Monthly abnormal return (solitary buys) | 1.2% |
| Cluster premium | **+0.9% per month** |

- Clustered purchases (within 2 days of a peer insider purchase) earned **75% higher abnormal returns** than solitary purchases.
- Results consistent with information sharing among corporate insiders.
- Origin: Jaffe (1974) first demonstrated that multiple insiders buying at the same firm around the same time produces a significantly stronger signal.

**Implication:** Our existing cluster detection (3+ buyers = HIGH) is well-grounded. The cluster premium stacks on top of the activist premium.

**Source:** [Wiley](https://onlinelibrary.wiley.com/doi/abs/10.1111/jfir.12172)

### 1E. Opportunistic vs Routine Classification (Cohen, Malloy, Pomorski 2012)

**Cohen, Malloy, and Pomorski (2012).** "Decoding Inside Information." *Journal of Finance*.

| Metric | Opportunistic Traders | Routine Traders |
|--------|----------------------|-----------------|
| VW monthly alpha | **82 bps (9.8% annualized)** | ~0 bps |
| EW monthly alpha | **180 bps (21.6% annualized)** | ~0 bps |
| Predict future firm news | Yes | No |
| SEC enforcement rate | Higher | Lower |

- Classification method: designate insiders as routine or opportunistic at the start of each year based on trading history (same-month-each-year = routine).
- Routine trades driven by diversification, liquidity, bonuses (same month each year).
- Opportunistic trades driven by private information.
- **Most informative traders:** local, non-senior opportunistic insiders at geographically concentrated, poorly governed firms.

**Implication for LookInsight:** We should consider adding an opportunistic/routine filter to improve our hit rate. A first approximation: flag insiders who trade in the same month every year as routine.

**Source:** [NBER](https://www.nber.org/system/files/working_papers/w16454/w16454.pdf) | [SSRN](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=1692517)

### 1F. Officer vs Director vs 10% Owner (Seyhun 1986, 1998)

**Seyhun (1986, 1998).** "Investment Intelligence from Insider Trading." *MIT Press*.

- Insiders who are **chairmen of the board or officer-directors** are more successful predictors than officers or shareholders alone.
- Directors have predictive power across **all firm sizes**; officers only predict for **small firms**.
- **10% owners (large shareholders) are the weakest predictors** -- their trades are often driven by portfolio rebalancing, not private information.
- Top directors with the highest ownership levels actually show **negative returns** when followed.

**Implication:** Our current scoring (officer > director > 10% owner) aligns with the academic hierarchy. We should further downweight 10% owner trades in the compound signal.

**Source:** [Amazon/MIT Press](https://mitpress.mit.edu/9780262692342/investment-intelligence-from-insider-trading/) | [LSV Asset](https://www.lsvasset.com/pdf/research-papers/Insider-Trades-Informative.pdf)

### 1G. Wolf Pack Activism (Brav, Dasgupta, Mathews 2015/2021)

**Brav, Dasgupta, and Mathews (2015/2021).** "Wolf Pack Activism."

- "Wolf pack" = multiple hedge funds buying into the same target without formal coordination.
- Pack can form **without explicit coordination** by the activist -- other funds detect the opportunity independently.
- However, evidence also suggests lead activists **tip off institutions** with prior relationships.
- Average abnormal short-term return: **7-8%** around the 13D filing.
- Wolf pack targets experience approximately **10% increase in aggregate short interest** as shorts respond to the campaign.

**Implication:** When we see multiple 13D filers on the same target, or a 13D plus insider buying, it may indicate a wolf pack forming. This is the highest-conviction configuration.

**Source:** [ECGI](https://www.ecgi.global/sites/default/files/working_papers/documents/bravdasguptamathewsfinal.pdf) | [LSE](https://eprints.lse.ac.uk/112118/2/Brav_Dasgupta_Mathews_accepted.pdf)

---

## 2. Competitor Landscape: How Alt-Data Providers Combine These Signals

### 2A. InsiderScore / VerityData

- Founded 20+ years ago; now part of VerityData suite.
- Used by hedge funds, long-only managers, multi-manager platforms, quant firms.
- Highlights: **cluster buying**, inflections vs 90-day baseline, cessation of selling, buys into weakness.
- Covers every U.S. company filing with the SEC.
- **Does NOT combine insider + activist signals** in a single product. InsiderScore focuses on Form 4 data; inFilings covers broader SEC disclosures.
- **Pricing:** Enterprise SaaS, estimated $15K-$50K/year for institutional.
- **Gap:** No compound signal engine crossing Form 4 + 13D + 8-K.

**Source:** [VerityData](https://verityplatform.com/solution/veritydata/insiderscore/)

### 2B. 2iQ Research

- Founded 2002; global coverage of 60,000+ stocks in 50+ countries.
- Real-time alerts, insider profiles, advanced analytics, sentiment scoring.
- Uses ML and "smart scraping" technology.
- Publishes research summaries of academic literature (e.g., their "Profiting from Insider Transactions" review).
- **Does NOT appear to combine insider + activist filings** as a product feature. Focus is purely on insider transaction data.
- **Pricing:** Enterprise data feeds, API access.

**Source:** [2iQ Research](https://www.2iqresearch.com/)

### 2C. WhaleWisdom

- Tracks **13F institutional filings** (quarterly, 45-day delay), not Form 4 insider transactions.
- Also provides **13D/13G filing tracking**.
- Allows users to track specific activist investors across their 13D filings.
- **Does NOT cross-reference Form 4 insider trades with 13D filings** in a systematic way.
- **Pricing:** Free tier + premium ($49-$299/month).

**Source:** [WhaleWisdom](https://whalewisdom.com/)

### 2D. ForcedAlpha

- Activist stakes tracker focused on 13D/13G filings.
- Claims 13D filings often reprice stocks **5-15% within days**.
- Surfaces filings within hours of SEC publication.
- **Does NOT combine with Form 4 data.**
- **Pricing:** Appears to be a newer/smaller provider.

**Source:** [ForcedAlpha](https://forcedalpha.com/tools/activist-stakes/)

### 2E. 13D Monitor

- Comprehensive research and advisory service specializing in shareholder activism.
- Used by activists, targets, and investment banks.
- **Focus:** Campaign-level analysis, not quantitative signal generation.

**Source:** [13D Monitor](https://www.13dmonitor.com/)

### 2F. 13D Activist Fund

- An actual **mutual fund** ($133M AUM) that uses 13D filings as its primary investment strategy.
- Invests in companies targeted by activist investors after 13D filing.
- Not a data product, but validates the investment thesis.

**Source:** [13D Activist Fund](https://www.13dactivistfund.com/)

### 2G. Competitive Gap Summary

| Provider | Form 4 Data | 13D Data | Combined Signal | Cluster Detection | 8-K Cross-Reference |
|----------|:-----------:|:--------:|:---------------:|:-----------------:|:-------------------:|
| InsiderScore/VerityData | Yes | No | No | Yes | No |
| 2iQ Research | Yes | No | No | Partial | No |
| WhaleWisdom | No | Yes | No | No | No |
| ForcedAlpha | No | Yes | No | No | No |
| 13D Monitor | No | Yes | No | No | No |
| **LookInsight** | **Yes** | **Yes** | **Yes** | **Yes** | **Yes** |

**No existing provider combines Form 4 insider cluster detection with Schedule 13D activist filings and 8-K material events into a unified compound signal.** This is a genuine product differentiation.

---

## 3. Most Predictive 13D Features to Pair with Insider Clusters

### 3A. Ownership Percentage

| Threshold | Signal Strength | Rationale |
|-----------|----------------|-----------|
| 5-7% | Baseline | Minimum filing threshold; may be passive |
| 7-10% | **Medium** | Meaningful stake; activist has skin in the game |
| 10%+ | **High** | Serious capital commitment; activist cannot easily exit |
| 20%+ | **Very High** | Near-control position; likely seeking board seats or sale |

- Brav et al. find activists holding **8-10%+ stakes** are "serious about pushing for change and have significant capital at risk."
- Our current scoring gives +10 points for >10%, +5 for >=7%. This aligns with academic evidence.

### 3B. Filing Type: 13D vs 13G

| Filing | Average Announcement Return | Signal |
|--------|:--------------------------:|--------|
| Schedule 13D (activist intent) | **6.34%** | Strong |
| Schedule 13G (passive) | **0.59%** | Weak |

- The 13D/13G distinction alone produces a **10x difference in announcement returns**.
- A **conversion from 13G to 13D** signals an investor upgrading from passive to activist -- a strong signal.
- A **conversion from 13D to 13G** signals the campaign is over.

**Implementation note:** We should track 13G-to-13D conversions as a separate high-signal event.

### 3C. Purpose Text (Item 4) Keywords

The purpose section of a 13D reveals the activist's playbook. High-signal keywords:

| Keyword Category | Examples | Signal Strength |
|-----------------|----------|-----------------|
| Board representation | "board seats", "board representation", "nominate directors" | **High** |
| Strategic alternatives | "strategic alternatives", "sale of the company", "spin-off" | **Very High** (M&A catalyst) |
| Undervaluation | "undervalued", "maximize shareholder value", "unlock value" | **High** |
| Operational | "cost reduction", "operational improvements", "restructuring" | **Medium** |
| Capital return | "share repurchase", "dividend", "capital allocation" | **Medium** |
| Soft engagement | "dialogue with management", "constructive discussions" | **Low** (passive tone) |

- 59.5% of campaigns cite "general undervaluation / maximize shareholder value" (Brav et al.).
- Attached exhibits (letters to board, presentation decks) often contain more specific information than the main filing text.

**Implementation note:** Our `signal_summary` field on ActivistFiling nodes should be enhanced with keyword extraction from the purpose text.

### 3D. Timing: 13D Filed BEFORE vs AFTER Insider Cluster

| Sequence | Interpretation | Conviction |
|----------|---------------|------------|
| **13D first, then insider cluster** | Insiders see activist creating value, pile in | **Highest** -- independent confirmation |
| **Insider cluster first, then 13D** | Insiders may have tipped activist, or both see same undervaluation | **High** -- but watch for information leakage |
| **Simultaneous (within 7 days)** | Convergence of independent signals | **Very High** |

- Duong et al. (2025) show insiders buy in the **20 days before** a 13D filing, so the most common pattern is actually **insider cluster first, 13D second**.
- Our current system uses a +/-30 day window for insider_activist compounds. This is well-calibrated.

### 3E. Amendment Patterns

- **Increasing stake** (13D/A showing higher ownership %) = doubling down, strongest conviction signal.
- **Softening purpose language** = moving toward settlement.
- **Adding board nominees** = campaign escalation.
- **Conversion 13D to 13G** = campaign over.

**Implementation note:** We currently store the initial 13D filing. Tracking amendments (13D/A) would add a temporal dimension to the signal.

---

## 4. Pitfalls and Risks

### 4A. Lookback Bias

- **Risk:** Testing compound signals using the transaction date (when the insider actually trades) rather than the filing date (when public investors learn about it).
- **Evidence:** Ozlen and Batumoglu (2025) show **70-80% of alpha dissipates between the transaction date and the filing date**. This is the "death of insider trading alpha" for public investors.
- **Our mitigation:** We use the Form 4 filing date (when the filing hits EDGAR), not the transaction date. This is correct. However, Form 4 must be filed within **2 business days** of the transaction, so there's still some decay.
- **13D specific:** The 13D must now be filed within **5 business days** (shortened from 10 in February 2024 per SEC modernization rules). The window between threshold crossing and filing is when the activist and wolf pack accumulate shares.

### 4B. Information Leakage

- **Risk:** Insider trading before the 13D is filed may be **illegal insider trading** (trading on MNPI about the activist's plans), not a legitimate signal.
- **Evidence:** Duong et al. (2025) show insiders earn 12.09% when buying before 13D filings, and the SEC only enforces against 0.5% of filing violations.
- **Our mitigation:** We are not endorsing or facilitating insider trading. We are detecting publicly filed Form 4 trades and publicly filed 13D filings. By the time both are public, the information asymmetry has resolved. Our compound signal fires **after** both filings are public.
- **Ethical note:** Our product helps public investors catch up to what insiders already know. This is market-democratizing, not market-manipulating.

### 4C. Correlation vs Causation

- **Risk:** Both insiders and activists may be attracted by the same **fundamental undervaluation**, rather than the compound signal having independent predictive power.
- **Evidence:** Brav et al. find 59.5% of activist campaigns cite "undervaluation." Insiders may simply be buying because the stock is cheap, not because they know an activist is coming.
- **Our mitigation:** This is actually fine for our purposes. If both signal sources independently identify undervaluation, the **convergence itself is the signal** -- two independent assessments of value agree. We don't need to prove causation; we need to prove that the compound signal predicts returns better than either signal alone.

### 4D. Survivorship Bias

- **Risk:** Our 13D dataset may overrepresent successful campaigns.
- **Mitigation:** Our database contains 7,463 13D filings, which should include both successful and unsuccessful campaigns.

### 4E. Small Sample Size for Compound Events

- **Risk:** The overlap between insider clusters and 13D filings may be small (currently 10 active compound signals from 114 companies with overlap).
- **Mitigation:** This is expected. Compound signals are rare by definition -- that's what makes them high-conviction. The academic literature shows the same pattern: rare events with strong predictive power.

### 4F. SEC Rule Changes (Feb 2024)

- 13D filing deadline shortened from **10 calendar days to 5 business days**.
- 13D amendments now due within **2 business days** (previously "promptly").
- Filings now require **structured, machine-readable data** (XBRL, effective Dec 2024).
- **Impact:** Less time for insiders and wolf packs to trade before public disclosure. This may reduce the insider-before-13D pattern over time, but increases the timeliness of our compound signal detection.

---

## 5. Implementation Approaches

### 5A. Current Implementation (Compound Signal Service)

Our existing `compound_signal_service.py` already implements the core architecture:

| Compound Type | Sources | Base Score | Decision Logic |
|---------------|---------|-----------|----------------|
| `insider_activist` | Form 4 cluster + 13D | 60 | BUY (>=70), WATCH (>=50), PASS (<50) |
| `activist_8k` | 13D + 8-K material event | 60 | Max WATCH (lagging indicator) |
| `triple_convergence` | Form 4 + 13D + 8-K | 85 | BUY (>=70), WATCH (>=50), PASS (<50) |
| `insider_activist_sell` | Form 4 sell cluster + 13D | 60 | Always PASS |

**Scoring bonuses:**
- Activist pct >10%: +10 | >=7%: +5
- Insider value >$500K: +10 | >$100K: +5
- Timing gap <=7 days: +10 | <=14 days: +5
- 8-K material agreement: +5

### 5B. Recommended Enhancements (Academic Evidence-Based)

#### Enhancement 1: Temporal Sequencing Score

Based on Duong et al. (2025), add a bonus for the sequence of signals:

```
If insider_cluster_date BEFORE activist_date (within 30 days):
    +5 (insiders detecting activist interest -- "betting on my enemy" pattern)
If activist_date BEFORE insider_cluster_date (within 30 days):
    +10 (insiders confirming activist thesis -- independent validation)
If simultaneous (within 7 days):
    +8 (convergence pattern)
```

The "activist first, then insiders confirm" pattern is the highest-conviction because it represents **two independent assessments** -- the activist's fundamental analysis plus insiders' private knowledge of the company's trajectory.

#### Enhancement 2: Opportunistic Trade Filter

Based on Cohen et al. (2012), classify insider trades as opportunistic vs routine:

```
For each insider in the cluster:
    Look at their trade history (prior 3 years)
    If they consistently trade in the same month each year -> routine (weight: 0.5x)
    If this trade breaks their pattern -> opportunistic (weight: 1.5x)
```

This could improve our hit rate by filtering out compensation-driven trades that happen to coincide with activist filings.

#### Enhancement 3: Role-Weighted Scoring

Based on Seyhun (1986, 1998), adjust insider trade weights by role:

```
Officer-director (chairman, CEO, CFO): weight 1.5x
Officer: weight 1.2x
Director: weight 1.0x
10% owner: weight 0.5x (weakest predictor per academic evidence)
```

We already partially do this; should formalize with explicit multipliers.

#### Enhancement 4: 13D Purpose Text Analysis

Extract high-signal keywords from the 13D purpose text:

```
"strategic alternatives" OR "sale of the company" -> +10 (M&A catalyst)
"board seats" OR "nominate directors" -> +7 (escalation)
"undervalued" OR "maximize shareholder value" -> +5 (standard activist thesis)
"constructive discussions" OR "dialogue" -> +0 (passive tone)
```

#### Enhancement 5: Amendment Tracking

Track 13D/A amendments for increasing stake:

```
If ownership_pct increased from prior filing -> +8 (doubling down)
If ownership_pct decreased -> -5 (exiting)
If 13G-to-13D conversion -> +12 (passive to activist upgrade)
If 13D-to-13G conversion -> -10 (campaign over)
```

#### Enhancement 6: Wolf Pack Detection

When multiple 13D filers target the same company within 90 days:

```
2 activists: +10
3+ activists: +15 (rare but very high conviction)
```

### 5C. Proposed Updated Scoring Model

```
Base score:
  2 sources (insider + activist): 60
  3 sources (insider + activist + 8-K): 85

Activist conviction:
  Ownership >10%: +10
  Ownership 7-10%: +5
  Purpose text (M&A keywords): +10
  Purpose text (board seats): +7
  Increasing stake (amendment): +8
  13G-to-13D conversion: +12

Insider conviction:
  Total value >$500K: +10
  Total value >$100K: +5
  3+ distinct insiders: +5
  Opportunistic trades only: +5
  Officer/chairman in cluster: +5

Timing:
  Gap <=7 days: +10
  Gap <=14 days: +5
  Activist first, insiders confirm: +5
  Simultaneous: +3

Material events:
  8-K material agreement (1.01): +5
  Wolf pack (2+ activists): +10

Decision thresholds:
  BUY: score >= 75 (was 70)
  WATCH: score >= 55 (was 50)
  PASS: < 55
  Always PASS for sell compounds
```

---

## 6. Expected Alpha from Compound Signals

### 6A. Academic Return Estimates

| Signal Source | Expected Abnormal Return | Time Horizon |
|---------------|:------------------------:|:------------:|
| Insider cluster buy (alone) | +2.1%/month, ~8-10% annualized | 1-12 months |
| 13D activist filing (alone) | +7% announcement + 11.4% subsequent year | 0-18 months |
| Insider buy before 13D (compound) | **+12.09%** (Duong et al.) | Event window |
| Insider buy before 13D, no prior talks | **+14.49%** (Duong et al.) | Event window |
| Opportunistic insider trades only | +9.8% annualized VW (Cohen et al.) | Annual |
| 13D vs 13G announcement return | 6.34% vs 0.59% | Announcement |

### 6B. Realistic Expectations for LookInsight

Given our current 65.9% hit rate and +8.0% alpha at 90 days on midcap insider clusters:

- **Compound signals (insider + activist) should improve hit rate to ~75-80%** based on the additional information content.
- **Alpha should improve to +12-15% at 90 days** based on the Duong et al. finding of 12.09% for insiders buying near 13D filings.
- **Sample size will be small** (~10-20 active compound signals at any time from our database of 7,463 13D filings and ~90K insider transactions).
- **The rarity is the feature**: high-conviction, low-frequency signals command premium pricing.

### 6C. Comparison to Stand-Alone Signals

```
Insider cluster (our current product):     65.9% hit rate, +8.0% alpha @ 90d
Insider + 13D compound (expected):          ~75-80% hit rate, +12-15% alpha @ 90d
Triple convergence (insider + 13D + 8-K):   ~80-85% hit rate, +15-20% alpha @ 90d (rare)
```

These estimates are directional, not backtested. Actual backtesting against our database should be the next step.

---

## 7. Key Academic References (Complete Bibliography)

1. **Duong, Pi, Sapp (2025).** "Betting on my enemy: Insider trading ahead of hedge fund 13D filings." *Journal of Corporate Finance*, 93.
   - [ScienceDirect](https://www.sciencedirect.com/science/article/abs/pii/S0929119925000628)

2. **Brav, Jiang, Partnoy, Thomas (2008).** "Hedge Fund Activism, Corporate Governance, and Firm Performance." *Journal of Finance*.
   - [SSRN](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=1111778)

3. **Bebchuk, Brav, Jiang (2015).** "The Long-Term Effects of Hedge Fund Activism." *Columbia Law Review*.
   - [NBER](https://www.nber.org/system/files/working_papers/w21227/w21227.pdf)

4. **Alldredge (2019).** "Do Insiders Cluster Trades with Colleagues? Evidence from Daily Insider Trading." *Journal of Financial Research*.
   - [Wiley](https://onlinelibrary.wiley.com/doi/abs/10.1111/jfir.12172)

5. **Cohen, Malloy, Pomorski (2012).** "Decoding Inside Information." *Journal of Finance*.
   - [NBER](https://www.nber.org/system/files/working_papers/w16454/w16454.pdf)

6. **Seyhun (1998).** "Investment Intelligence from Insider Trading." *MIT Press*.
   - [MIT Press](https://mitpress.mit.edu/9780262692342/investment-intelligence-from-insider-trading/)

7. **Brav, Dasgupta, Mathews (2021).** "Wolf Pack Activism." *Management Science*.
   - [ECGI](https://www.ecgi.global/sites/default/files/working_papers/documents/bravdasguptamathewsfinal.pdf)

8. **Ozlen, Batumoglu (2025).** "The Death of Insider Trading Alpha: Most Returns Occur Before Public Disclosure." *SSRN Working Paper*.
   - [SSRN](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=5966834)

9. **Brav, Jiang, Li (2022).** "Recent Advances in Research on Hedge Fund Activism: Value Creation and Identification." *ECGI Working Paper*.
   - [ECGI](https://www.ecgi.global/sites/default/files/working_papers/documents/bravjianglifinal_0.pdf)

---

## 8. Bottom Line for LookInsight

### What the research validates:
1. **Insider cluster + 13D is a real, documented alpha source** -- Duong et al. (2025) show 12.09% returns for insiders buying before 13D filings.
2. **Our compound signal architecture is academically sound** -- combining independent signal sources that converge is the right approach.
3. **No competitor does this** -- existing alt-data providers sell Form 4 data OR 13D data, never as a combined signal product.
4. **The compound signal is rare but high-conviction** -- exactly what institutional buyers want.

### What we should improve:
1. **Add opportunistic/routine classification** to filter noise from compensation-driven trades.
2. **Track 13D amendments and 13G-to-13D conversions** as separate signal events.
3. **Add purpose text keyword extraction** from 13D filings.
4. **Implement temporal sequencing scoring** (activist first + insiders confirm = strongest).
5. **Backtest compound signals against our actual database** to get real hit rates and alpha figures.

### What to be careful about:
1. **Alpha decay is real** -- 70-80% of insider trading alpha disappears before public disclosure. We must use filing dates, not transaction dates.
2. **Small sample sizes** -- compound events are rare. We need to be honest about statistical significance.
3. **Regulatory changes** -- the shortened 13D filing deadline (5 business days since Feb 2024) may reduce pre-filing trading opportunities over time.
