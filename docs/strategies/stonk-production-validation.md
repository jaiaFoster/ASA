# Stonk Strategy Library production validation

STONK-007 validates all four manifests as one deterministic production-quality
library. The suite builds the static Component Registry, compiles each graph,
executes a fixed typed vector twice, and requires byte-equivalent immutable
results and evaluation identities.

The validation covers:

- canonical manifest and graph validation;
- exact typed connections and static plugin resolution;
- deterministic execution and replay;
- complete ordered node traces with input/output provenance identities;
- component isolation and absence of hidden instance state;
- behavioral-equivalence vectors from pinned Stonk revision
  `5f3fec846f70e9739cf3f15695fd587f0604344c`;
- 200 uncached whole-graph executions under a deliberately generous five-second
  regression ceiling.

The performance ceiling is a regression tripwire, not a throughput promise.
Results depend only on immutable inputs, pinned Components, manifest versions,
and the Graph Runtime; no providers, clocks, persistence, networking, broker
operations, caches, or legacy code participate.
