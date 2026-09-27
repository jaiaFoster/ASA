# Lane 2 — Index put writing: candidate survey and qualification

**Result:** **1 of 2** primaries at READY_WITH_EXPLICIT_UNKNOWNS (Cboe PUT). The second primary (WPUT) is DEEP_RESEARCH_REQUIRED. The alternate (PUTY) is complete but INSUFFICIENT_EVIDENCE.

## Candidates

| Candidate | Source | Role | State |
|---|---|---|---|
| [Cboe PUT](strategy-specifications/ASA-QS-PW-01-CBOE-PUT.md) | CBOE-PUTWRITE-METHODOLOGY-2024 (full text); BONDARENKO-2019-CBOE, WILSHIRE-2019-CBOE, ENNISKNUPP-2008-PUT (full text) | PRIMARY | READY_WITH_EXPLICIT_UNKNOWNS |
| [Cboe WPUT](strategy-specifications/ASA-QS-PW-02-CBOE-WPUT.md) | CBOE-PUTWRITE-INDICES-METHODOLOGY-2024; BONDARENKO-2019-CBOE | PRIMARY | DEEP_RESEARCH_REQUIRED |
| [Cboe PUTY (2% OTM)](strategy-specifications/ASA-QS-PW-A1-CBOE-PUTY.md) | CBOE-PUTWRITE-INDICES-METHODOLOGY-2024 | ALTERNATE | INSUFFICIENT_EVIDENCE |

**Surveyed, not specified:**

| Source | Reason |
|---|---|
| PWT (PUT with a TWAP-of-bids sale price) | Same document as PUT, differing only in the execution price. A cosmetic variant of PUT, noted in the PUT spec as a sourced quote-only pricing sibling. |
| PUTR, WPTR (Russell 2000), PTLT (TLT) | Other underlyings; outside the S&P 500 index-option scope of the PW bundle. |
| SANTACLARA-SARETTO-2009 | Margin and "good deals" analysis (full text located, not reviewed in this sprint). |

## Lane-specific mathematics

| Requirement | PUT | WPUT | PUTY |
|---|---|---|---|
| Strike / moneyness | max listed K ≤ S before 11:00 ET | max K < SOQ (AM days) or < last value before 4:00 p.m. (PM days) | max K < 0.98·S before 11:00 ET |
| Collateral | 1-month + 3-month T-bills; fully collateralized (DF-CBOE-PUT-CONTRACT-COUNT) | K in 4-week bills | K in 4-week bills |
| Settlement | SOQ, AM | SOQ (AM days); buy back at the last ask before 4:00 p.m. (PM days) | SOQ |
| Roll | third Friday (preceding business day on holiday) | every Friday | third Friday |
| Treasury return | DF-CBOE-TBILL-DAILY-ACCRUAL (n = 28 / 91) | n = 28; no accrual on roll day | n = 28; no accrual on roll day |
| Crash loss | PUT max drawdown −32.7% (Bondarenko) / −35.5% (Wilshire); S&P 500 −50.9% | WPUT max drawdown −24.2% (2006–2018) | not recovered |
| Costs | VWAP entry; indexes exclude commissions and taxes; net UNKNOWN | bid entry, ask buy-back | VWAP entry |

**SPX vs SPY.** Every figure is an SPX index figure. No result is transferred to SPY.

## Why fewer than two ready

- **WPUT.** The methodology picks the AM-day strike "below the SOQ" but prices the premium at the "first bid quote … after 9:30 a.m. ET". The SOQ is generally not known at that time, so the live ordering is undefined on every third-Friday roll. Resolution requires Cboe clarification.
- **PUTY.** A fully specified, systematically OTM second candidate, but no performance evidence for it was recovered.

## Evidence uncertainties

- All evidence is index back-fill published or commissioned by the index owner (Cboe).
- Net-of-cost results for replication are absent.
- After launch (2006–2018), PUT's Sharpe ratio (0.50) did not exceed the S&P 500's (0.51).

## Closeout disposition (2026-09-27)

**Selected:** PUT (PW-01) and PUTY (PW-A1). PUTY was promoted after exact-rule evidence was recovered from the Cboe factsheet (1986–2026: 6.9% annualized, volatility 8.7%, max drawdown −28.9%). WPUT is not selected: the AM-roll blocker is unresolved. See [FINAL-SELECTION.md](FINAL-SELECTION.md).
