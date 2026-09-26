# ASA-RSCH-FAM-OPTION-SIGNAL-001 — Option-Implied Signals for Equity Direction

## Identity

- **Research ID:** ASA-RSCH-FAM-OPTION-SIGNAL-001
- **Strategy:** Option-Implied Signals for Equity Direction
- **Family:** FAM-OPTION-SIGNAL-EQUITY (E5 option-implied information); taxonomy in `research/sprints/ASA-RES-SPRINT-001/RES-001B-taxonomy.md`
- **Research status:** TRIAGE
- **Created:** 2026-09-26
- **Updated:** 2026-09-26

This is a family-level comparable record (RES-001C). Status describes evidence only. It is not a priority, selection, or implementation signal. Numeric values are stated only where a source reports them; everything else is UNKNOWN. Claim classes: REPORTED / DERIVED / INFERENCE / UNKNOWN. Source verification depth for this record: bibliographic_and_abstract: 11.

## Thesis

### Concise description

Use option prices or volumes (volatility smirk, call-put IV spread, IV changes, risk-neutral skewness, option/stock volume, put-call ratio, vol-of-vol) to predict the underlying's return, then trade the stock or an option expression.

### Proposed economic or behavioral mechanism

Informed traders prefer options, especially OTM puts for negative news (XING-ZHANG-ZHAO-2010, PAN-POTESHMAN-2006); embedded leverage (GE-LIN-PEARSON-2016); short-sale costs route bearish information to options (JOHNSON-SO-2012). Most recent evidence: option prices reflect borrow fees that themselves predict returns (MURAVYEV-PEARSON-POLLET-2025).

## Evidence

Sample, universe and method context: US optionable stocks, mostly 1996 onward; horizons from next day to 6 months.

### Original research

- **XING-ZHANG-ZHAO-2010** — Steep-smirk stocks underperform by 10.9%/yr risk-adjusted; persists 6 months.
- **CREMERS-WEINBAUM-2010** — Expensive-call minus expensive-put stocks: 50 bp/week.
- **PAN-POTESHMAN-2006** — Low put-call ratio stocks outperform by >40 bp next day, >1% next week (non-public data).

### Supporting research

- **AN-ET-AL-2014** — Call IV increases predict ~1%/month spreads for 6 months.
- **JOHNSON-SO-2012** — Low O/S outperforms high by 0.34%/week.
- **BALI-HOVAKIMIAN-2009** — Call-put IV spread positive; realized-implied spread negative.
- **BALTUSSEN-ET-AL-2018** — High vol-of-vol stocks underperform 8%/yr (US and Europe).
- **STILGER-KOSTAKIS-POON-2017** — High-RNS minus low-RNS: 55 bp/month alpha 1996-2012.

### Independent replications

- **GE-LIN-PEARSON-2016** — Re-examines O/S with signed volume; attributes predictability to embedded leverage.

### Failed replications

- None found in this sprint's search coverage (see `research/sprints/ASA-RES-SPRINT-001/RES-001A-landscape.md` §2).

### Contradictory research

- **CONRAD-DITTMAR-GHYSELS-2013** — Negative-skew stocks earn higher returns: sign opposite to STILGER-KOSTAKIS-POON-2017.
- **MURAVYEV-PEARSON-POLLET-2025** — Predictability from option signals falls by about two-thirds after borrow-fee adjustment or excluding high-fee stocks.

### Post-publication evidence

- **CREMERS-WEINBAUM-2010** — Predictability decreased over the sample period (within-sample decay).
- **MURAVYEV-PEARSON-POLLET-2025** — Re-interpretation: much of the effect is an equity short-sale-cost effect.

### Reported empirical results

| Field | Value |
|---|---|
| Reported return metrics | REPORTED: 10.9%/yr (smirk); 50 bp/week (CW); ~1%/month (IV change); 0.34%/week (O/S); 55 bp/month (RNS). Largely long-short, gross. |
| Reported risk metrics | UNKNOWN. |
| Drawdown / tail | Depends on expression. |
| Opportunity frequency | Daily to monthly across universe. |
| Regime dependence | UNKNOWN. |
| Persistence | **Decaying**: within-sample (CW) and borrow-fee re-attribution (MPP-2025). |
| Transaction-cost sensitivity | UNKNOWN; short leg requires borrowing costly stocks (MPP-2025). |

## Specification

As documented in the sources. No rule is invented, and missing parameters are UNKNOWN.

| Field | Value |
|---|---|
| Entry rules | Cross-sectional rank on option-implied measure. |
| DTE / expiration | Signal from near-term options (UNKNOWN exact). |
| Strike / delta | OTM put vs ATM call (smirk). |
| Liquidity requirements | Option liquidity matters (CW). |
| Exit rules | Horizon-based (1 week - 6 months). |
| Roll rules | Periodic. |
| Sizing assumptions | Decile/quintile portfolios. |
| Exclusions | UNKNOWN. |
| Unresolved rule gaps | Stock-return evidence does not specify an option expression; expression choice is not evidence-backed. |

## Practical evidence

| Risk field | Value |
|---|---|
| Maximum / tail risk | Expression-dependent. |
| Liquidity risk | Short leg borrow constraints. |
| Assignment / exercise risk | Expression-dependent. |
| Gap risk | Earnings. |
| Volatility-regime risk | UNKNOWN. |
| Model dependency | Medium (IV surface fitting). |
| Crowding / decay evidence | Decay evidence. |
| Known failure modes | Borrow-fee-driven returns not capturable long-only. |

## Adversarial review

| Question | Answer |
|---|---|
| Replicated? | Partially (O/S re-examined). |
| Failed? | None outright; RNS sign conflict. |
| Later research reduces? | Yes, by about two-thirds (MPP-2025). |
| Persisted? | Decaying. |
| Data mining? | Many related signals: high multiple-testing risk. |
| Concentrated? | High-fee stocks. |
| Parameter-dependent? | Measure-dependent (RNS sign). |
| Costs? | Borrow costs central. |
| Execution? | Short side problematic. |
| Another factor? | Short-sale cost / borrow fee. |
| Look-ahead? | No. |
| Failure regime? | UNKNOWN. |
| Crowding? | Decay consistent. |
| Omission risk? | Omitting MPP-2025. |

## ASA capability mapping

Performed after the external evidence assessment above. Implementation ease does not affect the evidence rating.

| Field | Value |
|---|---|
| Required market data | Chains (IV by strike), volume, borrow fees. |
| Required analytics | A06 skew/smirk; A07 RN moments; A10 borrow fee; A11 signed volume; A13 ranking. |
| Required history | IV history per name (A08 or prospective accumulation). |
| Required event data | Earnings (smirk predicts earnings shocks). |
| Structural primitives (RES-001B §3) | Expression-dependent (stock or P02). |
| Apparent existing ASA capabilities | Normalized skew, skew history (prospective), IV vs RV, cross-sectional/sector momentum, ranking; Skew Momentum policy consumes several of these. |
| Apparent missing ASA capabilities | Model-free RN moments; borrow fees; signed/open-close volume; historical IV panel. |
| Execution complexity | Medium. |

## Assessment

### Strongest supporting evidence

Many peer-reviewed signals with economically large reported spreads.

### Strongest contradictory evidence

Borrow-fee re-attribution (MURAVYEV-PEARSON-POLLET-2025) and RNS sign conflict.

### Unresolved questions

- Residual predictability for low-fee stocks
- Whether an option expression adds value over trading the stock

### Evidence limitations

Most sources were verified at bibliographic-and-abstract depth. Sample periods, cost models, and exact rules are often UNKNOWN until full texts are recovered.

### Qualification status

TRIAGE

### Qualification basis

TRIAGE: abundant peer-reviewed evidence, but the most recent top-journal evidence removes most of it for implementable (low-fee, long-biased) use.

## Research history

- 2026-09-26: record created as TRIAGE in ASA-RES-SPRINT-001 (RES-001C). No prior conclusion existed.

## Provenance

- `research/sources/XING-ZHANG-ZHAO-2010.yaml`
- `research/sources/CREMERS-WEINBAUM-2010.yaml`
- `research/sources/PAN-POTESHMAN-2006.yaml`
- `research/sources/AN-ET-AL-2014.yaml`
- `research/sources/JOHNSON-SO-2012.yaml`
- `research/sources/BALI-HOVAKIMIAN-2009.yaml`
- `research/sources/BALTUSSEN-ET-AL-2018.yaml`
- `research/sources/STILGER-KOSTAKIS-POON-2017.yaml`
- `research/sources/GE-LIN-PEARSON-2016.yaml`
- `research/sources/CONRAD-DITTMAR-GHYSELS-2013.yaml`
- `research/sources/MURAVYEV-PEARSON-POLLET-2025.yaml`
