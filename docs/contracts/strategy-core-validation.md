# Strategy Core Validation Matrix

STRAT-011 validates the complete Strategy Core through focused and integrated suites:

- manifest schema, canonical serialization, identity, version rejection, and immutability;
- exact Type System compatibility and immutable typed values;
- component metadata, purity, static registry validation, and plugin isolation;
- expression parsing, typing, exact arithmetic, limits, trace, and replay;
- DAG topology, connection typing, deterministic ordering, reachability, execution, and provenance;
- all Core components independently and through the reference manifest;
- end-to-end serialize → register → compile → execute → replay equivalence;
- static architecture-import and forbidden runtime-surface checks.

The suite uses no network, provider, broker, persistence, wall clock, randomness, or mutable
runtime state. Identical semantic inputs must produce identical graph identities, evaluation
identities, outputs, and trace events.
