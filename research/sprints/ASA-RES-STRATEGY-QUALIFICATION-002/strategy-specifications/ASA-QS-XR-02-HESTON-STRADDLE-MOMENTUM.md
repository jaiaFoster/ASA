# ASA-QS-XR-02-HESTON-STRADDLE-MOMENTUM — option (straddle) momentum, lags 2–12

- **Lane:** 6, cross-sectional option returns
- **Role:** PRIMARY (second specification)
- **Qualification state:** **DEEP_RESEARCH_REQUIRED**
- **Source methodology version:** Heston, Jones, Khorram, Li and Mo, "Option Momentum", *Journal of Finance* 78(6), 2023. Full text: working-paper version ([`HESTON-ET-AL-2023`](../../../sources/HESTON-ET-AL-2023.yaml)).
  - The JF typeset version was not accessed.
  - Table and page references are to the working-paper text.

## Why this is materially different from ASA-QS-XR-01

| Dimension | XR-02 (this spec) | XR-01 (Zhan) |
|---|---|---|
| Signal family | the option's own past returns (time-series history) | a stock characteristic |
| Structure primitive | P03 zero-delta straddle | P10 delta-hedged call |
| Lifecycle | hold to expiry (expiration-to-expiration) | month-end to month-end |
| Data dependence | a 12-month historical option-price panel (A08) | none beyond the month-end close |

## 1. Evidence qualification

| Item | Finding | Source |
|---|---|---|
| Sample | OptionMetrics and CRSP, January 1996 – June 2019; regular monthly expirations | Heston §1, full text |
| Gross (Table 13 Panel B, zero exercise costs) | Main quintile strategy 0.0622 per month (t 7.97); decile 0.0729 | Heston Table 13 |
| Net by cost assumption (Panel B, zero exercise costs, quintile / decile / low-cost decile) | algo 0.0362 / 0.0465 / 0.0599<br>adjusted −0.0040 / 0.0056 / 0.0408 (t 2.74)<br>effective −0.0356 / −0.0265 / 0.0260 (t 1.75)<br>quoted −0.0678 / −0.0592 / 0.0112 (t 0.75) | Heston Table 13 |
| Net with exercise costs, low-cost decile | effective 0.0088 (t 0.58); quoted −0.0061 | Heston Table 13 |
| Cost fractions | algo, adjusted and effective = 20.3%, 51.6% and 75.8% of the quoted half-spread (following Muravyev-Pearson 2020) | Heston §6 |
| Margin | SPAN margin ratio slightly above 2; margin-adjusted returns (no transaction costs) 0.0294 (quintile) and 0.0347 (low-cost decile) | Heston §6 |
| Authors' conclusion | "main momentum and reversal strategies are not profitable if one assumes that the entire quoted spread must be paid"; cost-optimized portfolios "quite profitable under a number of reasonable assumptions" | Heston §6 |
| Replication / post-publication | not recovered. HESTON-ET-AL-2026 (seasonal momentum, bibliographic only) is related, not a replication. | — |
| Evidence confidence | MEDIUM gross; LOW net at non-algorithmic execution | INFERENCE |

## 2. Universe

U_t = { common equity i with a zero-delta straddle formable on monthly expiration day t that passes the holding-period gates, and with 11 non-missing formation straddle returns }.

## 3. Canonical facts

| Fact | Unit | Observation | ASA status | Missing |
|---|---|---|---|---|
| option chain: bid, ask, OI, delta | — | each monthly expiration day | OPTION_CHAIN_V1. Delta source: OptionMetrics binomial. Provider equivalence UNKNOWN. | UNKNOWN |
| historical option prices, 12 months back | — | past expirations | **A08** (not available) | UNKNOWN |
| split-adjusted stock price at expiration | USD | expiration | HISTORICAL_BARS_V1, CORPORATE_ACTIONS_V1 | UNKNOWN |
| expiration calendar (pre-2015 Saturday → prior trading day) | date | — | TRADING_CALENDAR_V1 | UNKNOWN |
| common-equity identification | — | — | not available | UNKNOWN |

## 4. Derived facts

- DF-OPT-MID
- DF-STRADDLE-ZERO-DELTA-WEIGHT (weights ∝ (−Δp·C, Δc·P), with C and P at mid)
- DF-OPT-WEIGHTED-SPREAD
- DF-OPT-HOLDING-RETURN
- DF-STRADDLE-RETURN
- DF-STRADDLE-MOMENTUM-FORMATION
- DF-XS-QUANTILE-ASSIGNMENT
- DF-HESTON-SPAN-MARGIN

## 5. Fact ownership

| Input | Class |
|---|---|
| chain, deltas, historical option prices, stock price, calendar | CANONICAL_FACT |
| weights, straddle returns, MOM, quantile, margin | DERIVED_FACT |
| delta 0.5 target; [0.25, 0.75]; 50% spread; lags 2–12; quintile or decile; 10% option-spread cut (cost-optimized variant) | STRATEGY_PARAMETER |
| G-HES-* | STRATEGY_GATE |
| pair choice, replacement rule | STRUCTURE_SELECTION_RULE |
| hold to expiry; monthly re-formation; equal weight; long high / short low | PORTFOLIO_OR_LIFECYCLE_RULE |

## 6. Gates

| Gate | Status |
|---|---|
| G-HES-FORMATION-DATE | |
| G-HES-CALL-DELTA-BAND | |
| G-HES-SPREAD-MAX | aggregation UNKNOWN |
| G-HES-OI-HOLDING | |
| G-HES-FORMATION-COMPLETE | |
| Cost-optimized variant only: "avoid options with bid-ask spreads above 10% of option midpoints" | per-option vs per-straddle application UNKNOWN; not registered as a separate gate until resolved |

## 7. Verdict truth table (per stock-month)

| FORMATION-DATE | pair gates (delta band, spread, OI) | FORMATION-COMPLETE | quantile | Verdict |
|---|---|---|---|---|
| FAIL | * | * | * | hold |
| PASS | FAIL after replacement attempts | * | * | EXCLUDED |
| PASS | UNKNOWN | * | * | UNKNOWN |
| PASS | PASS | FAIL | * | EXCLUDED |
| PASS | PASS | UNKNOWN (no A08) | * | UNKNOWN |
| PASS | PASS | PASS | top | LONG straddle |
| PASS | PASS | PASS | bottom | SHORT straddle |
| PASS | PASS | PASS | middle | NO_POSITION |
| PASS | PASS | PASS | boundary/tie | UNKNOWN |

## 8. Score

NONE (rank of MOM).

## 9. Direction

| Dimension | Direction |
|---|---|
| delta | neutral at formation (zero-delta straddles) |
| volatility | long volatility on winners, short on losers (relative value) |
| theta | relative-value |
| after entry | no hedge; delta drifts |

## 10. Structure selection (P03 inside P12)

- **Holding-period pair.** On expiration day t, among call/put pairs with the same strike expiring in the following month, choose the pair whose call delta is closest to 0.5 **and** both legs have OI > 0 on that day.
  - Discard the pair if its call delta < 0.25 or > 0.75.
  - If the weighted spread exceeds 50% of the midpoint, "attempt to replace the straddle with another that is further from at-the-money, as long as the call delta is within the range".
  - **The order of replacement candidates is not stated** (for example next-closest |Δc − 0.5|, or next strike above vs below) → AMBIGUOUS_SELECTION.
- **Formation-period pair.** The same rule without the OI requirement. This pair supplies the historical returns.
- **Weights:** DF-STRADDLE-ZERO-DELTA-WEIGHT, using mid prices and OptionMetrics deltas.
- **Tie (|Δc − 0.5| equal for two strikes):** not stated → AMBIGUOUS_SELECTION.

## 11. DTE

Identified by the expiration calendar: options expiring in the following monthly cycle. It is not a DTE target.

## 12. Entry timing

On each monthly expiration day (the prior trading day for pre-2015 Saturday expirations), at the initial price equal to the bid-ask midpoint.

## 13. Lifecycle

- Hold to the next monthly expiration.
- Returns use the split-adjusted stock price at expiration; early exercise is ignored.
- Re-form monthly.
- No stops or targets.

## 14. Sizing

- Equal-weighted portfolios, top minus bottom quantile.
- **Main variant:** quintiles.
- **Cost-optimized variant:** deciles plus exclusion of options with spread > 10% of mid.
- Absolute capital is an account input. Margin per SPAN for the short book.

## 15. Transaction costs

- One-way costs are a fixed fraction of the quoted half-spread: 0, 20.3%, 51.6%, 75.8% or 100%.
- Optionally, a stock-liquidation cost of half the closing stock spread for exercised ITM options.

## 16. Capital and margin

SPAN (DF-HESTON-SPAN-MARGIN):
- underlying ±15% in 3% steps;
- IV ±10% of level;
- Black-Scholes revaluation;
- margin = largest scenario loss.

The margin-adjusted return is the unadjusted return × V0/M0.

## 17. Liquidity

The sourced gates are: OI > 0 in the holding period; weighted spread ≤ 50%; and, in the cost-optimized variant, the option spread ≤ 10%.

## 18. UNKNOWN / invalid states

| Condition | Outcome |
|---|---|
| no 12-month option history (A08) | UNKNOWN; cannot form the signal |
| replacement candidate ordering | AMBIGUOUS_SELECTION |
| weighted-spread aggregation | UNKNOWN |
| 10% spread cut: per option or per straddle | UNKNOWN |
| decile/quintile boundary rules | UNKNOWN |
| provider delta vs OptionMetrics binomial | UNKNOWN equivalence |
| net profitability at non-algorithmic execution | evidence insignificant (t 1.75 effective, 0.75 quoted) |

## 19. Provenance

| Object | Source | Depth | Direct / inferred |
|---|---|---|---|
| sample, OI policy, pair selection, 0.25/0.75, weights, 50% spread, replacement, hold-to-expiry pricing | Heston §1 | full text | direct |
| formation completeness (no missing for straddles; ⅔ rule only for VIX portfolios) | Heston §1 | full text | direct |
| quintiles, EW, lags 2–12 | Heston §2 | full text | direct |
| costs, margin | Heston §6, Table 13 | full text | direct |
| replacement order | — | — | UNKNOWN |

## 20. ASA translation sheet

| Field | Value |
|---|---|
| strategy_id_candidate | `xs_option_heston_straddle_momentum` |
| source_methodology_version | Option Momentum, JF 2023 (working-paper text) |
| required_market_capabilities | OPTION_CHAIN_V1 (all optionable stocks), HISTORICAL_BARS_V1, CORPORATE_ACTIONS_V1, TRADING_CALENDAR_V1 |
| structure_primitive | **P03** (non-unit ratios) inside **P12** |
| missing_reusable_primitives | A08 (HARD: 12-month option panel), A17 (option-return history, HARD on A08), P03, P12, A15 (SPAN), A12 |
| architecture_review_required | P12 semantics; A08/A17 point-in-time panel semantics |

## 21. Manifest readiness

**Not ready.** Open items:
- replacement ordering and spread aggregation are undefined;
- net evidence at conventional execution costs is not significant;
- the signal requires a historical option panel that ASA does not have.
