# ASA-RSCH-FAM-COLLAR-001 — Equity Collars

## Identity

- **Research ID:** ASA-RSCH-FAM-COLLAR-001
- **Strategy:** Equity Collars
- **Family:** FAM-LONGVOL-COLLAR (E2 insurance buying); taxonomy in `research/sprints/ASA-RES-SPRINT-001/RES-001B-taxonomy.md`
- **Research status:** INSUFFICIENT_EVIDENCE
- **Created:** 2026-09-26
- **Updated:** 2026-09-26

This is a family-level comparable record (RES-001C). Status describes evidence only. It is not a priority, selection, or implementation signal. Numeric values are stated only where a source reports them; everything else is UNKNOWN. Claim classes: REPORTED / DERIVED / INFERENCE / UNKNOWN. Source verification depth for this record: bibliographic_and_abstract: 2.

## Thesis

### Concise description

Hold the underlying, buy a put and sell a call (often zero-cost) to bound returns.

### Proposed economic or behavioral mechanism

Exchanges upside and equity premium for downside protection; net volatility exposure depends on strikes (ISRAELOV-KLEIN-2016).

## Evidence

Sample, universe and method context: QQQ and a small-cap fund (Szado-Schneeweis); equity index collars (Israelov-Klein).

### Original research

- **SZADO-SCHNEEWEIS-2010** — Passive QQQ collar most effective in declining markets; active conditioned variant.

### Supporting research

- None found in this sprint's search coverage (see `research/sprints/ASA-RES-SPRINT-001/RES-001A-landscape.md` §2).

### Independent replications

- None found in this sprint's search coverage (see `research/sprints/ASA-RES-SPRINT-001/RES-001A-landscape.md` §2).

### Failed replications

- None found in this sprint's search coverage (see `research/sprints/ASA-RES-SPRINT-001/RES-001A-landscape.md` §2).

### Contradictory research

- **ISRAELOV-KLEIN-2016** — Collars expected to underperform the underlying and alternatives; historically performed poorly vs alternatives.

### Post-publication evidence

- None found in this sprint's search coverage (see `research/sprints/ASA-RES-SPRINT-001/RES-001A-landscape.md` §2).

### Reported empirical results

| Field | Value |
|---|---|
| Reported return metrics | UNKNOWN (point values not recovered). |
| Reported risk metrics | Bounded by construction. |
| Drawdown / tail | Bounded below at put strike. |
| Opportunity frequency | Calendar or conditioned. |
| Regime dependence | Helps in declines, hurts in rallies (REPORTED). |
| Persistence | UNKNOWN. |
| Transaction-cost sensitivity | UNKNOWN. |

## Specification

As documented in the sources. No rule is invented, and missing parameters are UNKNOWN.

| Field | Value |
|---|---|
| Entry rules | Calendar; active variant conditioned on momentum/volatility/macro. |
| DTE / expiration | UNKNOWN. |
| Strike / delta | UNKNOWN (zero-cost variants). |
| Liquidity requirements | ETF. |
| Exit rules | Expiration. |
| Roll rules | Periodic. |
| Sizing assumptions | One collar per unit. |
| Exclusions | None. |
| Unresolved rule gaps | Active-rule specification is in-sample. |

## Practical evidence

| Risk field | Value |
|---|---|
| Maximum / tail risk | Bounded. |
| Liquidity risk | Low. |
| Assignment / exercise risk | Short call early assignment (INFERENCE). |
| Gap risk | Bounded. |
| Volatility-regime risk | Medium. |
| Model dependency | Low. |
| Crowding / decay evidence | UNKNOWN. |
| Known failure modes | Rallies; equity premium drag. |

## Adversarial review

| Question | Answer |
|---|---|
| Replicated? | No. |
| Failed? | No test. |
| Later research? | Negative expected-return analysis. |
| Persisted? | UNKNOWN. |
| Data mining? | Active variant in-sample. |
| Concentrated? | Crisis-period benefit. |
| Parameter-dependent? | Yes. |
| Costs? | UNKNOWN. |
| Execution? | Realistic. |
| Another factor? | Reduced equity beta. |
| Look-ahead? | Check for active variant. |
| Failure regime? | Bull markets. |
| Crowding? | UNKNOWN. |
| Omission risk? | Presenting crisis benefit without expected-return drag. |

## ASA capability mapping

Performed after the external evidence assessment above. Implementation ease does not affect the evidence rating.

| Field | Value |
|---|---|
| Required market data | Chain, underlying. |
| Required analytics | Conditioning signals for active variant. |
| Required history | Historical chains. |
| Required event data | None. |
| Structural primitives (RES-001B §3) | P09. |
| Apparent existing ASA capabilities | Chain, quote, momentum analytics. |
| Apparent missing ASA capabilities | Three-leg overlay structure. |
| Execution complexity | Low-medium. |

## Assessment

### Strongest supporting evidence

Effective protection in declines (SZADO-SCHNEEWEIS-2010).

### Strongest contradictory evidence

Expected underperformance (ISRAELOV-KLEIN-2016).

### Unresolved questions

- Net comparison to static de-risking

### Evidence limitations

Most sources were verified at bibliographic-and-abstract depth. Sample periods, cost models, and exact rules are often UNKNOWN until full texts are recovered.

### Qualification status

INSUFFICIENT_EVIDENCE

### Qualification basis

INSUFFICIENT_EVIDENCE: two sources with opposite framings; no replication; return evidence negative.

## Research history

- 2026-09-26: record created as INSUFFICIENT_EVIDENCE in ASA-RES-SPRINT-001 (RES-001C). No prior conclusion existed.

## Provenance

- `research/sources/SZADO-SCHNEEWEIS-2010.yaml`
- `research/sources/ISRAELOV-KLEIN-2016.yaml`
