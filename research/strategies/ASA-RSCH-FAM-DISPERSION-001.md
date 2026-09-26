# ASA-RSCH-FAM-DISPERSION-001 — Dispersion / Correlation Trading

## Identity

- **Research ID:** ASA-RSCH-FAM-DISPERSION-001
- **Strategy:** Dispersion / Correlation Trading
- **Family:** FAM-DISPERSION-CORRELATION (E3 volatility relative value); taxonomy in `research/sprints/ASA-RES-SPRINT-001/RES-001B-taxonomy.md`
- **Research status:** INSUFFICIENT_EVIDENCE
- **Created:** 2026-09-26
- **Updated:** 2026-09-26

This is a family-level comparable record (RES-001C). Status describes evidence only. It is not a priority, selection, or implementation signal. Numeric values are stated only where a source reports them; everything else is UNKNOWN. Claim classes: REPORTED / DERIVED / INFERENCE / UNKNOWN. Source verification depth for this record: bibliographic_and_abstract: 1, bibliographic_and_search_engine_summary: 1, bibliographic_only: 1.

## Thesis

### Concise description

Sell index volatility and buy constituent volatility to earn the correlation risk premium.

### Proposed economic or behavioral mechanism

Correlation risk is priced; index options are expensive relative to constituents (DRIESSEN-MAENHOUT-VILKOV-2009).

## Evidence

Sample, universe and method context: S&P 100 index and component options (DMV).

### Original research

- **DRIESSEN-MAENHOUT-VILKOV-2009** — Correlation strategy has high alpha without frictions but cannot be exploited with realistic trading frictions.

### Supporting research

- **EUREKAHEDGE-CBOE-VOL-INDICES** — Relative-value volatility managers exist as a distinct industry category (secondary).

### Independent replications

- **FARIA-KOSOWSKI-WANG-2022** — International correlation risk premium (claims unverified; bibliographic only).

### Failed replications

- None found in this sprint's search coverage (see `research/sprints/ASA-RES-SPRINT-001/RES-001A-landscape.md` §2).

### Contradictory research

- **DRIESSEN-MAENHOUT-VILKOV-2009** — Its own implementability finding is negative.

### Post-publication evidence

- None found in this sprint's search coverage (see `research/sprints/ASA-RES-SPRINT-001/RES-001A-landscape.md` §2).

### Reported empirical results

| Field | Value |
|---|---|
| Reported return metrics | REPORTED: high alpha frictionless; not exploitable with frictions. |
| Reported risk metrics | UNKNOWN. |
| Drawdown / tail | Correlation spikes in crises (INFERENCE). |
| Opportunity frequency | Monthly. |
| Regime dependence | Crisis correlation spikes (INFERENCE). |
| Persistence | UNKNOWN. |
| Transaction-cost sensitivity | Decisive (REPORTED). |

## Specification

As documented in the sources. No rule is invented, and missing parameters are UNKNOWN.

| Field | Value |
|---|---|
| Entry rules | UNKNOWN. |
| DTE / expiration | UNKNOWN. |
| Strike / delta | UNKNOWN. |
| Liquidity requirements | Index + all constituents. |
| Exit rules | UNKNOWN. |
| Roll rules | UNKNOWN. |
| Sizing assumptions | Index weights. |
| Exclusions | UNKNOWN. |
| Unresolved rule gaps | Marshall and Faria et al claims unverified. |

## Practical evidence

| Risk field | Value |
|---|---|
| Maximum / tail risk | Undefined. |
| Liquidity risk | High (many legs). |
| Assignment / exercise risk | Constituent legs (INFERENCE). |
| Gap risk | Correlation spikes. |
| Volatility-regime risk | High. |
| Model dependency | High. |
| Crowding / decay evidence | Institutional. |
| Known failure modes | Frictions; correlation spikes. |

## Adversarial review

| Question | Answer |
|---|---|
| Replicated? | International study unverified. |
| Failed? | Implementability fails in the original. |
| Later research? | UNKNOWN. |
| Persisted? | UNKNOWN. |
| Data mining? | Low. |
| Concentrated? | UNKNOWN. |
| Parameter-dependent? | UNKNOWN. |
| Costs? | Decisive. |
| Execution? | Unrealistic for small accounts (INFERENCE). |
| Another factor? | Correlation risk. |
| Look-ahead? | No. |
| Failure regime? | Crises. |
| Crowding? | UNKNOWN. |
| Omission risk? | Quoting frictionless alpha. |

## ASA capability mapping

Performed after the external evidence assessment above. Implementation ease does not affect the evidence rating.

| Field | Value |
|---|---|
| Required market data | Index and constituent chains; weights. |
| Required analytics | A16 implied correlation; A14 hedging. |
| Required history | Historical panels for index and constituents. |
| Required event data | Constituent earnings. |
| Structural primitives (RES-001B §3) | P13, P10. |
| Apparent existing ASA capabilities | Single-name chains. |
| Apparent missing ASA capabilities | Index identity; multi-underlying linked structures; weights; hedging. |
| Execution complexity | Very high. |

## Assessment

### Strongest supporting evidence

Priced correlation risk (DRIESSEN-MAENHOUT-VILKOV-2009).

### Strongest contradictory evidence

Not exploitable with realistic frictions (same source).

### Unresolved questions

- Post-2009 cost environment (MURAVYEV-PEARSON-2020 suggests lower effective spreads)

### Evidence limitations

Most sources were verified at bibliographic-and-abstract depth. Sample periods, cost models, and exact rules are often UNKNOWN until full texts are recovered.

### Qualification status

INSUFFICIENT_EVIDENCE

### Qualification basis

INSUFFICIENT_EVIDENCE: the primary source's own implementability finding is negative; follow-ups unverified.

## Research history

- 2026-09-26: record created as INSUFFICIENT_EVIDENCE in ASA-RES-SPRINT-001 (RES-001C). No prior conclusion existed.

## Provenance

- `research/sources/DRIESSEN-MAENHOUT-VILKOV-2009.yaml`
- `research/sources/EUREKAHEDGE-CBOE-VOL-INDICES.yaml`
- `research/sources/FARIA-KOSOWSKI-WANG-2022.yaml`
