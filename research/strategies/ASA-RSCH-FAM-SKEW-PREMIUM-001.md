# ASA-RSCH-FAM-SKEW-PREMIUM-001 — Index Skew Risk Premium (risk reversals / skew swaps)

## Identity

- **Research ID:** ASA-RSCH-FAM-SKEW-PREMIUM-001
- **Strategy:** Index Skew Risk Premium (risk reversals / skew swaps)
- **Family:** FAM-SKEW-PREMIUM-INDEX (E3 volatility relative value); taxonomy in `research/sprints/ASA-RES-SPRINT-001/RES-001B-taxonomy.md`
- **Research status:** INSUFFICIENT_EVIDENCE
- **Created:** 2026-09-26
- **Updated:** 2026-09-26

This is a family-level comparable record (RES-001C). Status describes evidence only. It is not a priority, selection, or implementation signal. Numeric values are stated only where a source reports them; everything else is UNKNOWN. Claim classes: REPORTED / DERIVED / INFERENCE / UNKNOWN. Source verification depth for this record: bibliographic_and_abstract: 3.

## Thesis

### Concise description

Sell downside skew (e.g. short OTM puts vs long OTM calls, delta-hedged, or skew swaps) to earn the premium embedded in the index smirk.

### Proposed economic or behavioral mechanism

Demand for index puts steepens the smirk (BOLLEN-WHALEY-2004, GARLEANU-PEDERSEN-POTESHMAN-2009); index risk-neutral skew is far more negative than single stocks (BAKSHI-KAPADIA-MADAN-2003).

## Evidence

Sample, universe and method context: S&P 500 options.

### Original research

- **KOZHAN-NEUBERGER-SCHNEIDER-2013** — Skew premium is >40% of the IV slope, but strategies capturing skew while hedging variance earn an insignificant premium.

### Supporting research

- **BOLLEN-WHALEY-2004** — Net buying pressure drives IV shape; delta-neutral writing earns returns matching IV > RV.
- **BALI-MURRAY-2013** — Cross-sectional skewness assets earn returns negatively related to RN skewness (single-stock).

### Independent replications

- None found in this sprint's search coverage (see `research/sprints/ASA-RES-SPRINT-001/RES-001A-landscape.md` §2).

### Failed replications

- None found in this sprint's search coverage (see `research/sprints/ASA-RES-SPRINT-001/RES-001A-landscape.md` §2).

### Contradictory research

- **KOZHAN-NEUBERGER-SCHNEIDER-2013** — Standalone skew premium insignificant once variance exposure is hedged.

### Post-publication evidence

- None found in this sprint's search coverage (see `research/sprints/ASA-RES-SPRINT-001/RES-001A-landscape.md` §2).

### Reported empirical results

| Field | Value |
|---|---|
| Reported return metrics | REPORTED: insignificant for variance-hedged skew strategies (KNS-2013). |
| Reported risk metrics | UNKNOWN. |
| Drawdown / tail | Severe (short downside). |
| Opportunity frequency | Monthly. |
| Regime dependence | UNKNOWN. |
| Persistence | UNKNOWN. |
| Transaction-cost sensitivity | UNKNOWN. |

## Specification

As documented in the sources. No rule is invented, and missing parameters are UNKNOWN.

| Field | Value |
|---|---|
| Entry rules | UNKNOWN. |
| DTE / expiration | UNKNOWN. |
| Strike / delta | OTM puts/calls. |
| Liquidity requirements | Index. |
| Exit rules | UNKNOWN. |
| Roll rules | UNKNOWN. |
| Sizing assumptions | UNKNOWN. |
| Exclusions | UNKNOWN. |
| Unresolved rule gaps | No explicit strategy rule set recovered. |

## Practical evidence

| Risk field | Value |
|---|---|
| Maximum / tail risk | Undefined. |
| Liquidity risk | Low. |
| Assignment / exercise risk | None (European). |
| Gap risk | Severe. |
| Volatility-regime risk | Severe. |
| Model dependency | High. |
| Crowding / decay evidence | UNKNOWN. |
| Known failure modes | Crashes. |

## Adversarial review

| Question | Answer |
|---|---|
| Replicated? | No. |
| Failed? | The primary source itself finds no independent skew premium. |
| Later research? | None found. |
| Persisted? | UNKNOWN. |
| Data mining? | Low. |
| Concentrated? | UNKNOWN. |
| Parameter-dependent? | UNKNOWN. |
| Costs? | UNKNOWN. |
| Execution? | UNKNOWN. |
| Another factor? | Variance risk. |
| Look-ahead? | No. |
| Failure regime? | Crashes. |
| Crowding? | UNKNOWN. |
| Omission risk? | Treating the smirk as a separate premium. |

## ASA capability mapping

Performed after the external evidence assessment above. Implementation ease does not affect the evidence rating.

| Field | Value |
|---|---|
| Required market data | Index chain. |
| Required analytics | A07 RN moments; A14 hedging. |
| Required history | Historical index options. |
| Required event data | None. |
| Structural primitives (RES-001B §3) | P10, P11. |
| Apparent existing ASA capabilities | Skew analytics (single-name/ETF). |
| Apparent missing ASA capabilities | SPX identity; RN moments; hedging. |
| Execution complexity | High. |

## Assessment

### Strongest supporting evidence

Smirk reflects demand (BOLLEN-WHALEY-2004).

### Strongest contradictory evidence

Skew premium not separable from variance premium (KOZHAN-NEUBERGER-SCHNEIDER-2013).

### Unresolved questions

- Whether any skew-specific rule earns a premium net of variance exposure

### Evidence limitations

Most sources were verified at bibliographic-and-abstract depth. Sample periods, cost models, and exact rules are often UNKNOWN until full texts are recovered.

### Qualification status

INSUFFICIENT_EVIDENCE

### Qualification basis

INSUFFICIENT_EVIDENCE: the key primary source finds skew exposure is not separately compensated at index level.

## Research history

- 2026-09-26: record created as INSUFFICIENT_EVIDENCE in ASA-RES-SPRINT-001 (RES-001C). No prior conclusion existed.

## Provenance

- `research/sources/KOZHAN-NEUBERGER-SCHNEIDER-2013.yaml`
- `research/sources/BOLLEN-WHALEY-2004.yaml`
- `research/sources/BALI-MURRAY-2013.yaml`
