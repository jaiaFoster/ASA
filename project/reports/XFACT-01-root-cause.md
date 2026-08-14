# XFACT-01 — Root Cause and Cross-Subject Boundary

## Root causes

- `call_skew_zscore` and `put_skew_zscore`: the scheduled production root
  resolved the default Postgres historical-skew repository, then passed the
  unresolved optional injection argument to the subject-first registry. With
  normal production construction that argument is `None`, so the Skew binding
  received no historical observations and could not materialize either fact.
- `cross_sectional_percentile` and `sector_relative_return`: subject-first
  preparation correctly seals one subject at a time, but no provider-free
  post-preparation owner materializes facts across the cycle's already-sealed
  subject knowledge. The Skew adapter therefore explicitly supplies `None`.

## Existing owners

- Cross-subject evidence contracts: `domain/strategy_evidence.py`.
- Registered formulas and versions: `analytics/derived_facts.py`.
- Immutable fact identity/materialization: `analytics/features.py` and
  `analytics/derived_fact_materialization.py`.
- Configured-universe asset and authoritative GICS/Select Sector SPDR mappings:
  `strategy_runtime/comparison_universe.py`.
- Subject-local read-only knowledge: `strategy_runtime/knowledge.py`.

Existing evidence references can pin every contributing canonical fact; no new
evidence kind is needed. Cross-subject identity must additionally bind the
ordered cohort/member identities and relevant input fact identities through
materialization parameters/digest.

## Correct boundary

Correct the historical-repository dependency at the production composition
root. Materialize comparison and sector facts in a provider-free,
strategy-neutral post-preparation stage over the cycle's sealed read-only
knowledge. Consumers bind those immutable facts declaratively. Missing cohort
coverage or authoritative sector/reference membership remains a specific typed
UNKNOWN; no peer, sector, or proxy is invented.
