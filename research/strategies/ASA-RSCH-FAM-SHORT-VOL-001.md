# ASA-RSCH-FAM-SHORT-VOL-001 — Index Short Volatility (straddle / strangle / delta-hedged / variance)

## Identity

- **Research ID:** ASA-RSCH-FAM-SHORT-VOL-001
- **Strategy:** Index Short Volatility (straddle / strangle / delta-hedged / variance)
- **Family:** FAM-VRP-INDEX-SHORT-VOL (E1 insurance selling); taxonomy in `research/sprints/ASA-RES-SPRINT-001/RES-001B-taxonomy.md`
- **Research status:** TRIAGE
- **Created:** 2026-09-26
- **Updated:** 2026-09-26

This is a family-level comparable record (RES-001C). Status describes evidence only. It is not a priority, selection, or implementation signal. Numeric values are stated only where a source reports them; everything else is UNKNOWN. Claim classes: REPORTED / DERIVED / INFERENCE / UNKNOWN. Source verification depth for this record: bibliographic_and_abstract: 9, bibliographic_and_search_engine_summary: 1.

## Thesis

### Concise description

Sell index volatility directly, via short straddles/strangles, delta-hedged short options, or short variance, to harvest the market volatility risk premium.

### Proposed economic or behavioral mechanism

Negative market volatility risk premium: investors pay to hedge volatility increases (BAKSHI-KAPADIA-2003, CARR-WU-2009). Equilibrium models can generate it as risk compensation (ERAKER-2021). Jump fears rise after jumps (TODOROV-2010).

## Evidence

Sample, universe and method context: Predominantly S&P 500 index options; sample periods UNKNOWN at abstract depth except FALLON-PARK-YU-2015 (multi-market).

### Original research

- **COVAL-SHUMWAY-2001** — Zero-beta ATM straddles lose ~3%/week on average (buyer side).
- **BAKSHI-KAPADIA-2003** — Delta-hedged long options underperform zero; more so at higher volatility.

### Supporting research

- **CARR-WU-2009** — Model-free VRP measurement across 5 indexes and 35 stocks.
- **FALLON-PARK-YU-2015** — Short volatility Sharpe ~1.0 across global markets with substantial tail risk.
- **BOLLEN-WHALEY-2004** — Simulated delta-neutral writing earns returns matching IV above RV.
- **ISRAELOV-NIELSEN-2015-JPM** — Protection remains expensive even in calm markets.

### Independent replications

- **FALLON-PARK-YU-2015** — Cross-market extension (different authors/markets).

### Failed replications

- **BROADIE-CHERNOV-JOHANNES-2009** — Straddle/delta-hedged returns explainable by jump risk premia and estimation risk (i.e. consistent with models).

### Contradictory research

- **CONSTANTINIDES-JACKWERTH-SAVOV-2013** — Crisis factors explain option portfolio returns.

### Post-publication evidence

- **EUREKAHEDGE-CBOE-VOL-INDICES** — Short-vol hedge-fund index annualized ~8.9%, Sharpe ~0.78 to 2016-03 (self-reported, secondary).
- **AUGUSTIN-CHENG-VANDENBERGEN-2021** — Feb-2018 short-volatility failure (ETP vehicle).

### Reported empirical results

| Field | Value |
|---|---|
| Reported return metrics | REPORTED: buyer straddle ~-3%/week (COVAL-SHUMWAY-2001); seller return is the negative gross of costs (DERIVED, not independently reported). |
| Reported risk metrics | REPORTED: short-vol Sharpe ~1.0 (FALLON-PARK-YU-2015). |
| Drawdown / tail | REPORTED: substantial tail risk (FALLON-PARK-YU-2015). |
| Opportunity frequency | Calendar or signal-conditioned (VRP level, JOHNSON-2017 SLOPE). |
| Regime dependence | REPORTED: VRP time-varying; BOLLERSLEV-TAUCHEN-ZHOU-2009 and JOHNSON-2017 show predictable variation. High losses in volatility spikes (INFERENCE). |
| Persistence | Positive through 2016 in hedge-fund indices (secondary). |
| Transaction-cost sensitivity | REPORTED: effective option spreads are lower than conventionally measured for timed execution (MURAVYEV-PEARSON-2020); strategy-level net results UNKNOWN. |

## Specification

As documented in the sources. No rule is invented, and missing parameters are UNKNOWN.

| Field | Value |
|---|---|
| Entry rules | None or VRP-conditioned. |
| DTE / expiration | Front month typical (UNKNOWN exact). |
| Strike / delta | ATM (straddle) or OTM (strangle). |
| Liquidity requirements | Index options. |
| Exit rules | Expiration or hedged to maturity. |
| Roll rules | Monthly. |
| Sizing assumptions | UNKNOWN (margin-dependent). |
| Exclusions | None documented. |
| Unresolved rule gaps | Hedging frequency, strangle widths and sizing rules not recovered. |

## Practical evidence

| Risk field | Value |
|---|---|
| Maximum / tail risk | Undefined. |
| Liquidity risk | Low (index). |
| Assignment / exercise risk | None for European index. |
| Gap risk | Very high. |
| Volatility-regime risk | Very high. |
| Model dependency | Medium (hedging model). |
| Crowding / decay evidence | Feb-2018 event shows crowding/structural risk in ETP form. |
| Known failure modes | Volatility spikes; jumps; hedging error. |

## Adversarial review

| Question | Answer |
|---|---|
| Independently replicated? | VRP sign repeatedly found; strategy-level independent replication limited. |
| Failed? | BCJ-2009: statistically explainable. |
| Later research reduces? | Crisis-factor pricing. |
| Persisted? | Positive to 2016 in fund indices (secondary). |
| Data mining? | Low for sign; conditioning signals higher. |
| Concentrated? | Losses concentrated in spikes. |
| Parameter-dependent? | Moneyness (BAKSHI-KAPADIA-2003). |
| Costs? | Execution-model dependent. |
| Execution realistic? | Hedging assumptions UNKNOWN. |
| Another factor? | Short volatility and jump risk. |
| Look-ahead? | Conditioning variables must be lagged (INFERENCE). |
| Failure regime? | Spikes, crashes. |
| Crowding? | Yes, event evidence 2018. |
| Omission risk? | Omitting tail-risk and BCJ findings overstates Sharpe. |

## ASA capability mapping

Performed after the external evidence assessment above. Implementation ease does not affect the evidence rating.

| Field | Value |
|---|---|
| Required market data | Index chain; underlying for hedging. |
| Required analytics | A03, A04, A14 (hedging), A15 (margin); A11/A05 for conditioning. |
| Required history | Historical option prices; high-frequency RV for BTZ-style conditioning. |
| Required event data | None. |
| Structural primitives (RES-001B §3) | P03, P04, P10, P11. |
| Apparent existing ASA capabilities | Chain, IV/greeks, realized volatility, ATM IV vs RV. |
| Apparent missing ASA capabilities | Straddle/strangle runtime structure; delta-hedging; SPX identity; historical option panel. |
| Execution complexity | Medium (unhedged) to high (hedged). |

## Assessment

### Strongest supporting evidence

Consistent negative VRP across methods and markets (BAKSHI-KAPADIA-2003, CARR-WU-2009, FALLON-PARK-YU-2015).

### Strongest contradictory evidence

Returns consistent with jump/crisis risk pricing (BROADIE-CHERNOV-JOHANNES-2009, CONSTANTINIDES-JACKWERTH-SAVOV-2013).

### Unresolved questions

- Net-of-cost returns of unhedged structures
- Conditioning benefit out of sample
- Transfer to ETF options

### Evidence limitations

Most sources were verified at bibliographic-and-abstract depth. Sample periods, cost models, and exact rules are often UNKNOWN until full texts are recovered.

### Qualification status

TRIAGE

### Qualification basis

TRIAGE: the underlying premium is among the best-documented in the landscape, but strategy-level, net-of-cost, rule-explicit evidence has not been recovered.

## Research history

- 2026-09-26: record created as TRIAGE in ASA-RES-SPRINT-001 (RES-001C). No prior conclusion existed.

## Provenance

- `research/sources/COVAL-SHUMWAY-2001.yaml`
- `research/sources/BAKSHI-KAPADIA-2003.yaml`
- `research/sources/CARR-WU-2009.yaml`
- `research/sources/FALLON-PARK-YU-2015.yaml`
- `research/sources/BOLLEN-WHALEY-2004.yaml`
- `research/sources/ISRAELOV-NIELSEN-2015-JPM.yaml`
- `research/sources/BROADIE-CHERNOV-JOHANNES-2009.yaml`
- `research/sources/CONSTANTINIDES-JACKWERTH-SAVOV-2013.yaml`
- `research/sources/EUREKAHEDGE-CBOE-VOL-INDICES.yaml`
- `research/sources/AUGUSTIN-CHENG-VANDENBERGEN-2021.yaml`
