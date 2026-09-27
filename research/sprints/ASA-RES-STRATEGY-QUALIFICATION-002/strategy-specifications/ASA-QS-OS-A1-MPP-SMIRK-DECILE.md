# ASA-QS-OS-A1-MPP-SMIRK-DECILE — stock-return signal from the implied-volatility smirk (decile sort)

- **Lane:** 5, option-implied information
- **Role:** ALTERNATE (no primary qualified in this lane)
- **Qualification state:** **RESEARCH_REJECT** (as a return-seeking rule net of borrow fees)
- **Source methodology version:** Muravyev, Pearson and Pollet, "Why Does Options Market Information Predict Stock Returns?", conference version dated May 13, 2022, full text ([`MURAVYEV-PEARSON-POLLET-2022-WP`](../../../sources/MURAVYEV-PEARSON-POLLET-2022-WP.yaml)).
  - The final version, JFE 172 (2025), 104153 ([`MURAVYEV-PEARSON-POLLET-2025`](../../../sources/MURAVYEV-PEARSON-POLLET-2025.yaml)), was not accessible in full text (publisher 403). Its abstract matches the direction of the conference version.
- **Signal originator:** Xing, Zhang and Zhao (2010), bibliographic only in this sprint ([`XING-ZHANG-ZHAO-2010`](../../../sources/XING-ZHANG-ZHAO-2010.yaml)).

## Specification (recorded)

| Element | Rule | Class |
|---|---|---|
| Universe | CRSP common stocks with valid OptionMetrics data (G-MPP-VALID-PAIR) and a Markit indicative borrow fee | gate |
| Signal | skew_i,t = IV(OTM put, 0.8 < K/S < 0.95) − IV(ATM call, 0.95 < K/S < 1.05) (DF-XZZ-SMIRK-MPP). Which option is used when several qualify: UNKNOWN. **Source-internal inconsistency:** §4.2 describes the skew as "an OTM call and an ATM call"; the data section and XZZ define an OTM *put*. Recorded as UNKNOWN pending the final version. | derived fact |
| Formation | decile sort at the close of day t, on every trading day (overlapping portfolios) | lifecycle |
| Holding | close of t+1 to close of t+22 (a one-day skip, then 21 trading days) | lifecycle |
| Expression | **stock**, not option: short decile 10 (highest skew); long decile 1 in the long-short variant | structure |
| Abnormal return | DGTW characteristic-matched against low-fee benchmark portfolios (size, B/M, 6-month return) | evaluation |
| Borrow treatment | the fee is added to long returns in deciles 9–10, so short positions pay it; long-side lending income = fee × utilization × 0.7 (D'Avolio 30% intermediation haircut) | cost |
| High-fee definition | Markit IndicativeFee > 1% per year (about 7% of observations) | parameter |
| Score | NONE | — |
| Sizing | equal-weighted decile averages; capital UNKNOWN | — |

## Evidence

| Item | Value (per month) |
|---|---|
| Decile 10 abnormal return | −0.59% (t −4.5) |
| Decile 9 | −0.22% (t −2.2) |
| Other deciles | "no evidence of abnormal performance" |
| D10 − D1 | −0.69% |
| **Net of borrow fee:** decile 10 | −0.21% (t −1.6, **insignificant**) |
| Net of borrow fee: long-short | −0.33% (48% of gross) |
| Low-fee stocks only: decile 10 | −0.17% (t −1.4, insignificant) |
| High-fee stocks in decile 10 | −1.56% (t −5.8). The predictability is concentrated in stocks that are expensive or impossible to short. |
| Sibling signals, same paper | IV spread: decile 10 −0.67% (t −5.5) → −0.19% (t −1.6) net of fee. O/S: net-of-fee decile 10 −6 bp. |

The final JFE abstract (2025): predictability "decreases by about two-thirds" after the borrow-fee adjustment.

**Status reason:** the recovered evidence shows that the abnormal return is almost entirely compensation for borrow costs on hard-to-borrow stocks. Net of those costs it is statistically insignificant. This materially defeats the return-seeking thesis for the stock expression.

The ASA-relevant corollary is recorded in LANE-05: an **option** expression would embed the same borrow cost in option prices (put-call parity with lending fees).

## Closeout disposition (2026-09-27)

NOT SELECTED (Founder direction). The existing evidence base (FAM-OPTION-SIGNAL-EQUITY dossier) holds no other signal with better than abstract-level evidence or net-positive results; MPP reattributes the family to borrow fees. Lane 5 closes with zero targets. State unchanged: RESEARCH_REJECT.
