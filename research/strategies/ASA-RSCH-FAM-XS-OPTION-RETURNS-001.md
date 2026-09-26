# ASA-RSCH-FAM-XS-OPTION-RETURNS-001 — Cross-Sectional Equity Option Return Strategies (IV-RV, idiosyncratic vol, characteristics, illiquidity, order flow)

## Identity

- **Research ID:** ASA-RSCH-FAM-XS-OPTION-RETURNS-001
- **Strategy:** Cross-Sectional Equity Option Return Strategies (IV-RV, idiosyncratic vol, characteristics, illiquidity, order flow)
- **Family:** FAM-XS-OPTION-RETURNS (E3 volatility relative value); taxonomy in `research/sprints/ASA-RES-SPRINT-001/RES-001B-taxonomy.md`
- **Research status:** TRIAGE
- **Created:** 2026-09-26
- **Updated:** 2026-09-26

This is a family-level comparable record (RES-001C). Status describes evidence only. It is not a priority, selection, or implementation signal. Numeric values are stated only where a source reports them; everything else is UNKNOWN. Claim classes: REPORTED / DERIVED / INFERENCE / UNKNOWN. Source verification depth for this record: bibliographic_and_abstract: 12.

## Thesis

### Concise description

Each period, rank optionable stocks on a characteristic (historical-minus-implied volatility, idiosyncratic volatility, firm characteristics, option illiquidity, order imbalance) and go long/short delta-hedged options or straddles across the ranks.

### Proposed economic or behavioral mechanism

Dealer inventory risk and limits to arbitrage (CAO-HAN-2013, MURAVYEV-2016, CHRISTOFFERSEN-ET-AL-2018), demand pressure (GARLEANU-PEDERSEN-POTESHMAN-2009), informational frictions and mispricing (BALI-ET-AL-2023), short-sale constraints (RAMACHANDRAN-TAYAL-2021). Latent-factor work attributes much of it to common option factors (HORENSTEIN-VASQUEZ-XIAO-2026, GOYAL-SARETTO-2022-IPCA).

## Evidence

Sample, universe and method context: US single-stock options (OptionMetrics-era, ~1996 onward per BALI-ET-AL-2023); mostly delta-hedged monthly returns.

### Original research

- **GOYAL-SARETTO-2009** — Long high (RV-IV) / short low (RV-IV) option portfolios earn significant monthly returns, robust across conditions and not explained by factor models.

### Supporting research

- **CAO-HAN-2013** — Delta-hedged returns fall monotonically with idiosyncratic volatility.
- **ZHAN-ET-AL-2022** — Characteristic-sorted delta-hedged call writing: annual Sharpe above two, profitable after transaction costs.
- **BALI-ET-AL-2023** — 1996-2020 ML predictions profitable out of sample after costs.
- **CHRISTOFFERSEN-ET-AL-2018** — Illiquid options earn 2.5-3.4%/day more (risk-adjusted).
- **MURAVYEV-2016** — Past order imbalance is the strongest predictor.
- **RAMACHANDRAN-TAYAL-2021** — Short-sale constraints predict put returns on overpriced stocks.
- **HU-JACOBS-2020** — Call (put) returns decrease (increase) with underlying volatility.
- **CHOY-2015** — Low retail-proportion options outperform.

### Independent replications

- **HORENSTEIN-VASQUEZ-XIAO-2026** — Independent factor model reproduces the historical-minus-implied volatility effect as one of four factors.

### Failed replications

- None found in this sprint's search coverage (see `research/sprints/ASA-RES-SPRINT-001/RES-001A-landscape.md` §2).

### Contradictory research

- **GOYAL-SARETTO-2022-IPCA** — IPCA reduces equity-option strategy alpha by 50-75% (co-author of the original anomaly).
- **ARETZ-LIN-POON-2023** — Sign of volatility effects depends on moneyness and systematic vs idiosyncratic volatility.

### Post-publication evidence

- **BALI-ET-AL-2023** — Out-of-sample profitability through 2020 after costs (REPORTED).
- **HORENSTEIN-VASQUEZ-XIAO-2026** — The IV-RV signal persists as a priced factor.

### Reported empirical results

| Field | Value |
|---|---|
| Reported return metrics | REPORTED: Sharpe > 2 (ZHAN-ET-AL-2022), after costs; other magnitudes UNKNOWN at abstract depth. |
| Reported risk metrics | UNKNOWN. |
| Drawdown / tail | INFERENCE: short-option legs carry jump risk; portfolio diversification across names limits single-name gaps. |
| Opportunity frequency | Monthly rebalance across hundreds of names (INFERENCE from design). |
| Regime dependence | UNKNOWN. |
| Persistence | REPORTED positive OOS to 2020 (BALI-ET-AL-2023); alpha partially explained by factors. |
| Transaction-cost sensitivity | REPORTED: profitable after costs in ZHAN-ET-AL-2022 and BALI-ET-AL-2023; illiquidity premium suggests liquidity takers pay it (INFERENCE). |

## Specification

As documented in the sources. No rule is invented, and missing parameters are UNKNOWN.

| Field | Value |
|---|---|
| Entry rules | Monthly cross-sectional rank. |
| DTE / expiration | ~1 month (typical; UNKNOWN exact). |
| Strike / delta | ATM (typical). |
| Liquidity requirements | Option liquidity filters (UNKNOWN exact). |
| Exit rules | Monthly, held to maturity or rebalance. |
| Roll rules | Monthly. |
| Sizing assumptions | Equal- or value-weighted portfolios (UNKNOWN). |
| Exclusions | UNKNOWN. |
| Unresolved rule gaps | Exact filters, hedging frequency and cost models not recovered. |

## Practical evidence

| Risk field | Value |
|---|---|
| Maximum / tail risk | Undefined (short legs). |
| Liquidity risk | Material: evidence concentrated in illiquid options. |
| Assignment / exercise risk | Early assignment on American single-stock options (INFERENCE). |
| Gap risk | Single-name earnings gaps (INFERENCE). |
| Volatility-regime risk | UNKNOWN. |
| Model dependency | High (hedging, characteristics). |
| Crowding / decay evidence | UNKNOWN. |
| Known failure modes | Liquidity-taking costs; factor crashes (INFERENCE). |

## Adversarial review

| Question | Answer |
|---|---|
| Replicated? | Yes, via independent factor-model work. |
| Failed? | None found. |
| Later research reduces? | Yes: latent factors explain 50-75%. |
| Persisted? | Yes to 2020 in ML study. |
| Data mining? | High risk across many characteristics; mitigated by ML OOS. |
| Concentrated? | UNKNOWN. |
| Parameter-dependent? | UNKNOWN. |
| Costs? | Survives in two studies; illiquidity premium a warning. |
| Execution? | Mid/effective-spread assumptions UNKNOWN. |
| Another factor? | Yes: common option factors. |
| Look-ahead? | Characteristics must be lagged. |
| Failure regime? | UNKNOWN. |
| Crowding? | UNKNOWN. |
| Omission risk? | Counting each characteristic as independent evidence. |

## ASA capability mapping

Performed after the external evidence assessment above. Implementation ease does not affect the evidence rating.

| Field | Value |
|---|---|
| Required market data | Chains across a broad universe; underlying prices. |
| Required analytics | A03, A04, A12, A13, A14; characteristics. |
| Required history | **Historical option panel (A08) for any faithful replication.** |
| Required event data | Earnings dates for exclusions (INFERENCE). |
| Structural primitives (RES-001B §3) | P10, P12 (or P03, P12). |
| Apparent existing ASA capabilities | ATM IV vs RV, realized volatility, cross-sectional ranking, spread/OI quality. |
| Apparent missing ASA capabilities | Historical option panel; delta hedging; portfolio-of-structures construct; firm characteristics beyond price/volume; borrow fees; signed order flow. |
| Execution complexity | High. |

## Assessment

### Strongest supporting evidence

Many peer-reviewed, OOS-tested and after-cost results (ZHAN-ET-AL-2022, BALI-ET-AL-2023).

### Strongest contradictory evidence

Alpha largely spanned by latent factors (GOYAL-SARETTO-2022-IPCA, HORENSTEIN-VASQUEZ-XIAO-2026).

### Unresolved questions

- Liquidity-taker net returns
- Whether factor exposure (not alpha) is still a compensated premium worth harvesting

### Evidence limitations

Most sources were verified at bibliographic-and-abstract depth. Sample periods, cost models, and exact rules are often UNKNOWN until full texts are recovered.

### Qualification status

TRIAGE

### Qualification basis

TRIAGE: the most heavily peer-reviewed family in the landscape with OOS and after-cost support; interpretation as alpha is contested and ASA-relevant implementation details are unrecovered.

## Research history

- 2026-09-26: record created as TRIAGE in ASA-RES-SPRINT-001 (RES-001C). No prior conclusion existed.

## Provenance

- `research/sources/GOYAL-SARETTO-2009.yaml`
- `research/sources/CAO-HAN-2013.yaml`
- `research/sources/ZHAN-ET-AL-2022.yaml`
- `research/sources/BALI-ET-AL-2023.yaml`
- `research/sources/CHRISTOFFERSEN-ET-AL-2018.yaml`
- `research/sources/MURAVYEV-2016.yaml`
- `research/sources/RAMACHANDRAN-TAYAL-2021.yaml`
- `research/sources/HU-JACOBS-2020.yaml`
- `research/sources/CHOY-2015.yaml`
- `research/sources/HORENSTEIN-VASQUEZ-XIAO-2026.yaml`
- `research/sources/GOYAL-SARETTO-2022-IPCA.yaml`
- `research/sources/ARETZ-LIN-POON-2023.yaml`
