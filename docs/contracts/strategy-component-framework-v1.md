# Strategy Component Framework v1

**Identity namespace/version:** `asa.strategy_component` / `v1`

ASA-ARCH-003 is authoritative. `strategies/components.py` implements the immutable Component Type
metadata and pure evaluator boundary. This contract defines component vocabulary; it does not
implement registry resolution, type compatibility, graph orchestration, or lifecycle callbacks.

## Component definition

Every Component Type declares:

- exact `(namespace, name, SemVer)` identity;
- one closed category: source, transform, predicate, aggregate, score, rank, constraint, proposal,
  or utility;
- named input and output ports with exact `StrategyTypeReference` name/version and single,
  optional, or many cardinality;
- typed parameter definitions with explicit required/default semantics;
- exact capability name/version requirements;
- an exact algorithm version;
- an immutable structured explanation template;
- immutable structured resource limits.

At least one output port is required. Port, parameter, and capability names are unique within
their respective collections. Keyed collections canonicalize by name before identity derivation.

`StrategyTypeReference` pins type identity without defining compatibility. STRAT-006 owns the
closed type catalog and compatibility rules. A Component or graph may not infer compatibility
from names or Python runtime types.

## Parameters and defaults

A required parameter has no default. An optional parameter declares whether a default is present,
so an explicit null default is distinguishable from no default. Defaults use the immutable
Strategy Manifest value contract. Decimal, Date, and Instant defaults share the manifest's
canonical literal rules and therefore cannot drift between authored and materialized values.

Core materializes defaults during graph compilation. Components do not read configuration or
environment state.

## Evaluation

Every implementation derives from `BaseComponent` and supplies exactly one operation:

```text
evaluate(immutable typed inputs, immutable effective parameters)
  -> immutable typed outputs
```

Implementations declare `__slots__ = ()` and retain no state. Evaluation is a pure synchronous
function. Components do not mutate inputs, retain values between evaluations, inspect scheduling,
discover peers, read a clock, perform I/O, or access services. Semantic time and other context are
ordinary explicit typed input ports.

Component lifecycle hooks do not exist. Core owns the closed lifecycle trace described by
ASA-ARCH-003 and records events around evaluation; a Component cannot intercept them or alter
control flow.

## Identity

Component identity is lowercase SHA-256 over canonical JSON containing the namespace/version,
complete definition metadata, ordered ports, materialized defaults, capabilities, algorithm
version, explanation template, and resource limits. Evaluator object identity, process state,
timestamps, source paths, registration order, and execution order are excluded.

Changing evaluator semantics requires a component semantic-version or algorithm-version change.
The registry will later bind the immutable definition to its evaluator and reject duplicates or
incompatible definitions.

## Capabilities are not permissions

Capabilities describe financial vocabulary for validation. They cannot authorize filesystem,
network, clock, randomness, provider, Observation, persistence, broker, execution, reflection,
imports, or runtime mutation. The Component framework exposes no API for those behaviors.
