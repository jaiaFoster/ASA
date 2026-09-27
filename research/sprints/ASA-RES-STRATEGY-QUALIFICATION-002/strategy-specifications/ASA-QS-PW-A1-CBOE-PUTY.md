# ASA-QS-PW-A1-CBOE-PUTY — Cboe S&P 500 2% OTM PutWrite (PUTY)

- **Lane:** 2, index put writing
- **Role:** ALTERNATE
- **Qualification state:** **INSUFFICIENT_EVIDENCE**
  - The specification is complete, and the equality edge case is typed.
  - No performance evidence for this exact rule was recovered.
- **Source methodology version:** [`CBOE-PUTWRITE-INDICES-METHODOLOGY-2024`](../../../sources/CBOE-PUTWRITE-INDICES-METHODOLOGY-2024.yaml). PUTY base date June 30, 1986; launched February 15, 2019.

## Why it is the alternate, not a primary

PUTY is the lane's only recovered **systematically OTM** specification. The lane requirements name ATM vs systematically OTM as a legitimate axis of differentiation.

This sprint recovered no performance statistics for PUTY:
- Bondarenko 2019 covers PUT, WPUT and PPUT.
- Wilshire 2019 covers BXM, BXMD, PUT, CMBO and PPUT.

Evidence therefore does not support advancement for return-seeking use. The specification is recorded so that it is ready if evidence is recovered.

## Specification

| Element | Rule | Class |
|---|---|---|
| Universe | listed SPX puts with the next monthly expiration on the roll date (X01) | — |
| Roll date | third Friday; preceding business day on holiday (`DF-THIRD-FRIDAY-ROLL-DATE`) | DERIVED_FACT |
| Reference | S_ref = last S&P 500 value disseminated before 11:00 a.m. ET (G-CBOE-SPX-REF-BEFORE-1100) | CANONICAL_FACT + gate |
| Strike | K* = max{ K(c) : K(c) < 0.98·S_ref }. "First available strike below 98%"; strictness DERIVED as for WPUT. Equality → AMBIGUOUS_SELECTION (G-PUTY-STRIKE-EXISTS). | STRUCTURE_SELECTION_RULE |
| Leg | short 1× put per unit notional (P01) | STRUCTURE |
| Sale price | VWAP 11:30 a.m.–12:00 p.m. ET via OPRA, excluding late, cancelled and spread trades; last bid before the end of the window if no trades | PARAMETER |
| Collateral | notional = K invested in a T-bill account at the 4-week bank-discount rate (`DF-CBOE-TBILL-DAILY-ACCRUAL`, n = 28); no accrual on roll day | LIFECYCLE |
| Roll-day return | (1 + R1)(1 + R2): R1 from the previous close to SOQ settlement, R2 from the VWAP sale to the close | DERIVED_FACT |
| Exit | hold to expiry; settle max(0, K_old − SOQ) | LIFECYCLE |
| Stops, targets | none (not sourced) | — |
| Score | NONE | — |
| Direction | delta positive (smaller than PUT); volatility negative; theta positive; skew negative | — |
| Sizing | notional K per unit in bills, fully collateralized | sourced |
| Costs | VWAP entry; commissions excluded; net UNKNOWN | sourced / UNKNOWN |
| Liquidity gates | none sourced | — |

### Verdict truth table

Identical in form to ASA-QS-PW-01 §7, with G-PUTY-STRIKE-EXISTS in place of G-PUT-STRIKE-EXISTS. An AMBIGUOUS_SELECTION result maps to UNKNOWN.

### UNKNOWN states

The same as PUT, plus the equality case above.

## Evidence

| Item | Status |
|---|---|
| Exact-strategy evidence | **not recovered** |
| Phenomenon evidence | shared with PUT (index volatility risk premium) — **indirect only, not reportable as PUTY's own evidence** |
| Net | UNKNOWN |

## ASA translation (summary)

- **Primitives:** P01, X01, X02a, X04.
- **Derived facts:** DF-THIRD-FRIDAY-ROLL-DATE, DF-CBOE-TBILL-DAILY-ACCRUAL, DF-OPT-MID.
- **Architect review:** tracking-price scope only (GAP-OPTION-TRADE-PRINTS), as for PUT.

**Manifest readiness:** a manifest could be authored mechanically. Advancement is blocked on evidence, not specification.
