# ANALYTICAL-COMPLETENESS-001 — AC-04 zero-pass causal proof

## Captured state

- Production release: `1aa93e548e762ab0e2b9f5af16b1f57efebcc1dc`
- Latest-state snapshot/checksum: `1e3ea47cb34793d73085b6483a13a8b784dbce31f9b1d8cfba5d1aac7552201e`
- Scope: canonical active S&P 500 subjects only
- Forward Factor: 354 evaluated, 149 missing data
- Skew Momentum: 492 evaluated, 11 missing data

Missing-data causality is owned by the merged AC-02/AC-03 census and repair.
This artifact addresses only whether a generic default, projection, or version
defect suppresses PASS among evaluated results.

## Forward Factor

### Deterministic distribution

| Native-score band | Eligible | Count |
| --- | ---: | ---: |
| below WATCH (`< 0.12`) | false | 280 |
| below WATCH (`< 0.12`) | true | 14 |
| WATCH (`>= 0.12`, `< 0.20`) | false | 28 |
| PASS (`>= 0.20`) | false | 32 |

Gate counts over the same 354 evaluated rows:

- `structure_constructible_gate=true`: 354
- `earnings_exclusion_gate=true/false`: 63 / 291
- `liquidity_gate=true/false`: 152 / 202
- `eligible=true/false`: 14 / 340

No row simultaneously has a PASS score and `eligible=true`. The highest
eligible score is CIEN at `0.079617479673689012104134495510416`, below the
WATCH boundary. Conversely, the lowest PASS-band but ineligible score is HCA
at `0.204585595846352170669640359664539`. This proves the zero-PASS result is
the intersection of current score and declared eligibility policy, not a
missing/null/default verdict projection.

The production rows uniformly carry `forward_factor@1.0.0` and
`implied_forward_volatility@1.0.0`. The exact `0.20` PASS boundary and an
otherwise-identical ineligible counterexample are pinned by
`tests/strategies/test_stonk_manifests.py::test_forward_factor_manifest_requires_source_iv_and_builds_double_calendar`.

## Skew Momentum

### Deterministic distribution

| Bullish core | Bearish core | Momentum complete | Count |
| --- | --- | --- | ---: |
| false | false | false | 401 |
| false | unknown | false | 61 |
| unknown | false | false | 19 |
| unknown | unknown | false | 11 |

No evaluated row has a true bullish or bearish core gate. The underlying
volatility-value conditions independently reconcile to the same population:

- neither call nor put value gate: 401
- put only: 61
- call only: 19
- both: 11

The remaining historical-stretch input is not silently defaulted: valid
historical observation counts are 0 for 470 subjects, 1 for 2, 2 for 2, and 3
for 18. All remain below the declared research minimum of 40, so the associated
z-score is correctly unknown. Momentum completeness is false for all 492 rows,
but it is not causal to zero PASS because no directional core qualifies first.

All production derived facts carry their expected `1.0.0` formula versions:
normalized call/put skew, call/put z-score, ATM-IV-minus-RV,
wing-IV-minus-RV, time-series return, cross-sectional percentile, and
sector-relative return. Exact research-policy boundaries, PASS, WATCH, FAIL,
unknown-history, one-directional-core, and incomplete-momentum vectors are
pinned by:

- `tests/strategies/test_stonk_manifests.py::test_skew_research_policy_boundaries_and_unknown_evidence`
- `tests/strategies/test_stonk_manifests.py::test_skew_research_policy_requires_one_true_directional_core_gate`

## Conclusion

The observed zero-PASS populations are causally consistent with the currently
authorized strategy policies and current evidence. No generic default, null,
projection, or formula-version defect suppresses PASS. No strategy parameter,
threshold, formula, or evidence value was changed.

The capture also shows prospective skew-history accumulation has not yet met
the research minimum. That is an evidence-state observation, not authority to
weaken the policy or fabricate history.
