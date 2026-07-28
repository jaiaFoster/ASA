# Derived Fact Contract

Status: Proposed — Founder merge required

A Derived Fact is an immutable, provider-neutral, point-in-time calculation
over canonical evidence. It is reusable financial knowledge, not strategy
judgment.

Required fields:

- `derived_fact_id`: stable semantic name;
- `value`: typed immutable value;
- `unit`: explicit interpretation of the value;
- `formula_version`: pinned calculation semantics;
- `effective_time`: timezone-aware semantic effective time;
- `input_evidence`: exact canonical evidence consumed;
- `quality_status`: `valid`, `degraded`, or `insufficient`.

Identity is a SHA-256 content hash over all fields plus the
`asa.derived_fact`/`v1` namespace. Execution timestamps, provider payloads,
strategy thresholds, weights, scores, and verdicts are excluded.

`DerivedFactSet` sorts by ID, rejects duplicate names, and provides named
lookup. Positional feature tuples are not a public contract.

## Ownership

`analytics/` owns ephemeral calculations. `indicators/` owns persisted,
cross-run derived indicators. A formula must have exactly one owner.

Strategies may consume Derived Facts and interpret them using versioned
manifest policy. Screening may orchestrate calculation but may not implement
financial formulas or reinterpret strategy decisions.

The initial registry contains realized volatility, implied forward volatility,
forward factor, earnings timing, expiration-gap measurements, normalized call
and put skew, historical skew location, IV-versus-realized spreads, momentum
dimensions, and raw option-liquidity dimensions.
