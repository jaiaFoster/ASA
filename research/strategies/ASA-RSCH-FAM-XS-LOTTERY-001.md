# ASA-RSCH-FAM-XS-LOTTERY-001 — Lottery / Skewness / Embedded-Leverage Option Selling

## Identity

- **Research ID:** ASA-RSCH-FAM-XS-LOTTERY-001
- **Strategy:** Lottery / Skewness / Embedded-Leverage Option Selling
- **Family:** FAM-XS-LOTTERY-SKEW-OPTION (E3 volatility relative value); taxonomy in `research/sprints/ASA-RES-SPRINT-001/RES-001B-taxonomy.md`
- **Research status:** TRIAGE
- **Created:** 2026-09-26
- **Updated:** 2026-09-26

This is a family-level comparable record (RES-001C). Status describes evidence only. It is not a priority, selection, or implementation signal. Numeric values are stated only where a source reports them; everything else is UNKNOWN. Claim classes: REPORTED / DERIVED / INFERENCE / UNKNOWN. Source verification depth for this record: bibliographic_and_abstract: 6.

## Thesis

### Concise description

Sell (or underweight) options with the most lottery-like, high-skewness or high-embedded-leverage profiles; buy the least.

### Proposed economic or behavioral mechanism

Investors with skewness preference or leverage constraints overpay; intermediaries earn a premium for unhedgeable risk (BOYER-VORKINK-2014, FRAZZINI-PEDERSEN-2022, BYUN-KIM-2016).

## Evidence

Sample, universe and method context: US single-stock options; sample periods UNKNOWN at abstract depth.

### Original research

- **BOYER-VORKINK-2014** — Option portfolios sorted on ex ante total skewness: 10-50%/week return differences, negative relation, after risk controls.

### Supporting research

- **FRAZZINI-PEDERSEN-2022** — Higher embedded leverage, lower risk-adjusted returns.
- **BYUN-KIM-2016** — Calls on lottery-like stocks underperform by 10-20%/month; stronger in high sentiment.
- **BALI-MURRAY-2013** — Delta- and vega-neutral skewness assets: strong negative relation.
- **CHOY-2015** — Retail-heavy options overpriced.
- **ILMANEN-2012** — Selling lottery tickets rewarded across contexts (review).

### Independent replications

- **BYUN-KIM-2016** — Different lottery measure and authors reach the same sign.

### Failed replications

- None found in this sprint's search coverage (see `research/sprints/ASA-RES-SPRINT-001/RES-001A-landscape.md` §2).

### Contradictory research

- None found in this sprint's search coverage (see `research/sprints/ASA-RES-SPRINT-001/RES-001A-landscape.md` §2).

### Post-publication evidence

- None found in this sprint's search coverage (see `research/sprints/ASA-RES-SPRINT-001/RES-001A-landscape.md` §2).

### Reported empirical results

| Field | Value |
|---|---|
| Reported return metrics | REPORTED spreads: 10-50%/week (BOYER-VORKINK-2014); 10-20%/month (BYUN-KIM-2016); gross. |
| Reported risk metrics | UNKNOWN. |
| Drawdown / tail | INFERENCE: short lottery legs carry right-tail (calls) or crash (puts) exposure. |
| Opportunity frequency | Weekly to monthly cross-sectional rebalance. |
| Regime dependence | REPORTED: stronger in high sentiment (BYUN-KIM-2016). |
| Persistence | UNKNOWN. |
| Transaction-cost sensitivity | UNKNOWN; magnitudes this large in OTM options suggest spreads are material (INFERENCE). |

## Specification

As documented in the sources. No rule is invented, and missing parameters are UNKNOWN.

| Field | Value |
|---|---|
| Entry rules | Rank on skewness / leverage / lottery characteristics. |
| DTE / expiration | Short-dated (UNKNOWN exact). |
| Strike / delta | OTM concentration (INFERENCE). |
| Liquidity requirements | UNKNOWN. |
| Exit rules | Periodic. |
| Roll rules | Weekly/monthly. |
| Sizing assumptions | UNKNOWN. |
| Exclusions | UNKNOWN. |
| Unresolved rule gaps | Cost-adjusted results and exact portfolio construction UNKNOWN. |

## Practical evidence

| Risk field | Value |
|---|---|
| Maximum / tail risk | Undefined (short OTM). |
| Liquidity risk | High (OTM). |
| Assignment / exercise risk | Possible. |
| Gap risk | High single-name. |
| Volatility-regime risk | Sentiment-dependent. |
| Model dependency | Medium. |
| Crowding / decay evidence | UNKNOWN. |
| Known failure modes | Right-tail events on short calls (INFERENCE). |

## Adversarial review

| Question | Answer |
|---|---|
| Replicated? | Convergent evidence from distinct measures. |
| Failed? | None found. |
| Later research? | Consistent (factor overlap possible). |
| Persisted? | UNKNOWN. |
| Data mining? | Moderate. |
| Concentrated? | Sentiment periods. |
| Parameter-dependent? | UNKNOWN. |
| Costs? | Likely material, UNKNOWN. |
| Execution? | UNKNOWN. |
| Another factor? | Overlaps XS-OPTION-RETURNS factors (INFERENCE). |
| Look-ahead? | No. |
| Failure regime? | Squeezes. |
| Crowding? | UNKNOWN. |
| Omission risk? | Presenting gross weekly spreads as achievable. |

## ASA capability mapping

Performed after the external evidence assessment above. Implementation ease does not affect the evidence rating.

| Field | Value |
|---|---|
| Required market data | Chains; retail flow (for Choy). |
| Required analytics | A07 risk-neutral moments; embedded leverage; A13. |
| Required history | Historical option panel. |
| Required event data | None. |
| Structural primitives (RES-001B §3) | P01/P03, P12, P10 (Bali-Murray). |
| Apparent existing ASA capabilities | Skew analytics (normalized skew), cross-sectional ranking. |
| Apparent missing ASA capabilities | Model-free risk-neutral moments; historical option panel; portfolio construct. |
| Execution complexity | High. |

## Assessment

### Strongest supporting evidence

Consistent sign across four peer-reviewed measures.

### Strongest contradictory evidence

None found directly; cost evidence missing.

### Unresolved questions

- Net-of-cost returns
- Overlap with common option factors

### Evidence limitations

Most sources were verified at bibliographic-and-abstract depth. Sample periods, cost models, and exact rules are often UNKNOWN until full texts are recovered.

### Qualification status

TRIAGE

### Qualification basis

TRIAGE: repeated peer-reviewed evidence; implementability and independence from XS factors unresolved.

## Research history

- 2026-09-26: record created as TRIAGE in ASA-RES-SPRINT-001 (RES-001C). No prior conclusion existed.

## Provenance

- `research/sources/BOYER-VORKINK-2014.yaml`
- `research/sources/FRAZZINI-PEDERSEN-2022.yaml`
- `research/sources/BYUN-KIM-2016.yaml`
- `research/sources/BALI-MURRAY-2013.yaml`
- `research/sources/CHOY-2015.yaml`
- `research/sources/ILMANEN-2012.yaml`
