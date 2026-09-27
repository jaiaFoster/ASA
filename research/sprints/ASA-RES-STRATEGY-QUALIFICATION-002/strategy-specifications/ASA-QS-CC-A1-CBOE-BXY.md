# ASA-QS-CC-A1-CBOE-BXY — Cboe S&P 500 2% OTM BuyWrite (BXY)

- **Lane:** 4, covered call
- **Role:** ALTERNATE
- **Qualification state:** **INSUFFICIENT_EVIDENCE**
  - The rules are complete except for an untyped tie case.
  - No exact-strategy performance evidence was recovered.
- **Source:** [`CBOE-BUYWRITE-METHODOLOGY-2024`](../../../sources/CBOE-BUYWRITE-METHODOLOGY-2024.yaml).

## Specification

| Element | Rule |
|---|---|
| Universe, roll date, reference, lifecycle, return accounting | as BXM (ASA-QS-CC-01) |
| Strike | c* = argmin_c | K(c) − 1.02·S_ref |, next-month SPX call. "The strike price closest to 102% of the last value of the S&P 500 Index reported before 11:00 a.m." |
| Tie rule | **none given for BXY.** The higher-strike tie rule is stated only in the 30-delta footnote. Two equidistant strikes → AMBIGUOUS_SELECTION (G-BXY-STRIKE-UNIQUE) → UNKNOWN. |
| Sale price | VWAP 11:30 a.m.–12:00 p.m. ET |
| Structure | P09: 1 index unit long, 1 call short |
| Score | NONE |
| Direction | delta positive (between BXM and BXMD); volatility negative |
| Sizing | equal notional |
| Costs | VWAP entry; net UNKNOWN |

## Evidence

- Exact-strategy statistics were not recovered. Wilshire 2019 reports statistics for BXM, BXMD, PUT, CMBO and PPUT only.
- Phenomenon evidence is shared with BXM and is **indirect**.

## Readiness

The specification is complete apart from the tie case, which is typed. It is not advanced because evidence is lacking.

## Closeout disposition (2026-09-27)

NOT SELECTED. BXY is a 2%-moneyness variant of BXM. The lane-4 requirement forbids counting "a trivial delta variant" as a second strategy, and no independent evaluation distinguishing it was recovered. State unchanged: INSUFFICIENT_EVIDENCE.
