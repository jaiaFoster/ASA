# Adding a strategy to the Universal Strategy Runtime

SPRINT-012 supersedes the older contract-first extension flow:
`StrategyManifest` is the only authored strategy definition. A runtime
`StrategyContract` is a mechanically validated projection, not a second source
of strategy identity, version, or market-capability semantics.

The production extension path is:

1. Author one versioned manifest and declare every acquired capability.
2. Reuse or add named, typed, versioned derived facts in `analytics/`.
3. Put thresholds, gates, direction, structure, score, and PASS/WATCH/FAIL in
   the strategy graph.
4. Keep screening orchestration-only: acquire declared facts, invoke derived
   calculators, execute the graph, and map its result.
5. Preserve facts, gates, reasons, provenance, and verdict through the generic
   universal result.

Each public manifest output must declare its explanation role on `OutputSpec`:
`fact`, `derived_fact`, `gate`, `direction`, `structure`, `score`, or `verdict`.
A `derived_fact` also declares its canonical analytics `formula_id`. This
metadata is part of manifest identity and is the only authority used by generic
projection; runtime code must not infer financial meaning from output names or
strategy IDs.

Adapters must not define financial formulas, normalize scores, duplicate
manifest parameters, read provider payloads, or perform hidden acquisition
from inside strategy evaluation.

The legacy contract-first flow (define a `StrategyContract`, implement Python
evaluation, register) is **prohibited for new strategies**. The Architect
decision for STRATEGY-LIBRARY-001 SL-01
(`project/reports/STRATEGY-LIBRARY-001-SL-01-ARCHITECT-DECISION.md`) records
this. The only exception on main, the B001/B002 stock benchmarks, is bounded
migration debt tracked as SL-03-00. Never copy it.

Every new strategy, option or stock, must complete
[`strategy-intake-template.md`](strategy-intake-template.md) before
implementation.

## Reference walkthrough: Forward Factor

Forward Factor is the reference implementation of the single authoring path.

1. **Manifest.** `FORWARD_FACTOR_CALENDAR_MANIFEST` in
   `strategies/stonk_manifests.py` is the only authored definition: id,
   semantic version, parameters, exact `required_market_capabilities`, graph,
   and outputs with explanation roles.
2. **Graph owns judgment.** Gates, thresholds, direction, structure selection,
   score and verdict are graph nodes built from registered components
   (`strategies/core_components.py` and related). Add a component only when no
   composition of existing ones works.
3. **Named derived facts.** Inputs are canonical values and registered
   `analytics/` derived facts, each with an id, unit and formula version. No
   private formula lives in a strategy, adapter or screening module.
4. **Evaluation module runs the graph only.**
   `strategies/forward_factor_evaluation.py` assembles typed inputs, then calls
   `compile_strategy_graph(FORWARD_FACTOR_CALENDAR_MANIFEST, ...)` and
   `execute_strategy_graph(...)`. It contains no Python verdict.
5. **Contract is a validated projection.** `FORWARD_FACTOR_CONTRACT`
   (`strategy_runtime/adapters/forward_factor.py`) is checked against the
   manifest by `validate_manifest_contract` in
   `build_migrated_strategy_registry()` (`strategy_runtime/adapters/__init__.py`),
   and the catalog carries the real `manifest_id`.
6. **Subject-first binding and adapter.**
   `build_forward_factor_subject_preparation_binding` declares acquisition
   demands through the shared market-data authority.
   `build_forward_factor_subject_first_adapter` maps graph outputs to a
   `UniversalScreeningResult`, with typed UNKNOWN reasons for missing inputs.
   Neither `screening/` nor `strategy_runtime/` branches on the strategy id.
7. **Product path.** Option structures resolve through the generic executable
   structure resolver into the canonical trade proposal. Strategies declaring
   `StructureKind.NONE` project through the stock proposal. Both surfaces are
   generic.
8. **Proof.** Replay determinism, complete result projection, and
   typed-failure tests are part of the change.

## Diagnostics

After registering, `strategy_runtime.describe_registry(MY_REGISTRY)` prints one human-readable
line per registered strategy (id, version, category, requirements, lifecycle, structure,
outputs, capabilities) -- use it to sanity-check a new strategy's own contract at a glance,
alongside every other strategy already running. `strategy_runtime.describe_contract(contract)`
does the same for one contract in isolation.

## What you will never need to touch

- `strategy_runtime/execution.py` -- `run_strategies()` already executes any registered
  strategy generically; it contains no strategy-named conditional and never will.
- `strategy_runtime/service.py` -- `refresh()`/`get_state()`/`record_opportunity_observation()`
  already work against any `StrategyRegistry[UniversalScreeningResult]`.
- Persistence (`strategy_runtime/persistence.py` and its Postgres implementations) -- shaped
  around `UniversalScreeningResult`/`OpportunityObservation`, not any one strategy_id.
- The Agent Data API routes (`asa/api/`) -- reading from a registry is a separate, deliberately
  deferred wiring step (SPRINT-009R/EPIC-R5's own scope), not something a new strategy causes
  by existing.
