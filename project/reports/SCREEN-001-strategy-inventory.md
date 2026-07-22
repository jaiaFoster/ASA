# SCREEN-001 — Strategy Inventory and Readiness Audit

Status: Complete. Discovery only — no strategy semantics, framework code, or architecture
contracts were changed or introduced.

Activity type: repository audit for SPRINT-006 (Screening Framework v1), preceding any
framework design or implementation work.

Audit time (UTC): 2026-07-22
Repository commit: `1d3483e` (`main`, post-PR-#140)
Sprint reference: SPRINT-006, ticket SCREEN-001

## 1. Method

Source, tests, docs, migration records, and git/PR history were searched for each target
strategy under its ticket name and plausible aliases. Located implementations were read
directly and their test suites were run (`PYTHONPATH=. python -m pytest -q tests/strategies/
tests/architecture/test_stonk_decommissioning.py`). GitHub issues and PRs were searched via
`gh issue list` / `gh pr list`. No network access was used other than the GitHub issue/PR
search; no code was executed against live providers.

## 2. Per-strategy findings

### Forward Factor
- **Status: partial** (fully implemented and tested; zero production integration)
- **Files:** `strategies/stonk_manifests.py` (`FORWARD_FACTOR_CALENDAR_MANIFEST`, id
  `asa.stonk.forward_factor_calendar`, v1.1.0), `strategies/stonk_components.py`
  (`ForwardFactor`, `ImpliedForwardVolatility`, `DoubleCalendarStructure`, `DteSelector`).
- **Input:** canonical `OptionChain` / `OptionContract` / `ExpirationCollection` from
  `domain/` only.
- **Output:** `factor` (Decimal), routed through `VerdictClassifier` to PASS/WATCH/FAIL, with
  `EvidenceReference` / `observed_at` provenance.
- **Clock:** none direct — all timing derives from `ExpirationCollection.as_of` / chain
  `observed_at`.
- **Tests:** `tests/strategies/test_stonk_manifests.py::test_forward_factor_manifest_*`,
  `tests/strategies/test_stonk_behavioral_equivalence.py::test_forward_factor_matches_legacy_reference_vector_and_replays`
  — pass.

### Earnings Calendar (strategy)
Distinct from `MarketCapability.EARNINGS_CALENDAR_V1`, which is a market-data capability, not
a strategy.
- **Status: partial** (fully implemented and tested; zero production integration)
- **Files:** `strategies/stonk_manifests.py` (`EARNINGS_CALENDAR_MANIFEST`, id
  `asa.stonk.earnings_calendar`, v1.0.0), `strategies/stonk_components.py`
  (`EarningsEventWindow`, `ExpirationPairSelector`, `NearestCommonStrikeCalendar`,
  `OptionStructureDebit`).
- **Input:** canonical `EarningsEvent`, `ExpirationCycle` from `domain/`; confirms
  `event.confirmed`, `announcement_time`, and `front.as_of == back.as_of`.
- **Output:** `eligible` (bool), `structure`, mid/conservative `debit`, `score`, PASS/WATCH/FAIL
  `verdict`.
- **Clock:** none direct — uses `as_of` on the domain `ExpirationCollection`.
- **Tests:** `tests/strategies/test_stonk_manifests.py::test_earnings_calendar_manifest_executes_and_replays`
  — pass.

### Skew Momentum
- **Status: partial** (fully implemented and tested; zero production integration)
- **Files:** `strategies/stonk_manifests.py` (`SKEW_MOMENTUM_VERTICAL_MANIFEST`, id
  `asa.stonk.skew_momentum_vertical`, v1.0.0), `strategies/stonk_components.py`
  (`VerticalStructure`, `OptionLegLiquidity`, `OptionStructureDebit`).
- **Input:** canonical `OptionChain`, delta-target parameters; liquidity gates use
  `open_interest` / `volume` / `spread_ratio` from the chain.
- **Output:** `structure` (vertical), `liquid` (bool), `score`, `verdict`.
- **Clock:** none direct — uses `chain.observed_at`.
- **Tests:** exercised in `tests/strategies/test_stonk_manifests.py`,
  `test_stonk_behavioral_equivalence.py`, `test_stonk_production_validation.py` (parametrized
  across all three manifests, no dedicated per-name test file) — pass.

## 3. Canonical-boundary compliance

Verified directly (not solely from the initial search): `grep -rln "market_data\.\|providers\."
strategies/*.py` and `grep -rn "datetime.now()\|date.today()" strategies/*.py` both return no
matches. All three strategies consume canonical `domain/` types exclusively and use no
wall-clock time. **Compliance: yes, for all three.**

## 4. Test verification

Independently re-run: `PYTHONPATH=. python -m pytest -q tests/strategies/
tests/architecture/test_stonk_decommissioning.py` → **259 passed**, 0 failed, 0 skipped.

## 5. Input-to-canonical-capability matrix

| Strategy | Canonical domain types consumed | Market data capability origin |
|---|---|---|
| Forward Factor | `OptionChain`, `OptionContract`, `ExpirationCollection` | `OPTION_CHAIN_V1` |
| Earnings Calendar | `EarningsEvent`, `ExpirationCycle` | `EARNINGS_CALENDAR_V1`, `OPTION_CHAIN_V1` |
| Skew Momentum | `OptionChain` (leg liquidity, deltas) | `OPTION_CHAIN_V1` |

## 6. Shared infrastructure

- **`strategies/`**: component/registry/manifest/graph-runtime machinery
  (`runtime.py::execute_strategy_graph` → `GraphExecutionResult(outputs: ComponentValues,
  trace: ExecutionTrace)`), plus `stonk_components.py`, `stonk_manifests.py`,
  `stonk_plugins.py`, `library.py` (`STONK_STRATEGY_LIBRARY`). A separate, older
  `engine.py` / `registry.py` (`evaluate_strategy`) produces `domain.opportunity.Opportunity`
  from Facts/Indicators directly — **unrelated to, and not wired to, the manifest/graph
  runtime the three target strategies use.**
- **`ranking/`**: `engine.py`, `models.py`, `scorers.py`, `registry.py` — consumes
  `domain.opportunity.Opportunity` and `GuardrailDecision`. Per SPRINT-003's own report:
  "Ranking remains owned by the Ranking Engine" (`project/reports/SPRINT-003.md:47`) —
  ranking/allocation was explicitly deferred to existing ASA engines when the three
  strategies were ported, not duplicated inside `strategies/`.
- **`simulation/`, `execution_planning/`**: order/portfolio simulation and planning,
  downstream of Risk decisions — unrelated to scoring/screening.

## 7. Integration-surface assessment (architecture gate finding)

`domain/execution.py` ("Immutable analytical execution contracts frozen by ASA-ARCH-006",
SPRINT-004 / PR #109) defines contracts for **portfolio delta, risk decision, planned orders,
and simulation** — strictly downstream of an already-approved position. It is not a
scoring/screening surface and was not designed to be one.

Independently confirmed: no file outside `strategies/` and its own tests references
`STONK_STRATEGY_LIBRARY` or `execute_strategy_graph`. `ranking/*.py` all reference
`domain.opportunity.Opportunity`, confirming `ranking/` is built to consume `Opportunity`
records, not `GraphExecutionResult`. `domain.opportunity.Opportunity` requires
`expected_outcome_metrics` (an `ExpectedOutcomeMetrics` record) and `evidence_confidence`
(a `Confidence` value) — neither of which a manifest's raw `factor`/`score`/PASS-WATCH-FAIL
`verdict` output maps to mechanically. Deciding that mapping (e.g. what confidence value a
"WATCH" verdict implies, what `ExpectedOutcomeMetrics` a Forward Factor score implies) is a
product/architecture decision, not a wiring task.

**This triggers SPRINT-006's own architecture_gate condition**: *"No existing analytical
execution contract can support screening without a new public interface."* Per the sprint's
own required action, implementation must stop here rather than improvise a public framework
contract; a bounded Architect ticket is required before SCREEN-002 proceeds.

## 8. GitHub issues and PRs

`gh issue list` / `gh pr list` searches for screening/screener/signal/strategy/"forward
factor"/earnings/"skew momentum" returned no open issue or PR matching screening or screener.
The sprint document's claim of zero relevant open issues found via code search is confirmed.
Adjacent (not directly relevant) open issues: #54 (Opportunity lacks a liquidity metric for
Ranking), #55 (Ranking v1 weights need calibration), #46 (placeholder outcome metrics) — these
concern eventual ranking calibration, not this discovery ticket.

## 9. Migration history

`project/lean/migration/legacy-inventory.yaml` and `capability-map.yaml` contain no mentions
of the three strategy names. The authoritative migration record is
`docs/migration/stonk-strategy-inventory.md` and `stonk-strategy-catalog.yaml` (ticket
STONK-001, PR #92): all three were ported from the `jaiaFoster/Stonk` legacy repository
(pinned commit `5f3fec8`) via SPRINT-003 (PRs #92, #96, #97, #98), with an explicit note that
ranking/portfolio integration was intentionally left to existing ASA engines rather than
duplicated. `project/lean/archive/legacy/` has no related content — the strategies are not
legacy/dead code, they are genuinely complete but unintegrated.

## 10. Recommendation

**Architecture gate.** SCREEN-002 through SCREEN-006 should not proceed by improvising a
`GraphExecutionResult` → `Opportunity` adapter inside a worker ticket. A bounded Architect
ticket is needed to decide: (a) whether screening results should be represented as
`domain.opportunity.Opportunity` records at all, or as a new, narrower canonical type; (b) if
`Opportunity`, how manifest verdict/score maps to `expected_outcome_metrics` and
`evidence_confidence`; (c) whether that mapping lives in `strategies/`, a new module, or
`ranking/`.

## 11. Deliverables

- `project/reports/SCREEN-001-strategy-inventory.md` — this report.
- `project/reports/SCREEN-001-strategy-inventory.json` — machine-readable inventory.
