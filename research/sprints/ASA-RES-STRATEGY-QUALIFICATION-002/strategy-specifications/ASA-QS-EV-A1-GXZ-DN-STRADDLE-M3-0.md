# ASA-QS-EV-A1-GXZ-DN-STRADDLE-M3-0 — delta-neutral straddle, close of day −3 to close of day 0

- **Lane:** 1, event volatility
- **Role:** ALTERNATE
- **Qualification state:** **RESEARCH_REJECT** (as a return-seeking rule)
- **Source:** [`GAO-XING-ZHANG-2013-WP`](../../../sources/GAO-XING-ZHANG-2013-WP.yaml), §3–§5, full text. Published abstract: [`GAO-XING-ZHANG-2018`](../../../sources/GAO-XING-ZHANG-2018.yaml).

## Specification (recorded for completeness)

| Element | Rule | Class |
|---|---|---|
| Universe and filters | as ASA-QS-EV-01 §2 and §6, plus G-GXZ-MATURITY-SAMPLE-FILTER (10–60 days; day-count unit UNKNOWN) | gates |
| Entry | close of session(day0, −3) | lifecycle |
| Exit | close of day 0 (I/B/E/S date; no after-close adjustment in the preprint) | lifecycle |
| Structure | P03; call and put weights set so that straddle delta is zero: DF-STRADDLE-ZERO-DELTA-WEIGHT (DERIVED from "weights adjusted to make straddle delta zero"; GXZ print no formula and cite Coval-Shumway, whose text was not accessed) | structure |
| Multi-pair | not stated for the main tables (UNKNOWN) | — |
| Score | NONE | — |
| Sizing | UNKNOWN (equal-weighted averages across straddles) | — |

## Evidence that defeats the return-seeking thesis

| Item | Value |
|---|---|
| Gross, equal-weighted DN, mid prices | [−3,0] 3.00%. Other windows: [−5,0] 2.22%; [−1,0] 2.30%; [−5,1] 2.68%; [−3,1] 1.25%; [−1,1] 3.09%. Simple straddles: 0.80%–2.25%. |
| Costs (source's own calculation) | Average relative spread is about 14% from day −20, 15% on day −1 and above 16% on day 0. The authors: "Even if we use 50% of the quoted spread as the realized spread, with average 3-day return of 3%, and around 11% relative spread for a round trip trade, this strategy would deliver a 3-day return of −8%." |
| Conclusion by the authors | "to some extent, the options market efficiently adjusts to surprises around earnings announcements" |
| Recent contrary evidence | ALX (2013–2020, top-100 option-volume firms): mean EAD one-day DN straddle return −0.86%, median −15.43% |

**Status reason:** the recovered evidence shows net-of-spread returns are negative even at 50% of the quoted spread. That materially defeats use of this rule for return-seeking. It remains useful as the phenomenon source for ASA-QS-EV-01.
