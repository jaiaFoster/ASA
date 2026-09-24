# SL-01 Architect Decision: manifest/contract reconciliation

ROLE-ARCH · STRATEGY-LIBRARY-001 SL-01 · 2026-09-24 · read-only, main @ df000e9

## 1. Verified facts

- ADR-010 makes `StrategyManifest` the only authored definition (`architecture/ADR-010-strategy-integrity-topology.md:59-61`). The contract is a validated projection (`:63-68`), and gates and verdicts live in the graph (`:80-88`). It is logged at `architecture/DECISION_LOG.md:11`. Its header still reads "Proposed" (`:3`), but it is on main.
- `validate_manifest_contract` checks id, version and capabilities (`strategy_runtime/manifest_contract.py:15-40`). It runs for FF/SM/EC (`strategy_runtime/adapters/__init__.py:86-92`).
- **All three option strategies execute their manifest graph in production.** The `*_evaluation.py` modules are thin graph callers:
  - FF: `strategies/forward_factor_evaluation.py:55-56`, called from `forward_factor_subject_first.py:273`.
  - EC: `strategies/earnings_calendar_evaluation.py:131-132`, called from `earnings_calendar_subject_first.py:367`.
  - SM: `skew_momentum_subject_first.py:340-341`.

  They conform to ADR-010.
- B001/B002 are contract-only:
  - Contracts: `adapters/stock_benchmarks.py:15-40`.
  - Python verdict: `strategies/stock_benchmark_evaluation.py:19-29`.
  - Skipped by validation (`adapters/__init__.py:98-103`), and the catalog uses `_NO_MANIFEST` (`:201,219-220`).
  - The comment says a `StructureKind.NONE` strategy "never compile[s] a graph" (`:196-200`). The repo contradicts this. `STOCK_MOMENTUM_MANIFEST` is a non-option graph (`strategies/stonk_manifests.py:498-538`), and the core `compare`/`boolean_not` components exist (`strategies/core_components.py:63,108`).
  - The shape came from a test fixture (`project/reports/STOCK-RUNTIME-001-STK-03.md:26-30`), not from an architecture decision.
- `adding-a-strategy.md:43-47,141-144` claims FF/SM/EC demonstrate the contract-first flow and the bridge pattern. That is false: `adapters/forward_factor.py` now holds only a contract, and production adapters are `_subject_first_only` (`adapters/__init__.py:80-81`).

## 2. Decision

This stays inside ADR-010 without amending it. **There is no governance conflict and no Founder blocker.** New strategies, stock or option, follow exactly this path:

1. Author one versioned manifest with exact `required_market_capabilities`.
2. Put all gates, thresholds, direction, structure, score and verdict in the graph, built from registered components. Add a component only when no composition of existing ones works.
3. Consume named `analytics/` derived facts. No private formulas.
4. The `*_evaluation.py` module may only assemble graph inputs and call `compile_strategy_graph`/`execute_strategy_graph`. No Python verdict.
5. Write the `StrategyContract` as a projection, validated in the composition root. The catalog carries the real `manifest_id`.
6. Add one subject-first binding plus an adapter that maps graph outputs to `UniversalScreeningResult`.
7. Prove replay determinism and complete projection.

The contract-first flow and `_NO_MANIFEST` are prohibited for new work.

## 3. B001/B002 classification

**This is bounded migration debt**, under ADR-010 `:95-98`.

- **Follow-up:** `SL-03-00 — B001/B002 manifest conformance`. Add manifests and graph verdicts, validate them, remove `_NO_MANIFEST`, and prove verdict parity.
- **Gate:** it must merge before any SL-03 stock strategy lands. It is never a template to copy.
- **Rationale:**
  - The behaviour is correct and trivial.
  - Conversion changes public catalog identity (`manifest_id`), so it needs its own reviewed PR, not a docs ticket.
  - The gate stops the ambiguity from multiplying.

## 4. Intake checklist additions

- [ ] Manifest id and version, with the exact market-capability list.
- [ ] Graph sketch: every gate and verdict path mapped to a registered component. Any new component is justified.
- [ ] `OutputSpec` role per output. Each `derived_fact` names its `formula_id`.
- [ ] Derived facts reused or added (id, unit, formula version), with no duplicate in `indicators/`.
- [ ] Evaluation module does graph execution only.
- [ ] Contract passes `validate_manifest_contract`, and the catalog `manifest_id` is not `"none"`.
- [ ] Subject-first binding with bootstrap and expansion demands, and no strategy-ID branching in `screening/` or `strategy_runtime/`.
- [ ] Typed UNKNOWN/terminal reason for every missing input.
- [ ] Replay and projection-completeness tests.
- [ ] "No ADR-010 deviation" attestation. Any deviation needs Architect sign-off.

## 5. Required doc corrections

- `docs/strategy_runtime/adding-a-strategy.md`:
  - Replace lines 30-159 (the legacy four-step flow and the false claims) with a §2 walkthrough that cites Forward Factor as the reference.
  - Keep "Diagnostics" and "never touch", but drop the `register()`-as-authoring framing.
- The comments at `adapters/__init__.py:98-101,196-200` should call this migration debt referencing SL-03-00. Make the change in that PR.
- ADR-010 `:3` has a stale status. This is a Founder notation fix and is non-blocking.
