# ASA-RSCH-FAM-ULTRA-SHORT-001 — Ultra-Short-Dated Premium Strategies (0DTE / weekly)

## Identity

- **Research ID:** ASA-RSCH-FAM-ULTRA-SHORT-001
- **Strategy:** Ultra-Short-Dated Premium Strategies (0DTE / weekly)
- **Family:** FAM-VRP-ULTRA-SHORT-DATED (E1 insurance selling); taxonomy in `research/sprints/ASA-RES-SPRINT-001/RES-001B-taxonomy.md`
- **Research status:** INSUFFICIENT_EVIDENCE
- **Created:** 2026-09-26
- **Updated:** 2026-09-26

This is a family-level comparable record (RES-001C). Status describes evidence only. It is not a priority, selection, or implementation signal. Numeric values are stated only where a source reports them; everything else is UNKNOWN. Claim classes: REPORTED / DERIVED / INFERENCE / UNKNOWN. Source verification depth for this record: bibliographic_and_search_engine_summary: 2, full_text_reviewed: 1, primary_repository_readme_reviewed: 1.

## Thesis

### Concise description

Sell (or trade) same-day or weekly index options, alone or in multi-leg templates, to capture short-horizon volatility and jump premia.

### Proposed economic or behavioral mechanism

Short-maturity options isolate jump-tail risk (ANDERSEN-FUSARI-TODOROV-2017); a 0DTE variance premium exists but is small at same-day horizons (VILKOV-0DTE). Retail demand dominates flow (BECKMEYER-BRANGER-GAYDA-0DTE, BRYZGALOVA-ET-AL-2023).

## Evidence

Sample, universe and method context: S&P 500 SPXW 0DTE options 2016-2026 (Vilkov); weekly SPX puts 2006-2018 (WPUT).

### Original research

- **VILKOV-0DTE** — Systematic study 2016-09 to 2026-01 of 0DTE straddles, strangles, iron butterflies/condors, verticals, ratio spreads, risk reversals.

### Supporting research

- **BONDARENKO-2019-CBOE** — WPUT (weekly put writing) 2006-2018: lower SD and drawdown than PUT but lower compound return (4.51%) and Sharpe (0.40).
- **BANDI-FUSARI-RENO-0DTE** — 0DTE pricing model; suggestive short-horizon risk-premium predictability (pricing paper).

### Independent replications

- None found in this sprint's search coverage (see `research/sprints/ASA-RES-SPRINT-001/RES-001A-landscape.md` §2).

### Failed replications

- **VILKOV-0DTE** — Aug-2026 erratum: half-spread charged at 1/100 of true size; after correction no strategy or basket retains a positive net Sharpe.

### Contradictory research

- **BECKMEYER-BRANGER-GAYDA-0DTE** — Retail loses on 0DTE, mostly through transaction costs (search-summary depth).

### Post-publication evidence

- **VILKOV-0DTE** — The erratum itself is post-publication evidence reversing the net conclusion.

### Reported empirical results

| Field | Value |
|---|---|
| Reported return metrics | REPORTED: after correction, no positive net Sharpe (VILKOV-0DTE). WPUT 4.51% compound 2006-2018. |
| Reported risk metrics | REPORTED: PnL distributions wide, state-dependent, dominated by tail risk (VILKOV-0DTE). |
| Drawdown / tail | High; realized skewness of index return explains PnL (VILKOV-0DTE). |
| Opportunity frequency | Daily (0DTE) or weekly. |
| Regime dependence | REPORTED: state-dependent (VILKOV-0DTE). |
| Persistence | Negative after correction. |
| Transaction-cost sensitivity | Decisive: a 2.2 bp half-spread vs 0.022 bp flips the sign (VILKOV-0DTE). |

## Specification

As documented in the sources. No rule is invented, and missing parameters are UNKNOWN.

| Field | Value |
|---|---|
| Entry rules | Intraday time rule (e.g. 10:00 ET) in Vilkov; calendar weekly for WPUT. |
| DTE / expiration | 0 days / 1 week. |
| Strike / delta | Moneyness templates (UNKNOWN exact). |
| Liquidity requirements | SPXW. |
| Exit rules | Expiration same day. |
| Roll rules | Daily/weekly. |
| Sizing assumptions | UNKNOWN. |
| Exclusions | UNKNOWN. |
| Unresolved rule gaps | Corrected paper under revision; exact templates and conditional rules not recovered. |

## Practical evidence

| Risk field | Value |
|---|---|
| Maximum / tail risk | Defined or undefined by template. |
| Liquidity risk | Spread costs decisive. |
| Assignment / exercise risk | None (European SPX). |
| Gap risk | Intraday jumps. |
| Volatility-regime risk | High. |
| Model dependency | Medium. |
| Crowding / decay evidence | Retail concentration documented. |
| Known failure modes | Transaction costs; intraday jumps. |

## Adversarial review

| Question | Answer |
|---|---|
| Independently replicated? | A third-party replication surfaced the cost bug (public report linked from search). |
| Failed? | Yes: corrected result negative. |
| Later research? | Erratum reverses conclusion. |
| Persisted? | No net edge. |
| Data mining? | Conditional rules at high risk. |
| Concentrated? | UNKNOWN. |
| Parameter-dependent? | Highly (cost parameter). |
| Costs? | Decisive. |
| Execution? | Intraday fill assumptions critical. |
| Another factor? | Short-horizon VRP/jump risk. |
| Look-ahead? | Strict OOS protocol claimed. |
| Failure regime? | Jump days. |
| Crowding? | Retail-dominated flow. |
| Omission risk? | Citing pre-erratum results. |

## ASA capability mapping

Performed after the external evidence assessment above. Implementation ease does not affect the evidence rating.

| Field | Value |
|---|---|
| Required market data | Intraday SPX 0DTE chain. |
| Required analytics | Intraday timing, realized-skewness forecast. |
| Required history | Intraday historical option bars (Cboe proprietary). |
| Required event data | Macro releases (INFERENCE). |
| Structural primitives (RES-001B §3) | P03, P04, P05, P08. |
| Apparent existing ASA capabilities | None specific. |
| Apparent missing ASA capabilities | SPX identity, intraday chain history, multi-leg structures beyond vertical. |
| Execution complexity | High (intraday). |

## Assessment

### Strongest supporting evidence

Existence of a small 0DTE VRP (VILKOV-0DTE); WPUT's lower drawdown (BONDARENKO-2019-CBOE).

### Strongest contradictory evidence

Corrected net Sharpe non-positive for every strategy/basket (VILKOV-0DTE).

### Unresolved questions

- Whether any conditional rule survives realistic costs
- Weekly (not 0DTE) put-writing net of costs

### Evidence limitations

Most sources were verified at bibliographic-and-abstract depth. Sample periods, cost models, and exact rules are often UNKNOWN until full texts are recovered.

### Qualification status

INSUFFICIENT_EVIDENCE

### Qualification basis

INSUFFICIENT_EVIDENCE: the only systematic multi-strategy study reports no positive net performance after its correction; weekly evidence shows lower returns than monthly.

## Research history

- 2026-09-26: record created as INSUFFICIENT_EVIDENCE in ASA-RES-SPRINT-001 (RES-001C). No prior conclusion existed.

## Provenance

- `research/sources/VILKOV-0DTE.yaml`
- `research/sources/BONDARENKO-2019-CBOE.yaml`
- `research/sources/BANDI-FUSARI-RENO-0DTE.yaml`
- `research/sources/BECKMEYER-BRANGER-GAYDA-0DTE.yaml`
