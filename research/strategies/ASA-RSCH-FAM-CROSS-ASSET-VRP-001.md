# ASA-RSCH-FAM-CROSS-ASSET-VRP-001 — Cross-Asset Volatility Premium (FX, commodity, rates)

## Identity

- **Research ID:** ASA-RSCH-FAM-CROSS-ASSET-VRP-001
- **Strategy:** Cross-Asset Volatility Premium (FX, commodity, rates)
- **Family:** FAM-CROSS-ASSET-VRP (E1 insurance selling); taxonomy in `research/sprints/ASA-RES-SPRINT-001/RES-001B-taxonomy.md`
- **Research status:** TRIAGE
- **Created:** 2026-09-26
- **Updated:** 2026-09-26

This is a family-level comparable record (RES-001C). Status describes evidence only. It is not a priority, selection, or implementation signal. Numeric values are stated only where a source reports them; everything else is UNKNOWN. Claim classes: REPORTED / DERIVED / INFERENCE / UNKNOWN. Source verification depth for this record: bibliographic_and_abstract: 3, bibliographic_only: 1.

## Thesis

### Concise description

Sell volatility in non-equity option markets.

### Proposed economic or behavioral mechanism

Same insurance-selling premium outside equities (ILMANEN-2012).

## Evidence

Sample, universe and method context: OTC FX options; global asset markets.

### Original research

- **LOW-ZHANG-2005** — Negative volatility risk premium in GBP, EUR, JPY, CHF options, decreasing in maturity.

### Supporting research

- **FALLON-PARK-YU-2015** — Short-vol Sharpe ~1.0 across global markets.
- **ILMANEN-2012** — Selling insurance rewarded broadly (review).
- **TROLLE-SCHWARTZ-2010** — Energy commodity VRP (unverified).

### Independent replications

- **FALLON-PARK-YU-2015** — Multi-asset extension.

### Failed replications

- None found in this sprint's search coverage (see `research/sprints/ASA-RES-SPRINT-001/RES-001A-landscape.md` §2).

### Contradictory research

- None found in this sprint's search coverage (see `research/sprints/ASA-RES-SPRINT-001/RES-001A-landscape.md` §2).

### Post-publication evidence

- None found in this sprint's search coverage (see `research/sprints/ASA-RES-SPRINT-001/RES-001A-landscape.md` §2).

### Reported empirical results

| Field | Value |
|---|---|
| Reported return metrics | REPORTED: Sharpe ~1.0 (standardized short-vol). |
| Reported risk metrics | Substantial tail risk (REPORTED). |
| Drawdown / tail | Severe. |
| Opportunity frequency | Monthly. |
| Regime dependence | UNKNOWN. |
| Persistence | UNKNOWN. |
| Transaction-cost sensitivity | UNKNOWN. |

## Specification

As documented in the sources. No rule is invented, and missing parameters are UNKNOWN.

| Field | Value |
|---|---|
| Entry rules | UNKNOWN |
| DTE / expiration | Short maturities strongest (LOW-ZHANG-2005). |
| Strike / delta | ATM straddles (FX). |
| Liquidity requirements | OTC. |
| Exit rules | UNKNOWN |
| Roll rules | Monthly. |
| Sizing assumptions | UNKNOWN |
| Exclusions | UNKNOWN |
| Unresolved rule gaps | Rules and costs UNKNOWN. |

## Practical evidence

| Risk field | Value |
|---|---|
| Maximum / tail risk | Undefined. |
| Liquidity risk | OTC access. |
| Assignment / exercise risk | n/a. |
| Gap risk | Devaluation/jumps. |
| Volatility-regime risk | High. |
| Model dependency | Low. |
| Crowding / decay evidence | UNKNOWN |
| Known failure modes | Currency crises (INFERENCE). |

## Adversarial review

| Question | Answer |
|---|---|
| Replicated? | Across markets. |
| Failed? | None found. |
| Later research? | Consistent. |
| Persisted? | UNKNOWN. |
| Data mining? | Low. |
| Concentrated? | UNKNOWN. |
| Parameter-dependent? | Maturity. |
| Costs? | UNKNOWN. |
| Execution? | OTC. |
| Another factor? | Global short vol. |
| Look-ahead? | No. |
| Failure regime? | Crises. |
| Crowding? | UNKNOWN. |
| Omission risk? | Tail risk. |

## ASA capability mapping

Performed after the external evidence assessment above. Implementation ease does not affect the evidence rating.

| Field | Value |
|---|---|
| Required market data | Non-equity option data. |
| Required analytics | A04. |
| Required history | Historical non-equity options. |
| Required event data | Central-bank events (INFERENCE). |
| Structural primitives (RES-001B §3) | P01, P03. |
| Apparent existing ASA capabilities | None for non-equity. |
| Apparent missing ASA capabilities | Non-equity instruments and data. |
| Execution complexity | Medium. |

## Assessment

### Strongest supporting evidence

Consistent VRP across asset classes.

### Strongest contradictory evidence

None found.

### Unresolved questions

- Listed-market implementability

### Evidence limitations

Most sources were verified at bibliographic-and-abstract depth. Sample periods, cost models, and exact rules are often UNKNOWN until full texts are recovered.

### Qualification status

TRIAGE

### Qualification basis

TRIAGE on evidence grounds; instrument universe is outside current ASA scope (a capability fact, not an evidence judgment).

## Research history

- 2026-09-26: record created as TRIAGE in ASA-RES-SPRINT-001 (RES-001C). No prior conclusion existed.

## Provenance

- `research/sources/LOW-ZHANG-2005.yaml`
- `research/sources/FALLON-PARK-YU-2015.yaml`
- `research/sources/ILMANEN-2012.yaml`
- `research/sources/TROLLE-SCHWARTZ-2010.yaml`
