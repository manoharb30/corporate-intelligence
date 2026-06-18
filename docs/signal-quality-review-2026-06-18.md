# Signal Quality Review — 2026-06-18

Per-arrival qualitative review (no automated quality gate; see memory
`project_quality_gate_design`). Covers the Jun 16–17 backfill signals and a
one-time quality scan of the immature strong_buy cohort's drawdowns.

## 1. Jun 16–17 backfill (2 new strong_buy signals, both dated Jun 16)

| Ticker | Company | Verdict | Action |
|---|---|---|---|
| CXT | Crane NXT, Co. | High-quality ~$3.0B industrial midcap; CEO Aaron Saak $1.01M + officer $149K cluster; durable currency-security/payments franchise; 2.9x leverage post-M&A but deleveraging on plan | **KEPT** |
| REI | Ring Energy, Inc. | True mcap ~$233–284M (253.9M sh × $1.12) — **below the $300M floor**; passed only on a stale 2026-04-22 yfinance mcap ($301.8M). Sub-$2 over-levered (debt > equity) Permian E&P, $162M Q1 impairment | **BLACKLISTED + removed** (CIK 0001384195) |

REI is the same stale-mcap failure mode as SBMT (`mcap_boundary_recheck`).

## 2. Immature cohort HR snapshot (as of Jun 17, unrealized, raw — NOT SPY-alpha)

22 immature strong_buy with current prices (CXT pending): **HR 50% (11/22 positive)**,
mean +4.1%, median ≈ flat (−0.4%). Mean skewed by NSP (+64%) and GO (+40%).
This is mid-flight and NOT comparable to the matured 67% HR / +9% alpha headline.

## 3. Drawdown analysis — why the losers are down

All six drawdown names are inside the $300M–$5B band (not eligibility failures
like REI). The losses concentrate in identifiable low-quality archetypes:

| Ticker | Company | Mcap | Drawdown | Cause | Quality verdict |
|---|---|---|---|---|---|
| RHLD | Resolute Holdings Mgmt | $1.17B | −17% | FY25 loss + over-levered M&A; valuation needs $Bs of future deals | **⛔ Control vehicle** |
| ALT | Altimmune | $601M | −21% | $225M dilutive raise ~13% below mkt + CEO exit | HIGH RISK — binary biotech |
| BETR | Better Home & Finance | $586M | −16% | $69M dilutive raise at signal price + Q1 loss ~2× miss | HIGH RISK — distressed post-SPAC |
| VTS | Vitesse Energy | $763M | −9% | 22% dividend cut + M&A dilution (oil was firm) | QUALITY CONCERN (mild) |
| GRNT | Granite Ridge | $700M | −10% | Gas-price crash + non-cash hedge loss | Sector beta — acceptable |
| ALG | Alamo Group | $1.88B | −7% | Cyclical margin compression on a beat-and-raise | ✅ Quality name — normal pullback |

### Detail

- **RHLD — control vehicle (LOGC pattern).** Asset-light, externally-managed
  alternative-asset manager spun out of CompoSecure (Feb 2026). Owns **no equity**
  in the businesses it manages; collects a self-dealing **2.5%-of-EBITDA fee** with
  no hurdles and near-permanent renewal. Founder-controlled "controlled company"
  (Tungsten/Cote/Knott entities ~50.5% voting). The Mar-17 cluster is Kurt Schoen
  ($71K) + **John D. Cote ($78K) — a controlling insider** buying his own fee
  vehicle. SIC "Finance Services," not an operating midcap. → **Blacklisted.**
- **ALT, BETR — capital-raise-dependent speculative names.** Both dropped on
  dilution shortly after the signal. ALT: pre-revenue single-asset binary biotech,
  Phase 3 readout ~2029. BETR: chronically loss-making post-SPAC mortgage lender
  that did a 1-for-50 reverse split to stay listed. Quality concerns, judgment
  calls — left in for now (no automated gate).
- **GRNT, VTS — commodity E&P** (same sector as REI). GRNT mostly sector beta on a
  low-leverage balance sheet (acceptable). VTS mild concern — cut its dividend 22%
  while oil was firm (idiosyncratic, not a dip the signal can ride).
- **ALG — genuine quality midcap.** Net cash (~$104M), 171% FCF conversion,
  beat-and-raise, dividend raised 13%. The −7% is a normal cyclical machinery
  de-rate. No concern.

## 4. Cross-cutting pattern (candidate red flag)

**3 of the 6 losers (ALT, BETR, VTS) fell on a dilution/capital action shortly
after the signal.** Insider clusters that precede equity raises or dividend cuts
are a recurring drawdown driver — a candidate qualitative red-flag at signal
arrival. Not an automated gate (consistent with per-arrival review).

## 5. Actions taken (2026-06-18)

- **REI** blacklisted (CIK 0001384195) + immature signal removed — midcap-floor failure.
- **RHLD** blacklisted (CIK 0002039497) + immature signal removed — control vehicle.
- `EXCLUDED_CIKS` now: `{0002064307 (LOGC), 0001384195 (REI), 0002039497 (RHLD)}`.
- Underlying Form 4 buys left GENUINE in all cases (company-eligibility exclusion,
  not transaction relabel).
