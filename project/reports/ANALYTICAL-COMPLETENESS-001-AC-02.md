# ANALYTICAL-COMPLETENESS-001 — AC-02 typed missing-data census

Captured at `2026-09-03T19:29:01.675506Z` from production
`508eab2d733c140e7d97bee67f8cb5f3ba515470`, API snapshot
`6e75a1db8259f2a82c6520ac0c400958e9889e1f5cbab7521bff2fd909205231`.
Only the 1,509 canonical active identities established by AC-01 are included.

## Exact census

| Strategy | Stable reason | Count | Examples | Classification |
|---|---|---:|---|---|
| earnings_calendar | `missing_earnings_date` | 38 | A, ADI, ADSK, AVGO, BBY | unresolved external dependency |
| earnings_calendar | `no_valid_expiration_pair` | 374 | AAPL, ABBV, ABNB, ACGL, ADBE | legitimate domain/policy absence |
| earnings_calendar | `subject_preparation_failed` | 2 | CPRT, FDS | proven software defect AC02-D01 |
| forward_factor | `missing_implied_volatility` | 5 | APTV, FITB, HONA, Q, SPGI | unresolved external dependency |
| forward_factor | `no_valid_expiration_pair` | 131 | AEE, ALL, ALLE, AMCR, APD | legitimate domain/policy absence |
| forward_factor | `non_positive_forward_variance` | 11 | BAX, CCL, HAL, IP, KIM | legitimate derived-domain absence |
| forward_factor | `subject_preparation_failed` | 2 | CPRT, FDS | proven software defect AC02-D01 |
| skew_momentum | `missing_implied_volatility` | 4 | BDX, HONA, Q, VICI | unresolved external dependency |
| skew_momentum | `no_future_expiration` | 3 | BF.B, BRK.B, NVR | unresolved external dependency |
| skew_momentum | `subject_preparation_failed` | 2 | CPRT, FDS | proven software defect AC02-D01 |
| skew_momentum | `unusable_quote` | 2 | AVB, EQR | unresolved external dependency |

Totals: 574 active `missing_data` rows; 574 stable primary typed reasons;
zero untyped rows. Strategy totals are Earnings Calendar 414, Forward Factor
149, and Skew Momentum 11.

`missing_data` remains unchanged. The classification does not convert evidence
absence into `no_signal` and does not assert that unresolved provider evidence
is legitimate absence without proof.

## AC-03 defect inventory

### AC02-D01 — shared subject preparation fails for CPRT and FDS

- Scope: six active identities, both subjects across all three strategies.
- Evidence: stable `subject_preparation_failed` blocker and unavailable temporal
  metadata for every sibling strategy on each subject.
- Owning boundary to reproduce: shared subject preparation before independent
  strategy knowledge projection.
- Required correction: identify the exact exception and repair it at its owner;
  do not add strategy-specific fallback or hide the failure.

No other software defect is authorized for AC-03 by this census. A new proven
defect must first amend this artifact within AC-02 scope.

## Stable diagnostic projection

The existing blocker prefix already owns stable reason IDs. Strategy health now
projects one normalized primary reason per incomplete result and retains verbose
detail only on the underlying result. Therefore reason totals reconcile exactly
without inventing a second diagnostic taxonomy.
