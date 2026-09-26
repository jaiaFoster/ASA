# ASA-RSCH-FAM-ARBITRAGE-001 — Parity, Box-Spread and Exercise Arbitrage

## Identity

- **Research ID:** ASA-RSCH-FAM-ARBITRAGE-001
- **Strategy:** Parity, Box-Spread and Exercise Arbitrage
- **Family:** FAM-ARBITRAGE-PARITY (E7 structural / arbitrage); taxonomy in `research/sprints/ASA-RES-SPRINT-001/RES-001B-taxonomy.md`
- **Research status:** DISCOVERED
- **Created:** 2026-09-26
- **Updated:** 2026-09-26

This is a family-level comparable record (RES-001C). Status describes evidence only. It is not a priority, selection, or implementation signal. Numeric values are stated only where a source reports them; everything else is UNKNOWN. Claim classes: REPORTED / DERIVED / INFERENCE / UNKNOWN. Source verification depth for this record: bibliographic_and_abstract: 1, bibliographic_only: 2.

## Thesis

### Concise description

Exploit put-call parity deviations, box-spread implied rates, or suboptimal early exercise around dividends.

### Proposed economic or behavioral mechanism

Short-sale constraints (OFEK-RICHARDSON-WHITELAW-2004), Treasury convenience yields (VANBINSBERGEN-DIAMOND-GROTTERIA-2022), exercise frictions (POOL-STOLL-WHALEY-2008).

## Evidence

Sample, universe and method context: US options; details UNKNOWN.

### Original research

- **VANBINSBERGEN-DIAMOND-GROTTERIA-2022** — Option-implied risk-free rates reveal a ~40 bp Treasury convenience yield.

### Supporting research

- **POOL-STOLL-WHALEY-2008** — Dividend exercise anomaly (bibliographic only).
- **OFEK-RICHARDSON-WHITELAW-2004** — Parity violations and short-sale constraints (bibliographic only).

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
| Reported return metrics | UNKNOWN. |
| Reported risk metrics | UNKNOWN. |
| Drawdown / tail | Low (box); execution/assignment risk (INFERENCE). |
| Opportunity frequency | Event-driven (dividends) or continuous. |
| Regime dependence | UNKNOWN. |
| Persistence | UNKNOWN. |
| Transaction-cost sensitivity | Likely decisive (INFERENCE). |

## Specification

As documented in the sources. No rule is invented, and missing parameters are UNKNOWN.

| Field | Value |
|---|---|
| Entry rules | UNKNOWN |
| DTE / expiration | UNKNOWN |
| Strike / delta | UNKNOWN |
| Liquidity requirements | UNKNOWN |
| Exit rules | UNKNOWN |
| Roll rules | UNKNOWN |
| Sizing assumptions | UNKNOWN |
| Exclusions | UNKNOWN |
| Unresolved rule gaps | Evidence not assessed beyond identity/abstract. |

## Practical evidence

| Risk field | Value |
|---|---|
| Maximum / tail risk | Low (box) / assignment. |
| Liquidity risk | UNKNOWN |
| Assignment / exercise risk | Central (dividend plays). |
| Gap risk | Low. |
| Volatility-regime risk | Low. |
| Model dependency | Low. |
| Crowding / decay evidence | UNKNOWN |
| Known failure modes | Execution; assignment. |

## Adversarial review

| Question | Answer |
|---|---|
| Replicated? | UNKNOWN. |
| Failed? | UNKNOWN. |
| Later research? | UNKNOWN. |
| Persisted? | UNKNOWN. |
| Data mining? | UNKNOWN. |
| Concentrated? | UNKNOWN. |
| Parameter-dependent? | UNKNOWN. |
| Costs? | Likely decisive. |
| Execution? | Institutional. |
| Another factor? | Financing / frictions. |
| Look-ahead? | No. |
| Failure regime? | UNKNOWN. |
| Crowding? | Market-maker domain (INFERENCE). |
| Omission risk? | Treating as a return premium. |

## ASA capability mapping

Performed after the external evidence assessment above. Implementation ease does not affect the evidence rating.

| Field | Value |
|---|---|
| Required market data | Chains, dividends, rates. |
| Required analytics | Parity calculations. |
| Required history | Historical chains. |
| Required event data | Ex-dividend dates. |
| Structural primitives (RES-001B §3) | P15. |
| Apparent existing ASA capabilities | Chains; corporate actions capability. |
| Apparent missing ASA capabilities | Rate source; box structure. |
| Execution complexity | Medium. |

## Assessment

### Strongest supporting evidence

Convenience-yield evidence (VANBINSBERGEN-DIAMOND-GROTTERIA-2022).

### Strongest contradictory evidence

None assessed.

### Unresolved questions

- Everything beyond identity

### Evidence limitations

Most sources were verified at bibliographic-and-abstract depth. Sample periods, cost models, and exact rules are often UNKNOWN until full texts are recovered.

### Qualification status

DISCOVERED

### Qualification basis

DISCOVERED: identified; evidence quality not assessed (two of three sources bibliographic only).

## Research history

- 2026-09-26: record created as DISCOVERED in ASA-RES-SPRINT-001 (RES-001C). No prior conclusion existed.

## Provenance

- `research/sources/VANBINSBERGEN-DIAMOND-GROTTERIA-2022.yaml`
- `research/sources/POOL-STOLL-WHALEY-2008.yaml`
- `research/sources/OFEK-RICHARDSON-WHITELAW-2004.yaml`
