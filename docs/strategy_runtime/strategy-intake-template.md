# Strategy intake template (STRATEGY-LIBRARY-001 SL-01)

Copy this file to `docs/strategies/intake/<strategy_id>.md` and complete every
section **before** implementation. A strategy whose material semantics the
source does not define is skipped, not guessed.

The authoring path is fixed by ADR-010 and the SL-01 Architect decision
(`project/reports/STRATEGY-LIBRARY-001-SL-01-ARCHITECT-DECISION.md`). See
[`adding-a-strategy.md`](adding-a-strategy.md) for the reference walkthrough.

## 1. Source

- Source/reference (title, author, URL or repository path):
- Source version/date:
- Why this strategy (selection priorities 1–6 in `docs/sprints/STRATEGY-LIBRARY-001.md`):
- Semantics the source leaves ambiguous, and how the repository resolves each
  (unresolved ambiguity means **skip**):

## 2. Strategy semantics

| Item | Source rule | ASA representation |
|---|---|---|
| Entry gates | | |
| Exit / lifecycle (if any) | | |
| Structure (`StructureKind`) | | |
| Expiration rules | | |
| Strike / delta rules | | |
| Liquidity rules | | |
| Exclusions (e.g. earnings) | | |
| Direction / action | | |
| Allocation (only if source-defined) | | |

## 3. Manifest

- [ ] Manifest id and semantic version:
- [ ] Exact `required_market_capabilities` (canonical capability names):
- [ ] Graph sketch: every gate and verdict path mapped to a registered
      component. Justify any new component: no composition of existing
      components suffices.
- [ ] `OutputSpec` explanation role per output (`fact`, `derived_fact`,
      `gate`, `direction`, `structure`, `score`, `verdict`). Each
      `derived_fact` names its `formula_id`.

## 4. Data and analytics

- [ ] Derived facts reused (id, unit, formula version):
- [ ] Derived facts added (id, unit, formula version, pinned vectors). None
      duplicates a formula in `indicators/`.
- [ ] Capability overlap with current acquisition (reuse of shared demands).
      Paid data needed: must be **no** to start.

## 5. Runtime

- [ ] The evaluation module only assembles graph inputs and executes the
      graph. No Python verdict.
- [ ] The contract passes `validate_manifest_contract`. The catalog
      `manifest_id` is the real manifest, never `"none"`.
- [ ] Subject-first binding declares bootstrap and expansion demands through
      the shared market-data authority. No strategy-ID branch in `screening/`
      or `strategy_runtime/`.
- [ ] Scheduled/current operation path (universe or scheduler-declared pairs).

## 6. UNKNOWN behavior

| Missing or unusable input | Typed reason | Terminal state |
|---|---|---|
| | | |

Missing data never becomes PASS, zero, or a fabricated proxy.

## 7. User presentation

- Option strategies: exact legs through the executable structure resolver →
  canonical trade proposal, payoff, and typed blocker categories.
- Stock strategies: stock proposal (action and allocation only when emitted).
- Expected card for a qualifying result:
- Expected typed failure for a nonconstructible result:

## 8. Proof

- [ ] Replay determinism test.
- [ ] Complete result projection test.
- [ ] Typed-failure tests for each UNKNOWN row above.
- [ ] Observation plan (collector or census coverage).

## 9. Attestation

- [ ] No ADR-010 deviation. Any deviation has recorded Architect sign-off.
