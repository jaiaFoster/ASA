# STRATEGY-PRODUCTION-001 — SP-03A

Primary ticket: `SP-03A` — P01 and A15 cash-secured put collateral.

## Outcome

The generic execution-readiness owner now resolves `StructureKind.SINGLE_LEG`
for one exact option contract with either direction and any positive unit or
non-unit quantity. Exact contract identity flows through the existing generic
assessment and trade-proposal surfaces; no PUT/PUTY strategy identifier is
present in the primitive.

`DF-CASH-SECURED-PUT-COLLATERAL@1.0.0` is the analytics-owned collateral
formula. It computes the present Treasury collateral required to fund the full
strike obligation at expiration. Missing or invalid collateral return is typed
UNKNOWN; it never becomes zero-return cash. This capital fact is distinct from
terminal option maximum loss and from vertical-spread margin.

The existing `DF-CBOE-TBILL-DAILY-ACCRUAL@1.0.0` remains the single Treasury
accrual owner. SP-03B may compose these generic facts with the complete sourced
Cboe contract-count lifecycle; SP-03A introduces no strategy policy.

## Verification

- P01 long/short, unit/non-unit, exact identity, assessment and proposal vectors: green.
- Cash-collateral value, typed UNKNOWN, formula identity/version vectors: green.
- Full repository on rebased exact head: `3,856 passed, 50 skipped`.
- Architecture, static, and Lean validation are recorded on the PR.
