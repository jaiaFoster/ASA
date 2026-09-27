# ASA-QS-PW-02-CBOE-WPUT — Cboe S&P 500 One-Week PutWrite (WPUT)

- **Lane:** 2, index put writing
- **Role:** PRIMARY (second specification)
- **Qualification state:** **DEEP_RESEARCH_REQUIRED**
- **Source methodology version:** Cboe Global Indices, *Cboe PutWrite Indices Methodology* (PUTR, PUTY, PTLT, WPTR, WPUT), retrieved 2026-09-27 ([`CBOE-PUTWRITE-INDICES-METHODOLOGY-2024`](../../../sources/CBOE-PUTWRITE-INDICES-METHODOLOGY-2024.yaml)). WPUT base date January 31, 2006; launch date August 3, 2015.

## Why this is a distinct second strategy, not a cosmetic variant of PUT

The rules differ in four respects:
- **Roll frequency:** weekly vs monthly.
- **Settlement handling:** AM **or** PM depending on the roll day.
- **Strike reference and premium timing:** the SOQ or the 4:00 p.m. value, instead of the 11:00 a.m. value plus the 11:30–12:00 VWAP.
- **Collateral:** 4-week bills only.

Bondarenko (2019) documents materially different economics, 2006–2018:

| | WPUT | PUT |
|---|---|---|
| Gross premium collected per year | 37.1% | 22.1% |
| Compound return | 4.51% | 5.97% |
| Sharpe | 0.40 | 0.50 |
| Maximum drawdown | −24.2% | (not in the WPUT comparison) |

WPUT's shorter tenor concentrates exposure in the front week of the volatility surface. Weekly-versus-monthly is admitted as a distinction in the lane requirements only "if evidence establishes materially different rules/economics". Both conditions hold here.

## 1. Evidence qualification

| Item | Finding | Source |
|---|---|---|
| Exact-strategy evidence | 2006–2018: compound 4.51%, Sharpe 0.40, max drawdown −24.2%; gross premium 37.1% per year vs 22.1% for PUT | BONDARENKO-2019-CBOE (full text; figures appended in this sprint) |
| Independent evaluation | none recovered (Wilshire 2019 does not cover WPUT) | — |
| Post-publication | 2006–2018 includes about 3 years after the 2015 launch; later evidence not recovered | — |
| Gross vs net | index, gross; net UNKNOWN | methodology disclaimer |
| Tail | max drawdown −24.2% (2006–2018) | BONDARENKO-2019-CBOE |
| Evidence confidence | LOW–MEDIUM: one sponsor-published study, 13-year back-filled history | INFERENCE |

## 2. Universe

U_t = { listed SPX puts expiring on the next weekly roll date (one week), observable on roll date t }.

The underlying is the S&P 500 index. On third-Friday roll dates the expiring option is the AM-settled standard SPX. On other Fridays it is a PM-settled weekly. Distinguishing the two requires **X01**.

## 3. Canonical facts

| Fact | Unit | Observation | ASA status | Missing |
|---|---|---|---|---|
| `soq(t)` (AM days) | index points | roll-day open auction | not available (X01) | UNKNOWN |
| `spx_value(t)` last before 4:00 p.m. ET (PM days) | index points | < 16:00:00 ET | X01 INDEX quote | UNKNOWN |
| option chain, root, settlement style | — | roll day | OPTION_CHAIN_V1 + X01 | UNKNOWN |
| first bid after 9:30 a.m. ET (AM days); last bid before 4:00 p.m. ET (PM days) | USD | exact quote events | OPTION_CHAIN_V1 snapshots cannot guarantee "first after 9:30" (quote-event capture) | UNKNOWN |
| last ask of the expiring put before 4:00 p.m. ET (PM days) | USD | < 16:00 ET | OPTION_CHAIN_V1 | UNKNOWN |
| usbr_4w | decimal | daily | X04 | UNKNOWN |

## 4. Derived facts

- `DF-WEEKLY-FRIDAY-ROLL-DATE`
- `DF-OPT-MID` (daily marks)
- `DF-CBOE-TBILL-DAILY-ACCRUAL` with n = 28 only; no interest accrues on roll days

## 5. Fact ownership

| Input | Class |
|---|---|
| SOQ, SPX value, quotes, rates | CANONICAL_FACT |
| roll date, mid, accrual | DERIVED_FACT |
| 9:30 a.m. and 4:00 p.m. ET event times | STRATEGY_PARAMETER |
| the four WPUT gates in gate-registry | STRATEGY_GATE |
| strike rule | STRUCTURE_SELECTION_RULE |
| weekly roll; PM buy-back at ask; notional K in bills | PORTFOLIO_OR_LIFECYCLE_RULE |

## 6. Gates

| Gate | PASS | FAIL | UNKNOWN |
|---|---|---|---|
| G-CBOE-WEEKLY-ROLL-DATE | Friday (or preceding business day) | hold | calendar missing |
| G-WPUT-EXPIRING-SETTLEMENT-KNOWN | AM or PM identified | — | X01 missing |
| G-WPUT-AM-ROLL-TIMING-CONSISTENT | — | — | **Always UNKNOWN on AM days.** Research blocker; see §18. |
| G-WPUT-STRIKE-EXISTS | strike < reference exists | — | chain missing, or a strike equals the reference (AMBIGUOUS_SELECTION) |

## 7. Verdict truth table

| ROLL | SETTLEMENT-KNOWN | settlement style | AM-TIMING | STRIKE | Verdict |
|---|---|---|---|---|---|
| FAIL | * | * | * | * | NO_ACTION (hold) |
| UNKNOWN | * | * | * | * | UNKNOWN |
| PASS | UNKNOWN | * | * | * | UNKNOWN |
| PASS | PASS | AM | UNKNOWN (always) | * | UNKNOWN |
| PASS | PASS | PM | n/a | UNKNOWN | UNKNOWN |
| PASS | PASS | PM | n/a | PASS | PASS: write |

## 8. Score

NONE.

## 9. Direction

| Dimension | Direction |
|---|---|
| delta | positive |
| volatility | negative, front-week |
| theta | positive |
| skew | negative |
| term | none |
| event | none |

## 10. Structure selection (P01)

- **Leg:** short put expiring on the next weekly roll date ("one week put option").
- **Strike on AM-settlement days:** K* = max{ K(c) : K(c) < SOQ_t }.
- **Strike on PM-settlement days:** K* = max{ K(c) : K(c) < S_last<16:00 }.
- **Strictness:**
  - The text says "first available strike below".
  - The same document says "lower than or equal to" for PTLT. That contrast supports a strict inequality (DERIVED).
  - Equality of a listed strike with the reference is AMBIGUOUS_SELECTION.

## 11. DTE

Identified by calendar: the expiration equal to the next weekly roll date. It is not a DTE target.

## 12. Entry timing

| Roll day | Premium | Buy-back of expiring put |
|---|---|---|
| AM-settlement | first bid quote of the new put after 9:30 a.m. ET | settles against the SOQ |
| PM-settlement | last bid quote of the new put before 4:00 p.m. ET | bought back at the last ask before 4:00 p.m. ET |

## 13. Lifecycle

- Hold to the next weekly roll date. There is no profit target or stop.
- **AM expiry:** settles max(0, K_old − SOQ).
- **PM expiry:** bought back at the last ask before 4:00 p.m. ET.
- Then write the next put immediately.
- One position at a time.

## 14. Sizing (sourced)

- Notional equal to the strike K is invested in a T-bill account that accrues at the 4-week bank-discount rate.
- Returns follow eqs. (1 + R1)(1 + R2) on roll days, with M_new as the cash allocated to cover the new put.
- The contract quantity for an absolute capital amount is implied by "notional amount equal to the strike (K) … invested in a Treasury bill account": N = M / K per unit of index notional (DERIVED).

## 15. Transaction costs

The source sells at the bid (entry) and buys back at the ask (PM exit), so the spread is paid on the index's own terms. Commissions are excluded. gross = index; net beyond bid/ask = UNKNOWN.

## 16. Capital and margin

Cash-secured at K per unit in 4-week bills. There is no leverage. Maximum loss is K − premium per unit (theoretical).

## 17. Liquidity

No sourced gates. A12 is used for diagnostics only.

## 18. UNKNOWN / invalid states

| Condition | Outcome |
|---|---|
| **AM-settlement roll day** | **RESEARCH BLOCKER.** The strike is chosen "below the SOQ", but the premium is "the first bid quote … after 9:30 a.m. ET". The SOQ is computed only after all constituents have opened, usually before 11:00 a.m., so it is generally not known at the first post-9:30 bid. The methodology does not say whether the index back-fills the premium from a quote earlier than the strike reference, or how a live implementer should order these events. The gate is UNKNOWN on every third-Friday roll. No fallback (for example "use the first bid after the SOQ") may be substituted. |
| settlement style unknown | UNKNOWN |
| strike equals reference | AMBIGUOUS_SELECTION → UNKNOWN |
| quote-event timing unavailable (snapshot-only capture) | UNKNOWN |
| rates unavailable | UNKNOWN |

## 19. Provenance

| Object | Source | Depth | Direct / inferred |
|---|---|---|---|
| weekly roll, holiday rule | CBOE-PUTWRITE-INDICES-METHODOLOGY-2024 | full text | direct |
| AM/PM strike reference, premium timing, PM buy-back | same, §2.2.3 | full text | direct |
| strict "below" | same (contrast with PTLT wording) | full text | DERIVED |
| collateral | same | full text | direct |
| AM-day live ordering | — | — | **UNKNOWN (research blocker)** |
| performance | BONDARENKO-2019-CBOE | full text | direct (gross) |

## 20. ASA translation sheet

| Field | Value |
|---|---|
| strategy_id_candidate | `index_putwrite_cboe_wput` |
| lane | index put writing |
| source_methodology_version | Cboe PutWrite Indices Methodology (retrieved 2026-09-27) |
| required_market_capabilities | OPTION_CHAIN_V1, REAL_TIME_QUOTE_V1 (SPX), TRADING_CALENDAR_V1 |
| canonical_facts | §3 |
| derived_facts_new | DF-WEEKLY-FRIDAY-ROLL-DATE, DF-OPT-MID, DF-CBOE-TBILL-DAILY-ACCRUAL |
| strategy_parameters | 9:30 / 16:00 ET event times |
| gates | §6 |
| direction | §9 |
| structure_primitive | P01 |
| structure_selection_rules | §10 |
| score | NONE |
| verdict_truth_table | §7 |
| lifecycle | §13 |
| sizing | §14 |
| cost_model | bid entry, ask buy-back |
| capital_model | cash-secured |
| unknown_states | §18 |
| current_ASA_reuse | chain, calendar, verdict classifier |
| missing_reusable_primitives | X01 (HARD; AM/PM identity is signal-relevant here), P01, X04, X06 QUOTE_EVENT_CAPTURE ("first bid after 9:30"; Architect classification) |
| architecture_review_required | **yes, for quote-event capture semantics** (a timing primitive, not a strategy path) |

## 21. Manifest readiness

**Not ready.** On roughly one roll in four or five (AM-settlement days), the strike/premium ordering is undefined for live use. Resolving it requires Cboe clarification or a Cboe-published calculation example.

Required research action: recover the Cboe WPUT calculation notes or data-vendor documentation specifying the AM-day premium timestamp relative to the SOQ.

## Closeout disposition (2026-09-27)

NOT SELECTED. The targeted pass re-checked the Cboe methodology (the dedicated One-Week PutWrite document is access-denied; the combined methodology and web sources repeat the same wording). The AM-roll strike/premium ordering remains undefined. State unchanged: DEEP_RESEARCH_REQUIRED. X06 QUOTE_EVENT_CAPTURE would still be needed if it is ever resolved.
