# Lane 4 — Index covered call / buy-write: candidate survey and qualification

**Result:** **1 of 2** primaries at READY_WITH_EXPLICIT_UNKNOWNS (BXM). The second primary (BXMD) is DEEP_RESEARCH_REQUIRED. The alternate (BXY) is INSUFFICIENT_EVIDENCE.

## Candidates

| Candidate | Source | Role | State |
|---|---|---|---|
| [Cboe BXM (ATM)](strategy-specifications/ASA-QS-CC-01-CBOE-BXM.md) | CBOE-BUYWRITE-METHODOLOGY-2024 (full text); WILSHIRE-2019-CBOE; ISRAELOV-NIELSEN-2015-FAJ; ISRAELOV-KLEIN-TUMMALA-2018 (full text) | PRIMARY | READY_WITH_EXPLICIT_UNKNOWNS |
| [Cboe BXMD (30-delta)](strategy-specifications/ASA-QS-CC-02-CBOE-BXMD.md) | CBOE-BUYWRITE-METHODOLOGY-2024; CBOE-BXRT-METHODOLOGY; WILSHIRE-2019-CBOE | PRIMARY | DEEP_RESEARCH_REQUIRED |
| [Cboe BXY (2% OTM)](strategy-specifications/ASA-QS-CC-A1-CBOE-BXY.md) | CBOE-BUYWRITE-METHODOLOGY-2024 | ALTERNATE | INSUFFICIENT_EVIDENCE |

**Surveyed, not specified:**

| Source | Reason |
|---|---|
| Israelov-Nielsen "risk-managed covered call" | Trades S&P 500 exposure so the covered call's equity exposure stays constant. Sharpe improves from 0.37 to 0.52; volatility falls from 11.4% to 9.2%. The hedge schedule and instrument are described only at the level recovered here, and it needs A14. Recorded as a DEEP_RESEARCH lead, not a specification. |
| BXMVM (volatility-managed) | Methodology fetched to check delta inputs. It is a multi-leg structure outside the CC bundle. |

## Lane-specific mathematics

| Requirement | BXM | BXMD |
|---|---|---|
| Underlying position | long S&P 500 index (total return, with Div_t) | same |
| Notional ratio | 1:1 ("equal notional amounts") | same |
| Strike | min K ≥ S before 11:00 ET | OTM with Black delta closest to 0.30; ties → higher strike; **inputs UNKNOWN** |
| Maturity | next monthly | next monthly |
| Roll timing | third Friday; SOQ settle; VWAP 11:30–13:30 ET (since 2010-11-19) | VWAP 11:30–12:00 ET (since 2022-02-18) |
| Assignment / ex-dividend | not applicable (European, cash-settled SPX); dividends accrue in the index return | same |
| Return decomposition | Israelov-Nielsen: equity, short volatility, equity timing (timing is uncompensated) | same framework applies (INFERENCE) |
| Benchmark | the S&P 500 (Wilshire comparisons) | same |
| Costs | VWAP entry; indexes exclude costs; net UNKNOWN | same |

## Diversity rule

BXM vs BXMD is at the boundary of "do not represent covered call and a trivial delta variant as two independent strategies".

- **For distinctness:** different selection mechanism (index-level strike vs model delta), and documented differences in market-regime exposure: beta 0.55 vs 0.77, max drawdown −35.8% vs −42.7%.
- **Against:** under the Israelov-Nielsen decomposition, both are the same mechanism.

This is recorded for the Founder. It does not change BXMD's state, which is blocked independently.

## Why fewer than two ready

BXMD's strike depends on a Black-formula delta whose volatility, rate and dividend inputs are not stated in any Cboe methodology recovered, including BXRT, which was checked specifically. That is a signal-level unknown.

## Evidence uncertainties

- The evidence is sponsor-commissioned index history.
- Independent academic work (Israelov and co-authors) confirms the premium but argues the naive covered call carries uncompensated timing risk.
- Net-of-cost replication results are absent.
