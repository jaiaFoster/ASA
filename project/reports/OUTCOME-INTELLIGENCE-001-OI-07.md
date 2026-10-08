# OUTCOME-INTELLIGENCE-001 — OI-07 Data-Value Report

- **Verdict:** `evidence_insufficient`
  - insufficient: unclassified_reasons CBOE_PUT_REQUIRED_EVIDENCE_UNUSABLE,G_CBOE_SPX_REF_BEFORE_1100_UNKNOWN,G_GXZ_EA_DATE_KNOWN_UNKNOWN,G_GXZ_ENTRY_SESSION_UNKNOWN,G_GXZ_HOLD_TO_EXPIRY_DTE_FAIL,G_GXZ_HOLD_TO_EXPIRY_DTE_UNKNOWN,G_SCS_STRIKE_UNIQUE_UNKNOWN,strategy_gates_rejected,strategy_knowledge_construction_failed,unusable_phase_two_evidence
- **Eligible sessions:** 11 (required 5)
- **Data-adequacy artifact:** `sha256:b4c5ba84c0b889de980191669dc668890e2e7fd6ea712d888322aa31f4c3d4c7`
- **Report checksum:** `085b1a8c3158ca04027c6fb57848a0d7bb9b5058dfb2918e9577dc92a3c5e9ad`
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

## Opportunity counts by strategy

| Strategy | Asset | Sessions | Qualifying | Actionable | Actionable / session |
|---|---|---|---|---|---|
| B001 | stock | 11 | 6 | 6 | 0.5455 |
| B002 | stock | 11 | 0 | 0 | 0.0 |
| earnings_calendar | option | 11 | 241 | 225 | 20.4545 |
| event_vol_gxz_preea_straddle_to_expiry | option | 5 | 0 | 0 | 0.0 |
| forward_factor | option | 11 | 70 | 0 | 0.0 |
| index_buywrite_cboe_bxm | option | 6 | 0 | 0 | 0.0 |
| index_putwrite_cboe_put | option | 9 | 0 | 0 | 0.0 |
| index_putwrite_cboe_puty | option | 9 | 0 | 0 | 0.0 |
| index_short_vol_scs_near_atm_straddle | option | 5 | 0 | 0 | 0.0 |
| skew_momentum | option | 11 | 0 | 0 | 0.0 |
| spy_put_credit_spread | option | 11 | 6 | 6 | 0.5455 |

## Lost opportunities by cause

| Category | Rows |
|---|---|
| asa_internal | 7 |
| market_structure_or_policy | 1951 |
| provider_capability | 526 |
| strategy_semantics | 13862 |
| unclassified | 2593 |

Provider-capability losses by capability:

- `earnings_calendar_v1`: 312
- `historical_bars_v1`: 15
- `option_chain_v1`: 141
- `real_time_quote_v1`: 58

| Strategy | Reason | Rows | Sessions | Category | Capability | Paid data could resolve |
|---|---|---|---|---|---|---|
| B001 | `unusable_quote` | 5 | 5 | provider_capability | real_time_quote_v1 | partially |
| B002 | `unusable_historical_bars` | 6 | 6 | provider_capability | historical_bars_v1 | yes |
| B002 | `unusable_quote` | 5 | 5 | provider_capability | real_time_quote_v1 | partially |
| earnings_calendar | `missing_earnings_date` | 242 | 11 | provider_capability | earnings_calendar_v1 | partially |
| earnings_calendar | `missing_implied_volatility` | 13 | 10 | provider_capability | option_chain_v1 | yes |
| earnings_calendar | `no_compatible_contract` | 16 | 7 | market_structure_or_policy | — | no |
| earnings_calendar | `no_valid_expiration_pair` | 941 | 11 | market_structure_or_policy | — | no |
| earnings_calendar | `strategy_knowledge_construction_failed` | 1 | 1 | unclassified | — | no |
| earnings_calendar | `unusable_phase_two_evidence` | 55 | 9 | unclassified | — | no |
| earnings_calendar | `verdict` | 4040 | 11 | strategy_semantics | — | no |
| event_vol_gxz_preea_straddle_to_expiry | `G_GXZ_EA_DATE_KNOWN_UNKNOWN` | 83 | 5 | unclassified | — | no |
| event_vol_gxz_preea_straddle_to_expiry | `G_GXZ_ENTRY_SESSION_UNKNOWN` | 73 | 5 | unclassified | — | no |
| event_vol_gxz_preea_straddle_to_expiry | `G_GXZ_HOLD_TO_EXPIRY_DTE_FAIL` | 2346 | 5 | unclassified | — | no |
| event_vol_gxz_preea_straddle_to_expiry | `G_GXZ_HOLD_TO_EXPIRY_DTE_UNKNOWN` | 13 | 5 | unclassified | — | no |
| forward_factor | `earnings_clearance` | 70 | 11 | provider_capability | earnings_calendar_v1 | partially |
| forward_factor | `missing_implied_volatility` | 114 | 11 | provider_capability | option_chain_v1 | yes |
| forward_factor | `no_usable_expiration_pair` | 3 | 3 | market_structure_or_policy | — | no |
| forward_factor | `no_valid_expiration_pair` | 927 | 11 | market_structure_or_policy | — | no |
| forward_factor | `non_positive_forward_variance` | 16 | 8 | market_structure_or_policy | — | no |
| forward_factor | `unusable_option_chain` | 5 | 5 | provider_capability | option_chain_v1 | partially |
| forward_factor | `unusable_quote` | 16 | 11 | provider_capability | real_time_quote_v1 | partially |
| forward_factor | `verdict` | 4382 | 11 | strategy_semantics | — | no |
| index_buywrite_cboe_bxm | `G_CBOE_SPX_REF_BEFORE_1100_UNKNOWN` | 3 | 3 | unclassified | — | no |
| index_buywrite_cboe_bxm | `strategy_gates_rejected` | 1 | 1 | unclassified | — | no |
| index_buywrite_cboe_bxm | `subject_preparation_failed` | 2 | 2 | asa_internal | — | no |
| index_putwrite_cboe_put | `CBOE_PUT_REQUIRED_EVIDENCE_UNUSABLE` | 1 | 1 | unclassified | — | no |
| index_putwrite_cboe_put | `G_CBOE_SPX_REF_BEFORE_1100_UNKNOWN` | 5 | 5 | unclassified | — | no |
| index_putwrite_cboe_put | `strategy_gates_rejected` | 1 | 1 | unclassified | — | no |
| index_putwrite_cboe_put | `subject_preparation_failed` | 2 | 2 | asa_internal | — | no |
| index_putwrite_cboe_puty | `CBOE_PUT_REQUIRED_EVIDENCE_UNUSABLE` | 1 | 1 | unclassified | — | no |
| index_putwrite_cboe_puty | `G_CBOE_SPX_REF_BEFORE_1100_UNKNOWN` | 5 | 5 | unclassified | — | no |
| index_putwrite_cboe_puty | `strategy_gates_rejected` | 1 | 1 | unclassified | — | no |
| index_putwrite_cboe_puty | `subject_preparation_failed` | 2 | 2 | asa_internal | — | no |
| index_short_vol_scs_near_atm_straddle | `G_SCS_STRIKE_UNIQUE_UNKNOWN` | 3 | 3 | unclassified | — | no |
| index_short_vol_scs_near_atm_straddle | `strategy_gates_rejected` | 1 | 1 | unclassified | — | no |
| index_short_vol_scs_near_atm_straddle | `subject_preparation_failed` | 1 | 1 | asa_internal | — | no |
| skew_momentum | `missing_implied_volatility` | 3 | 3 | provider_capability | option_chain_v1 | yes |
| skew_momentum | `no_call_contracts_at_selected_expiration` | 7 | 5 | market_structure_or_policy | — | no |
| skew_momentum | `no_future_expiration` | 41 | 11 | market_structure_or_policy | — | no |
| skew_momentum | `unusable_historical_bars` | 9 | 1 | provider_capability | historical_bars_v1 | yes |
| skew_momentum | `unusable_option_chain` | 6 | 6 | provider_capability | option_chain_v1 | partially |
| skew_momentum | `unusable_quote` | 27 | 11 | provider_capability | real_time_quote_v1 | partially |
| skew_momentum | `verdict` | 5440 | 11 | strategy_semantics | — | no |
| spy_put_credit_spread | `unusable_quote` | 5 | 5 | provider_capability | real_time_quote_v1 | partially |

## Forward-outcome sample sizes: user-tracked

Ledger: `available`

| Strategy | Subjects | Distinct opportunities | Distinct leg sets | Horizon statuses | Observed with modeled P&L | Due coverage | Meets guard |
|---|---|---|---|---|---|---|---|
| forward_factor | 1 | 1 | 1 | {"missed": 3} | 0 | 0.0 | no |
| spy_put_credit_spread | 1 | 1 | 1 | {"observed": 2, "pending": 2} | 2 | 1.0 | no |

## Forward-outcome sample sizes: system-actionable (ND-01)

Ledger: `available`

| Strategy | Subjects | Distinct opportunities | Distinct leg sets | Horizon statuses | Observed with modeled P&L | Due coverage | Meets guard |
|---|---|---|---|---|---|---|---|
| earnings_calendar | 70 | 53 | 60 | {"observed": 98, "pending": 136} | 98 | 1.0 | yes |
| spy_put_credit_spread | 10 | 10 | 10 | {"observed": 14, "pending": 26} | 14 | 1.0 | no |

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
- Latest-session observed rows: 9 {"unusable_historical_bars": 9, "insufficient_adjusted_history": 0, "unusable_total_return_history": 0}
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
- Latest-session observed rows: 21 {"missing_earnings_date": 17, "earnings_clearance": 4}
- Evidence: `project/reports/DATA-RELIABILITY-001-REL-05.md`, `project/reports/OPTIONS-TRUTH-001-OT-06.md`

### BD-07: Evaluate option strategies on symbols whose chain lacks IV, Greeks, or a usable quote

- Blocked by: Provider option-evidence coverage and entitlement
- Unlock: Complete option expiration, contract, quote, Greek, and IV evidence
- Paid data could resolve: **yes**
- Latest-session observed rows: 26 {"missing_implied_volatility": 16, "missing_actual_delta": 0, "unusable_quote": 10, "unusable_option_chain": 0}
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
- Observed rows only partially resolvable: {"latest_session": 21, "mean_per_session": 28.3636}
- Blocked decisions: BD-06

### complete option expiration, contract, quote, Greek, and implied-volatility evidence

- Strategies affected: forward_factor, skew_momentum, earnings_calendar
- Would better data solve it: provider coverage gaps yes; declared expiration policy ineligibility no
- Observed rows a source could resolve: {"latest_session": 16, "mean_per_session": 11.8182}
- Observed rows only partially resolvable: {"latest_session": 10, "mean_per_session": 6.2727}
- Blocked decisions: BD-07

### split-and-dividend-adjusted or authoritative total-return history

- Strategies affected: B002, S001, TGSM-RESEARCH-001
- Would better data solve it: yes, if semantics, depth, timestamps, and redistribution treatment are explicit
- Observed rows a source could resolve: {"latest_session": 9, "mean_per_session": 1.3636}
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
