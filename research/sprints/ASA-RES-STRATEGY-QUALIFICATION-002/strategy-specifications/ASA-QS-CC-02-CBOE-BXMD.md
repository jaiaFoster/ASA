# ASA-QS-CC-02-CBOE-BXMD — Cboe S&P 500 30-Delta BuyWrite (BXMD)

- **Lane:** 4, covered call
- **Role:** PRIMARY (second specification)
- **Qualification state:** **DEEP_RESEARCH_REQUIRED**
- **Source methodology version:** [`CBOE-BUYWRITE-METHODOLOGY-2024`](../../../sources/CBOE-BUYWRITE-METHODOLOGY-2024.yaml). BXMD VWAP window 11:30 a.m.–12:00 p.m. ET since February 18, 2022; a 30-minute VWAP was used before that date. The BXRT methodology was also checked for the delta inputs ([`CBOE-BXRT-METHODOLOGY`](../../../sources/CBOE-BXRT-METHODOLOGY.yaml)).

## Why this is not a cosmetic variant of BXM

The lane rule forbids counting "a trivial delta variant" as a second strategy. BXMD is retained as the second primary for three reasons, and the Founder should weigh them against that rule:

1. **Different selection mechanism.** The strike is chosen by *model delta* (Black formula), not by index level. This consumes a different derived fact and different inputs.
2. **Documented, materially different economics** (Wilshire 2019, 1986–2018):

   | | BXMD | BXM |
   |---|---|---|
   | Return | 10.22% | 8.50% |
   | SD | 12.8% | 10.6% |
   | Max drawdown | −42.7% | −35.8% |
   | Beta | 0.77 | 0.55 |
   | Correlation with S&P 500 | 0.95 | 0.89 |

   The distinction is in market-regime exposure (beta 0.77 vs 0.55), not only in a threshold.
3. **Contrary consideration.** Israelov-Nielsen's decomposition treats strike choice as a dial on the same three exposures. On that view BXMD is the same mechanism with a different equity/volatility mix.

**Recommendation recorded for the Founder:** treat the BXM/BXMD pair as *at the boundary* of the diversity rule. It passes on the market-regime-exposure criterion only.

## 1. Evidence qualification

| Item | Finding | Source |
|---|---|---|
| Exact-strategy evidence | 1986–2018: 10.22%, SD 12.8%, Sharpe 0.55, max drawdown −42.7%, beta 0.77; alpha 0.25% per year; highest on Wilshire's mean-variance frontier | WILSHIRE-2019-CBOE, full text (prepared for Cboe) |
| Independent replication | none specific to 30-delta recovered | — |
| Gross vs net | gross; net UNKNOWN | disclaimer |
| Tail | max drawdown −42.7% | WILSHIRE-2019-CBOE |
| Evidence confidence | LOW–MEDIUM (sponsor-commissioned only) | INFERENCE |

## 2–5. Universe, facts, ownership

As BXM (ASA-QS-CC-01 §2–§5), with two changes:
- **Additional derived fact:** `DF-BLACK-CALL-DELTA-CBOE-BXMD`.
- **Structure rule** replaced as in §10 below.

## 6. Gates

| Gate | PASS | FAIL | UNKNOWN |
|---|---|---|---|
| G-CBOE-MONTHLY-ROLL-DATE | as BXM | as BXM | as BXM |
| G-CBOE-SPX-REF-BEFORE-1100 | as BXM | as BXM | as BXM |
| G-BXMD-DELTA-COMPUTABLE | — | — | **always UNKNOWN**: the Black-formula inputs are not defined by the source |

## 7. Verdict truth table

| ROLL | REF | DELTA-COMPUTABLE | Verdict |
|---|---|---|---|
| FAIL | * | * | NO_ACTION |
| UNKNOWN | * | * | UNKNOWN |
| PASS | UNKNOWN | * | UNKNOWN |
| PASS | PASS | UNKNOWN | **UNKNOWN (current state on every roll)** |
| PASS | PASS | PASS | PASS: write the selected call |

## 8. Score

NONE.

## 9. Direction

| Dimension | Direction |
|---|---|
| delta | positive, larger than BXM (index 1.0 minus about 0.30) |
| volatility | negative |
| theta | positive |
| skew | short OTM upside |

## 10. Structure selection (P09)

The call leg is:

c* = argmin_{c ∈ OTM next-month SPX calls} | Δ_Black(c) − 0.30 |

- "OTM" means K(c) > S_ref (DERIVED from "OTM strike").
- **Tie rule (sourced):** "If there are two options with deltas that have an equal distance to a delta of 0.30, then the option with the higher strike is chosen."
- Δ_Black is computed with "all inputs … the last available values before 11:00 a.m. ET".
- **Volatility input, rate input and dividend/forward treatment: UNKNOWN.**
  - They are not stated in the BuyWrite methodology or in the BXRT methodology (checked 2026-09-27).
  - A web search result describing a volatility input "average IV of the nearest monthly option 30 days or more out" could not be traced to a BXMD methodology document and is **not** used.

## 11–16. DTE, entry, lifecycle, sizing, costs, capital

As BXM, except that the sale price is the VWAP from 11:30 a.m. to 12:00 p.m. ET.

## 17. Liquidity

No sourced gates.

## 18. UNKNOWN / invalid states

| Condition | Outcome |
|---|---|
| Black-formula inputs undefined | **RESEARCH BLOCKER** → UNKNOWN on every roll. Different volatility choices (each option's own IV vs a single ATM IV) can move the selected strike by one or more increments, so this is a signal-level unknown. |
| All BXM states | as BXM |

## 19. Provenance

| Object | Source | Direct / inferred |
|---|---|---|
| 0.30 target, OTM, higher-strike tie rule, inputs "before 11:00 a.m. ET" | CBOE-BUYWRITE-METHODOLOGY-2024 | direct |
| Black inputs | — | **UNKNOWN** |
| Performance | WILSHIRE-2019-CBOE | direct (gross) |

## 20. ASA translation sheet

As BXM, with these differences:

| Field | Value |
|---|---|
| strategy_id_candidate | `index_buywrite_cboe_bxmd` |
| derived_facts_new | adds DF-BLACK-CALL-DELTA-CBOE-BXMD (blocked) |
| missing_reusable_primitives | X01, P09, X05, X07, possibly X04 (rate input, if Cboe uses one) |
| architecture_review_required | as BXM |

## 21. Manifest readiness

**Not ready.** An implementation worker would have to choose the Black-formula volatility, rate and dividend inputs. That is a financial decision the source does not make.

Required research action: obtain the Cboe BXMD calculation specification for delta inputs (Cboe index-methodology contact or a licensed data-vendor methodology note).

## Closeout disposition (2026-09-27)

NOT SELECTED. The BXMD factsheet (as of 2026-08) and the BXRT/BXMVM methodologies give no Black-formula volatility, rate or dividend inputs. The volatility choice selects the strike, so this is a financial-rule gap, not an Architect-resolvable analytic question. State unchanged: DEEP_RESEARCH_REQUIRED.
