# ASA-QS-CC-01-CBOE-BXM — Cboe S&P 500 BuyWrite (BXM)

- **Lane:** 4, index covered call / buy-write
- **Role:** PRIMARY
- **Qualification state:** **READY_WITH_EXPLICIT_UNKNOWNS**
- **Source methodology version:** Cboe Global Indices, *Cboe BuyWrite Indices Methodology* (BXD, BXDE, BXM, BXMN, BXMCAD, BXMD, BXR, BXRD, BXY), retrieved 2026-09-27 ([`CBOE-BUYWRITE-METHODOLOGY-2024`](../../../sources/CBOE-BUYWRITE-METHODOLOGY-2024.yaml)).
  - **Version sensitivity:** the BXM VWAP window was a half hour starting 11:30 a.m. ET from May 21, 2004. It was extended to two hours, 11:30 a.m.–1:30 p.m. ET, on November 19, 2010.
  - This specification pins the **current** window.

## 1. Evidence qualification

| Item | Finding | Source |
|---|---|---|
| Phenomenon | Covered calls collect the equity and volatility risk premiums and embed an uncompensated equity-reversal ("timing") exposure. In a BXM-mimicking backtest (Mar 1996–Dec 2014), short volatility had a Sharpe ratio of about 1.0 but carried under 10% of the risk; equity timing carried about 25% of the risk with little return. | ISRAELOV-NIELSEN-2015-FAJ, full text |
| Exact-strategy evidence | 1986-06 to 2018-12: BXM 8.50%, SD 10.6%, Sharpe 0.51, max drawdown −35.8%, beta 0.55, skew −1.56 (S&P 500: 9.80%, 14.9%, 0.45, −50.9%) | WILSHIRE-2019-CBOE Exhibit 8, full text (prepared for Cboe) |
| Independent replication | Israelov-Nielsen replicate the BXM methodology and decompose it. The covered call Sharpe ratio is 0.37 over their sample; a risk-managed variant reaches 0.52. Israelov-Klein-Tummala (J. Risk 2018) find the same three-component attribution consistent across 11 global indexes, with equity timing "statistically insignificant in all eleven". | ISRAELOV-NIELSEN-2015-FAJ; ISRAELOV-KLEIN-TUMMALA-2018, full text |
| Contradictory | The risk decomposition argues the naive BXM carries uncompensated risk. This is contradictory to *optimality*, not to the existence of the premium. | as above |
| Post-publication | Whaley (2002) introduced BXM; Wilshire's 2010–Q3 2018 bull-market sub-period shows option-writing Sharpe below the S&P 500 | WHALEY-2002 (bibliographic), WILSHIRE-2019-CBOE |
| Gross vs net | index gross; transaction costs and taxes excluded; net UNKNOWN | WILSHIRE-2019-CBOE disclaimer |
| Tail | max drawdown −35.8%; negative skew; kurtosis 6.40 | WILSHIRE-2019-CBOE |
| Evidence confidence | MEDIUM | INFERENCE |

## 2. Universe

U_t = { listed SPX calls with the next monthly (AM-settled) expiration on roll date t } ∪ { S&P 500 index position }.

- The underlying position is the S&P 500 index, a total-return position with dividends (Div_t, index points, on ex-dates).
- This is not SPY. **No SPX result transfers to SPY.**

## 3. Canonical facts

| Fact | Unit | Observation | ASA status | Missing |
|---|---|---|---|---|
| spx_value(t) | index points | last before 11:00 a.m. ET (strike); close (marks) | X01 INDEX quote | UNKNOWN |
| option chain (SPX calls) | — | roll date | OPTION_CHAIN_V1 + X01 | UNKNOWN |
| call bid/ask, last before 4:00 p.m. ET | USD | daily | OPTION_CHAIN_V1 | UNKNOWN |
| call trades 11:30 a.m.–1:30 p.m. ET (OPRA; late, cancelled and spread trades excluded) | USD | roll date | **X05 OPTION_TRADE_TAPE** | fallback only for the no-trade case (last bid before end of window) |
| S_VWAV (volume-weighted index value at the same times and weights as the call VWAP) | index points | roll date | **not available** (needs trade prints + intraday index) | UNKNOWN |
| soq(t) | index points | roll date | not available (X01) | UNKNOWN |
| index dividends Div_t | index points | ex-date | **not available** (index-level dividend points) | UNKNOWN |

## 4. Derived facts

- `DF-THIRD-FRIDAY-ROLL-DATE`
- `DF-OPT-MID`
- `DF-CBOE-BUYWRITE-DAILY-RETURN` (return accounting, outcome only)

## 5. Fact ownership

| Input | Class |
|---|---|
| index values, quotes, trades, SOQ, dividends | CANONICAL_FACT |
| roll date, mid, daily return | DERIVED_FACT |
| 11:00 a.m. reference time; VWAP window 11:30–13:30 ET | STRATEGY_PARAMETER |
| G-CBOE-MONTHLY-ROLL-DATE, G-CBOE-SPX-REF-BEFORE-1100, G-BXM-STRIKE-EXISTS | STRATEGY_GATE |
| strike = min{K ≥ S_ref}; next-month expiry | STRUCTURE_SELECTION_RULE |
| equal notional (1:1 index vs short call); hold to maturity; monthly roll | PORTFOLIO_OR_LIFECYCLE_RULE |

## 6. Gates

| Gate | PASS | FAIL | UNKNOWN |
|---|---|---|---|
| G-CBOE-MONTHLY-ROLL-DATE | roll today | hold | calendar missing |
| G-CBOE-SPX-REF-BEFORE-1100 | S_ref observed | — | missing or late |
| G-BXM-STRIKE-EXISTS | a strike ≥ S_ref exists | — (no sourced fallback) | chain or X01 missing |

## 7. Verdict truth table

| ROLL | REF | STRIKE | Verdict |
|---|---|---|---|
| FAIL | * | * | NO_ACTION (hold) |
| UNKNOWN | * | * | UNKNOWN |
| PASS | UNKNOWN | * | UNKNOWN |
| PASS | PASS | UNKNOWN | UNKNOWN |
| PASS | PASS | PASS | PASS: sell the selected call against the held index |

## 8. Score

NONE.

## 9. Direction

| Dimension | Direction |
|---|---|
| delta | positive (index 1.0 minus an ATM call of about 0.5 at inception; Wilshire beta 0.55) |
| volatility | negative |
| theta | positive |
| skew | short upside convexity (upside capped at K) |
| term | none |
| event | none |

The "equity timing" exposure described by Israelov-Nielsen arises because the call delta changes after entry and is not rebalanced.

## 10. Structure selection (P09 stock/index + option overlay)

| Leg | Rule |
|---|---|
| Long leg | S&P 500 index position, notional = 1 index unit |
| Short leg | 1 SPX call per index unit (equal notional: the short call "is covered by the long underlying") |
| Strike | K* = min{ K(c) : K(c) ≥ S_ref }, the "closest strike price at or above" the last S&P 500 value before 11:00 a.m. ET. Unique by construction. |
| Expiration | the call "expiring in the next month" |

## 11. DTE

Identified by calendar (next monthly expiration). It is not a DTE target.

## 12. Entry timing

- Roll date (§6).
- The strike is fixed from S_ref before 11:00 ET.
- The call is deemed sold at the VWAP from 11:30 a.m. to 1:30 p.m. ET, or at the last bid before 1:30 p.m. if there are no trades.

## 13. Lifecycle

- Hold the call to maturity. It settles at max(0, SOQ − K_old).
- On the same day, roll into the new call.
- No early exercise handling, profit target, stop or ex-dividend rule is defined; the European, cash-settled SPX makes assignment risk inapplicable.
- Daily return accounting follows `DF-CBOE-BUYWRITE-DAILY-RETURN`: non-roll days use the close-to-close formula; roll days use (1 + Ra)(1 + Rb)(1 + Rc).

## 14. Sizing

- One call per index unit (equal notional).
- The capital allocated to the strategy determines index units; that allocation is an account input.
- **Portfolio percentage / volatility scaling: not part of the rule.**

## 15. Transaction costs

VWAP entry and SOQ settlement. Commissions, taxes and index-replication costs are excluded. gross = index; net = UNKNOWN.

## 16. Capital and margin

The long index position covers the short call, so there is no additional margin in the index definition. capital_required = index notional − premium received (the denominator S_{t−1} − C_{t−1} in the return formula). Maximum loss equals that of the index less the premium.

## 17. Liquidity

No sourced gates. A12 is used for diagnostics only.

## 18. UNKNOWN / invalid states

| Condition | Outcome |
|---|---|
| calendar, reference, chain or X01 missing | UNKNOWN |
| trades exist but ASA cannot observe prints | entry price UNKNOWN; proposal selection unaffected |
| no trades in the window | sourced: last bid |
| SOQ, index dividend points or S_VWAV unavailable | outcome return UNKNOWN |

## 19. Provenance

| Object | Source | Depth | Direct / inferred |
|---|---|---|---|
| roll date, strike, VWAP window and history | CBOE-BUYWRITE-METHODOLOGY-2024 | full text | direct |
| equal notional | same, §2.2 | full text | direct |
| return formulas | same, §3.1 | full text | direct |
| performance | WILSHIRE-2019-CBOE | full text | direct (gross) |
| decomposition | ISRAELOV-NIELSEN-2015-FAJ, ISRAELOV-KLEIN-TUMMALA-2018 | full text | direct |

## 20. ASA translation sheet

| Field | Value |
|---|---|
| strategy_id_candidate | `index_buywrite_cboe_bxm` |
| lane | covered call |
| source_methodology_version | Cboe BuyWrite Indices Methodology (retrieved 2026-09-27; VWAP window from 2010-11-19) |
| required_market_capabilities | REAL_TIME_QUOTE_V1 (SPX), OPTION_CHAIN_V1, TRADING_CALENDAR_V1 |
| derived_facts_new | DF-THIRD-FRIDAY-ROLL-DATE, DF-OPT-MID, DF-CBOE-BUYWRITE-DAILY-RETURN |
| strategy_parameters | 11:00 a.m. reference; VWAP window |
| gates | §6 |
| direction | §9 |
| structure_primitive | **P09** overlay (index + short call) |
| structure_selection_rules | §10 |
| score | NONE |
| verdict_truth_table | §7 |
| lifecycle | §13 |
| sizing | §14 |
| cost_model | §15 |
| capital_model | §16 |
| unknown_states | §18 |
| current_ASA_reuse | chain, calendar, verdict classifier |
| missing_reusable_primitives | X01 (HARD), P09 (HARD; semantics ARCHITECT_REVIEW_REQUIRED), X05 (outcome), X07 INDEX_DIVIDEND_POINTS (outcome) |
| architecture_review_required | P09 must represent a long **index** leg, a non-tradable index identity (X01). Tracking-price gap as for PUT. |

## 21. Manifest readiness

The signal, structure, lifecycle and sizing rules are complete, so a manifest can be authored without a new financial-policy decision. The explicit unknowns are non-signal:
- trade prints for entry valuation;
- SOQ;
- index dividend points;
- net-of-cost evidence.

**Architect note (not a research gap):** P09 has to hold the "long S&P 500 index" leg. How ASA represents a non-tradable index as the covered leg (index identity via X01) is architectural. The source defines the leg as the index itself. Any ETF or futures proxy would be a different strategy and would require its own evidence.

## Closeout disposition (2026-09-27)

SELECTED (lane-4 target) with **architecture status ARCHITECT_REVIEW_REQUIRED** for its P09 expression (PR #501 Architect review item 7). The index must not be represented as a tradable stock, and SPY or futures must not be substituted. Research state: READY_WITH_EXPLICIT_UNKNOWNS. X02a removed; X05 and X07 added.
