# Strategy Manifest Wire Contract v1

**Schema version:** `1.0.0`

**Identity namespace/version:** `asa.strategy_manifest` / `v1`

ASA-ARCH-003 is the architecture authority. `strategies/manifest.py` is the executable schema,
canonical serializer, strict decoder, and deterministic identity implementation for this wire
contract.

## Canonical document

A Strategy Manifest is a UTF-8 JSON object with exactly these fields:

| Field | Shape | Meaning |
|---|---|---|
| `schema_version` | SemVer string | Exact supported document schema version |
| `strategy_id` | identifier string | Immutable strategy identity |
| `strategy_version` | SemVer string | Semantic version of this strategy definition |
| `metadata` | metadata object | Display-only name, description, and tags |
| `parameters` | parameter array | Effective typed strategy parameters |
| `required_capabilities` | capability array | Exact capability name/version requirements |
| `nodes` | node array | Exact component instances and typed parameter bindings |
| `edges` | edge array | Directed output-port to input-port connections |
| `outputs` | output array | Named graph outputs |
| `events` | event-binding array | Declarative trace-field selections |

Unknown and missing fields are errors at every object level. JSON duplicate keys are errors.
Empty node and output collections are errors.

## Nested records

```text
metadata = {
  name: string,
  description: string,
  tags: [string]
}

parameter = {
  name: identifier,
  type_ref: identifier,
  value: immutable JSON value
}

capability = {
  name: identifier,
  version: exact SemVer
}

node = {
  node_id: identifier,
  component: {
    namespace: identifier,
    name: identifier,
    version: exact SemVer
  },
  parameters: [parameter]
}

edge = {
  source_node_id: identifier,
  source_port: identifier,
  target_node_id: identifier,
  target_port: identifier
}

output = {
  name: identifier,
  node_id: identifier,
  port: identifier
}

event_binding = {
  event: lifecycle event,
  node_id: identifier | null,
  explanation_fields: [identifier]
}
```

The v1 lifecycle event vocabulary is `manifest_validated`, `graph_compiled`,
`evaluation_started`, `node_started`, `node_completed`, `node_failed`,
`evaluation_completed`, and `evaluation_failed`. These bindings select structured trace fields;
they are not callbacks and cannot change control flow.

## Value rules

Manifest values may contain null, Boolean, integer, string, immutable arrays, and string-keyed
objects. Binary floating-point JSON values are forbidden. Decimal, Date, and Instant parameters
are strings interpreted from their explicit `type_ref`:

- `Decimal` is normalized to a finite base-10 string without exponent or insignificant trailing
  zeroes; negative zero becomes `0`.
- `Date` uses ISO-8601 `YYYY-MM-DD` form.
- `Instant` must include an offset and is normalized to an ISO-8601 UTC value.

The Strategy Type System may add validation for other exact `type_ref` values; it cannot change
these canonical wire rules without a versioned contract change.

## Canonicalization

Canonical JSON uses lexicographically sorted object keys, no insignificant whitespace, UTF-8
without ASCII escaping, and no NaN or infinity. Schema-owned collections that have set or keyed
semantics are sorted before serialization:

- metadata tags;
- strategy and node parameters by name;
- capabilities by name/version;
- nodes by node ID;
- edges by their complete endpoint tuple;
- outputs by name/node/port;
- event bindings by event/node.

Arrays inside a parameter value preserve their authored order. This is semantic order.

## Identity

Manifest identity is lowercase SHA-256 over canonical JSON containing:

- identity namespace and version;
- schema, strategy, and exact component versions;
- effective parameters;
- capability requirements;
- nodes, edges, outputs, and event bindings.

Display metadata is excluded, so renaming or retagging a strategy changes serialized document
bytes but not semantic identity. Timestamps, file paths, input enumeration order, runtime state,
and execution order do not exist in the schema and cannot enter identity.

## Versioning

The v1 implementation accepts only schema version `1.0.0`; unknown versions fail closed. Runtime
resolution never treats `latest`, ranges, or compatible-looking versions as exact versions.

A semantic graph change requires a new `strategy_version`. A schema migration produces a new
manifest value and never mutates the prior value. Future minor schema versions may add only
optional semantics-preserving fields. Major versions may be incompatible and require an explicit
migration; the decoder never guesses or silently upgrades.

## Deferred validation

STRAT-002 validates serialized structure and identity only. Component availability, parameter
schema compatibility, port typing/cardinality, DAG cycles and reachability, declared capabilities,
dead nodes, lifecycle applicability, and graph execution are validated by the later Component,
Type System, Registry, and Graph Runtime tickets. Deferral does not make an uncompiled manifest
executable.
