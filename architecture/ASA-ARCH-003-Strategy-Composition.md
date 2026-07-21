# ASA-ARCH-003: Strategy Composition Architecture

**Status:** Proposed — Founder merge required

**Date:** 2026-07-21

**Sprint:** SPRINT-002

**Patch:** STRAT-001

## Context

ASA currently has a deterministic Strategy Layer, but it does not yet have a canonical way to
describe a strategy as data, validate its structure, or execute a composition of reusable
financial components. SPRINT-002 needs one frozen contract before it can define a manifest,
component framework, registry, graph runtime, type system, expression engine, plugin SDK, or
reference strategy.

This decision extends the existing intelligence pipeline without changing its ownership. It is
governed by the Constitution: Strategies consume established knowledge rather than provider data;
calculation ownership remains singular; evaluation is deterministic; recommendations remain
explainable; and ASA stays read-only. The graph system is a representation and orchestration
mechanism inside the Strategy Layer, not a new pipeline stage.

## Decision Summary

1. A **Strategy Manifest** is the complete canonical serialized definition of a strategy.
2. A **Strategy Graph** is the validated, immutable directed acyclic graph derived from exactly one
   manifest and is the sole source of strategy execution.
3. **Core** owns manifest validation, type checking, deterministic graph ordering, orchestration,
   tracing, replay verification, and the closed expression evaluator.
4. **Components** own bounded financial transformations expressed through typed, immutable values.
5. **Plugins** may contribute additional component types through explicit static registration.
   They cannot alter Core, choose execution order, bypass validation, or add runtime behavior.
6. The visual editor is a possible future manifest-authoring interface. It has no special runtime
   authority and is outside SPRINT-002.

## Scope and Boundaries

The Strategy Composition system lives within the existing Strategy Layer:

```text
Canonical Facts + Indicators
            │
            ▼
      Strategy Manifest
            │ validate and compile
            ▼
       Strategy Graph
            │ deterministic evaluation
            ▼
        Opportunity
            │
            ▼
 Guardrails → Ranking → operational analytical pipeline
```

The runtime may consume only immutable Canonical Facts, Indicators, explicit evaluation context,
manifest parameters, and upstream values produced by nodes in the same graph. It must not access
providers, Observations, repositories, infrastructure, presentation, brokers, filesystems,
networks, clocks, environment variables, random sources, language models, or mutable global state.

The runtime does not replace Indicators, Guardrails, Ranking, Position Proposal, Portfolio, or
Execution Planning. A component may select and transform established knowledge to produce a
candidate Opportunity; it may not privately recreate a shared Indicator or embed platform-owned
Guardrail policy.

## Canonical Terms

- **Strategy Manifest:** the immutable, versioned serialized strategy definition and canonical
  source of truth.
- **Strategy Graph:** the validated in-memory graph compiled from one manifest.
- **Component Type:** a versioned contract describing one deterministic operation, its ports,
  parameters, capabilities, and evaluator.
- **Node:** one manifest instance of a Component Type with an immutable node ID and explicit
  parameter bindings.
- **Port:** a named, typed component input or output.
- **Edge:** a directed connection from exactly one output port to exactly one compatible input
  port.
- **Component Registry:** the immutable catalog of Component Types available for compilation.
- **Plugin Package:** a distributable declaration of additional Component Types plus metadata. A
  plugin is vocabulary, not an alternative runtime.
- **Evaluation Context:** immutable semantic inputs common to one graph evaluation. It contains no
  service objects and no implicit clock.
- **Execution Trace:** the immutable, ordered provenance record of compilation and evaluation.
- **Replay:** evaluation of the same canonical manifest, registry snapshot, and semantic inputs
  with an identical result identity and trace semantics.

## Strategy Manifest

### Authority and shape

The manifest is the only authored strategy definition. Generated diagrams, editor state, compiled
graphs, caches, and traces are derived and never authoritative. Handwritten orchestration code is
not a strategy definition.

Every manifest contains:

- `schema_version`: the manifest document-format version;
- `strategy_id`: an immutable, globally unique strategy identity;
- `strategy_version`: a semantic version for the strategy definition;
- `metadata`: display-only name, description, and bounded tags;
- `parameters`: named strategy-level parameter declarations and canonical values;
- `required_capabilities`: the finite capabilities the strategy needs;
- `nodes`: component instances with immutable IDs, exact component type/version references, and
  parameter bindings;
- `edges`: explicit source-node/source-port to target-node/target-port connections;
- `outputs`: named graph outputs that identify the Opportunity-producing result;
- `events`: declarative bindings to the closed lifecycle events defined below.

Unknown fields are rejected. Duplicate IDs, keys, nodes, edges, outputs, or parameter bindings are
rejected. References are exact; version ranges and “latest” resolution are forbidden in an
executable manifest.

### Serialization and identity

The canonical wire format for v1 is UTF-8 JSON. Human-facing YAML may be an import/export format
only if it is parsed into the same schema and then canonicalized; YAML bytes are never identity
inputs. Canonical serialization:

- sorts object keys lexicographically;
- preserves list order only where the schema declares order semantic;
- represents decimals as normalized base-10 strings, never binary floating point;
- represents dates and timezone-aware instants in their domain canonical forms;
- rejects NaN, infinity, duplicate keys, aliases, executable tags, and implementation objects;
- uses no insignificant whitespace in identity material.

Manifest identity is derived from namespace `asa.strategy_manifest`, identity version `v1`, the
schema version, strategy ID and semantic version, effective parameters, required capabilities,
nodes, edges, outputs, and event bindings after canonicalization. Display metadata is excluded.
Timestamps, source-file paths, serialization order of keyed values, process order, and runtime
state are excluded.

Changing semantic graph content requires a new `strategy_version`. A schema migration creates a
new manifest value; it never mutates the prior manifest. Major schema versions may reject older
documents. Minor schema revisions may add only optional, semantics-preserving fields. The runtime
supports only explicitly enumerated schema versions and never guesses a migration.

## Strategy Graph Model

The compiled graph is directed and acyclic. Each node is identified by its manifest node ID.
Every edge connects one declared output port to one declared input port with a statically
compatible type. Required inputs must be satisfied exactly once by an edge, an explicit manifest
binding, or an explicitly declared evaluation-context binding. Optional and variadic inputs must
be declared by the Component Type; implicit fan-in is forbidden.

Compilation performs, in order:

1. manifest schema and canonical-value validation;
2. exact component and plugin resolution against the supplied registry snapshot;
3. capability validation;
4. node parameter validation and default materialization;
5. port existence, cardinality, and type compatibility validation;
6. lifecycle binding validation;
7. cycle detection and reachability validation;
8. deterministic execution-order construction;
9. graph identity construction.

All declared nodes must contribute to a declared output. Dead nodes are rejected because they
obscure intent and provenance. Cycles, self-edges, unresolved references, ambiguous bindings, and
implicit type conversions are rejected before any component evaluates.

Reusable subgraphs are not part of v1. A later architecture revision may add them only with
explicit identity, parameter, type, trace, and cycle semantics. Copying a validated node/edge
fragment into a manifest is permitted but has no separate subgraph identity.

## Component Model

### Categories

Every Component Type declares exactly one closed v1 category:

- `source`: selects declared Facts, Indicators, or evaluation-context values;
- `transform`: derives a typed value from typed inputs;
- `predicate`: produces a Boolean decision value;
- `aggregate`: combines a declared finite collection;
- `score`: produces a bounded, provenance-bearing score;
- `rank`: orders a finite collection with explicit tie-breakers;
- `constraint`: applies strategy-local structural constraints that are not platform Guardrails;
- `proposal`: emits the graph's candidate Opportunity-compatible output;
- `utility`: a semantics-preserving adapter such as Constant or PassThrough.

Category metadata supports validation and explainability; it does not grant I/O or side-effect
capabilities. A component that performs multiple unrelated calculations must be split so that
each calculation has one home.

### Contract

A Component Type is identified by `(namespace, name, semantic_version)` and declares:

- named input and output ports with exact Strategy Types and cardinality;
- an immutable parameter schema, including canonical defaults and validation rules;
- one category and a finite capability set;
- deterministic evaluator semantics;
- an algorithm/heuristic version when financial semantics are not fully described by the
  component semantic version;
- provenance and explanation templates expressed as structured data;
- resource bounds relevant to validation, such as maximum aggregation input size.

Evaluation is a pure function of the component definition, effective parameters, typed input
values, and explicit evaluation context. Outputs are immutable. Components cannot mutate inputs,
retain hidden state between evaluations, inspect node scheduling, discover peers, or perform I/O.
Defaults are materialized during compilation and included in graph and trace identity.

### Capabilities

Capabilities are closed, declarative labels used to reject a graph whose requirements are not
satisfied. V1 capabilities describe financial vocabulary, such as consuming Canonical Facts,
consuming Indicators, aggregating finite collections, scoring, ranking, and emitting an
Opportunity. They are not permissions and cannot authorize filesystem, network, clock, random,
provider, persistence, broker, execution, or reflection access.

## Strategy Type System

The type system is structural only where explicitly stated and nominal everywhere else. Every
edge must be validated before execution. V1 includes:

- primitives: `Boolean`, `Integer`, `Decimal`, `Text`, `Date`, `Instant`, and bounded enums;
- domain scalars: `Currency`, `Money`, `Ratio`, `Probability`, `Quantity`, and canonical IDs;
- financial/domain values already owned by ASA: `Instrument`, `CanonicalFact`, `IndicatorValue`,
  `Evidence`, `ExpectedOutcomeMetrics`, and `Opportunity`;
- containers: immutable `Optional[T]`, finite ordered `List[T]`, and finite keyed `Map[K, V]` where
  the component contract explicitly allows them.

No implicit numeric narrowing, text-to-domain parsing, symbol-to-Instrument resolution, timezone
inference, unit conversion, or optional unwrapping is allowed. `Integer` may widen to `Decimal`
only through an explicit, registered conversion component. `Money` compatibility requires equal
currency. Domain objects are compatible only by their declared canonical type and version.

Type definitions are versioned. Adding or changing compatibility rules is an architecture change,
not a registry implementation detail.

## Expression Language

Expressions provide small deterministic calculations inside components that explicitly declare an
expression parameter. They are not a general-purpose scripting or component language.

V1 permits:

- decimal and integer arithmetic with explicit precision and rounding policy;
- comparisons between compatible types;
- Boolean conjunction, disjunction, and negation with total two-valued semantics;
- date arithmetic using explicit dates, durations, and timezone-aware instants;
- finite aggregations: `count`, `sum`, `min`, `max`, `mean`, `all`, and `any`;
- explicit normalization functions with declared bounds and zero-range behavior.

The grammar, operator table, function registry, type rules, error semantics, evaluation-step
limit, collection-size limit, decimal context, and rounding mode are versioned as one expression
language version. Evaluation uses a parsed and validated AST; expressions never use host-language
`eval` or `exec`.

Loops, recursion, assignment, mutation, filesystem and network access, clocks, randomness,
reflection, imports, object construction, dynamic property access, arbitrary calls, exception
handling, and arbitrary code are forbidden. Division by zero, invalid date operations, missing
values, non-finite results, overflow of declared bounds, and exhausted resource limits are
deterministic evaluation errors; no fallback value is invented.

## Registry and Plugin Boundary

Core owns the Component Registry implementation and validation. Registry construction is explicit:
the composition root supplies a finite ordered collection of Core Component Types and approved
Plugin Packages. Registration completes before any manifest is compiled. The resulting registry
is immutable for its lifetime.

Resolution uses exact `(namespace, name, semantic_version)` identity. Duplicate identities,
undeclared dependencies, incompatible SDK versions, missing capability declarations, invalid
schemas, and prohibited capabilities reject the registry. Registry identity includes the ordered
canonical identities of every registered Component Type and Plugin Package; construction input
order does not affect that canonical order.

A Plugin Package contains only:

- immutable plugin identity and semantic version;
- required Plugin SDK version;
- declarative metadata and capability declarations;
- an explicit finite tuple of Component Type definitions and evaluators;
- optional documentation and deterministic test vectors.

Plugins extend component vocabulary. They do not provide a loader, scheduler, graph runtime,
expression evaluator, validation bypass, service locator, event bus, repository, or alternate
composition root. A plugin cannot register after startup or modify an existing registration.

“Loading” means validating and registering Plugin Package objects explicitly supplied by the
application composition root. V1 forbids filesystem scanning, Python entry-point discovery,
manifest-directed imports, remote downloads, branch-name inference, and dynamic module loading.
Packaging and distribution are outside this architecture; adding a package to deployment is an
explicit application configuration change.

## Deterministic Execution

The graph runtime is a synchronous, pure evaluator. Its scheduler is only the deterministic
topological-order function; it is not a background scheduler, queue, thread, service, or clock.

Execution order is computed with Kahn's algorithm. Among simultaneously ready nodes, the node with
the lexicographically smallest canonical node ID executes first. A node's multiple input bindings
are presented in lexicographic input-port order; explicitly ordered collection values preserve
their semantic order. No parallel execution is permitted in v1. Node order is recorded for
explanation but excluded from semantic output identities unless ordering is itself an output.

Each node evaluates exactly once after all required inputs exist. Evaluation either returns a
complete typed immutable output set or a structured deterministic error. There is no retry,
fallback component, partial output, timeout-dependent behavior, or continuation after failure.

The runtime receives all semantic time, market, and portfolio-effective values explicitly. It
never reads the wall clock. Resource limits are fixed effective runtime parameters and are
included in runtime/trace identity where they can affect success or failure.

## Lifecycle and Event Model

V1 has a closed synchronous lifecycle:

1. `manifest_validated`
2. `graph_compiled`
3. `evaluation_started`
4. `node_started`
5. `node_completed` or `node_failed`
6. `evaluation_completed` or `evaluation_failed`

Lifecycle events are immutable trace records emitted by Core after the corresponding state
transition. They are not commands and cannot trigger arbitrary callbacks. Manifest `events`
bindings may select which declared structured explanation fields appear in the trace; they cannot
invoke components, mutate data, change control flow, publish externally, or access infrastructure.

Each event includes graph identity, evaluation identity, lifecycle kind, and relevant node and
typed input/output identities. Sequence is the deterministic graph-evaluation sequence. Execution
timestamps are excluded; if an effective semantic time is relevant, it is an explicit evaluation
input and identified as such.

## Replay and Identity Guarantees

A replay input bundle consists of:

- canonical manifest bytes and manifest identity;
- immutable registry snapshot and registry identity;
- exact component, runtime, type-system, and expression-language versions;
- complete effective parameters and resource limits;
- immutable semantic Evaluation Context;
- identities and canonical values of all consumed Facts and Indicators.

Given an identical replay bundle, evaluation must produce the same graph identity, node outputs,
Opportunity identity, structured errors (if any), and semantic trace. Environment, host, process,
locale, hash seed, input enumeration order, wall-clock time, and installation discovery cannot
affect the result.

Graph identity uses namespace `asa.strategy_graph`, version `v1`, and includes manifest identity,
registry identity, resolved component identities, fully materialized parameters, typed edges,
outputs, lifecycle bindings, and all versioned semantic policies. Evaluation identity uses
namespace `asa.strategy_evaluation`, version `v1`, and includes graph identity and complete
semantic input identities. It excludes timestamps, runtime duration, logging fields, thread or
process identity, and incidental execution order.

Core must reject replay when any required component or policy version is unavailable. It must not
substitute a compatible-looking version.

## Validation Model

Validation is fail-closed and completes before component evaluation. Errors are immutable,
structured, path-addressable, and stably ordered by validation phase, manifest path, and error
code. At minimum, validation covers:

- manifest syntax, schema version, canonical values, and identity;
- exact registry, plugin, component, and SDK versions;
- component parameter schemas and materialized defaults;
- capability requirements and prohibited capabilities;
- node/edge uniqueness, references, port cardinality, and type compatibility;
- DAG acyclicity, reachability, deterministic order, and declared outputs;
- expression grammar, typing, functions, limits, and forbidden constructs;
- lifecycle binding validity;
- replay-bundle completeness;
- architecture dependency and forbidden-import boundaries.

Warnings cannot make an invalid graph executable. Unknown versions or extensions are errors.

## Explainability and Provenance

The runtime preserves the existing structured Evidence chain. Components cite only the Facts,
Indicators, parameters, and upstream node outputs actually consumed. They do not copy the entire
available evidence set. Every node trace records:

- component and node identities;
- effective parameter identities;
- typed input and output identities;
- consumed Evidence identities;
- algorithm or heuristic version;
- structured decision/rationale codes;
- deterministic success or error outcome.

The final Opportunity retains evidence and rationale produced by the graph. Presentation may
render or summarize this structure but cannot add financial reasoning. Logs and traces are
derived diagnostic outputs, never canonical strategy state.

## Ownership

### ASA Core owns

- manifest schema and canonicalization;
- type definitions and compatibility rules;
- component and plugin validation;
- immutable registry construction;
- graph compilation and deterministic scheduling;
- synchronous orchestration and error semantics;
- expression parsing and evaluation;
- trace construction, replay verification, and identity policies.

### Components own

- one bounded financial or structural transformation;
- declared typed ports and parameters;
- versioned deterministic evaluator semantics;
- narrow evidence attribution and structured rationale.

### Plugins own

- metadata for one approved package;
- additional Component Type vocabulary;
- their components' financial semantics, versions, tests, and documentation.

Plugins do not own or replace any Core responsibility.

## Security and Isolation

The Plugin SDK is a contract boundary, not a security sandbox. V1 plugin packages are trusted code
approved and installed with the application. Static registration, dependency validation, and
forbidden-import tests reduce accidental boundary violations but do not make hostile Python code
safe. Untrusted plugin execution would require a separately governed isolation architecture and
is out of scope.

Manifests and expression text are treated as data. They cannot name import paths, environment
variables, credentials, files, URLs, or executable callbacks. Trace and validation output must
use bounded structured values and existing redaction policy; component inputs must not contain
secrets.

## Implementation Sequence

After Founder acceptance of this architecture, SPRINT-002 proceeds in dependency order:

1. STRAT-002 defines the manifest schema and canonical serialization.
2. STRAT-003 defines the pure Component Type contract.
3. STRAT-006 implements the Strategy Type System needed by registry and graph validation.
4. STRAT-004 implements immutable explicit registration and resolution.
5. STRAT-007 implements the closed expression parser/evaluator.
6. STRAT-005 implements graph compilation, deterministic evaluation, trace, and replay.
7. STRAT-008 exposes the static Plugin SDK contract.
8. STRAT-009 supplies the minimum Core Component library.
9. STRAT-010 supplies a manifest-only reference strategy.
10. STRAT-011 completes cross-cutting validation and regression coverage.

This dependency order refines ticket execution only; it does not change ticket scope or add a
pipeline stage.

## Required Verification

Implementation must prove:

- byte-stable canonical manifest serialization and deterministic identities;
- graph-order and input-enumeration independence;
- deterministic success and deterministic structured failure replay;
- immutable manifests, graphs, registry snapshots, values, outputs, and traces;
- exact-version component resolution and rejection of ambiguity;
- type, cardinality, capability, cycle, dead-node, and expression validation;
- static plugin registration and rejection of runtime mutation or discovery;
- narrow Evidence attribution and complete Opportunity provenance;
- architecture, dependency, forbidden-import, circular-dependency, integrity, lint, typing, and
  test gates.

## Alternatives Considered

1. **Handwritten Strategy classes as canonical definitions.** Rejected because code shape is not a
   deterministic portable strategy contract and cannot support manifest-only reference strategies.
2. **Runtime plugin discovery through package entry points or filesystem scanning.** Rejected
   because installed environment state would affect vocabulary and replay, and because it creates
   an implicit composition path.
3. **Manifest-directed imports or embedded Python.** Rejected because it bypasses validation,
   permits arbitrary behavior, and makes the manifest executable code rather than canonical data.
4. **Cycles with iteration until convergence.** Rejected because termination, ordering, and
   replay semantics are materially more complex and unnecessary for the approved component set.
5. **Parallel node evaluation.** Rejected for v1 because it adds trace and failure-order ambiguity
   without an established performance need.
6. **Structural duck typing and implicit conversions.** Rejected because graph validity could
   depend on runtime values and hidden coercion.
7. **Plugins supplying alternate runtimes.** Rejected because plugins extend vocabulary only;
   orchestration, validation, and replay remain Core-owned.
8. **Reusable subgraphs in v1.** Deferred because no current reference strategy requires them and
   their versioning and provenance rules would be speculative.

## Consequences and Risks

- Strategies become portable, reviewable data with one deterministic execution path.
- Core has zero strategy-specific financial behavior; reusable components contain that behavior.
- Exact version pinning increases manifest maintenance but prevents silent semantic drift.
- Static plugin registration requires an application configuration change to install a plugin;
  this is intentional and auditable.
- V1 execution is synchronous and single-threaded. Performance work must preserve semantic output
  and trace determinism and requires evidence before architectural change.
- The SDK does not isolate hostile code. Only trusted, reviewed plugins are in scope.
- The closed v1 type and expression systems favor safety and replay over convenience.

Rollback before implementation is deletion of this proposed document. After dependent contracts
exist, changing manifest authority, plugin boundary, type compatibility, or lifecycle semantics is
a breaking architecture change requiring Founder review and an explicit migration plan.

## Resolved Implementation Questions

- The manifest, not editor state or code, is canonical.
- The graph is a validated DAG and the only source of execution.
- Ordering is a deterministic lexicographic tie-break over ready node IDs.
- V1 is synchronous and single-threaded.
- Reusable subgraphs are deferred.
- Connections are statically typed with no implicit coercion.
- Expressions use a closed AST evaluator, never host-language evaluation.
- Lifecycle events are trace records, not hooks or callbacks.
- Registration is explicit, static, exact-versioned, and immutable.
- Plugin loading performs no discovery and supplies no runtime behavior.
- Plugins are trusted installed code; hostile-code sandboxing is not claimed.
- Core owns validation, orchestration, replay, and identity; components own financial logic.
- Evaluation errors are deterministic, structured, and fail the graph without fallback.
- Semantic time is explicit input; execution time is never identity material.
- Derived traces and compiled graphs do not compete with the manifest as canonical state.

## Governance and Acceptance

This document is an architecture contract and cannot be merged under delegated implementation
authority. Founder merge is required. No STRAT-002 through STRAT-011 implementation may begin
until this document is Founder-reviewed and merged.

After Founder merge, any SPRINT-002 implementation delegation must be activated and recorded under
Accepted GOV-AMD-001 Amendment 013 before a worker self-merges an enumerated implementation PR.
That delegation cannot cover architecture, contract, governance, deployment, risk-floor, or scope
changes. Any such change stops the sprint for Founder review.

Acceptance of this document freezes for SPRINT-002 the manifest authority, graph model, type-system
rules, expression safety boundary, lifecycle semantics, registry construction, plugin boundary,
deterministic execution, replay inputs, validation ordering, and explainability requirements.

## References

- Architecture Constitution, Laws 3–10
- Architecture Vision
- ADR-003: Explainable Opportunity Model
- ADR-004: Repository Organization
- ADR-005: Guardrail Model
- ADR-006: Indicator Versioning
- ADR-007: Deterministic Ranking Model
- ADR-009: Execution Semantics and Governance Boundary
- Accepted GOV-AMD-001 Amendment 013: Founder Sprint Delegation
- `roles/shared/AUTHORITY_BOUNDARIES.md`
