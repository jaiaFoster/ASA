# ASA-QS-SV-A1-BK-DELTA-HEDGED-INDEX-CALL — daily delta-hedged long S&P 500 index call (volatility-risk-premium measurement)

- **Lane:** 3, index short volatility
- **Role:** ALTERNATE (no primary qualified in this lane)
- **Qualification state:** **DEEP_RESEARCH_REQUIRED**
- **Source methodology version:** Bakshi and Kapadia, "Delta-Hedged Gains and the Negative Market Volatility Risk Premium", *Review of Financial Studies* 16(2), 2003, full text ([`BAKSHI-KAPADIA-2003`](../../../sources/BAKSHI-KAPADIA-2003.yaml)).

## What the source defines

BK is a **measurement design**, not a trading strategy. It evaluates every eligible option-day and reports average delta-hedged gains.

| Element | Rule |
|---|---|
| Sample | S&P 500 index options, January 1988 – December 1995 |
| Quotes | the last quote before 3:00 p.m. CST |
| Filters (G-BK-OPTION-FILTERS) | arbitrage bounds; IV between 1% and 100%; maturity 14–60 days; moneyness within ±10% |
| Rate | r implied from put-call parity using bid/ask pairs |
| Dividends | the present value of actual dividends is subtracted from the index |
| Position | **buy** one call; short Δ units of the index; rebalance daily to the Black-Scholes delta; hold to expiry |
| Hedge-volatility estimator | GARCH fitted over **the full sample** (look-ahead), or a historical-volatility alternative; the window length for the alternative is not recovered |
| Gain | DF-BK-DELTA-HEDGED-GAIN |
| Result | ATM delta-hedged calls lose about 0.10% of the index level, about $0.43 per call, against a mean bid-ask spread of $0.375 |

## Why this is not a primary

1. **No entry schedule.** Every option-day is an observation, so there is no rule for when to open, how many series to hold or how to roll.
2. **No sizing.** SIZING = UNKNOWN.
3. **Look-ahead** in the GARCH hedge volatility.
4. **Direction.** The source studies the long hedged call; the short-volatility expression is its negative. The gain per option (about $0.43) is barely above the mean spread (about $0.375), so a short-volatility trader who pays the spread keeps close to nothing on these numbers (INFERENCE from the reported figures; BK do not report net results).
5. **Needs A14** (daily hedge simulation) and X01.

The paper remains the lane's best-specified evidence for the **phenomenon** (a negative market volatility risk premium). DF-BK-DELTA-HEDGED-GAIN is registered for reuse.

## Closeout disposition (2026-09-27)

NOT SELECTED. It remains a measurement design; the lane-3 target is ASA-QS-SV-01-SCS-SHORT-NEAR-ATM-STRADDLE. State unchanged: DEEP_RESEARCH_REQUIRED.
