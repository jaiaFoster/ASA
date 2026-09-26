# ASA-RSCH-FAM-VIX-CARRY-001 — VIX Futures / Volatility ETP Term Carry

## Identity

- **Research ID:** ASA-RSCH-FAM-VIX-CARRY-001
- **Strategy:** VIX Futures / Volatility ETP Term Carry
- **Family:** FAM-VOLDERIV-VIX-CARRY (E1/E2 volatility term premium); taxonomy in `research/sprints/ASA-RES-SPRINT-001/RES-001B-taxonomy.md`
- **Research status:** TRIAGE
- **Created:** 2026-09-26
- **Updated:** 2026-09-26

This is a family-level comparable record (RES-001C). Status describes evidence only. It is not a priority, selection, or implementation signal. Numeric values are stated only where a source reports them; everything else is UNKNOWN. Claim classes: REPORTED / DERIVED / INFERENCE / UNKNOWN. Source verification depth for this record: bibliographic_and_abstract: 4.

## Thesis

### Concise description

Short (or long) VIX futures or volatility ETPs to earn (or pay) the volatility term premium embedded in contango.

### Proposed economic or behavioral mechanism

VIX term-structure slope reflects the price of variance risk rather than expected VIX changes (JOHNSON-2017).

## Evidence

Sample, universe and method context: VIX futures and ETPs post-2004/2009; US.

### Original research

- **JOHNSON-2017** — SLOPE predicts excess returns of variance swaps, VIX futures and S&P 500 straddles; incremental to other VRP proxies.

### Supporting research

- **WHALEY-2013** — Long VIX ETPs virtually guaranteed to lose over time; ~$4bn losses since 2009 launch (i.e. the short side earned the roll).

### Independent replications

- None found in this sprint's search coverage (see `research/sprints/ASA-RES-SPRINT-001/RES-001A-landscape.md` §2).

### Failed replications

- None found in this sprint's search coverage (see `research/sprints/ASA-RES-SPRINT-001/RES-001A-landscape.md` §2).

### Contradictory research

- **AUGUSTIN-CHENG-VANDENBERGEN-2021** — Short-volatility products crashed on 2018-02-05 through rebalancing feedback.
- **ALEXANDER-KOROVILAS-KAPRAUN-2016** — Long volatility diversification almost never realized after costs.

### Post-publication evidence

- **AUGUSTIN-CHENG-VANDENBERGEN-2021** — Catastrophic failure of the most popular short-carry vehicles.

### Reported empirical results

| Field | Value |
|---|---|
| Reported return metrics | UNKNOWN point values at abstract depth. |
| Reported risk metrics | Extreme tail for short side (REPORTED event). |
| Drawdown / tail | Short ETPs lost >90% in one day (secondary). |
| Opportunity frequency | Continuous/monthly roll. |
| Regime dependence | Contango vs backwardation (INFERENCE from JOHNSON-2017). |
| Persistence | Short-carry vehicles failed 2018. |
| Transaction-cost sensitivity | Roll and transaction costs erode long side (REPORTED). |

## Specification

As documented in the sources. No rule is invented, and missing parameters are UNKNOWN.

| Field | Value |
|---|---|
| Entry rules | Term-slope conditioned or continuous. |
| DTE / expiration | 1-2 month futures. |
| Strike / delta | n/a. |
| Liquidity requirements | VIX futures. |
| Exit rules | Roll. |
| Roll rules | Daily ETP rebalance / monthly futures. |
| Sizing assumptions | UNKNOWN. |
| Exclusions | None. |
| Unresolved rule gaps | SIMON-CAMPASANO-2014 claims unverified. |

## Practical evidence

| Risk field | Value |
|---|---|
| Maximum / tail risk | Undefined (short). |
| Liquidity risk | Crowded rebalancing (REPORTED). |
| Assignment / exercise risk | n/a. |
| Gap risk | Extreme. |
| Volatility-regime risk | Extreme. |
| Model dependency | Low. |
| Crowding / decay evidence | Documented (2018). |
| Known failure modes | Volatility spike with rebalancing feedback. |

## Adversarial review

| Question | Answer |
|---|---|
| Replicated? | Predictability single study recorded. |
| Failed? | Vehicle failure 2018. |
| Later research? | Failure mechanism documented. |
| Persisted? | Short carry ended catastrophically for ETP holders. |
| Data mining? | Low for sign. |
| Concentrated? | Losses concentrated. |
| Parameter-dependent? | UNKNOWN. |
| Costs? | High for long side. |
| Execution? | Crowded-rebalance risk. |
| Another factor? | Short volatility. |
| Look-ahead? | No. |
| Failure regime? | Spikes. |
| Crowding? | Yes. |
| Omission risk? | Omitting 2018. |

## ASA capability mapping

Performed after the external evidence assessment above. Implementation ease does not affect the evidence rating.

| Field | Value |
|---|---|
| Required market data | VIX futures curve. |
| Required analytics | A05 on VIX curve. |
| Required history | VIX futures history. |
| Required event data | None. |
| Structural primitives (RES-001B §3) | P14. |
| Apparent existing ASA capabilities | None specific. |
| Apparent missing ASA capabilities | VIX futures capability; futures instruments. |
| Execution complexity | Medium. |

## Assessment

### Strongest supporting evidence

Term-slope predictability (JOHNSON-2017); persistent long-ETP losses (WHALEY-2013).

### Strongest contradictory evidence

Catastrophic short-vehicle failure (AUGUSTIN-CHENG-VANDENBERGEN-2021).

### Unresolved questions

- Futures-level (not ETP) short-carry net returns
- SIMON-CAMPASANO-2014 basis strategy

### Evidence limitations

Most sources were verified at bibliographic-and-abstract depth. Sample periods, cost models, and exact rules are often UNKNOWN until full texts are recovered.

### Qualification status

TRIAGE

### Qualification basis

TRIAGE: peer-reviewed predictability and persistent roll losses to long holders justify deep research; tail/failure evidence is severe.

## Research history

- 2026-09-26: record created as TRIAGE in ASA-RES-SPRINT-001 (RES-001C). No prior conclusion existed.

## Provenance

- `research/sources/JOHNSON-2017.yaml`
- `research/sources/WHALEY-2013.yaml`
- `research/sources/AUGUSTIN-CHENG-VANDENBERGEN-2021.yaml`
- `research/sources/ALEXANDER-KOROVILAS-KAPRAUN-2016.yaml`
