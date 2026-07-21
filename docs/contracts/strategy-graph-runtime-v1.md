# Strategy Graph Runtime Contract v1

The STRAT-005 runtime compiles one canonical `StrategyManifest` against one immutable
`ComponentRegistry`. Compilation resolves exact component versions, materializes parameters,
validates capabilities, ports, exact types, cardinality, outputs, reachability, and acyclicity,
then computes a lexicographically stable Kahn topological order.

Execution is synchronous and component-agnostic. Every node executes exactly once, receives
immutable values ordered by input-port name, and must return its complete declared output set.
The runtime contains no financial rules, component name checks, retries, fallback, clock,
networking, persistence, parallelism, or mutable graph state.

Graph identity is `asa.strategy_graph/v1` and includes the manifest and registry identities,
resolved component identities, materialized parameters, typed edges, outputs, and runtime policy.
Evaluation identity is `asa.strategy_evaluation/v1` and includes the graph identity and canonical
semantic context. Ordered immutable trace events record compilation, evaluation, node boundaries,
and typed input/output identities without execution timestamps.
