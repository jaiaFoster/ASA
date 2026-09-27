# ASA-QS-XR-01-ZHAN-NEG-LNPRICE-DN-CALL — delta-neutral call writing sorted on −ln(stock price)

- **Lane:** 6, cross-sectional option returns
- **Role:** PRIMARY
- **Qualification state:** **DEEP_RESEARCH_REQUIRED**
- **Source methodology version:** Zhan, Han, Cao and Tong, "Option Return Predictability", *Review of Financial Studies* 35(3), 2022, 1394–1442. Author-accepted post-print, University of Toronto TSpace, full text ([`ZHAN-ET-AL-2022`](../../../sources/ZHAN-ET-AL-2022.yaml)).

## Why this characteristic among the ten

Zhan et al. test ten characteristics. −Ln(PRICE) is selected here because:
- It is the **only one computable from ASA-type canonical market data alone** (a month-end close). The other nine need Compustat, I/B/E/S or 60-month cash-flow histories (see LANE-06).
- It has the **largest and most cost-robust** spread in the paper's Table 6.

Selecting it does **not** combine rules across papers: it is one of the source's own ten strategies.

## 1. Evidence qualification

| Item | Finding | Source |
|---|---|---|
| Sample | OptionMetrics, CRSP, January 1996 – April 2016; about 763 optionable stocks per month | Zhan §1, full text |
| Exact-strategy evidence (Table 6, Stock-VW decile 10 − decile 1 spread, % per month) | **Full sample** by effective/quoted spread ratio:<br>• 0% (mid): 4.67 (t 25.17)<br>• 25%: 3.72<br>• 50%: 2.80<br>• 75%: 1.90<br>• 100%: **1.01 (t 5.48)**<br>• 50% + margin: 2.68 (t 15.71)<br>**OPRA subsample 2003-05 to 2016-04:**<br>• mid 3.96<br>• actual effective spread 2.78 (t 12.86)<br>• effective + margin 2.70 (t 12.21) | Zhan Table 6 |
| Gross, other weights | Table 3 reports EW and Option-VW decile spreads for each characteristic. Costs are reported only for Stock-VW. | Zhan Table 3 |
| Subperiods | Profits "remain significant and just as strong" in 2006–2016 vs 1996–2005; significant in January and non-January months, high and low sentiment, and high and low funding liquidity | Zhan §2.2 |
| Factor spanning | Profits "can be explained by two option factors" (option IVOL and option illiquidity factors, Table 10) while equity risk factors have no explanatory power. This is recorded faithfully: the alpha is largely **spanned by option factors**. | Zhan abstract and §4 |
| Independent replication | none recovered | — |
| Post-publication (after April 2016 / 2022) | not recovered | — |
| Tail | Nine of ten strategies have slightly negative skew; the price-sorted strategy is **slightly positively skewed**; excess kurtosis positive | Zhan §2.2 |
| Evidence confidence | MEDIUM: peer-reviewed, net-of-cost with actual effective spreads, single study | INFERENCE |

## 2. Universe

U_t = { common stocks i (CRSP share code 10 or 11) with closing price P_i,t ≥ $5 at formation month end t, with an OptionMetrics call–put pair passing all option gates }.

- **Option pair:** at month end t, the call and put "closest to being at-the-money" with "the shortest maturity among those with more than one month to expiration".
- **Maturity:** in the sample, maturities were 47–52 calendar days (average 50).
- **Look-ahead:** the dividend-during-life exclusion is ex post (§18).

## 3. Canonical facts

| Fact | Unit | Observation | ASA status | Missing |
|---|---|---|---|---|
| close P_i,t | USD | last trading day of month t | HISTORICAL_BARS_V1 | UNKNOWN |
| security type (common stock) | — | t | **not available** | UNKNOWN |
| market capitalization (for Stock-VW weights) | USD | t | **not available** (shares outstanding) | UNKNOWN |
| option chain (bid, ask, volume, OI, strike, expiration) | — | close of t, and close of t+1 | OPTION_CHAIN_V1 | UNKNOWN |
| option delta | — | t | provider (ORATS via Tradier). Source: "Black-Scholes call option delta" from OptionMetrics. Equivalence UNKNOWN. | UNKNOWN |
| dividends during option life | USD, dates | ex post | CORPORATE_ACTIONS_V1 (declared only) | UNKNOWN |
| risk-free rate / LIBOR matched to option maturity | decimal | t | X04 | UNKNOWN |

## 4. Derived facts

- DF-NEG-LN-PRICE
- DF-XS-QUANTILE-ASSIGNMENT
- DF-OPT-MID
- DF-OPT-DTE-CALENDAR
- DF-DN-CALL-WRITE-RETURN
- DF-CBOE-NAKED-MARGIN
- DF-OPT-EFFECTIVE-PRICE (cost evaluation)

## 5. Fact ownership

| Input | Class |
|---|---|
| close, chain, delta, market cap, dividends, rates | CANONICAL_FACT |
| −ln P, decile, DN return, margin | DERIVED_FACT |
| $5; mid ≥ $1/8; moneyness [0.8, 1.2]; 10 deciles | STRATEGY_PARAMETER |
| G-ZHAN-* | STRATEGY_GATE |
| ATM, shortest maturity > 1 month; call hedged with Δ shares | STRUCTURE_SELECTION_RULE |
| monthly formation; one-month hold; no hedge rebalancing; decile 10 − decile 1; Stock-VW | PORTFOLIO_OR_LIFECYCLE_RULE |

## 6. Gates

| Gate | Status |
|---|---|
| G-ZHAN-COMMON-STOCK | |
| G-ZHAN-PRICE-MIN | |
| G-ZHAN-NO-DIVIDEND-DURING-LIFE | research blocker |
| G-ZHAN-OPTION-QUOTE | |
| G-ZHAN-NO-ARBITRAGE | |
| G-ZHAN-MONEYNESS | |
| G-ZHAN-MODAL-MATURITY | |
| G-ZHAN-CALL-AND-PUT | |

## 7. Verdict truth table (per stock-month)

| stock gates | option gates | NO-DIVIDEND | decile | Verdict |
|---|---|---|---|---|
| any FAIL | * | * | * | EXCLUDED |
| any UNKNOWN | * | * | * | UNKNOWN |
| PASS | any FAIL | * | * | EXCLUDED |
| PASS | PASS | UNKNOWN (live) | * | UNKNOWN |
| PASS | PASS | PASS | 10 | SHORT delta-hedged call (write the call, long Δ shares) |
| PASS | PASS | PASS | 1 | LONG delta-hedged call (buy the call, short Δ shares) |
| PASS | PASS | PASS | 2–9 | NO_POSITION |
| PASS | PASS | PASS | boundary/tie UNKNOWN (DF-XS-QUANTILE-ASSIGNMENT) | UNKNOWN |

Decile 10 is the highest −ln P, i.e. the lowest-priced stocks.

## 8. Score

The sort variable is x = −ln P. There is no composite score. **score: NONE** beyond the rank.

## 9. Direction

| Dimension | Direction |
|---|---|
| delta | neutral at formation (Δ-share hedge); drifts, not rebalanced |
| volatility | short volatility on low-price stocks, long volatility on high-price stocks (relative value) |
| theta | net positive expected (INFERENCE) |
| stock exposure after entry | residual delta from the unrebalanced hedge |

## 10. Structure selection (P10 delta-hedged option, within a P12 cross-sectional portfolio)

| Field | Rule |
|---|---|
| Call | the ATM call of the selected pair: closest to at-the-money; shortest maturity with more than one month to expiration; modal maturity across stocks |
| Hedge | Δ_t shares of the underlying, Δ_t = Black-Scholes call delta at t (sign: long Δ shares against a written call) |
| Short book | decile 10: write one call and buy Δ shares (Zhan: "we sell one contract of call option against a long position of Δ shares") |
| Long book | decile 1: buy the call and short Δ shares (Cao-Han describe the same long delta-hedged construction) |
| "Closest to ATM" tie | equidistant strikes are not addressed → AMBIGUOUS_SELECTION |

## 11. DTE

Calendar days. The rule is the shortest expiration with DTE > "one month". Whether "one month" means 30 calendar days or the next monthly cycle is UNKNOWN. In practice the sample's maturities were 47–52 days.

## 12. Entry timing

- Formation at the close of the last trading day of each month.
- Entry at that close, at mid, or at mid ± k·half-spread for cost scenarios.

## 13. Lifecycle

- Hold to the end of the next month, "without rebalancing the delta-hedges".
- Close out the option and stock at the next month-end close; the option is not held to expiry. The paper also reports a hold-to-maturity variant with larger spreads; that is a different rule.
- Re-form monthly.
- No stops or targets.

## 14. Sizing

**Portfolio return weights** within a decile are **Stock-VW**, proportional to market capitalization at formation (the paper's conservative headline). EW and Option-VW variants are reported gross only.

Per-position capital:
- **Short book:** H_t = Δ_t·S_t − C_t per written call.
- **Long book:** the capital convention is not stated (UNKNOWN).

Absolute allocation to the strategy: an account input. Contract counts follow from w_i / H_t per unit capital (DERIVED for the short book only).

## 15. Transaction costs

| Case | Treatment |
|---|---|
| Option spread, full sample | effective/quoted ratios 0.25, 0.50, 0.75, 1.00 via DF-OPT-EFFECTIVE-PRICE on entry and exit |
| Option spread, OPRA subsample | actual effective spreads (on average 55% of quoted) |
| Stock hedge trading costs | **not stated (UNKNOWN)** |
| Borrow cost of the short-stock hedge in decile 1 | **not modelled (UNKNOWN)** |
| Commissions | not modelled |

## 16. Capital and margin

- **Margin:** the CBOE initial margin for a naked short call (DF-CBOE-NAKED-MARGIN). The long stock is conservatively **not** used to offset it.
- **Financing:** the margin is financed at option-maturity-matched LIBOR over one month (eq. 2).
- **Maximum loss:** not stated.

## 17. Liquidity

The sourced gates are: volume > 0, bid > 0, bid < ask, mid ≥ $1/8. No spread-width gate is sourced.

## 18. UNKNOWN / invalid states

| Condition | Outcome |
|---|---|
| dividend-during-life filter (ex post) | **RESEARCH BLOCKER** for exact-rule fidelity → UNKNOWN |
| moneyness ratio definition (K/S vs S/K) | UNKNOWN for options near the 0.8 and 1.2 edges |
| no-arbitrage conditions beyond the example | UNKNOWN |
| decile breakpoints, ties | UNKNOWN |
| market cap unavailable (Stock-VW) | UNKNOWN weights; EW has **no** cost evidence |
| common-stock identification unavailable | UNKNOWN universe |
| provider vs Black-Scholes/OptionMetrics delta | UNKNOWN equivalence (the hedge ratio is economic) |
| long-book capital and stock-borrow cost | UNKNOWN |

## 19. Provenance

| Object | Source | Depth | Direct / inferred |
|---|---|---|---|
| universe, pair selection, filters | Zhan §1.1 and footnotes 8–10 | full text | direct |
| DN return eq. (1), margin eq. (2) | Zhan §1.2, §2.4 | full text | direct |
| characteristic definition | Zhan §1.3 item 7 | full text | direct |
| sort, weights, hold | Zhan §2.1; Table 3 notes | full text | direct |
| costs | Zhan §2.4; Table 6 | full text | direct |
| decile mechanics | — | — | UNKNOWN |

## 20. ASA translation sheet

| Field | Value |
|---|---|
| strategy_id_candidate | `xs_option_zhan_neg_lnprice_dn_call` |
| lane | cross-sectional option returns |
| source_methodology_version | RFS 2022 accepted manuscript |
| required_market_capabilities | HISTORICAL_BARS_V1, OPTION_CHAIN_V1 (all optionable US stocks monthly), CORPORATE_ACTIONS_V1, TRADING_CALENDAR_V1 |
| derived_facts_existing | latest_price (partial), days_to_expiration, cross-sectional ranking (partial) |
| derived_facts_new | §4 |
| gates | §6 |
| direction | §9 |
| structure_primitive | **P10** delta-hedged option (one call + Δ shares) inside a **P12** cross-sectional long/short portfolio |
| score | NONE (rank only) |
| sizing | Stock-VW (market cap is a missing canonical fact) |
| missing_reusable_primitives | P10 (HARD), P12 (HARD), A15 (margin), X04 (LIBOR/rates), A12 (diagnostic); canonical gaps: security type, shares outstanding |
| architecture_review_required | P12 cross-sectional portfolio semantics (a decile long/short book over about 700 names) |

## 21. Manifest readiness

**Not ready.** An implementer would face three open decisions:
- how to treat the ex-post dividend filter;
- the long-book capital convention and borrow;
- weights when market cap is unavailable.

The core signal and structure are otherwise precisely sourced, and the net-of-cost evidence is the strongest in the lane.

Required research actions:
1. Check the RFS published appendix or replication package for the live dividend treatment and moneyness ratio.
2. Recover any post-2016 replication.
