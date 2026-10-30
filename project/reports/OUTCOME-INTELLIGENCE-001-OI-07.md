# OUTCOME-INTELLIGENCE-001 — OI-07 Data-Value Report

- **Verdict:** `evidence_insufficient`
  - insufficient: unclassified_reasons AMBIGUOUS_SELECTION,CAPACITY_DEFERRED_INCOMPLETE_COHORT,CBOE_PUT_REQUIRED_EVIDENCE_UNUSABLE,G_CBOE_SPX_REF_BEFORE_1100_UNKNOWN,G_GXZ_EA_DATE_KNOWN_UNKNOWN,G_GXZ_ENTRY_SESSION_UNKNOWN,G_GXZ_HOLD_TO_EXPIRY_DTE_FAIL,G_GXZ_HOLD_TO_EXPIRY_DTE_UNKNOWN,G_SCS_STRIKE_UNIQUE_UNKNOWN,strategy_gates_rejected,strategy_knowledge_construction_failed,unusable_phase_two_evidence
- **Eligible sessions:** 27 (required 5)
- **Data-adequacy artifact:** `sha256:b4c5ba84c0b889de980191669dc668890e2e7fd6ea712d888322aa31f4c3d4c7`
- **Report checksum:** `42d93fa7eaaa5803732101b71e684d30c9ce945944f336787593d36153083b63`
- **Procurement:** none; this report informs a later Founder decision only

## Sessions

| Session | SHA | Captured | Eligible |
|---|---|---|---|
| 2026-09-24 | `d52146f` | 2026-09-25T01:31:31.870585+00:00 | yes |
| 2026-09-25 | `0f00dfa` | 2026-09-25T22:38:29.404528+00:00 | yes |
| 2026-09-28 | `6b91b54` | 2026-09-28T22:38:52.594284+00:00 | yes |
| 2026-09-29 | `3f7eaaf` | 2026-09-29T22:38:43.252473+00:00 | yes |
| 2026-09-30 | `a63ae59` | 2026-09-30T22:38:22.257121+00:00 | yes |
| 2026-10-01 | `1efac18` | 2026-10-01T22:38:18.340735+00:00 | yes |
| 2026-10-02 | `244b9aa` | 2026-10-02T22:38:34.522111+00:00 | yes |
| 2026-10-05 | `b87fbf7` | 2026-10-05T22:39:08.398087+00:00 | yes |
| 2026-10-06 | `86e691d` | 2026-10-06T22:38:41.176911+00:00 | yes |
| 2026-10-07 | `86e691d` | 2026-10-07T22:38:41.903017+00:00 | yes |
| 2026-10-08 | `716bdab` | 2026-10-08T22:38:30.285806+00:00 | yes |
| 2026-10-09 | `6744ca9` | 2026-10-09T22:38:13.294048+00:00 | yes |
| 2026-10-12 | `ba1e253` | 2026-10-12T22:38:52.074401+00:00 | yes |
| 2026-10-13 | `70ec994` | 2026-10-13T22:39:06.175887+00:00 | yes |
| 2026-10-14 | `fd18952` | 2026-10-14T22:38:49.301805+00:00 | yes |
| 2026-10-15 | `6be2b15` | 2026-10-15T22:38:46.800168+00:00 | yes |
| 2026-10-16 | `cb1f6d3` | 2026-10-16T22:38:16.556105+00:00 | yes |
| 2026-10-19 | `070245c` | 2026-10-19T22:38:46.465831+00:00 | yes |
| 2026-10-20 | `e5f898f` | 2026-10-20T22:38:52.894577+00:00 | yes |
| 2026-10-21 | `635628f` | 2026-10-21T22:38:49.804168+00:00 | yes |
| 2026-10-22 | `635628f` | 2026-10-22T22:38:51.924646+00:00 | yes |
| 2026-10-23 | `ec2cd1c` | 2026-10-23T22:38:36.564670+00:00 | yes |
| 2026-10-26 | `34508da` | 2026-10-26T22:38:13.580387+00:00 | yes |
| 2026-10-27 | `9d6d1fd` | 2026-10-27T22:37:59.102504+00:00 | yes |
| 2026-10-28 | `78acdeb` | 2026-10-28T22:38:10.578074+00:00 | yes |
| 2026-10-29 | `3a79b96` | 2026-10-29T22:38:31.760029+00:00 | yes |
| 2026-10-30 | `d83b538` | 2026-10-30T22:38:08.590480+00:00 | yes |

## Opportunity counts by strategy

| Strategy | Asset | Sessions | Qualifying | Actionable | Actionable / session |
|---|---|---|---|---|---|
| B001 | stock | 27 | 6 | 6 | 0.2222 |
| B002 | stock | 27 | 0 | 0 | 0.0 |
| earnings_calendar | option | 27 | 343 | 292 | 10.8148 |
| event_vol_gxz_preea_straddle_to_expiry | option | 21 | 0 | 0 | 0.0 |
| forward_factor | option | 27 | 217 | 0 | 0.0 |
| index_buywrite_cboe_bxm | option | 22 | 0 | 0 | 0.0 |
| index_putwrite_cboe_put | option | 25 | 0 | 0 | 0.0 |
| index_putwrite_cboe_puty | option | 25 | 0 | 0 | 0.0 |
| index_short_vol_scs_near_atm_straddle | option | 21 | 0 | 0 | 0.0 |
| skew_momentum | option | 27 | 0 | 0 | 0.0 |
| spy_put_credit_spread | option | 27 | 6 | 6 | 0.2222 |
| xs_option_heston_straddle_momentum_lowcost | option | 11 | 0 | 0 | 0.0 |
| xs_option_zhan_neg_lnprice_dn_call | option | 1 | 0 | 0 | 0.0 |

## Lost opportunities by cause

| Category | Rows |
|---|---|
| asa_internal | 27 |
| market_structure_or_policy | 7778 |
| provider_capability | 2498 |
| strategy_semantics | 30157 |
| unclassified | 16752 |

Provider-capability losses by capability:

- `earnings_calendar_v1`: 1848
- `historical_bars_v1`: 15
- `option_chain_v1`: 417
- `real_time_quote_v1`: 218

| Strategy | Reason | Rows | Sessions | Category | Capability | Paid data could resolve |
|---|---|---|---|---|---|---|
| B001 | `unusable_quote` | 21 | 21 | provider_capability | real_time_quote_v1 | partially |
| B002 | `unusable_historical_bars` | 6 | 6 | provider_capability | historical_bars_v1 | yes |
| B002 | `unusable_quote` | 21 | 21 | provider_capability | real_time_quote_v1 | partially |
| earnings_calendar | `missing_earnings_date` | 1631 | 27 | provider_capability | earnings_calendar_v1 | partially |
| earnings_calendar | `missing_implied_volatility` | 22 | 18 | provider_capability | option_chain_v1 | yes |
| earnings_calendar | `no_compatible_contract` | 51 | 23 | market_structure_or_policy | — | no |
| earnings_calendar | `no_valid_expiration_pair` | 5720 | 27 | market_structure_or_policy | — | no |
| earnings_calendar | `strategy_knowledge_construction_failed` | 1 | 1 | unclassified | — | no |
| earnings_calendar | `subject_preparation_failed` | 5 | 5 | asa_internal | — | no |
| earnings_calendar | `unusable_phase_two_evidence` | 69 | 16 | unclassified | — | no |
| earnings_calendar | `verdict` | 5790 | 27 | strategy_semantics | — | no |
| event_vol_gxz_preea_straddle_to_expiry | `G_GXZ_EA_DATE_KNOWN_UNKNOWN` | 1472 | 21 | unclassified | — | no |
| event_vol_gxz_preea_straddle_to_expiry | `G_GXZ_ENTRY_SESSION_UNKNOWN` | 1168 | 21 | unclassified | — | no |
| event_vol_gxz_preea_straddle_to_expiry | `G_GXZ_HOLD_TO_EXPIRY_DTE_FAIL` | 7879 | 21 | unclassified | — | no |
| event_vol_gxz_preea_straddle_to_expiry | `G_GXZ_HOLD_TO_EXPIRY_DTE_UNKNOWN` | 39 | 21 | unclassified | — | no |
| event_vol_gxz_preea_straddle_to_expiry | `subject_preparation_failed` | 5 | 5 | asa_internal | — | no |
| forward_factor | `earnings_clearance` | 217 | 27 | provider_capability | earnings_calendar_v1 | partially |
| forward_factor | `missing_implied_volatility` | 340 | 27 | provider_capability | option_chain_v1 | yes |
| forward_factor | `no_usable_expiration_pair` | 5 | 4 | market_structure_or_policy | — | no |
| forward_factor | `no_valid_expiration_pair` | 1805 | 27 | market_structure_or_policy | — | no |
| forward_factor | `non_positive_forward_variance` | 99 | 24 | market_structure_or_policy | — | no |
| forward_factor | `subject_preparation_failed` | 5 | 5 | asa_internal | — | no |
| forward_factor | `unusable_option_chain` | 9 | 9 | provider_capability | option_chain_v1 | partially |
| forward_factor | `unusable_quote` | 64 | 27 | provider_capability | real_time_quote_v1 | partially |
| forward_factor | `verdict` | 11037 | 27 | strategy_semantics | — | no |
| index_buywrite_cboe_bxm | `G_CBOE_SPX_REF_BEFORE_1100_UNKNOWN` | 17 | 17 | unclassified | — | no |
| index_buywrite_cboe_bxm | `strategy_gates_rejected` | 3 | 3 | unclassified | — | no |
| index_buywrite_cboe_bxm | `subject_preparation_failed` | 2 | 2 | asa_internal | — | no |
| index_putwrite_cboe_put | `CBOE_PUT_REQUIRED_EVIDENCE_UNUSABLE` | 1 | 1 | unclassified | — | no |
| index_putwrite_cboe_put | `G_CBOE_SPX_REF_BEFORE_1100_UNKNOWN` | 19 | 19 | unclassified | — | no |
| index_putwrite_cboe_put | `strategy_gates_rejected` | 3 | 3 | unclassified | — | no |
| index_putwrite_cboe_put | `subject_preparation_failed` | 2 | 2 | asa_internal | — | no |
| index_putwrite_cboe_puty | `CBOE_PUT_REQUIRED_EVIDENCE_UNUSABLE` | 1 | 1 | unclassified | — | no |
| index_putwrite_cboe_puty | `G_CBOE_SPX_REF_BEFORE_1100_UNKNOWN` | 19 | 19 | unclassified | — | no |
| index_putwrite_cboe_puty | `strategy_gates_rejected` | 3 | 3 | unclassified | — | no |
| index_putwrite_cboe_puty | `subject_preparation_failed` | 2 | 2 | asa_internal | — | no |
| index_short_vol_scs_near_atm_straddle | `AMBIGUOUS_SELECTION` | 1 | 1 | unclassified | — | no |
| index_short_vol_scs_near_atm_straddle | `G_SCS_STRIKE_UNIQUE_UNKNOWN` | 16 | 16 | unclassified | — | no |
| index_short_vol_scs_near_atm_straddle | `strategy_gates_rejected` | 3 | 3 | unclassified | — | no |
| index_short_vol_scs_near_atm_straddle | `subject_preparation_failed` | 1 | 1 | asa_internal | — | no |
| skew_momentum | `missing_implied_volatility` | 35 | 19 | provider_capability | option_chain_v1 | yes |
| skew_momentum | `no_call_contracts_at_selected_expiration` | 9 | 7 | market_structure_or_policy | — | no |
| skew_momentum | `no_future_expiration` | 89 | 27 | market_structure_or_policy | — | no |
| skew_momentum | `strategy_knowledge_construction_failed` | 2 | 2 | unclassified | — | no |
| skew_momentum | `subject_preparation_failed` | 5 | 5 | asa_internal | — | no |
| skew_momentum | `unusable_historical_bars` | 9 | 1 | provider_capability | historical_bars_v1 | yes |
| skew_momentum | `unusable_option_chain` | 11 | 11 | provider_capability | option_chain_v1 | partially |
| skew_momentum | `unusable_quote` | 91 | 27 | provider_capability | real_time_quote_v1 | partially |
| skew_momentum | `verdict` | 13330 | 27 | strategy_semantics | — | no |
| spy_put_credit_spread | `unusable_quote` | 21 | 21 | provider_capability | real_time_quote_v1 | partially |
| xs_option_heston_straddle_momentum_lowcost | `CAPACITY_DEFERRED_INCOMPLETE_COHORT` | 5533 | 11 | unclassified | — | no |
| xs_option_zhan_neg_lnprice_dn_call | `CAPACITY_DEFERRED_INCOMPLETE_COHORT` | 503 | 1 | unclassified | — | no |

## Forward-outcome sample sizes: user-tracked

Ledger: `available`

| Strategy | Subjects | Distinct opportunities | Distinct leg sets | Horizon statuses | Observed with modeled P&L | Due coverage | Meets guard |
|---|---|---|---|---|---|---|---|
| forward_factor | 1 | 1 | 1 | {"missed": 3} | 0 | 0.0 | no |
| spy_put_credit_spread | 1 | 1 | 1 | {"observed": 4} | 4 | 1.0 | no |

## Forward-outcome sample sizes: system-actionable (ND-01)

Ledger: `available`

| Strategy | Subjects | Distinct opportunities | Distinct leg sets | Horizon statuses | Observed with modeled P&L | Due coverage | Meets guard |
|---|---|---|---|---|---|---|---|
| earnings_calendar | 147 | 93 | 129 | {"missed": 39, "observed": 356, "pending": 52} | 356 | 0.9013 | yes |
| index_putwrite_cboe_put | 1 | 1 | 1 | {"observed": 3, "pending": 1} | 3 | 1.0 | no |
| index_putwrite_cboe_puty | 1 | 1 | 1 | {"observed": 3, "pending": 1} | 3 | 1.0 | no |
| spy_put_credit_spread | 26 | 26 | 26 | {"missed": 2, "observed": 66, "pending": 36} | 66 | 0.9706 | yes |

## Decisions blocked by missing data

### BD-01: Weight opportunity ordering by forward outcomes, or claim one strategy outperforms another

- Blocked by: Forward-outcome sample below the OI-06 guard (30 observed outcomes with modeled P&L per strategy). The corpus is user-tracked only until the Architect-approved system enrollment (ND-01, migration 0020) is Founder-merged.
- Unlock: Time and corpus growth, not purchase. Paid historical option chains would give backtest evidence, a different evidence class that does not replace ASA's own forward outcomes.
- Paid data could resolve: **no**
- Latest-session observed rows: 0 {}
- Evidence: `project/reports/OUTCOME-INTELLIGENCE-001-OI-06.md`, `project/reports/OUTCOME-INTELLIGENCE-001-OI-02-04-ARCHITECT-DECISION.md`, `project/reports/OUTCOME-INTELLIGENCE-001-ND-01-ARCHITECT-DECISION.md`

### BD-02: Evaluate B002 (adjusted-close stock benchmark) at all

- Blocked by: Adjusted-close history entitlement (Alpha Vantage). B002 is typed unknown every session.
- Unlock: A source of split-and-dividend-adjusted or total-return history with explicit semantics
- Paid data could resolve: **yes**
- Latest-session observed rows: 0 {"unusable_historical_bars": 0, "insufficient_adjusted_history": 0, "unusable_total_return_history": 0}
- Evidence: `project/reports/STOCK-RUNTIME-001-STK-01.md`, `project/reports/STOCK-PRODUCT-001-SP-06.md`

### BD-03: Apply Skew Momentum's historical skew-stretch gate before 40 sessions have accumulated

- Blocked by: No configured provider supplies prior option chains, so historical skew accumulates one session at a time and nothing is backfilled.
- Unlock: Time (prospective accumulation), or historical option chains/IV history. That capability is absent from the data-adequacy-v1 matrix and would need a matrix amendment.
- Paid data could resolve: **yes**
- Latest-session observed rows: 0 {}
- Evidence: `project/reports/SPRINT-013-S13-04-trace.md`

### BD-04: Add IV-Rank-gated option strategies (e.g. tastylive 45-DTE credit spread, Option Alpha CORE put credit spread)

- Blocked by: No producer for historical IV / IV Rank; such strategies would be permanently UNKNOWN
- Unlock: Historical implied-volatility series per underlying, or time to accumulate IV prospectively
- Paid data could resolve: **yes**
- Latest-session observed rows: 0 {}
- Evidence: `project/reports/STRATEGY-LIBRARY-001-SL-02-SELECTION.md`

### BD-05: Add SPX index-option strategies (e.g. Cboe CNDR) without an SPY substitution

- Blocked by: Index-underlying, root and settlement identity are not modelled, and the T-bill rate is not acquired. The missing modelling is ASA-owned work, and it needs an ARCH-005 amendment.
- Unlock: An Architect decision and index modelling (ASA work), plus a rate source
- Paid data could resolve: **partially**
- Latest-session observed rows: 0 {}
- Evidence: `project/reports/STRATEGY-LIBRARY-001-SL-02-CNDR-ARCHITECT-DECISION.md`, `project/reports/STRATEGY-LIBRARY-001-SL-02-SELECTION.md`

### BD-06: Evaluate earnings-driven opportunities on symbols without a confirmed earnings date

- Blocked by: Provider earnings coverage. Some events are genuinely unannounced, and no source can resolve those.
- Unlock: A confirmed earnings calendar with announcement status
- Paid data could resolve: **partially**
- Latest-session observed rows: 295 {"missing_earnings_date": 271, "earnings_clearance": 24}
- Evidence: `project/reports/DATA-RELIABILITY-001-REL-05.md`, `project/reports/OPTIONS-TRUTH-001-OT-06.md`

### BD-07: Evaluate option strategies on symbols whose chain lacks IV, Greeks, or a usable quote

- Blocked by: Provider option-evidence coverage and entitlement
- Unlock: Complete option expiration, contract, quote, Greek, and IV evidence
- Paid data could resolve: **yes**
- Latest-session observed rows: 28 {"missing_implied_volatility": 17, "missing_actual_delta": 0, "unusable_quote": 10, "unusable_option_chain": 1}
- Evidence: `project/reports/DATA-RELIABILITY-001-REL-05.md`, `project/reports/OPTIONS-TRUTH-001-OT-06.md`

### BD-08: Run TGSM / S001 research on qualified long history

- Blocked by: No qualified total-return, Treasury total-return, or point-in-time reference data
- Unlock: The corresponding data-adequacy sources
- Paid data could resolve: **yes**
- Latest-session observed rows: 0 {}
- Evidence: `project/reports/DATA-RELIABILITY-001-REL-05.md`

## Paid-capability gaps (quantified)

### confirmed earnings calendar with announcement status and effective timestamps

- Strategies affected: earnings_calendar, forward_factor_execution_readiness
- Would better data solve it: only provider-confirmed coverage/entitlement cases; genuinely unannounced events remain unknown
- Observed rows a source could resolve: {"latest_session": 0, "mean_per_session": 0.0}
- Observed rows only partially resolvable: {"latest_session": 295, "mean_per_session": 68.4444}
- Blocked decisions: BD-06

### complete option expiration, contract, quote, Greek, and implied-volatility evidence

- Strategies affected: forward_factor, skew_momentum, earnings_calendar
- Would better data solve it: provider coverage gaps yes; declared expiration policy ineligibility no
- Observed rows a source could resolve: {"latest_session": 17, "mean_per_session": 14.7037}
- Observed rows only partially resolvable: {"latest_session": 11, "mean_per_session": 8.8148}
- Blocked decisions: BD-07

### split-and-dividend-adjusted or authoritative total-return history

- Strategies affected: B002, S001, TGSM-RESEARCH-001
- Would better data solve it: yes, if semantics, depth, timestamps, and redistribution treatment are explicit
- Observed rows a source could resolve: {"latest_session": 0, "mean_per_session": 0.5556}
- Observed rows only partially resolvable: {"latest_session": 0, "mean_per_session": 0.0}
- Blocked decisions: BD-02, BD-08

### canonical three-month Treasury total-return history

- Strategies affected: S001, TGSM-RESEARCH-001
- Would better data solve it: yes, if it supplies total return rather than ETF, cash, or raw-yield proxy
- Observed rows a source could resolve: {"latest_session": 0, "mean_per_session": 0.0}
- Observed rows only partially resolvable: {"latest_session": 0, "mean_per_session": 0.0}
- Blocked decisions: BD-08

### authoritative point-in-time sector membership and historical exchange calendar

- Strategies affected: TGSM-RESEARCH-001
- Would better data solve it: yes, if effective dates and source provenance are authoritative
- Observed rows a source could resolve: {"latest_session": 0, "mean_per_session": 0.0}
- Observed rows only partially resolvable: {"latest_session": 0, "mean_per_session": 0.0}
- Blocked decisions: BD-08
