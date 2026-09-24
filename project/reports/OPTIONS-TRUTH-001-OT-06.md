# OPTIONS-TRUTH-001 — OT-06 market-session validation and closure

State: `OBSERVATION_PASS` → `CLOSED`
Operational issue: [#466](https://github.com/jaiaFoster/ASA/issues/466)
Production SHA observed: `d6d4c8d65ea45655a8a893b7ab0fa2df10328663` (verified via `/api/v1/version`;
contains OT-01, OT-02, OT-03, and OT-05)
Session: regular US equity session, Thursday 2026-09-24 (~12:25–12:33 ET)

## Method

Both captures are read-only GETs against the deployed Agent Data API. They
perform no refresh, acquisition, tracking, or broker call, and record no
credentials or raw provider payloads.

1. `tools/options_truth/earnings_cohort.py` (OT-03), captured
   `2026-09-24T16:24:55Z` → [`OPTIONS-TRUTH-001-OT-06-cohort.json`](OPTIONS-TRUTH-001-OT-06-cohort.json)
2. `tools/options_truth/funnel_census.py` (new; traces **every** active
   option-strategy row through its OT-02 funnel), captured
   `2026-09-24T16:33:15Z` → [`OPTIONS-TRUTH-001-OT-06-census.json`](OPTIONS-TRUTH-001-OT-06-census.json)

## Funnel census: every active option-strategy row

| Strategy | Active | Traced | Actionable | Structure unavailable/unknown | Strategy rejected | Typed evidence gap | Unexplained |
|---|---:|---:|---:|---:|---:|---:|---:|
| earnings_calendar | 503 | 503 | 4 | 1 | 166 | 332 | 0 |
| forward_factor | 503 | 503 | 0 | 2 | 389 | 112 | 0 |
| skew_momentum | 503 | 503 | 0 | 0 | 483 | 20 | 0 |

**1,509 / 1,509 rows traced; zero unexplained drops.** No row terminates in
`structure_unresolved` (qualifying signal without current readiness).

Typed evidence-gap reasons, all within the OT-01 source semantics:

- Earnings Calendar: `no_valid_expiration_pair` 298, `missing_earnings_date` 18,
  `missing_implied_volatility` 11, `unusable_phase_two_evidence` 5.
- Forward Factor: `no_valid_expiration_pair` 93, `missing_implied_volatility` 12,
  `non_positive_forward_variance` 3, `unusable_option_chain` 2,
  `no_usable_expiration_pair` 1, `unusable_quote` 1.
- Skew Momentum: `no_future_expiration` 12, `no_call_contracts_at_selected_expiration` 3,
  `unusable_option_chain` 3, `unusable_quote` 2.

## Earnings Calendar bounded cohort (30 of 503)

| Classification | Count |
|---|---:|
| true_strategy_rejection | 17 |
| legitimate_temporal_or_policy_absence (`no_valid_expiration_pair`) | 12 |
| provider_entitlement_or_coverage (`missing_earnings_date`) | 1 |
| asa_defect | **0** |
| legitimate_unknown | 0 |

Earnings Calendar behavior is explainable for every sampled earnings
candidate.

## Acceptance

- Bounded live cohort proves complete funnel traceability: **pass**.
- Earnings Calendar behavior explainable on actual earnings candidates: **pass**.
- Zero unexplained candidate loss: **pass**. The census covers all three option
  strategies, not only the cohort.

## Closure record

- Discrepancies: OT-01 found zero clear implementation discrepancies. None
  fixed or deferred.
- Corrections reopened: none. OT-04 stays closed.
- Typed external limits: provider coverage for earnings dates (18 symbols) and
  implied volatility (23 strategy rows). This is quantified here but
  procurement is **not** escalated: it does not block the product path, and
  constructible opportunities are observed on current data.
- Tests: collector/census unit and replay tests in `tests/tools/`.
- Earlier captures were not re-run on a newer SHA. Any later falsifying
  observation reopens this sprint per the program rule.

OPTIONS-TRUTH-001 is closed.
