# ASA-QS-PW-01-CBOE-PUT — Cboe S&P 500 PutWrite (PUT) collateralized monthly ATM put writing

- **Lane:** 2, index put writing
- **Role:** PRIMARY
- **Qualification state:** **READY_WITH_EXPLICIT_UNKNOWNS**
- **Source methodology version:** Cboe Global Indices, *Cboe S&P 500 PutWrite Indices Methodology* (PUT, PUTCAD, PWT), as retrieved 2026-09-27 ([`CBOE-PUTWRITE-METHODOLOGY-2024`](../../../sources/CBOE-PUTWRITE-METHODOLOGY-2024.yaml)).
  - Base date June 1988 (history back-filled). Index launched 2007.
  - Earlier methodology versions were not recovered. The rules below are the current version only.

Every rule below is transcribed from the methodology unless it is labelled DERIVED or UNKNOWN. Formulas are referenced by their IDs in [`../derived-fact-registry.yaml`](../derived-fact-registry.yaml); gates by their IDs in [`../gate-registry.yaml`](../gate-registry.yaml).

## 1. Evidence qualification

| Item | Finding | Source / depth |
|---|---|---|
| Phenomenon evidence | Index-option implied volatility exceeds subsequently realized volatility. VIX averaged 19.3% against 15.1% realized over 1990–2018. | BONDARENKO-2019-CBOE C5, full text |
| Exact-strategy evidence | Index-level history of this exact rule set, 1986-06 to 2018-12:<br>• compound return 9.54%, SD 9.95%, Sharpe 0.65<br>• S&P 500: 9.80%, 14.93%, Sharpe 0.49 | BONDARENKO-2019-CBOE C1, full text |
| Independent evaluation | Wilshire 2019, prepared for Cboe, 1986-06 to 2018-12:<br>• PUT 9.54%, SD 9.9%, Sharpe 0.64, max drawdown −35.5%, beta 0.47, skew −2.10, kurtosis 9.72<br>• S&P 500 max drawdown −50.9%<br>Ennis Knupp 2008: PUT 10.32% annualized, SD 9.91%, **before fees** | WILSHIRE-2019-CBOE and ENNISKNUPP-2008-PUT, full text. **Both were commissioned or published with Cboe**, so they are not fully independent. |
| Failed replication | None recovered | — |
| Contradictory / post-publication | Post-launch 2006–2018: PUT 5.97% (Sharpe 0.50) vs S&P 500 7.59% (Sharpe 0.51). There was no risk-adjusted advantage after launch. | BONDARENKO-2019-CBOE C4 |
| Gross vs net | All figures are **index figures**. Wilshire states that the indexes "do not take into account significant factors such as transaction costs and taxes". Ennis Knupp reports returns before fees. Entry at trade VWAP is the index's only execution-cost treatment. **Net-of-cost performance of an implemented PUT replication: UNKNOWN.** | WILSHIRE-2019-CBOE, ENNISKNUPP-2008-PUT |
| Tail behavior | Maximum drawdown −32.7% (Jan 2009), longest drawdown 40 months (Bondarenko). Maximum drawdown −35.5% (Wilshire; the drawdown convention differs). Negative skew and high kurtosis. | as above |
| Regime dependence | Underperformed the S&P 500 in the 2010–Q3 2018 bull market on Sharpe ratio. | WILSHIRE-2019-CBOE |
| Specification precision | Complete for strike, roll, settlement, collateral and sizing (§5–§10) | methodology full text |
| Evidence confidence | MEDIUM. The history is long, but it is the sponsor's own back-filled index and there is no net-of-cost replication. | INFERENCE |

## 2. Universe

The strategy trades a single underlying, so there is no cross-section.

U_t = { listed SPX put options on the S&P 500 index, observable on roll date t, with the next-month standard (AM-settled, SOQ) expiration }.

- **Underlying:** the S&P 500 index (not SPY and not a futures proxy). **No SPX result transfers to SPY.**
- **Settlement:** the expiring put settles at the Special Opening Quotation (SOQ) of the S&P 500: payoff max(0, K_old − SOQ).
  - Distinguishing AM-settled standard SPX from PM-settled SPXW on the same Friday requires **X01** (root/settlement identity).

## 3. Canonical facts

| Canonical fact | Meaning | Unit | Observation time | Freshness | ASA status | Missing / invalid |
|---|---|---|---|---|---|---|
| `spx_value(t)` | S&P 500 index level | index points | last value disseminated strictly before 11:00:00 ET on the roll date | must be timestamped < 11:00 ET on that date | REAL_TIME_QUOTE_V1 on an index identity: **X01 + X02a** | UNKNOWN |
| `option_chain(SPX, exp)` | listed SPX puts, strikes, identity | — | roll date, before 11:00 ET and during 11:30–12:00 ET | same session | OPTION_CHAIN_V1; root/settlement identity needs **X01** | UNKNOWN |
| `option_bid/ask(c,t)` | NBBO quotes | USD per index unit | last quote before 4:00 p.m. ET (daily marks) | same session | OPTION_CHAIN_V1 | UNKNOWN |
| `option_trades(c, 11:30–12:00 ET)` | OPRA trade prints, excluding sale-condition codes A–H and f–t | USD, contracts | roll date | same window | **Not available.** No existing capability and no taxonomy entry (see capability-map `GAP-OPTION-TRADE-PRINTS`). | fallback defined by source only for the *no trades* case |
| `soq(t)` | SPX Special Opening Quotation on the expiration date | index points | roll date morning | same day | **not available** (X01 settlement semantics) | UNKNOWN |
| `usbr_4w(t)`, `usbr_13w(t)` | US Treasury 4-week and 13-week bank-discount rates | decimal | per business day | daily | **X04** | UNKNOWN |
| `trading_calendar` | Cboe Options holiday schedule | dates | — | current | TRADING_CALENDAR_V1 (Cboe schedule equivalence not verified) | UNKNOWN |

## 4. Derived facts

- `DF-THIRD-FRIDAY-ROLL-DATE`
- `DF-OPT-MID` (daily marks)
- `DF-CBOE-TBILL-DAILY-ACCRUAL`
- `DF-CBOE-PUT-CONTRACT-COUNT`

There are no strategy-private formulas.

## 5. Fact ownership classification

| Input | Class |
|---|---|
| SPX value before 11:00 ET, chain, quotes, trades, SOQ, T-bill rates, calendar | CANONICAL_FACT |
| roll date, midpoint, T-bill accrual, contract count | DERIVED_FACT |
| reference time 11:00 ET; VWAP window 11:30–12:00 ET; excluded sale-condition codes A–H, f–t; T-bill tenors 28/91 days | STRATEGY_PARAMETER |
| G-CBOE-MONTHLY-ROLL-DATE, G-CBOE-SPX-REF-BEFORE-1100, G-PUT-STRIKE-EXISTS | STRATEGY_GATE |
| strike = max{K listed : K ≤ S_ref}; next-month expiration; put | STRUCTURE_SELECTION_RULE |
| hold to expiration; SOQ settlement; monthly roll; fully collateralized sizing; 1-month and 3-month bill allocation | PORTFOLIO_OR_LIFECYCLE_RULE |

## 6. Gates

| Gate | Predicate | PASS | FAIL | UNKNOWN |
|---|---|---|---|---|
| G-CBOE-MONTHLY-ROLL-DATE | date = third Friday, or the preceding business day if that Friday is a holiday | roll today | hold the existing position (not an error) | calendar missing |
| G-CBOE-SPX-REF-BEFORE-1100 | an SPX value timestamped strictly before 11:00 ET exists | S_ref defined | — | no or late observation |
| G-PUT-STRIKE-EXISTS | ∃ listed next-month SPX put with K ≤ S_ref | strike defined | — (the source has no no-strike rule) | chain or X01 identity missing |

There are no source-defined liquidity, volatility or market-state gates. **None may be added** (see §12).

## 7. Verdict truth table

| ROLL-DATE | SPX-REF | STRIKE-EXISTS | Verdict |
|---|---|---|---|
| FAIL | * | * | NO_ACTION (hold the open put to expiry) |
| UNKNOWN | * | * | UNKNOWN |
| PASS | UNKNOWN | * | UNKNOWN |
| PASS | PASS | UNKNOWN | UNKNOWN |
| PASS | PASS | PASS | PASS: write the selected put |

The strategy is unconditional: on every roll date where all inputs are known, it writes. A FAIL in the table means only "not a roll date".

## 8. Score

**NONE.** The source defines no score.

## 9. Direction

| Dimension | Direction |
|---|---|
| delta | positive (short ATM put; approximately +0.5 per unit at inception) |
| volatility | negative |
| theta | positive |
| skew | negative (short downside) |
| term | none (single expiry) |
| event exposure | none |
| collateral | long Treasury bills |

After entry the position is static. Delta drifts with the index, and there is no hedge.

## 10. Structure selection (primitive P01 single leg)

| Field | Value |
|---|---|
| role | short put |
| long_or_short | short |
| call_or_put | put |
| quantity | N_new from `DF-CBOE-PUT-CONTRACT-COUNT` (§14) |
| expiration relationship | "a new put option expiring in the next month": the next standard monthly SPX expiration after the roll date |
| strike rule | K* = max{ K(c) : c ∈ U_t, K(c) ≤ S_ref }, where S_ref = last S&P 500 value reported before 11:00 a.m. ET |
| delta / moneyness target | none; the rule is strike-based |
| tie rule | not needed: the maximum over strikes ≤ S_ref is unique |

## 11. DTE

DTE is not a selection input. The expiration is identified by calendar identity: the next month's standard AM-settled expiration. The realized holding period runs from roll date to next roll date, which is 28 or 35 calendar days (DERIVED).

## 12. Entry timing

1. **Roll date:** `DF-THIRD-FRIDAY-ROLL-DATE`.
2. **Strike determination:** from S_ref, the last index value before 11:00 a.m. ET.
3. **Sale price:** P_price = VWAP of trades in the selected put between 11:30 a.m. and 12:00 p.m. ET.
   - Trades are taken from Cboe via OPRA, excluding sale-condition codes A–H and f–t.
   - If no trade occurs in the window, the put is deemed sold at the last bid before 12:00 p.m. ET.
4. **Sourced sibling variant:** PWT, the "PutWrite T-W" index in the same methodology document, differs only in using the time-weighted average of the bid over 11:30–12:00 ET. That is a separate index, not a fallback for PUT.

## 13. Exit, roll and lifecycle

| Stage | Rule |
|---|---|
| Initial entry | on a roll date per §12 |
| Holding period | to expiration. The index "require[s] that the put options … be held to maturity". |
| Exit | settlement at the SOQ on the next roll date: payoff max(0, K_old − SOQ) |
| Profit target / stop | none. The source defines none, so none may be added. |
| Roll | on the same roll date, after settlement, write the new put per §10–§12 |
| Re-entry / cooldown | none; continuous monthly rolls |
| Maximum simultaneous positions | one short put series at a time (DERIVED from the roll sequence) |
| Daily mark | P_t = mean of the last bid and ask before 4:00 p.m. ET; Index_t = M_t − N_last·P_t |

## 14. Sizing (sourced)

The position is **fully collateralized**. The T-bill account covers the maximum put liability, so the notional is financed by the account.

- **Third roll dates** (selling a March, June, September or December expiry; the roll is in the preceding month):
  N_new = (Σ_i (1 + r^i)·M^i − N_last·max(0, K_old − SOQ)) / (K_new/(1 + R3) − P_price)
- **Other roll dates:** equation (8), transcribed in full in `DF-CBOE-PUT-CONTRACT-COUNT`.

The account capital M is the only external input. It is the capital assigned to the strategy, not a strategy parameter. N is fractional in the index definition, so rounding N to whole contracts would be an implementation assumption.

## 15. Transaction costs

| Item | Treatment in source |
|---|---|
| Entry | trade VWAP (11:30–12:00 ET), so the realized trade price stands in for a spread cost; last bid if there are no trades |
| Exit | cash settlement at SOQ; no closing trade |
| Commissions, fees, taxes | excluded |
| Slippage, market impact | not modelled |

gross_result = index return. net_result = UNKNOWN (§1).

## 16. Capital and margin

| Item | Value |
|---|---|
| capital_required | M, the T-bill balance ≥ N·K/(1 + R) at inception by construction |
| margin_rule | none; cash-secured, no leverage |
| maximum_loss | N·K_old − premium, if SOQ = 0 (theoretical). The collateral covers it by construction. |
| collateral_rule | 1-month and 3-month bills per §14; interest per `DF-CBOE-TBILL-DAILY-ACCRUAL` |

ASA's current max-loss model must not be substituted for this collateral definition.

## 17. Liquidity

- **Source-defined liquidity gates:** none.
- **ASA diagnostics:** A12 may record bid, ask, relative spread and VWAP-window activity for outcome interpretation only. None of these may gate the verdict.

## 18. UNKNOWN and invalid-state table

| Condition | Outcome |
|---|---|
| exchange calendar missing | UNKNOWN |
| no SPX value before 11:00 ET, or value later than 11:00 ET | UNKNOWN |
| chain missing, or AM/PM root cannot be distinguished (X01) | UNKNOWN |
| no listed strike ≤ S_ref | UNKNOWN (no sourced fallback) |
| no trades in 11:30–12:00 ET | sourced: deemed sold at last bid before 12:00 ET |
| trades exist but ASA cannot observe prints | UNKNOWN for entry price. **Proposal selection is unaffected**; outcome valuation is affected. |
| SOQ unavailable at settlement | UNKNOWN for settlement value |
| T-bill rate unavailable | UNKNOWN sizing and accrual |

## 19. Provenance matrix

| Object | Rule | Source | Depth | Direct / inferred |
|---|---|---|---|---|
| roll date | third Friday, preceding business day on holiday | CBOE-PUTWRITE-METHODOLOGY-2024 | full text | direct |
| strike | closest to but not greater than the last S&P 500 value before 11:00 ET | same | full text | direct |
| expiration | option "expiring in the next month" | same | full text | direct |
| sale price | VWAP 11:30–12:00 ET, exclusions, last-bid fallback | same | full text | direct |
| settlement | max(0, K − SOQ) | same | full text | direct |
| sizing | eqs. (5)–(14) | same | full text | direct |
| collateral return | eqs. (3)–(4), 4-week and 13-week rates | same | full text | direct |
| holding period 28/35 days | calendar consequence | — | — | DERIVED |
| performance | index statistics | BONDARENKO-2019-CBOE, WILSHIRE-2019-CBOE, ENNISKNUPP-2008-PUT | full text | direct (index, gross) |

## 20. ASA translation sheet

| Field | Value |
|---|---|
| strategy_id_candidate | `index_putwrite_cboe_put` |
| lane | index put writing |
| source_methodology_version | Cboe S&P 500 PutWrite Indices Methodology (retrieved 2026-09-27) |
| required_market_capabilities | REAL_TIME_QUOTE_V1 (SPX index), OPTION_CHAIN_V1 (SPX), TRADING_CALENDAR_V1; rates via X04 |
| canonical_facts | §3 |
| derived_facts_existing | none identical |
| derived_facts_new | DF-THIRD-FRIDAY-ROLL-DATE, DF-OPT-MID, DF-CBOE-TBILL-DAILY-ACCRUAL, DF-CBOE-PUT-CONTRACT-COUNT |
| strategy_parameters | reference time 11:00 ET; VWAP window; excluded codes; bill tenors |
| gates | §6 |
| direction | §9 |
| structure_primitive | **P01** single short put |
| structure_selection_rules | §10 |
| score | NONE |
| verdict_truth_table | §7 |
| lifecycle | §13 |
| sizing | §14 (sourced; capital M is an account input) |
| cost_model | trade-VWAP entry, SOQ settlement, no commissions |
| capital_model | cash-secured T-bill collateral (A15 must represent it without substituting ASA max-loss) |
| unknown_states | §18 |
| current_ASA_reuse | OPTION_CHAIN_V1, TRADING_CALENDAR_V1, generic verdict classifier |
| missing_reusable_primitives | X01 (HARD), P01 (HARD), X02a (HARD for the 11:00 ET index reference), X04 (HARD for sizing/accrual), A15 (collateral representation), GAP-OPTION-TRADE-PRINTS (outcome price only) |
| architecture_review_required | **No** for the strategy graph. **Yes (tracking scope only)** for the option-trade-print gap, which has no taxonomy entry. |

## 21. Manifest readiness test

| Item | Status |
|---|---|
| identity/version | known |
| capabilities | named (X01, X02a, X04 missing) |
| canonical inputs | known |
| derived facts | defined |
| parameters | sourced |
| every gate predicate and threshold | sourced |
| direction | known |
| structure and leg selection | sourced, unique |
| entry timing | sourced |
| verdict behavior | sourced (unconditional) |
| lifecycle | sourced |
| sizing | sourced |
| critical cost assumptions | sourced (VWAP) |
| critical capital assumptions | sourced (cash-secured) |
| UNKNOWN semantics | §18 |

**Result:** a manifest can be authored without a new financial-policy decision.

The state is READY_WITH_EXPLICIT_UNKNOWNS rather than IMPLEMENTATION_READY_RESEARCH because three **non-signal** canonical inputs are provider questions, not research gaps:
- option trade prints for the VWAP entry price;
- the SOQ settlement value;
- Treasury bank-discount rates.

Two further open items:
- Net-of-cost evidence is absent.
- Post-launch performance does not beat the S&P 500 on a risk-adjusted basis.

These are **evidence** limits, recorded above. They are not specification gaps.
