# ASA-RSCH-FAM-PUTWRITE-001 — Index Put Writing (cash-secured)

## Identity

- **Research ID:** ASA-RSCH-FAM-PUTWRITE-001
- **Strategy:** Index Put Writing (cash-secured)
- **Family:** FAM-VRP-INDEX-PUTWRITE (E1 insurance selling); taxonomy in `research/sprints/ASA-RES-SPRINT-001/RES-001B-taxonomy.md`
- **Research status:** TRIAGE
- **Created:** 2026-09-26
- **Updated:** 2026-09-26

This is a family-level comparable record (RES-001C). Status describes evidence only. It is not a priority, selection, or implementation signal. Numeric values are stated only where a source reports them; everything else is UNKNOWN. Claim classes: REPORTED / DERIVED / INFERENCE / UNKNOWN. Source verification depth for this record: bibliographic_and_abstract: 7, full_text_reviewed: 1.

## Thesis

### Concise description

Systematically sell one-month (or weekly) at-the-money or OTM index puts, fully collateralized by T-bills, rolled on a calendar schedule.

### Proposed economic or behavioral mechanism

Index puts are priced above their physical expected payoff. Sources attribute this variously to (a) compensation for crash, volatility-jump and liquidity risk (CONSTANTINIDES-JACKWERTH-SAVOV-2013, ERAKER-2021), (b) end-user demand pressure on OTM puts (GARLEANU-PEDERSEN-POTESHMAN-2009), or (c) an anomaly no model in a broad class explains (BONDARENKO-2014). The mechanism is **contested**; the premium's existence is not.

## Evidence

Sample, universe and method context: Evidence is overwhelmingly S&P 500 (SPX) monthly ATM or OTM puts, 1986-2018 for the longest index study. Single-stock and ETF (SPY) variants are not directly studied in the sources recorded here.

### Original research

- **UNGAR-MORAN-2009** — Cboe PUT outperformed the S&P 500 with significantly lower volatility; IV usually above subsequent RV. Sponsor-affiliated author.

### Supporting research

- **BONDARENKO-2019-CBOE** — 1986-2018 PUT: 9.54% compound, Sharpe 0.65 vs S&P 500 9.80% / 0.49; max drawdown -32.7% vs -50.9%. Cboe-published.
- **BONDARENKO-2014** — Put overpricing not explained by a broad model class.
- **CHAMBERS-ET-AL-2014** — Put returns inconsistent with pricing models over 1987-2012.
- **COVAL-SHUMWAY-2001** — Expected put returns below the risk-free rate.

### Independent replications

- **CHAMBERS-ET-AL-2014** — Re-examines the BROADIE-CHERNOV-JOHANNES-2009 method on 1987-2012 and rejects model consistency; counts as independent re-analysis.

### Failed replications

- **BROADIE-CHERNOV-JOHANNES-2009** — OTM put-writing returns are statistically insignificant relative to Black-Scholes/Heston because of extreme sampling uncertainty.

### Contradictory research

- **CONSTANTINIDES-JACKWERTH-SAVOV-2013** — Short-maturity OTM put alphas become insignificant once crisis factors are included, i.e. the premium is risk compensation, not free alpha.
- **SANTACLARA-SARETTO-2009** — Margin requirements cap notional and force loss realization; frictions economically important.

### Post-publication evidence

- **BONDARENKO-2019-CBOE** — 2006-2018 (after the index's 2007 launch): PUT Sharpe 0.50 vs S&P 500 0.51; compound 5.97% vs 7.59%. REPORTED; DERIVED: no post-launch risk-adjusted advantage in that window.

### Reported empirical results

| Field | Value |
|---|---|
| Reported return metrics | REPORTED: PUT 1986-2018 9.54%/yr compound (BONDARENKO-2019-CBOE). Net-of-cost treatment of the index is UNKNOWN. |
| Reported risk metrics | REPORTED: PUT SD 9.95% vs 14.93% S&P 500; beta and full distribution UNKNOWN beyond summary. |
| Drawdown / tail | REPORTED: max drawdown -32.7% (Jan-2009), longest drawdown 40 months (BONDARENKO-2019-CBOE). INFERENCE: loss concentrated in crash months. |
| Opportunity frequency | Calendar-driven: 12 entries/yr (monthly) or ~52 (weekly WPUT). Opportunity frequency is not signal-limited. |
| Regime dependence | REPORTED: VRP averages 4.2 vol points 1990-2018 (BONDARENKO-2019-CBOE) but is time-varying; returns weak in 2006-2018. Crash regimes dominate losses (INFERENCE). |
| Persistence | Mixed: long-sample positive; post-launch subperiod no risk-adjusted edge (REPORTED numbers, DERIVED comparison). |
| Transaction-cost sensitivity | REPORTED: frictions and margin economically important (SANTACLARA-SARETTO-2009). Index cost assumptions UNKNOWN. |

## Specification

As documented in the sources. No rule is invented, and missing parameters are UNKNOWN.

| Field | Value |
|---|---|
| Entry rules | Calendar roll (typically 3rd Friday monthly; weekly for WPUT). No signal. |
| DTE / expiration | ~1 month (PUT); 1 week (WPUT). |
| Strike / delta | ATM (PUT); OTM variants in academic studies with moneyness targets (UNKNOWN exact). |
| Liquidity requirements | SPX options (deepest US index option market). |
| Exit rules | Hold to expiration / cash settlement. |
| Roll rules | Monthly/weekly calendar roll. |
| Sizing assumptions | Fully cash-secured (notional collateral in T-bills). |
| Exclusions | None documented. |
| Unresolved rule gaps | Exact strike rounding, settlement-price conventions and cost treatment of the index not recovered; ETF (SPY) and single-stock transfers unstudied here. |

## Practical evidence

| Risk field | Value |
|---|---|
| Maximum / tail risk | Undefined per position up to strike × notional (cash-secured, so no leverage). Tail = equity crash. |
| Liquidity risk | Low for SPX; UNKNOWN for single names. |
| Assignment / exercise risk | European SPX: none. American ETF variants: early assignment possible (INFERENCE). |
| Gap risk | High: overnight/crash gaps pass through fully. |
| Volatility-regime risk | High: losses cluster when volatility spikes. |
| Model dependency | Low. |
| Crowding / decay evidence | INFERENCE: large option-income fund AUM may compress the premium; no direct crowding study recorded. |
| Known failure modes | Crash months (e.g. 2008 per max drawdown date); margin calls for levered writers (SANTACLARA-SARETTO-2009). |

## Adversarial review

| Question | Answer |
|---|---|
| Independently replicated? | Partially: model-consistency re-analysis (CHAMBERS-ET-AL-2014); index studies are sponsor-linked. |
| Failed replications? | Yes: significance fails under model-based inference (BROADIE-CHERNOV-JOHANNES-2009). |
| Later research reduces claim? | Yes: crisis-factor explanation (CONSTANTINIDES-JACKWERTH-SAVOV-2013). |
| Persisted after publication? | Weakly/no: 2006-2018 Sharpe below S&P 500. |
| Data mining/selection? | Low for rules (benchmark); sample-start sensitivity UNKNOWN. |
| Concentrated in a small period? | Losses concentrated in crashes (INFERENCE). |
| Parameter-dependent? | UNKNOWN beyond monthly vs weekly difference. |
| Costs change conclusion? | Possibly for levered or aggressive writing (SANTACLARA-SARETTO-2009). |
| Execution realistic? | Index uses settlement conventions; UNKNOWN. |
| Another known factor? | Largely equity beta + short volatility/jump risk. |
| Look-ahead info? | No. |
| Known failure regime? | Crashes, volatility spikes. |
| Crowding/decay? | Post-launch weakness is consistent with decay but not proof. |
| Omission risk? | Omitting the 2006-2018 subperiod or BCJ-2009 would overstate the case. |

## ASA capability mapping

Performed after the external evidence assessment above. Implementation ease does not affect the evidence rating.

| Field | Value |
|---|---|
| Required market data | Index option chain (SPX), T-bill rate. |
| Required analytics | None beyond strike selection; margin model for levered variants (A15). |
| Required history | Historical SPX option prices for any external replication (A08). |
| Required event data | None. |
| Structural primitives (RES-001B §3) | P01; A02 (variants), A15. |
| Apparent existing ASA capabilities | Option chain, quote, delta selection (for an ETF such as SPY). |
| Apparent missing ASA capabilities | SPX index instrument and settlement identity (per STRATEGY-LIBRARY-001 CNDR Architect decision); P01 runtime structure; historical option panel; T-bill/collateral model UNKNOWN. |
| Execution complexity | Low (single leg, calendar roll). |

## Assessment

### Strongest supporting evidence

Long-sample benchmark evidence plus peer-reviewed rejection of model consistency (CHAMBERS-ET-AL-2014, BONDARENKO-2014).

### Strongest contradictory evidence

Premium is risk compensation that vanishes under crisis factors and weakened post-launch (CONSTANTINIDES-JACKWERTH-SAVOV-2013; BONDARENKO-2019-CBOE subperiod).

### Unresolved questions

- Net-of-cost index returns
- Transfer to SPY / single names
- Optimal moneyness
- Whether post-2006 weakness is regime or decay

### Evidence limitations

Most sources were verified at bibliographic-and-abstract depth. Sample periods, cost models, and exact rules are often UNKNOWN until full texts are recovered.

### Qualification status

TRIAGE

### Qualification basis

TRIAGE: abundant external evidence establishes the premium's existence; interpretation and post-publication persistence are contested, and full-text recovery (costs, exact rules) has not been done. Not qualified.

## Research history

- 2026-09-26: record created as TRIAGE in ASA-RES-SPRINT-001 (RES-001C). No prior conclusion existed.

## Provenance

- `research/sources/UNGAR-MORAN-2009.yaml`
- `research/sources/BONDARENKO-2019-CBOE.yaml`
- `research/sources/BONDARENKO-2014.yaml`
- `research/sources/CHAMBERS-ET-AL-2014.yaml`
- `research/sources/COVAL-SHUMWAY-2001.yaml`
- `research/sources/BROADIE-CHERNOV-JOHANNES-2009.yaml`
- `research/sources/CONSTANTINIDES-JACKWERTH-SAVOV-2013.yaml`
- `research/sources/SANTACLARA-SARETTO-2009.yaml`
