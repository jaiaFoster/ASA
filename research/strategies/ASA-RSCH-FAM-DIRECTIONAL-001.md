# ASA-RSCH-FAM-DIRECTIONAL-001 — Directional Option Expression (long options, debit verticals, stock replacement)

## Identity

- **Research ID:** ASA-RSCH-FAM-DIRECTIONAL-001
- **Strategy:** Directional Option Expression (long options, debit verticals, stock replacement)
- **Family:** FAM-DIRECTIONAL-OPTION-EXPRESSION (E6 directional expression); taxonomy in `research/sprints/ASA-RES-SPRINT-001/RES-001B-taxonomy.md`
- **Research status:** INSUFFICIENT_EVIDENCE
- **Created:** 2026-09-26
- **Updated:** 2026-09-26

This is a family-level comparable record (RES-001C). Status describes evidence only. It is not a priority, selection, or implementation signal. Numeric values are stated only where a source reports them; everything else is UNKNOWN. Claim classes: REPORTED / DERIVED / INFERENCE / UNKNOWN. Source verification depth for this record: bibliographic_and_abstract: 4.

## Thesis

### Concise description

Express a directional view by buying calls/puts or debit verticals instead of trading the underlying.

### Proposed economic or behavioral mechanism

Buying options pays for embedded leverage and volatility risk (FRAZZINI-PEDERSEN-2022, COVAL-SHUMWAY-2001); returns depend on the external signal's quality net of that premium (INFERENCE).

## Evidence

Sample, universe and method context: Retail/discretionary trading; not systematic signals.

### Original research

- **BAUER-COSEMANS-EICHHOLTZ-2009** — Most individual investors lose substantially on options, more than on equities.

### Supporting research

- **BRYZGALOVA-ET-AL-2023** — Retail option traders lose money on average; average bid-ask 12.6%.
- **FRAZZINI-PEDERSEN-2022** — High embedded leverage, low risk-adjusted returns.
- **HU-JACOBS-2020** — Call returns decrease with underlying volatility.

### Independent replications

- **BRYZGALOVA-ET-AL-2023** — Different market and era reach the same sign as Bauer et al.

### Failed replications

- None found in this sprint's search coverage (see `research/sprints/ASA-RES-SPRINT-001/RES-001A-landscape.md` §2).

### Contradictory research

- None found in this sprint's search coverage (see `research/sprints/ASA-RES-SPRINT-001/RES-001A-landscape.md` §2).

### Post-publication evidence

- None found in this sprint's search coverage (see `research/sprints/ASA-RES-SPRINT-001/RES-001A-landscape.md` §2).

### Reported empirical results

| Field | Value |
|---|---|
| Reported return metrics | REPORTED: negative on average for retail/discretionary buyers. |
| Reported risk metrics | Defined (premium). |
| Drawdown / tail | Defined. |
| Opportunity frequency | Signal-dependent. |
| Regime dependence | UNKNOWN |
| Persistence | Negative persists (2009 and 2023 evidence). |
| Transaction-cost sensitivity | REPORTED: high spreads a major loss source. |

## Specification

As documented in the sources. No rule is invented, and missing parameters are UNKNOWN.

| Field | Value |
|---|---|
| Entry rules | External signal. |
| DTE / expiration | UNKNOWN |
| Strike / delta | UNKNOWN |
| Liquidity requirements | UNKNOWN |
| Exit rules | UNKNOWN |
| Roll rules | UNKNOWN |
| Sizing assumptions | UNKNOWN |
| Exclusions | UNKNOWN |
| Unresolved rule gaps | No source evaluates systematic signal-driven debit structures vs trading the underlying. |

## Practical evidence

| Risk field | Value |
|---|---|
| Maximum / tail risk | Premium. |
| Liquidity risk | Spreads. |
| Assignment / exercise risk | Low. |
| Gap risk | Beneficial or harmful by direction. |
| Volatility-regime risk | Long vega. |
| Model dependency | Low. |
| Crowding / decay evidence | Retail. |
| Known failure modes | Theta/VRP bleed; spreads. |

## Adversarial review

| Question | Answer |
|---|---|
| Replicated? | Negative outcome replicated across eras. |
| Failed? | n/a. |
| Later research? | Consistent. |
| Persisted? | Yes (negative). |
| Data mining? | Low. |
| Concentrated? | UNKNOWN. |
| Parameter-dependent? | UNKNOWN. |
| Costs? | Major. |
| Execution? | Realistic. |
| Another factor? | Leverage premium. |
| Look-ahead? | No. |
| Failure regime? | Low-realized-vol periods. |
| Crowding? | Retail. |
| Omission risk? | Ignoring that the evidence is about discretionary traders, not rules. |

## ASA capability mapping

Performed after the external evidence assessment above. Implementation ease does not affect the evidence rating.

| Field | Value |
|---|---|
| Required market data | Chain + signal. |
| Required analytics | Signal-dependent. |
| Required history | UNKNOWN |
| Required event data | UNKNOWN |
| Structural primitives (RES-001B §3) | P01, P02. |
| Apparent existing ASA capabilities | Vertical structure (Skew Momentum expression). |
| Apparent missing ASA capabilities | Single-leg runtime. |
| Execution complexity | Low. |

## Assessment

### Strongest supporting evidence

None for systematic positive returns found.

### Strongest contradictory evidence

Consistent negative outcomes for option buyers.

### Unresolved questions

- Does any systematic signal overcome the leverage/VRP premium when expressed through options?

### Evidence limitations

Most sources were verified at bibliographic-and-abstract depth. Sample periods, cost models, and exact rules are often UNKNOWN until full texts are recovered.

### Qualification status

INSUFFICIENT_EVIDENCE

### Qualification basis

INSUFFICIENT_EVIDENCE: evidence is negative for buyers and absent for systematic signal-driven debit structures. Relevant to any hybrid (e.g. Skew Momentum) that expresses a signal through long premium.

## Research history

- 2026-09-26: record created as INSUFFICIENT_EVIDENCE in ASA-RES-SPRINT-001 (RES-001C). No prior conclusion existed.

## Provenance

- `research/sources/BAUER-COSEMANS-EICHHOLTZ-2009.yaml`
- `research/sources/BRYZGALOVA-ET-AL-2023.yaml`
- `research/sources/FRAZZINI-PEDERSEN-2022.yaml`
- `research/sources/HU-JACOBS-2020.yaml`
