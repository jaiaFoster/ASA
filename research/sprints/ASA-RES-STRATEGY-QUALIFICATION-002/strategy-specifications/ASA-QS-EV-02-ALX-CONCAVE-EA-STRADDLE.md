# ASA-QS-EV-02-ALX-CONCAVE-EA-STRADDLE — earnings-day straddle conditioned on IV-curve concavity

- **Lane:** 1, event volatility
- **Role:** PRIMARY (second specification)
- **Qualification state:** **DEEP_RESEARCH_REQUIRED**
- **Source methodology version:** Alexiou, Goyal, Kostakis and Rompolis, "Pricing Event Risk: Evidence from Concave Implied Volatility Curves", *Review of Finance* 29(4), 2025, doi 10.1093/rof/rfaf016. Publisher full text reviewed ([`ALEXIOU-ET-AL-2025`](../../../sources/ALEXIOU-ET-AL-2025.yaml)).

## Why this is materially different from ASA-QS-EV-01

| | ASA-QS-EV-01 (GXZ) | ASA-QS-EV-02 (ALX) |
|---|---|---|
| Signal | unconditional | computed from the shape of the short-dated IV curve (a risk-neutral-density-based derived fact) |
| Timing | 3 sessions before to expiry | one day: close of d−1 to close of the EAD |
| Return mechanism | underpricing of event uncertainty (long) | an event-risk premium that is large **only** when the curve is concave (the premium investors pay) |

## 1. Evidence qualification

| Item | Finding | Source |
|---|---|---|
| Sample | 2013–2020; each calendar year the 100 firms with the highest option volume (194 firms in total); common stock; price > $5; OptionMetrics | ALX §2.1, full text |
| Phenomenon | CONCAVE on d−1 predicts larger EAD price moves (the paper's main result: a valid ex-ante event-risk signal) | ALX, full text |
| Exact result | Mean DN STRADDLE on EAD −0.86% (median −15.43%). CONCAVE = 1: −3.74%; CONCAVE = 0: +0.91%; difference −4.65% (t −2.16). Panel regression −4.57% (t 2.40, as printed); −7.60% with controls. JUMPSTRADDLE (delta- and vega-neutral) −10.69% vs 2.29%. | ALX §5.2–5.3, Tables 3 and 5 |
| Costs | With costs (ask to buy, bid to sell; or effective spread at 75% or 50% of quoted), "straddle returns are overall substantially lower", but the **differential** "remains intact and significant". **Level returns net of cost are not reported.** | ALX footnote 17 |
| Replication | none recovered | — |
| Contradictory | GXZ (1996–2010) find positive pre-EA straddle returns. ALX's unconditional EAD mean is negative. Different windows and eras. | GXZ 2013 WP |
| Evidence confidence | LOW–MEDIUM: single recent study; differential evidence only | INFERENCE |

## 2. Universe

U_d = { firms i in the top 100 by option trading volume in calendar year(d), common stock (share code 10/11), price > $5, with an earnings announcement date d (DF-EA-EFFECTIVE-DATE-ALX) }.

**Look-ahead:** the ranking uses the same calendar year's option volume, which is not known at d−1. **A live universe rule is not source-defined** (G-ALX-UNIVERSE-TOP100-VOLUME is always UNKNOWN live).

## 3. Canonical facts

| Fact | Unit | Observation | ASA status | Missing |
|---|---|---|---|---|
| earnings date and time-of-day (after close) | date, BMO/AMC | before d−1 | EARNINGS_CALENDAR_V1 (time-of-day coverage unverified) | UNKNOWN |
| option chain with IV, bid, ask, OI, volume, settlement type | — | close of d−1 | OPTION_CHAIN_V1. IV is provider IV, not OptionMetrics: equivalence UNKNOWN. | option discarded / UNKNOWN |
| S | USD | close of d−1 | quote/bars | UNKNOWN |
| risk-free rate r | decimal | d−1 | X04 | UNKNOWN |
| annual option volume across all US optionable stocks | contracts | calendar year | not available | UNKNOWN |
| security type (share code) | — | — | not available | UNKNOWN |

## 4. Derived facts

- DF-EA-EFFECTIVE-DATE-ALX
- DF-TRADING-SESSION-OFFSET
- DF-OPT-MID
- DF-OPT-RELATIVE-SPREAD
- DF-OPT-MONEYNESS-KS
- DF-OPT-DTE-CALENDAR
- DF-ALX-BLENDED-IV-POINTS
- DF-ALX-CONCAVE
- DF-STRADDLE-ZERO-DELTA-WEIGHT
- DF-STRADDLE-RETURN

## 5. Fact ownership

| Input | Class |
|---|---|
| chain, S, r, earnings date/time | CANONICAL_FACT |
| CONCAVE, IV points, weights | DERIVED_FACT |
| ±2% blend band; 6/2/2 points; 0.01% start tolerance and 0.005% steps; 0.03 concavity length; 3–13 and 4–13 day windows; 0.98–1.02; 20% spread; $0.125; $5 | STRATEGY_PARAMETER |
| G-ALX-* | STRATEGY_GATE |
| nearest-to-money pair in the shortest 4–13 day expiry | STRUCTURE_SELECTION_RULE |
| close d−1 → close d | PORTFOLIO_OR_LIFECYCLE_RULE |
| **position direction as a function of CONCAVE** | **ambiguous: not source-authored (§9)** |

## 6. Gates

| Gate | Status |
|---|---|
| G-ALX-UNIVERSE-TOP100-VOLUME | always UNKNOWN live |
| G-ALX-COMMON-STOCK-PRICE | |
| G-ALX-OPTION-FILTERS | per option |
| G-ALX-CURVE-EXPIRY | |
| G-ALX-CURVE-POINTS | |
| G-ALX-CONCAVE | direction-determining |
| G-ALX-STRADDLE-PAIR | |

## 7. Verdict truth table

| UNIVERSE | STOCK | CURVE-EXPIRY & POINTS | CONCAVE | PAIR | Verdict |
|---|---|---|---|---|---|
| UNKNOWN (always live) | * | * | * | * | UNKNOWN |
| PASS (research replay only) | FAIL | * | * | * | FAIL |
| PASS | PASS | FAIL | * | * | FAIL (no curve) |
| PASS | PASS | PASS | UNKNOWN | * | UNKNOWN |
| PASS | PASS | PASS | 1 or 0 | FAIL | FAIL |
| PASS | PASS | PASS | 1 or 0 | PASS | **conditional return state known; position UNKNOWN** (§9) |

## 8. Score

NONE. CONCAVE is binary. Regression coefficients are not a score.

## 9. Direction

- **Measured object:** a long zero-delta straddle, held from close d−1 to close d.
- **Source-authored trade:** none. The paper reports conditional returns and interprets them: "investors pay a significant premium to hedge … only when IV curves become concave".
- **Candidate expressions and why neither can be adopted:**

  | Candidate | Basis | Problem |
  |---|---|---|
  | Short the straddle when CONCAVE = 1 | INFERENCE | not stated by the authors |
  | Long the straddle when CONCAVE = 0 | +0.91% mean | significance not reported separately |
  | Long/short differential across firms | — | not source-defined |

  Net level returns for any of these are UNKNOWN.

**direction = UNKNOWN (signal-dependent, not source-authored).**

## 10. Structure selection (P03)

| Field | Rule |
|---|---|
| Expiry | the shortest available expiry with 4 ≤ DTE_cal ≤ 13 at d−1 |
| Pair | "nearest-to-the-money pair of call and put options within the moneyness (K/S) range of 0.98 to 1.02" |
| Weights | w = −(ΔP/P)/(ΔC/C − ΔP/P) on the call return, 1 − w on the put (ALX eq. 5; OptionMetrics deltas; formation prices) → DF-STRADDLE-ZERO-DELTA-WEIGHT |
| Tie rule | none stated. Two strikes equidistant from S → AMBIGUOUS_SELECTION. Whether call and put must share a strike is not explicit; "pair" suggests yes (INFERENCE). |

## 11. DTE

- **Calendar days:** "between three and thirteen calendar days ahead" for the curve.
- **Straddle:** "with expiry between 4 and 13 days" (calendar, DERIVED from the same paragraph).

## 12. Entry timing

- EAD = d, with the after-close rule applied.
- Entry at the close of session(d, −1).

## 13. Lifecycle

- Exit at the close of d.
- No target, stop or roll.

## 14. Sizing

**SIZING = UNKNOWN.** The paper averages across firm-events and uses panel regressions.

## 15. Transaction costs

| Case | Result |
|---|---|
| Mid prices (headline) | as in §1 |
| Ask/bid; 75% or 50% effective spread | levels "substantially lower"; differential intact |

net_result (levels) = UNKNOWN.

## 16. Capital and margin

- **Long straddle:** premium at risk.
- **Short straddle:** margin UNKNOWN (not addressed by the source).

## 17. Liquidity

The sourced option filters include relative spread ≤ 20% of mid, OI > 0 and volume > 0. These are **gates**.

## 18. UNKNOWN / invalid states

| Condition | Outcome |
|---|---|
| universe (same-year volume ranking) | UNKNOWN live (look-ahead) |
| trade direction | not source-authored → UNKNOWN |
| spline fit never admissible, or tolerance cap unstated | UNKNOWN |
| r unavailable | UNKNOWN (density admissibility check) |
| announcement time-of-day unknown | UNKNOWN (EAD shift rule cannot be applied) |
| MATLAB `spaps` numerical equivalence in another implementation | UNKNOWN; the fitted-curve identity is software-specific |
| provider IV and delta vs OptionMetrics | UNKNOWN equivalence |

## 19. Provenance

| Object | Source | Depth | Direct / inferred |
|---|---|---|---|
| sample, filters, 20% spread | ALX §2.1 | full text | direct |
| blending, spline, tolerance loop, RND checks | ALX §2.1, eqs. (1)–(2) | full text | direct |
| CONCAVE definition (1,001-point curve, finite-difference RND) | ALX §2.1–§2.2 | full text | direct |
| straddle construction and weights | ALX §5.2, eqs. (4)–(5) | full text | direct |
| costs | ALX footnote 17 | full text | direct (differential only) |
| direction | — | — | UNKNOWN |

## 20. ASA translation sheet

| Field | Value |
|---|---|
| strategy_id_candidate | `event_vol_alx_concave_ead_straddle` |
| lane | event volatility |
| source_methodology_version | ALX, Review of Finance 29(4), 2025 |
| required_market_capabilities | EARNINGS_CALENDAR_V1 (with time-of-day), OPTION_CHAIN_V1, TRADING_CALENDAR_V1 |
| derived_facts_new | §4 (DF-ALX-CONCAVE is the principal new analytic) |
| gates | §6 |
| direction | UNKNOWN |
| structure_primitive | **P03** with non-unit leg ratios |
| score | NONE |
| sizing | UNKNOWN |
| missing_reusable_primitives | P03 (HARD); X04 (HARD for the RND admissibility check); A07-adjacent spline/RND machinery (**not the same as A07 model-free moments**; the spline-fit derived fact is new); A12 (diagnostic) |
| architecture_review_required | yes: whether a software-specific smoothing-spline fit (MATLAB `spaps` semantics) can be a reusable analytics fact with a pinned formula version |

## 21. Manifest readiness

**Not ready.** Three things are missing:
- a live universe rule;
- a source-authored position direction;
- net level returns.
