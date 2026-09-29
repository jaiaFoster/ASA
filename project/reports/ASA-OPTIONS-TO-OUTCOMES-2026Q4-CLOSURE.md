# ASA-OPTIONS-TO-OUTCOMES-2026Q4 — Program Closure Report

- **Verdict:** `observation_pending`
- **Report checksum:** `76302aa78fcc0bc646c123b410b3f8fa23d4f478503764011c03a2632f449f40`
- **OI-07 data-value verdict:** `evidence_insufficient` (`10a0ed3a2c02`)

## Evidence gates

| Gate | State | Detail |
|---|---|---|
| prior_sprints_closed | **pass** | all closed |
| forward_ledger_deployed | **pass** | latest eligible capture ledger_status=available |
| forward_outcome_observed | **pass** | observed horizons in the latest readable ledgers, by source (never pooled): user_tracked=1, system_actionable=16 |
| aoy_measured | **pending** | 4 eligible session(s), required 5 |
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

- AOY total: {"n": 4, "mean": 13.25, "median": 14.0, "min": 3.0, "max": 22.0}
- AOY options: {"n": 4, "mean": 12.25, "median": 13.0, "min": 2.0, "max": 21.0}
- AOY stocks: {"n": 4, "mean": 1.0, "median": 1.0, "min": 1.0, "max": 1.0}
- Evaluation coverage (mean): 1.0
- Strategy evaluation completion rate (mean): 0.8399
- Constructible rate after qualifying signals (mean): 0.6635
- Trade-card completeness (mean): 0.6635
- Median actionable evidence age at session close, seconds (mean of sessions): 2671.9
- Unexplained drops (total): 0

| Session | SHA | AOY | Options | Stocks | Coverage | Completion | Constructible | Provider-limited |
|---|---|---|---|---|---|---|---|---|
| 2026-09-24 | `d52146f` | 3 | 2 | 1 | 1.0 | 0.7269 | 0.4 | {"earnings_calendar_v1": 0.0126, "historical_bars_v1": 0.0007, "option_chain_v1": 0.0073, "real_time_quote_v1": 0.002} |
| 2026-09-25 | `0f00dfa` | 11 | 10 | 1 | 1.0 | 0.8823 | 0.7143 | {"earnings_calendar_v1": 0.0106, "historical_bars_v1": 0.0007, "option_chain_v1": 0.0073, "real_time_quote_v1": 0.002} |
| 2026-09-28 | `6b91b54` | 17 | 16 | 1 | 1.0 | 0.8758 | 0.7619 | {"earnings_calendar_v1": 0.0112, "historical_bars_v1": 0.0007, "option_chain_v1": 0.0086, "real_time_quote_v1": 0.002} |
| 2026-09-29 | `3f7eaaf` | 22 | 21 | 1 | 1.0 | 0.8745 | 0.7778 | {"earnings_calendar_v1": 0.0112, "historical_bars_v1": 0.0007, "option_chain_v1": 0.0066, "real_time_quote_v1": 0.002} |

## Forward-outcome corpus

- **System-actionable (ND-01)**, ledger `available`
  - earnings_calendar: 21 subject(s); horizons {"observed": 14, "pending": 65}; n=14 with modeled P&L
  - spy_put_credit_spread: 3 subject(s); horizons {"observed": 2, "pending": 10}; n=2 with modeled P&L
- **User-tracked**, ledger `available`
  - forward_factor: 1 subject(s); horizons {"missed": 3}; n=0 with modeled P&L
  - spy_put_credit_spread: 1 subject(s); horizons {"observed": 1, "pending": 3}; n=1 with modeled P&L

## Remaining quantified data/provider blockers

- confirmed earnings calendar with announcement status and effective timestamps: resolvable rows {"latest_session": 0, "mean_per_session": 0.0}; partially {"latest_session": 17, "mean_per_session": 17.25}; blocks BD-06
- complete option expiration, contract, quote, Greek, and implied-volatility evidence: resolvable rows {"latest_session": 10, "mean_per_session": 10.75}; partially {"latest_session": 3, "mean_per_session": 3.5}; blocks BD-07
- split-and-dividend-adjusted or authoritative total-return history: resolvable rows {"latest_session": 1, "mean_per_session": 1.0}; partially {"latest_session": 0, "mean_per_session": 0.0}; blocks BD-02, BD-08
- canonical three-month Treasury total-return history: resolvable rows {"latest_session": 0, "mean_per_session": 0.0}; partially {"latest_session": 0, "mean_per_session": 0.0}; blocks BD-08
- authoritative point-in-time sector membership and historical exchange calendar: resolvable rows {"latest_session": 0, "mean_per_session": 0.0}; partially {"latest_session": 0, "mean_per_session": 0.0}; blocks BD-08

## Genuine next product decisions

- **ND-01** (Founder (merge); Architect decision recorded): Founder merge of the auto-enrollment PR (migration 0020). The Architect APPROVED-WITH-AMENDMENTS; the PR must follow #493.. The corpus grows only when the user tracks a proposal, which keeps it small and selection-biased (BD-01). See project/reports/OUTCOME-INTELLIGENCE-001-ND-01-ARCHITECT-DECISION.md.
- **ND-02** (Founder): Whether to procure any capability in the OI-07 paid-capability gaps. The OI-07 report quantifies the rows each gap costs. Purchase is not delegated.
- **ND-03** (Architect): Whether to fund index-option modelling (ARCH-005 amendment) for SPX strategies such as CNDR. This is the SL-02 breadth blocker (BD-05). The work is mostly ASA-owned rather than a data purchase.
