# DATA-RELIABILITY-001 — REL-01 current missingness census boundary

Baseline: `main@7a2f8d90b565dac13f8bdf41f947985259080c5e`.

## Root finding

Production acquisition attempts are subject-scoped. `scheduled_screening`
constructs one plan identity per cycle and symbol, and subject-plan recording
stores that identity in the legacy `pair_evaluation_id` column. It is therefore
incorrect to infer a strategy from that column. Shared attempt evidence must be
joined to the exact declared strategy capability demands for the cycle.

The bounded deterministic census in `strategy_runtime/reliability_census.py`
does that join explicitly. It preserves provider diagnostic codes, typed latest
result reasons, scheduler diagnostic completeness, and an explicit authoritative
absence flag. A missing attempt becomes `acquisition_not_executed` only when the
cycle proves diagnostics complete; otherwise it remains an ASA-owned
`diagnostic_gap`.

## Ownership categories

The census distinguishes current usable, stale, acquisition not executed,
provider failure, entitlement/coverage, identity/mapping/canonicalization,
derivation/insufficient history, temporal unavailability, genuinely
unknown/unannounced, and diagnostic gaps. Every row carries one of:

- `asa_owned`
- `provider_external`
- `legitimately_unavailable`
- `unresolved`

`STALE_DATA` remains unresolved until REL-02 proves the freshness owner.
Provider `NO_DATA`/empty evidence is not called legitimate absence unless the
caller provides explicit authoritative-absence confirmation.

## Quantitative production state

The last immutable active-universe census remains the 2026-09-03 AC-02 capture:
574/1,509 active rows were `missing_data`, with zero untyped rows. That artifact
predates this sprint and cannot truthfully be relabeled current. This worker has
no linked production Railway project or production database/API credential in
the current environment, so a new production count is not fabricated.

The new census boundary makes the next authorized production capture capable of
dividing exact current demand into ASA-owned, provider/external, legitimately
unavailable, and unresolved buckets without strategy misattribution. REL-02 and
REL-03 now own the two known unresolved semantic classes: false freshness and
earnings clearance.
