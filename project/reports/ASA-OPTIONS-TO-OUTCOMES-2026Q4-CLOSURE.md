# ASA-OPTIONS-TO-OUTCOMES-2026Q4 — Program Closure Report

- **Verdict:** `observation_pending`
- **Report checksum:** `c1b6a81c3cee24318aafb6070026c1644712b173a20533f8755807ed0b367d12`
- **OI-07 data-value verdict:** `evidence_insufficient` (`5795146b0c2a`)

## Evidence gates

| Gate | State | Detail |
|---|---|---|
| prior_sprints_closed | **pass** | all closed |
| forward_ledger_deployed | **pass** | latest eligible capture ledger_status=available |
| forward_outcome_observed | **pass** | observed horizons in the latest readable ledgers, by source (never pooled): user_tracked=3, system_actionable=198 |
| aoy_measured | **pass** | 15 eligible session(s), required 5 |
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

- AOY total: {"n": 15, "mean": 18.2, "median": 22.0, "min": 0.0, "max": 34.0}
- AOY options: {"n": 15, "mean": 17.8, "median": 21.0, "min": 0.0, "max": 34.0}
- AOY stocks: {"n": 15, "mean": 0.4, "median": 0.0, "min": 0.0, "max": 1.0}
- Evaluation coverage (mean): 1.0
- Strategy evaluation completion rate (mean): 0.7006
- Constructible rate after qualifying signals (mean): 0.637
- Trade-card completeness (mean): 0.637
- Median actionable evidence age at session close, seconds (mean of sessions): 3734.7143
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
| 2026-10-05 | `b87fbf7` | 25 | 25 | 0 | 1.0 | 0.6513 | 0.8929 | {"earnings_calendar_v1": 0.0074, "option_chain_v1": 0.005, "real_time_quote_v1": 0.003} |
| 2026-10-06 | `86e691d` | 29 | 29 | 0 | 1.0 | 0.6444 | 0.8788 | {"earnings_calendar_v1": 0.0114, "option_chain_v1": 0.0084, "real_time_quote_v1": 0.004} |
| 2026-10-07 | `86e691d` | 33 | 33 | 0 | 1.0 | 0.6483 | 0.9429 | {"earnings_calendar_v1": 0.0089, "option_chain_v1": 0.0079, "real_time_quote_v1": 0.005} |
| 2026-10-08 | `716bdab` | 25 | 25 | 0 | 1.0 | 0.629 | 0.8333 | {"earnings_calendar_v1": 0.0104, "historical_bars_v1": 0.0045, "option_chain_v1": 0.0079, "real_time_quote_v1": 0.005} |
| 2026-10-09 | `6744ca9` | 34 | 34 | 0 | 1.0 | 0.6528 | 0.85 | {"earnings_calendar_v1": 0.0124, "option_chain_v1": 0.0079, "real_time_quote_v1": 0.005} |
| 2026-10-12 | `ba1e253` | 1 | 1 | 0 | 1.0 | 0.5215 | 0.3333 | {"earnings_calendar_v1": 0.0059, "option_chain_v1": 0.0079, "real_time_quote_v1": 0.005} |
| 2026-10-13 | `70ec994` | 1 | 1 | 0 | 1.0 | 0.5186 | 0.1667 | {"earnings_calendar_v1": 0.0079, "option_chain_v1": 0.0084, "real_time_quote_v1": 0.005} |
| 2026-10-14 | `fd18952` | 0 | 0 | 0 | 1.0 | 0.5181 | 0.0 | {"earnings_calendar_v1": 0.0114, "option_chain_v1": 0.0084, "real_time_quote_v1": 0.005} |

## Forward-outcome corpus

- **System-actionable (ND-01)**, ledger `available`
  - earnings_calendar: 83 subject(s); horizons {"missed": 2, "observed": 172, "pending": 92}; n=172 with modeled P&L
  - spy_put_credit_spread: 14 subject(s); horizons {"observed": 26, "pending": 30}; n=26 with modeled P&L
- **User-tracked**, ledger `available`
  - forward_factor: 1 subject(s); horizons {"missed": 3}; n=0 with modeled P&L
  - spy_put_credit_spread: 1 subject(s); horizons {"observed": 3, "pending": 1}; n=3 with modeled P&L

## Remaining quantified data/provider blockers

- confirmed earnings calendar with announcement status and effective timestamps: resolvable rows {"latest_session": 0, "mean_per_session": 0.0}; partially {"latest_session": 23, "mean_per_session": 25.8667}; blocks BD-06
- complete option expiration, contract, quote, Greek, and implied-volatility evidence: resolvable rows {"latest_session": 17, "mean_per_session": 13.0667}; partially {"latest_session": 10, "mean_per_session": 7.2667}; blocks BD-07
- split-and-dividend-adjusted or authoritative total-return history: resolvable rows {"latest_session": 0, "mean_per_session": 1.0}; partially {"latest_session": 0, "mean_per_session": 0.0}; blocks BD-02, BD-08
- canonical three-month Treasury total-return history: resolvable rows {"latest_session": 0, "mean_per_session": 0.0}; partially {"latest_session": 0, "mean_per_session": 0.0}; blocks BD-08
- authoritative point-in-time sector membership and historical exchange calendar: resolvable rows {"latest_session": 0, "mean_per_session": 0.0}; partially {"latest_session": 0, "mean_per_session": 0.0}; blocks BD-08

## Genuine next product decisions

- **ND-01** (Founder (merge); Architect decision recorded): Founder merge of the auto-enrollment PR (migration 0020). The Architect APPROVED-WITH-AMENDMENTS; the PR must follow #493.. The corpus grows only when the user tracks a proposal, which keeps it small and selection-biased (BD-01). See project/reports/OUTCOME-INTELLIGENCE-001-ND-01-ARCHITECT-DECISION.md.
- **ND-02** (Founder): Whether to procure any capability in the OI-07 paid-capability gaps. The OI-07 report quantifies the rows each gap costs. Purchase is not delegated.
- **ND-03** (Architect): Whether to fund index-option modelling (ARCH-005 amendment) for SPX strategies such as CNDR. This is the SL-02 breadth blocker (BD-05). The work is mostly ASA-owned rather than a data purchase.
