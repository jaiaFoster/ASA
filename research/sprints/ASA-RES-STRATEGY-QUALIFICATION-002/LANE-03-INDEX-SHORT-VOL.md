# Lane 3 — Index short volatility: candidate survey and qualification

**Result:** **0 primaries.** One alternate is at DEEP_RESEARCH_REQUIRED.

## Candidates

| Candidate | Source | Role | State |
|---|---|---|---|
| [Bakshi-Kapadia daily delta-hedged index call](strategy-specifications/ASA-QS-SV-A1-BK-DELTA-HEDGED-INDEX-CALL.md) | BAKSHI-KAPADIA-2003 (full text) | ALTERNATE | DEEP_RESEARCH_REQUIRED |

**Surveyed, not specified:**

| Source | Finding | Why not a candidate |
|---|---|---|
| CARR-WU-2009 (full text, RFS 2009) | Synthetic 30-day variance swap rate (eq. 49, registered as DF-CW-SYNTHETIC-VARIANCE-SWAP-RATE-30D) against ex-post realized variance (eq. 51, DF-CW-REALIZED-VARIANCE-30D). Excess return RV/SW − 1; log risk premium ln(RV/SW); daily overlapping observations, 1996–2003. | A **measurement** of the variance risk premium. It defines no traded strategy: no entry schedule, sizing, replication-portfolio trading or exit. It supplies the variance-replication derived facts for the lane. |
| Israelov-Tummala | 2-page summary only | Insufficient depth |
| Cboe CNDR / BFLY (iron condor / butterfly) | Methodology recorded bibliographically in RES-001 | Four-leg P05 structures, not in the advanced SV bundle (X01 + P03). Not deep-researched here. |
| 0DTE short volatility | — | Excluded by the assignment, given the current unfavorable net-cost evidence. No new evidence was recovered to overturn it. |

## Lane-specific mathematics recovered

| Requirement | Source definition |
|---|---|
| Delta neutrality | BK: short Δ_t index units against one long call |
| Hedge frequency | BK: daily |
| Hedge equation | DF-BK-DELTA-HEDGED-GAIN (BK eq. for π) |
| Volatility estimator | BK: GARCH over the full sample (look-ahead) or historical volatility |
| Option selection | BK: every option-day passing the filters (14–60 days, ±10% moneyness, IV 1–100%) |
| Jump treatment | not separately modelled in the trading rule |
| Realized vs implied | CW eq. 49 vs eq. 51 |
| Turnover and costs | BK compare the gain per option (about $0.43) with the mean spread (about $0.375); no net result |

## Why zero

The lane asks for "two materially different expressions of the volatility-risk premium". The recovered full texts document the premium robustly (BK, CW), but neither defines a strategy with:
- an entry schedule;
- position sizing;
- an exit rule;
- net-of-cost results.

Building one would combine or invent rules, for example choosing a straddle strike, DTE and roll to wrap the BK or CW measurement. The no-invention rule forbids that.

**Next research step:** locate an explicit, independently evaluated SPX short-straddle or short-strangle rule set within the SV bundle (X01 + P03), such as an index methodology or a replicated academic rule with a roll schedule.
