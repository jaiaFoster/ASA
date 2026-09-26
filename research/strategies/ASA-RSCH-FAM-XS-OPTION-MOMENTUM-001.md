# ASA-RSCH-FAM-XS-OPTION-MOMENTUM-001 — Option Return Momentum and Seasonality

## Identity

- **Research ID:** ASA-RSCH-FAM-XS-OPTION-MOMENTUM-001
- **Strategy:** Option Return Momentum and Seasonality
- **Family:** FAM-XS-OPTION-MOMENTUM (E3 volatility relative value); taxonomy in `research/sprints/ASA-RES-SPRINT-001/RES-001B-taxonomy.md`
- **Research status:** TRIAGE
- **Created:** 2026-09-26
- **Updated:** 2026-09-26

This is a family-level comparable record (RES-001C). Status describes evidence only. It is not a priority, selection, or implementation signal. Numeric values are stated only where a source reports them; everything else is UNKNOWN. Claim classes: REPORTED / DERIVED / INFERENCE / UNKNOWN. Source verification depth for this record: bibliographic_and_abstract: 2.

## Thesis

### Concise description

Buy options (straddles) with high historical returns and sell those with low historical returns; variant exploits quarterly seasonal continuation.

### Proposed economic or behavioral mechanism

Implied variance under-anticipates persistent and seasonal patterns in realized variance, linked to analyst earnings revisions (HESTON-ET-AL-2026).

## Evidence

Sample, universe and method context: US single-stock ATM straddles (sample UNKNOWN at abstract depth).

### Original research

- **HESTON-ET-AL-2023** — ATM straddle momentum over 6-36 months; robust to OTM and delta hedging; no long-run reversal; survives factor adjustment and IV controls.

### Supporting research

- **HESTON-ET-AL-2026** — Quarterly seasonal continuation in realized and implied variance.

### Independent replications

- None found in this sprint's search coverage (see `research/sprints/ASA-RES-SPRINT-001/RES-001A-landscape.md` §2).

### Failed replications

- None found in this sprint's search coverage (see `research/sprints/ASA-RES-SPRINT-001/RES-001A-landscape.md` §2).

### Contradictory research

- None found in this sprint's search coverage (see `research/sprints/ASA-RES-SPRINT-001/RES-001A-landscape.md` §2).

### Post-publication evidence

- None found in this sprint's search coverage (see `research/sprints/ASA-RES-SPRINT-001/RES-001A-landscape.md` §2).

### Reported empirical results

| Field | Value |
|---|---|
| Reported return metrics | UNKNOWN at abstract depth. |
| Reported risk metrics | UNKNOWN. |
| Drawdown / tail | UNKNOWN. |
| Opportunity frequency | Monthly cross-sectional rebalance. |
| Regime dependence | UNKNOWN. |
| Persistence | UNKNOWN (no post-publication study). |
| Transaction-cost sensitivity | REPORTED: trading costs unrelated to momentum profit magnitude across stocks (HESTON-ET-AL-2023). |

## Specification

As documented in the sources. No rule is invented, and missing parameters are UNKNOWN.

| Field | Value |
|---|---|
| Entry rules | Sort on past straddle returns. |
| DTE / expiration | ~1 month (UNKNOWN exact). |
| Strike / delta | ATM straddles. |
| Liquidity requirements | UNKNOWN. |
| Exit rules | Monthly. |
| Roll rules | Monthly. |
| Sizing assumptions | UNKNOWN. |
| Exclusions | UNKNOWN. |
| Unresolved rule gaps | Lookback/skip structure and filters UNKNOWN. |

## Practical evidence

| Risk field | Value |
|---|---|
| Maximum / tail risk | Undefined (short leg). |
| Liquidity risk | UNKNOWN. |
| Assignment / exercise risk | Possible (American). |
| Gap risk | Earnings gaps. |
| Volatility-regime risk | UNKNOWN. |
| Model dependency | Medium. |
| Crowding / decay evidence | UNKNOWN. |
| Known failure modes | UNKNOWN. |

## Adversarial review

| Question | Answer |
|---|---|
| Replicated? | Only by the same author team (seasonal extension). |
| Failed? | None found. |
| Later research? | None. |
| Persisted? | UNKNOWN. |
| Data mining? | Moderate (lookback choices). |
| Concentrated? | UNKNOWN. |
| Parameter-dependent? | Robust 6-36 months (REPORTED). |
| Costs? | Unrelated to profit magnitude (REPORTED). |
| Execution? | UNKNOWN. |
| Another factor? | Controlled for IV and characteristics. |
| Look-ahead? | No. |
| Failure regime? | UNKNOWN. |
| Crowding? | UNKNOWN. |
| Omission risk? | Counting the 2026 paper as independent replication. |

## ASA capability mapping

Performed after the external evidence assessment above. Implementation ease does not affect the evidence rating.

| Field | Value |
|---|---|
| Required market data | Chains across universe. |
| Required analytics | A17 per-name option-return history; A13 ranking. |
| Required history | **6-36 months of per-name option return history (A08/A17).** |
| Required event data | Earnings revision data for seasonal variant. |
| Structural primitives (RES-001B §3) | P03, P12. |
| Apparent existing ASA capabilities | Cross-sectional ranking. |
| Apparent missing ASA capabilities | Straddle structure; historical option panel; option-return history. |
| Execution complexity | High. |

## Assessment

### Strongest supporting evidence

Top-journal robustness evidence (HESTON-ET-AL-2023).

### Strongest contradictory evidence

None found; absence of independent replication is the limitation.

### Unresolved questions

- Independent replication
- Net returns

### Evidence limitations

Most sources were verified at bibliographic-and-abstract depth. Sample periods, cost models, and exact rules are often UNKNOWN until full texts are recovered.

### Qualification status

TRIAGE

### Qualification basis

TRIAGE: strong single-team evidence in top journals; no independent replication yet.

## Research history

- 2026-09-26: record created as TRIAGE in ASA-RES-SPRINT-001 (RES-001C). No prior conclusion existed.

## Provenance

- `research/sources/HESTON-ET-AL-2023.yaml`
- `research/sources/HESTON-ET-AL-2026.yaml`
