# OUTCOME-INTELLIGENCE-001 — OI-07 Data-Value Report

- **Verdict:** `evidence_insufficient`
  - insufficient: unclassified_reasons CBOE_PUT_REQUIRED_EVIDENCE_UNUSABLE,G_CBOE_SPX_REF_BEFORE_1100_UNKNOWN,G_GXZ_EA_DATE_KNOWN_UNKNOWN,G_GXZ_ENTRY_SESSION_UNKNOWN,G_GXZ_HOLD_TO_EXPIRY_DTE_FAIL,G_GXZ_HOLD_TO_EXPIRY_DTE_UNKNOWN,G_SCS_STRIKE_UNIQUE_UNKNOWN,strategy_knowledge_construction_failed,unusable_phase_two_evidence
- **Eligible sessions:** 9 (required 5)
- **Data-adequacy artifact:** `sha256:b4c5ba84c0b889de980191669dc668890e2e7fd6ea712d888322aa31f4c3d4c7`
- **Report checksum:** `438e50e82a7f5b92ab73ec51c998c357e631ed83943643574479608eaeef410a`
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

## Opportunity counts by strategy

| Strategy | Asset | Sessions | Qualifying | Actionable | Actionable / session |
|---|---|---|---|---|---|
| B001 | stock | 9 | 6 | 6 | 0.6667 |
| B002 | stock | 9 | 0 | 0 | 0.0 |
| earnings_calendar | option | 9 | 182 | 167 | 18.5556 |
| event_vol_gxz_preea_straddle_to_expiry | option | 3 | 0 | 0 | 0.0 |
| forward_factor | option | 9 | 64 | 0 | 0.0 |
| index_buywrite_cboe_bxm | option | 4 | 0 | 0 | 0.0 |
| index_putwrite_cboe_put | option | 7 | 0 | 0 | 0.0 |
| index_putwrite_cboe_puty | option | 7 | 0 | 0 | 0.0 |
| index_short_vol_scs_near_atm_straddle | option | 3 | 0 | 0 | 0.0 |
| skew_momentum | option | 9 | 0 | 0 | 0.0 |
| spy_put_credit_spread | option | 9 | 6 | 6 | 0.6667 |

## Lost opportunities by cause

| Category | Rows |
|---|---|
| asa_internal | 7 |
| market_structure_or_policy | 1631 |
| provider_capability | 426 |
| strategy_semantics | 11352 |
| unclassified | 1543 |

Provider-capability losses by capability:

- `earnings_calendar_v1`: 273
- `historical_bars_v1`: 6
- `option_chain_v1`: 109
- `real_time_quote_v1`: 38

| Strategy | Reason | Rows | Sessions | Category | Capability | Paid data could resolve |
|---|---|---|---|---|---|---|
| B001 | `unusable_quote` | 3 | 3 | provider_capability | real_time_quote_v1 | partially |
| B002 | `unusable_historical_bars` | 6 | 6 | provider_capability | historical_bars_v1 | yes |
| B002 | `unusable_quote` | 3 | 3 | provider_capability | real_time_quote_v1 | partially |
| earnings_calendar | `missing_earnings_date` | 209 | 9 | provider_capability | earnings_calendar_v1 | partially |
| earnings_calendar | `missing_implied_volatility` | 9 | 8 | provider_capability | option_chain_v1 | yes |
| earnings_calendar | `no_compatible_contract` | 15 | 6 | market_structure_or_policy | — | no |
| earnings_calendar | `no_valid_expiration_pair` | 800 | 9 | market_structure_or_policy | — | no |
| earnings_calendar | `strategy_knowledge_construction_failed` | 1 | 1 | unclassified | — | no |
| earnings_calendar | `unusable_phase_two_evidence` | 19 | 7 | unclassified | — | no |
| earnings_calendar | `verdict` | 3307 | 9 | strategy_semantics | — | no |
| event_vol_gxz_preea_straddle_to_expiry | `G_GXZ_EA_DATE_KNOWN_UNKNOWN` | 50 | 3 | unclassified | — | no |
| event_vol_gxz_preea_straddle_to_expiry | `G_GXZ_ENTRY_SESSION_UNKNOWN` | 27 | 3 | unclassified | — | no |
| event_vol_gxz_preea_straddle_to_expiry | `G_GXZ_HOLD_TO_EXPIRY_DTE_FAIL` | 1423 | 3 | unclassified | — | no |
| event_vol_gxz_preea_straddle_to_expiry | `G_GXZ_HOLD_TO_EXPIRY_DTE_UNKNOWN` | 9 | 3 | unclassified | — | no |
| forward_factor | `earnings_clearance` | 64 | 9 | provider_capability | earnings_calendar_v1 | partially |
| forward_factor | `missing_implied_volatility` | 89 | 9 | provider_capability | option_chain_v1 | yes |
| forward_factor | `no_usable_expiration_pair` | 2 | 2 | market_structure_or_policy | — | no |
| forward_factor | `no_valid_expiration_pair` | 764 | 9 | market_structure_or_policy | — | no |
| forward_factor | `non_positive_forward_variance` | 11 | 6 | market_structure_or_policy | — | no |
| forward_factor | `unusable_option_chain` | 5 | 5 | provider_capability | option_chain_v1 | partially |
| forward_factor | `unusable_quote` | 10 | 9 | provider_capability | real_time_quote_v1 | partially |
| forward_factor | `verdict` | 3582 | 9 | strategy_semantics | — | no |
| index_buywrite_cboe_bxm | `G_CBOE_SPX_REF_BEFORE_1100_UNKNOWN` | 2 | 2 | unclassified | — | no |
| index_buywrite_cboe_bxm | `subject_preparation_failed` | 2 | 2 | asa_internal | — | no |
| index_putwrite_cboe_put | `CBOE_PUT_REQUIRED_EVIDENCE_UNUSABLE` | 1 | 1 | unclassified | — | no |
| index_putwrite_cboe_put | `G_CBOE_SPX_REF_BEFORE_1100_UNKNOWN` | 4 | 4 | unclassified | — | no |
| index_putwrite_cboe_put | `subject_preparation_failed` | 2 | 2 | asa_internal | — | no |
| index_putwrite_cboe_puty | `CBOE_PUT_REQUIRED_EVIDENCE_UNUSABLE` | 1 | 1 | unclassified | — | no |
| index_putwrite_cboe_puty | `G_CBOE_SPX_REF_BEFORE_1100_UNKNOWN` | 4 | 4 | unclassified | — | no |
| index_putwrite_cboe_puty | `subject_preparation_failed` | 2 | 2 | asa_internal | — | no |
| index_short_vol_scs_near_atm_straddle | `G_SCS_STRIKE_UNIQUE_UNKNOWN` | 2 | 2 | unclassified | — | no |
| index_short_vol_scs_near_atm_straddle | `subject_preparation_failed` | 1 | 1 | asa_internal | — | no |
| skew_momentum | `missing_implied_volatility` | 1 | 1 | provider_capability | option_chain_v1 | yes |
| skew_momentum | `no_call_contracts_at_selected_expiration` | 5 | 4 | market_structure_or_policy | — | no |
| skew_momentum | `no_future_expiration` | 34 | 9 | market_structure_or_policy | — | no |
| skew_momentum | `unusable_option_chain` | 5 | 5 | provider_capability | option_chain_v1 | partially |
| skew_momentum | `unusable_quote` | 19 | 9 | provider_capability | real_time_quote_v1 | partially |
| skew_momentum | `verdict` | 4463 | 9 | strategy_semantics | — | no |
| spy_put_credit_spread | `unusable_quote` | 3 | 3 | provider_capability | real_time_quote_v1 | partially |

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
| earnings_calendar | 56 | 45 | 49 | {"observed": 70, "pending": 122} | 70 | 1.0 | yes |
| spy_put_credit_spread | 8 | 8 | 8 | {"observed": 10, "pending": 22} | 10 | 1.0 | no |

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
- Latest-session observed rows: 23 {"missing_earnings_date": 19, "earnings_clearance": 4}
- Evidence: `project/reports/DATA-RELIABILITY-001-REL-05.md`, `project/reports/OPTIONS-TRUTH-001-OT-06.md`

### BD-07: Evaluate option strategies on symbols whose chain lacks IV, Greeks, or a usable quote

- Blocked by: Provider option-evidence coverage and entitlement
- Unlock: Complete option expiration, contract, quote, Greek, and IV evidence
- Paid data could resolve: **yes**
- Latest-session observed rows: 25 {"missing_implied_volatility": 15, "missing_actual_delta": 0, "unusable_quote": 8, "unusable_option_chain": 2}
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
- Observed rows only partially resolvable: {"latest_session": 23, "mean_per_session": 30.3333}
- Blocked decisions: BD-06

### complete option expiration, contract, quote, Greek, and implied-volatility evidence

- Strategies affected: forward_factor, skew_momentum, earnings_calendar
- Would better data solve it: provider coverage gaps yes; declared expiration policy ineligibility no
- Observed rows a source could resolve: {"latest_session": 15, "mean_per_session": 11.0}
- Observed rows only partially resolvable: {"latest_session": 10, "mean_per_session": 5.3333}
- Blocked decisions: BD-07

### split-and-dividend-adjusted or authoritative total-return history

- Strategies affected: B002, S001, TGSM-RESEARCH-001
- Would better data solve it: yes, if semantics, depth, timestamps, and redistribution treatment are explicit
- Observed rows a source could resolve: {"latest_session": 0, "mean_per_session": 0.6667}
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
