# ASA-RSCH-FAM-TERM-STRUCTURE-001 — Volatility Term-Structure Trades (calendars, forward volatility, slope sorts)

## Identity

- **Research ID:** ASA-RSCH-FAM-TERM-STRUCTURE-001
- **Strategy:** Volatility Term-Structure Trades (calendars, forward volatility, slope sorts)
- **Family:** FAM-TERM-STRUCTURE (E3 volatility relative value); taxonomy in `research/sprints/ASA-RES-SPRINT-001/RES-001B-taxonomy.md`
- **Research status:** TRIAGE
- **Created:** 2026-09-26
- **Updated:** 2026-09-26

This is a family-level comparable record (RES-001C). Status describes evidence only. It is not a priority, selection, or implementation signal. Numeric values are stated only where a source reports them; everything else is UNKNOWN. Claim classes: REPORTED / DERIVED / INFERENCE / UNKNOWN. Source verification depth for this record: bibliographic_and_abstract: 5.

## Thesis

### Concise description

Take opposite volatility positions across expirations (calendars, diagonals, forward-volatility trades) or sort underlyings on term-structure slope.

### Proposed economic or behavioral mechanism

The variance premium is concentrated at the short end: news about future variance is essentially unpriced, only transitory realized variance is (DEWBECKER-ET-AL-2017); optimal variance allocation is short front / long back (EGLOFF-LEIPPOLD-WU-2010); term slope predicts returns (VASQUEZ-2017, JOHNSON-2017).

## Evidence

Sample, universe and method context: Individual US equity options (Vasquez); S&P 500 variance claims (Dew-Becker, Egloff); VIX (Johnson).

### Original research

- **VASQUEZ-2017** — High-slope straddle portfolios outperform low-slope significantly; not explained by standard or option factors or jump risk.
- **DEWBECKER-ET-AL-2017** — 1996-2014: hedging news about future variance costless on average from 1 quarter to 14 years.

### Supporting research

- **EGLOFF-LEIPPOLD-WU-2010** — Optimal: short short-term variance, long long-term variance.
- **JOHNSON-2017** — VIX SLOPE predicts variance swap, VIX futures and straddle returns at all maturities.
- **DUBINSKY-ET-AL-2019** — Earnings announcements create large, time-varying anticipated uncertainty (event contamination of term structure).

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
| Reported return metrics | UNKNOWN point values at abstract depth. |
| Reported risk metrics | UNKNOWN. |
| Drawdown / tail | INFERENCE: calendar long back / short front loses on sharp front-month spikes and term inversions. |
| Opportunity frequency | Monthly cross-sectional rebalance (Vasquez) or continuous (index). |
| Regime dependence | Slope itself is the conditioning variable. |
| Persistence | UNKNOWN. |
| Transaction-cost sensitivity | UNKNOWN; two-expiry structures double leg costs (INFERENCE). |

## Specification

As documented in the sources. No rule is invented, and missing parameters are UNKNOWN.

| Field | Value |
|---|---|
| Entry rules | Sort on IV term slope (Vasquez); forward-vol conditions (practitioner). |
| DTE / expiration | Front vs next/longer expiry. |
| Strike / delta | ATM (straddles in Vasquez). |
| Liquidity requirements | UNKNOWN. |
| Exit rules | Monthly. |
| Roll rules | Monthly. |
| Sizing assumptions | Equal-weight portfolios (INFERENCE, UNKNOWN). |
| Exclusions | UNKNOWN. |
| Unresolved rule gaps | **Evidence is for straddle sorts and variance claims, not for calendar spreads as traded by practitioners; transfer to calendars is INFERENCE.** |

## Practical evidence

| Risk field | Value |
|---|---|
| Maximum / tail risk | Defined (debit calendar) or undefined (variance). |
| Liquidity risk | Back-month liquidity (INFERENCE). |
| Assignment / exercise risk | Short front leg early assignment (INFERENCE). |
| Gap risk | Medium. |
| Volatility-regime risk | Term inversions in stress (INFERENCE). |
| Model dependency | Medium. |
| Crowding / decay evidence | UNKNOWN. |
| Known failure modes | Front-month spikes; event mis-dating. |

## Adversarial review

| Question | Answer |
|---|---|
| Replicated? | No direct replication found; convergent evidence from distinct methods. |
| Failed? | None found. |
| Later research? | None found reducing it. |
| Persisted? | UNKNOWN. |
| Data mining? | Moderate. |
| Concentrated? | UNKNOWN. |
| Parameter-dependent? | UNKNOWN. |
| Costs? | UNKNOWN. |
| Execution? | UNKNOWN. |
| Another factor? | Short-end VRP. |
| Look-ahead? | Earnings dates must be known ex ante. |
| Failure regime? | Stress inversions. |
| Crowding? | UNKNOWN. |
| Omission risk? | Treating straddle-sort evidence as calendar-spread evidence. |

## ASA capability mapping

Performed after the external evidence assessment above. Implementation ease does not affect the evidence rating.

| Field | Value |
|---|---|
| Required market data | Multi-expiry chains; earnings dates. |
| Required analytics | A05 slope / forward vol; A09 event adjustment. |
| Required history | Historical multi-expiry option data. |
| Required event data | Earnings calendar to separate event from term effect. |
| Structural primitives (RES-001B §3) | P06, P07, P03, P12. |
| Apparent existing ASA capabilities | Calendar and double calendar structures; IV term-structure spread; implied forward volatility; forward factor; earnings windows. |
| Apparent missing ASA capabilities | Historical option panel; straddle structure for the Vasquez sort; cross-sectional structure portfolio. |
| Execution complexity | Medium. |

## Assessment

### Strongest supporting evidence

Convergent peer-reviewed evidence that variance risk is priced mainly at the short end (DEWBECKER-ET-AL-2017, EGLOFF-LEIPPOLD-WU-2010) and that slope predicts returns (VASQUEZ-2017, JOHNSON-2017).

### Strongest contradictory evidence

None found; gap is structural transfer, not contradiction.

### Unresolved questions

- Calendar-spread-specific evidence
- Net-of-cost results
- Event-contaminated vs clean term structure

### Evidence limitations

Most sources were verified at bibliographic-and-abstract depth. Sample periods, cost models, and exact rules are often UNKNOWN until full texts are recovered.

### Qualification status

TRIAGE

### Qualification basis

TRIAGE: multiple independent peer-reviewed lines support the mechanism; strategy-form (calendar) evidence is absent.

## Research history

- 2026-09-26: record created as TRIAGE in ASA-RES-SPRINT-001 (RES-001C). No prior conclusion existed.

## Provenance

- `research/sources/VASQUEZ-2017.yaml`
- `research/sources/DEWBECKER-ET-AL-2017.yaml`
- `research/sources/EGLOFF-LEIPPOLD-WU-2010.yaml`
- `research/sources/JOHNSON-2017.yaml`
- `research/sources/DUBINSKY-ET-AL-2019.yaml`
