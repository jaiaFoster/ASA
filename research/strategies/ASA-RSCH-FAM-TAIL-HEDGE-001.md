# ASA-RSCH-FAM-TAIL-HEDGE-001 — Tail Hedging / Protective Puts / Long Volatility

## Identity

- **Research ID:** ASA-RSCH-FAM-TAIL-HEDGE-001
- **Strategy:** Tail Hedging / Protective Puts / Long Volatility
- **Family:** FAM-LONGVOL-TAIL-HEDGE (E2 insurance buying); taxonomy in `research/sprints/ASA-RES-SPRINT-001/RES-001B-taxonomy.md`
- **Research status:** INSUFFICIENT_EVIDENCE
- **Created:** 2026-09-26
- **Updated:** 2026-09-26

This is a family-level comparable record (RES-001C). Status describes evidence only. It is not a priority, selection, or implementation signal. Numeric values are stated only where a source reports them; everything else is UNKNOWN. Claim classes: REPORTED / DERIVED / INFERENCE / UNKNOWN. Source verification depth for this record: bibliographic_and_abstract: 5, bibliographic_and_search_engine_summary: 1, full_text_reviewed: 1.

## Thesis

### Concise description

Buy puts, put spreads or volatility exposure to protect an equity portfolio or to profit from crashes.

### Proposed economic or behavioral mechanism

Buyer pays the insurance premium harvested by E1 families; value depends on timing and on the investor's utility for crash protection, not on positive expected return (INFERENCE).

## Evidence

Sample, universe and method context: S&P 500 PPUT 1986-2018; 10 global indexes; simulations.

### Original research

- **ISRAELOV-2018** — Typical protective puts are quite ineffective vs statically reducing exposure; can worsen drawdowns per unit of expected return.

### Supporting research

- **ISRAELOV-NIELSEN-2015-JPM** — Protection still expensive in calm markets across 10 indexes.
- **BONDARENKO-2019-CBOE** — PPUT 1986-2018: 6.64% compound, Sharpe 0.33, max drawdown -38.9%, longest drawdown 80 months.
- **CHAMBERS-ET-AL-2014** — OTM put protection may include a significant premium.

### Independent replications

- **ISRAELOV-NIELSEN-2015-JPM** — Cross-index extension of the expensiveness result (overlapping authors, so not fully independent).

### Failed replications

- None found in this sprint's search coverage (see `research/sprints/ASA-RES-SPRINT-001/RES-001A-landscape.md` §2).

### Contradictory research

- **SZADO-2009** — Long VIX exposure was an effective diversifier during 2008 (single episode).

### Post-publication evidence

- **EUREKAHEDGE-CBOE-VOL-INDICES** — Tail-risk hedge-fund index annualized -3.13%, Sharpe -0.38 to 2016-03 (secondary, self-reported).
- **ALEXANDER-KOROVILAS-KAPRAUN-2016** — Long volatility diversification almost never realized except in the banking crisis.

### Reported empirical results

| Field | Value |
|---|---|
| Reported return metrics | REPORTED: PPUT 6.64% vs S&P 500 9.80% compound (BONDARENKO-2019-CBOE). |
| Reported risk metrics | REPORTED: PPUT SD 12.08%, max DD -38.9%. |
| Drawdown / tail | Protective by design; realized protection depends on timing (ISRAELOV-2018). |
| Opportunity frequency | Calendar or timing-based. |
| Regime dependence | Pays off only in sharp crashes aligned with option maturity (ISRAELOV-2018). |
| Persistence | Negative return persists. |
| Transaction-cost sensitivity | Adds to cost drag (INFERENCE). |

## Specification

As documented in the sources. No rule is invented, and missing parameters are UNKNOWN.

| Field | Value |
|---|---|
| Entry rules | Calendar (PPUT) or timing. |
| DTE / expiration | ~1 month (PPUT). |
| Strike / delta | 5% OTM (PPUT). |
| Liquidity requirements | Index. |
| Exit rules | Expiration. |
| Roll rules | Monthly. |
| Sizing assumptions | One put per unit of underlying. |
| Exclusions | None. |
| Unresolved rule gaps | Timing rules for 'effective' hedging are not specified in sources. |

## Practical evidence

| Risk field | Value |
|---|---|
| Maximum / tail risk | Premium paid (defined). |
| Liquidity risk | Low. |
| Assignment / exercise risk | None for long options. |
| Gap risk | Beneficial. |
| Volatility-regime risk | Benefits in spikes. |
| Model dependency | Low. |
| Crowding / decay evidence | UNKNOWN. |
| Known failure modes | Slow declines, mistimed maturities, persistent premium bleed. |

## Adversarial review

| Question | Answer |
|---|---|
| Replicated? | Expensiveness repeatedly found. |
| Failed? | None found. |
| Later research? | Consistent. |
| Persisted? | Negative return persists. |
| Data mining? | Low. |
| Concentrated? | Payoff concentrated in crashes. |
| Parameter-dependent? | Timing-dependent. |
| Costs? | Worsen. |
| Execution? | Realistic. |
| Another factor? | Long volatility/crash risk. |
| Look-ahead? | No. |
| Failure regime? | Calm/grinding markets. |
| Crowding? | UNKNOWN. |
| Omission risk? | Omitting the 2008 diversification evidence. |

## ASA capability mapping

Performed after the external evidence assessment above. Implementation ease does not affect the evidence rating.

| Field | Value |
|---|---|
| Required market data | Chain. |
| Required analytics | None. |
| Required history | Historical options for replication. |
| Required event data | None. |
| Structural primitives (RES-001B §3) | P01, P09. |
| Apparent existing ASA capabilities | Chain, quote. |
| Apparent missing ASA capabilities | Single-leg and overlay runtime structures. |
| Execution complexity | Low. |

## Assessment

### Strongest supporting evidence

Crash-period diversification (SZADO-2009).

### Strongest contradictory evidence

Negative expected return and ineffective drawdown control in typical use (ISRAELOV-2018, BONDARENKO-2019-CBOE).

### Unresolved questions

- Utility-based value of protection is outside return evidence

### Evidence limitations

Most sources were verified at bibliographic-and-abstract depth. Sample periods, cost models, and exact rules are often UNKNOWN until full texts are recovered.

### Qualification status

INSUFFICIENT_EVIDENCE

### Qualification basis

INSUFFICIENT_EVIDENCE as a return-generating strategy: external evidence is consistently negative on expected return; its hedging value is a portfolio-objective question, not an evidence question this library answers.

## Research history

- 2026-09-26: record created as INSUFFICIENT_EVIDENCE in ASA-RES-SPRINT-001 (RES-001C). No prior conclusion existed.

## Provenance

- `research/sources/ISRAELOV-2018.yaml`
- `research/sources/ISRAELOV-NIELSEN-2015-JPM.yaml`
- `research/sources/BONDARENKO-2019-CBOE.yaml`
- `research/sources/CHAMBERS-ET-AL-2014.yaml`
- `research/sources/SZADO-2009.yaml`
- `research/sources/EUREKAHEDGE-CBOE-VOL-INDICES.yaml`
- `research/sources/ALEXANDER-KOROVILAS-KAPRAUN-2016.yaml`
