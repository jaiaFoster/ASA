# ASA-OPTIONS-TO-OUTCOMES-2026Q4 — Program Closure Report

- **Verdict:** `observation_pending`
- **Report checksum:** `3e6bc7692f7def74c0306b3afa6c20cf44856d1e402ab0cef96955a652e02043`
- **OI-07 data-value verdict:** `evidence_insufficient` (`927d6892743a`)

## Evidence gates

| Gate | State | Detail |
|---|---|---|
| prior_sprints_closed | **pass** | all closed |
| forward_ledger_deployed | **pass** | latest eligible capture ledger_status=available |
| forward_outcome_observed | **pass** | observed horizons in the latest readable ledgers, by source (never pooled): user_tracked=2, system_actionable=48 |
| aoy_measured | **pass** | 7 eligible session(s), required 5 |
| zero_unexplained_drops | **pass** | 0 unexplained drop(s) across eligible sessions |
| presentation_defect_free | **pass** | 0 trade-card/stock-proposal defect(s) across eligible sessions |
| oi07_data_value_complete | **pending** | OI-07 verdict=evidence_insufficient |
| no_open_corrections | **pass** | 0 open correction(s) |

## Unmet / downgraded targets

- **UNMET (downgraded)**: STRATEGY-LIBRARY-001: SL-02: add 2-4 option strategies. Achieved: 1 (spy_put_credit_spread). This is not a success.

## Sprints

| Sprint | State | Closure report |
|---|---|---|
| OPTIONS-TRUTH-001 | closed | project/reports/OPTIONS-TRUTH-001-OT-06.md |
| OPTIONS-PRODUCT-001 | closed | project/reports/OPTIONS-PRODUCT-001-CLOSURE.md |
| STOCK-PRODUCT-001 | closed | project/reports/STOCK-PRODUCT-001-SP-06.md |
| STRATEGY-LIBRARY-001 | closed_with_downgrade | project/reports/STRATEGY-LIBRARY-001-CLOSURE.md |
| OUTCOME-INTELLIGENCE-001 | in_progress | — |

## AOY and coverage

AOY is the count of complete, currently actionable proposals per eligible session, measured without lowering any gate.

- AOY total: {"n": 7, "mean": 17.8571, "median": 21.0, "min": 3.0, "max": 28.0}
- AOY options: {"n": 7, "mean": 17.0, "median": 20.0, "min": 2.0, "max": 28.0}
- AOY stocks: {"n": 7, "mean": 0.8571, "median": 1.0, "min": 0.0, "max": 1.0}
- Evaluation coverage (mean): 1.0
- Strategy evaluation completion rate (mean): 0.8178
- Constructible rate after qualifying signals (mean): 0.6652
- Trade-card completeness (mean): 0.6652
- Median actionable evidence age at session close, seconds (mean of sessions): 3512.3571
- Unexplained drops (total): 0

| Session | SHA | AOY | Options | Stocks | Coverage | Completion | Constructible | Provider-limited |
|---|---|---|---|---|---|---|---|---|
| 2026-09-24 | `d52146f` | 3 | 2 | 1 | 1.0 | 0.7269 | 0.4 | {"earnings_calendar_v1": 0.0126, "historical_bars_v1": 0.0007, "option_chain_v1": 0.0073, "real_time_quote_v1": 0.002} |
| 2026-09-25 | `0f00dfa` | 11 | 10 | 1 | 1.0 | 0.8823 | 0.7143 | {"earnings_calendar_v1": 0.0106, "historical_bars_v1": 0.0007, "option_chain_v1": 0.0073, "real_time_quote_v1": 0.002} |
| 2026-09-28 | `6b91b54` | 17 | 16 | 1 | 1.0 | 0.8758 | 0.7619 | {"earnings_calendar_v1": 0.0112, "historical_bars_v1": 0.0007, "option_chain_v1": 0.0086, "real_time_quote_v1": 0.002} |
| 2026-09-29 | `3f7eaaf` | 22 | 21 | 1 | 1.0 | 0.8745 | 0.7778 | {"earnings_calendar_v1": 0.0112, "historical_bars_v1": 0.0007, "option_chain_v1": 0.0066, "real_time_quote_v1": 0.002} |
| 2026-09-30 | `a63ae59` | 23 | 22 | 1 | 1.0 | 0.8791 | 0.8462 | {"earnings_calendar_v1": 0.0092, "historical_bars_v1": 0.0007, "option_chain_v1": 0.0086, "real_time_quote_v1": 0.002} |
| 2026-10-01 | `1efac18` | 21 | 20 | 1 | 1.0 | 0.8343 | 0.3077 | {"earnings_calendar_v1": 0.0845, "historical_bars_v1": 0.0007, "option_chain_v1": 0.0086, "real_time_quote_v1": 0.002} |
| 2026-10-02 | `244b9aa` | 28 | 28 | 0 | 1.0 | 0.6518 | 0.8485 | {"earnings_calendar_v1": 0.0119, "option_chain_v1": 0.0054, "real_time_quote_v1": 0.003} |

## Forward-outcome corpus

- **System-actionable (ND-01)**, ledger `available`
  - earnings_calendar: 42 subject(s); horizons {"observed": 42, "pending": 108}; n=42 with modeled P&L
  - spy_put_credit_spread: 6 subject(s); horizons {"observed": 6, "pending": 18}; n=6 with modeled P&L
- **User-tracked**, ledger `available`
  - forward_factor: 1 subject(s); horizons {"missed": 3}; n=0 with modeled P&L
  - spy_put_credit_spread: 1 subject(s); horizons {"observed": 2, "pending": 2}; n=2 with modeled P&L

## Remaining quantified data/provider blockers

- confirmed earnings calendar with announcement status and effective timestamps: resolvable rows {"latest_session": 0, "mean_per_session": 0.0}; partially {"latest_session": 24, "mean_per_session": 33.5714}; blocks BD-06
- complete option expiration, contract, quote, Greek, and implied-volatility evidence: resolvable rows {"latest_session": 9, "mean_per_session": 10.5714}; partially {"latest_session": 8, "mean_per_session": 4.5714}; blocks BD-07
- split-and-dividend-adjusted or authoritative total-return history: resolvable rows {"latest_session": 0, "mean_per_session": 0.8571}; partially {"latest_session": 0, "mean_per_session": 0.0}; blocks BD-02, BD-08
- canonical three-month Treasury total-return history: resolvable rows {"latest_session": 0, "mean_per_session": 0.0}; partially {"latest_session": 0, "mean_per_session": 0.0}; blocks BD-08
- authoritative point-in-time sector membership and historical exchange calendar: resolvable rows {"latest_session": 0, "mean_per_session": 0.0}; partially {"latest_session": 0, "mean_per_session": 0.0}; blocks BD-08

## Genuine next product decisions

- **ND-01** (Founder (merge); Architect decision recorded): Founder merge of the auto-enrollment PR (migration 0020). The Architect APPROVED-WITH-AMENDMENTS; the PR must follow #493.. The corpus grows only when the user tracks a proposal, which keeps it small and selection-biased (BD-01). See project/reports/OUTCOME-INTELLIGENCE-001-ND-01-ARCHITECT-DECISION.md.
- **ND-02** (Founder): Whether to procure any capability in the OI-07 paid-capability gaps. The OI-07 report quantifies the rows each gap costs. Purchase is not delegated.
- **ND-03** (Architect): Whether to fund index-option modelling (ARCH-005 amendment) for SPX strategies such as CNDR. This is the SL-02 breadth blocker (BD-05). The work is mostly ASA-owned rather than a data purchase.
