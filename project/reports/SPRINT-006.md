# SPRINT-006 — Screening Framework v1

Status: Implementation complete, **founder_verification_pending**. Per this sprint's own
`docs/sprints/SPRINT-006.yaml` (Founder Sprint Delegation, GOV-AMD-001-013 / GOV-006, #141),
Founder verification is required before a successor sprint (SPRINT-007) begins; that
authorization is explicitly out of this sprint's scope regardless.

Validation time (UTC): 2026-07-22
Repository commit: `f65b8c4` (`main`, through PR #148)

## 1. Sprint summary

Established a canonical, deterministic screening framework that discovers, registers,
executes, isolates, and ranks-by-grouping existing ASA analytical strategies without
changing their trading logic. All three target strategies (Forward Factor, Earnings
Calendar, Skew Momentum) were confirmed present, fully implemented, and unintegrated
(SCREEN-001); a minimal framework contract and registry were introduced (SCREEN-002); a
canonical, immutable, provenance-bearing result envelope and an isolated, deterministic
runner were added (SCREEN-003); all three strategies were wired to the framework through
pure composition-glue adapters with zero changes to their semantics (SCREEN-004); and a
bounded, fail-closed local entrypoint was delivered (SCREEN-005).

An architecture gate was correctly triggered and resolved along the way: SCREEN-001 found
no existing analytical execution contract could host screening results without a new
public interface. Per the Founder's explicit decision (issue #143), screening introduces
its own new, narrower canonical result type this sprint rather than reusing
`domain.opportunity.Opportunity` -- the `Opportunity`/`ranking` bridge is deferred to
SPRINT-007.

## 2. Completed tickets

| Ticket | Title | PR |
|---|---|---|
| GOV-006 | Activate SPRINT-006 Founder Sprint Delegation | #141 |
| SCREEN-001 | Strategy Inventory and Readiness Audit | #142 |
| SCREEN-002 | Screening Framework Contract and Registration | #144 |
| SCREEN-003 | Canonical Screening Run and Signal Results | #145 |
| SCREEN-004 | Target Strategy Adapters | #146 |
| SCREEN-005 | Bounded Screening Entrypoint | #148 |
| SCREEN-006 | Sprint Integration and Completion Validation | this PR |

## 3. Delegated merged pull requests

#144, #145, #146, #148 were merged under the active Founder Sprint Delegation
(Amendment 013, activated by the Founder's merge of #141) after all required gates
passed. #141 and #142 were merged by the Founder directly, per the delegation's own
activation sequencing (delegation cannot be self-activated) and the ticket's own
`merge_authority: founder_only`, respectively.

## 4. Validation results

- `pytest tests/` (full repository): **2034 passed, 2 skipped** (pre-existing skips,
  unrelated to this sprint).
- `pytest tests/screening/ tests/architecture/` (screening + full architecture boundary
  suite): **420 passed**.
- `pytest tests/strategies/ tests/architecture/test_stonk_decommissioning.py` (existing
  strategy regression, re-run unmodified): **259 passed** -- identical to SCREEN-001's
  baseline, confirming zero strategy semantic drift across the whole sprint.
- `ruff check screening/ tests/screening/ tests/architecture/test_screening_boundaries.py`:
  clean throughout every ticket.
- `mypy screening/`: **zero errors** in any file this sprint added or modified. Reaching
  `strategies`/`indicators` transitively (via `screening.adapters`) surfaces 22
  **pre-existing** errors in `strategies/calculations.py`, `strategies/registry.py`,
  `strategies/__init__.py`, `indicators/calculations.py`, `indicators/registry.py`,
  `indicators/engine.py` -- confirmed byte-identical via `git stash` (present on `main`
  before this sprint, not introduced by it), and never previously caught because no CI
  workflow runs root-level mypy. Documented as issue #147, not fixed here (fixing them
  is unrelated-refactoring risk to code this sprint must not touch).
- `tools/pos/lean/check_integrity.py`, `validate.py`, `generate.py current-state`,
  `check_entrypoints.py`, `pre_push_check.py`: all green throughout every ticket.
- `git status --short` after every merge: worktree clean, no drift.

## 5. Architecture and governance verification

- Every `screening/*.py` file imports only `screening`, `domain`, `strategies`, and
  stdlib -- enforced by `tests/architecture/test_screening_boundaries.py` (57
  parametrized+direct tests), extended once per ticket as genuinely new dependencies
  were discovered (`collections.abc` in SCREEN-003; `strategies` itself in SCREEN-004;
  `argparse`/`sys` in SCREEN-005) rather than loosened speculatively.
- `strategies/` cannot import `screening/` -- enforced by `strategies/`'s own,
  unmodified `test_strategy_boundaries.py` allowlist. The dependency is one-directional.
- No strategy's threshold, formula, entry logic, or scoring changed -- confirmed by the
  unchanged 259-test regression count and by inspection (zero lines touched under
  `strategies/` all sprint).
- No new frozen public architecture contract was introduced without a gate: the
  architecture gate SCREEN-001 triggered was resolved by an explicit Founder decision
  (#143) before SCREEN-002 began, not improvised by a worker ticket.
- Founder Sprint Delegation (Amendment 013) was used exactly as designed: activation
  required a Founder merge (#141) before any delegated merge occurred; every delegated
  merge (#144, #145, #146, #148) passed its full required-gate list first; `.github/`
  and `governance/frozen/` were never touched; one ambiguous-gate situation (SCREEN-004's
  pre-existing mypy findings) was surfaced to the Founder rather than resolved
  unilaterally, per the delegation's own "any ambiguity ... returns merge authority to
  the Founder" principle.

## 6. Strategy readiness matrix

| Strategy | SCREEN-001 status | SCREEN-004 status | Live-ready |
|---|---|---|---|
| Forward Factor | partial (implemented, tested, unintegrated) | integrated (fixture-backed) | No -- see gaps below |
| Earnings Calendar | partial (implemented, tested, unintegrated) | integrated (fixture-backed) | No -- see gaps below |
| Skew Momentum | partial (implemented, tested, unintegrated) | integrated (fixture-backed) | No -- see gaps below |

## 7. Canonical sample output

`python -m screening --as-of 2026-07-22T16:00:00+00:00 --json`, repeated twice and
byte-diffed identical (deterministic repeated-run comparison, per this ticket's own
required validation):

```json
{"dry_run": false, "results": [
  {"run_id": "fe026d12ef7f9e645ca92631b690f94839b6e97bd5f3ebc3b93d569b21759357",
   "strategy_id": "earnings_calendar", "strategy_version": "1.0.0",
   "subject_identity": "figi:figi-AAPL", "as_of": "2026-07-22T16:00:00+00:00",
   "outcome_status": "pass", "signal_classification": "PASS",
   "strategy_native_score": "75", "failure_detail": null},
  {"run_id": "fe026d12ef7f9e645ca92631b690f94839b6e97bd5f3ebc3b93d569b21759357",
   "strategy_id": "forward_factor", "strategy_version": "1.1.0",
   "subject_identity": "figi:figi-AAPL", "as_of": "2026-07-22T16:00:00+00:00",
   "outcome_status": "pass", "signal_classification": "PASS",
   "strategy_native_score": "0.202944132896095057902621245", "failure_detail": null},
  {"run_id": "fe026d12ef7f9e645ca92631b690f94839b6e97bd5f3ebc3b93d569b21759357",
   "strategy_id": "skew_momentum", "strategy_version": "1.0.0",
   "subject_identity": "figi:figi-AAPL", "as_of": "2026-07-22T16:00:00+00:00",
   "outcome_status": "pass", "signal_classification": "PASS",
   "strategy_native_score": "76.66666666666666666666666667", "failure_detail": null}
]}
```

(`evidence`/`input_provenance`/`completeness` fields omitted here for brevity; the full
payload is exactly what `tests/screening/test_cli.py` and `test_sprint_integration.py`
assert against.)

**Failure-isolation run** (one real adapter deliberately broken, the other two real,
unmodified adapters left to run normally):

```text
earnings_calendar  strategy_exception   classification=None score=None
                   failure_detail='RuntimeError: unhandled adapter exception'
forward_factor     pass                 classification='PASS' score=0.202944132896095057902621245
skew_momentum      pass                 classification='PASS' score=76.66666666666666666666666667
```

The broken adapter's raw exception message ("simulated adapter bug for
failure-isolation evidence") never appears in the result -- only its type name does,
matching the runner's bounded, redacted `STRATEGY_EXCEPTION` handling from SCREEN-003.
See `tests/screening/test_sprint_integration.py` for the executable version of both runs
above.

## 8. Explicit list of live-data gaps

1. **No live symbol/universe acquisition.** `python -m screening` only supports the
   approved fixture universe (`AAPL`, matching `screening/fixtures.py`); `--live` is
   recognized and documented but fails closed, exactly as designed -- live acquisition
   is this sprint's explicit exclusion (`successor_candidate.authorized: false`).
2. **Forward Factor's implied-forward-volatility and DTE inputs have no computation
   pipeline anywhere in this codebase.** Discovered while building SCREEN-004: the
   manifest's `implied_forward_volatility` node has no incoming graph edges -- it
   expects `front_iv`/`back_iv`/`front_dte`/`back_dte` supplied directly as external
   context, meaning IV surface computation from raw option prices happens (or would
   need to happen) entirely outside this manifest. SPRINT-007 needs to either build that
   computation or source it from a live provider/indicator pipeline.
3. **`Opportunity`/`ranking` bridge deferred** per the Founder's #143 decision --
   screening results don't yet feed `ranking/`; that mapping (verdict/score ->
   `expected_outcome_metrics`/`evidence_confidence`) needs real signal history to
   calibrate against before it's decided, not before it's guessed.
4. **Live request-budget integration** with the existing Market Data Platform's
   ceilings (`backend/src/asa/market_data_ops`, PRs #136-#140) is not yet wired to the
   screening framework -- `--live` failing closed means this was never exercised, by
   design.

## 9. Discovered and resolved defects

No defect in shipped code was discovered during this sprint. One fixture-construction
mistake was caught and corrected *before* merge while building SCREEN-004: the initial
Earnings Calendar fixture placed the front expiration after the earnings event date,
violating `expiration_pair_selector`'s date-relative-to-earnings-event filter
(`strategies/stonk_components.py`) and failing at the `pair` graph node with
`ComponentContractError: expiration pair projection requires exactly two cycles`. Traced
to the selector's actual filter logic and fixed in the fixture dates before #146 was
opened -- never reached `main` in a broken state, so this is a caught authoring mistake,
not a regression.

## 10. Remaining non-blocking issues

- **#147** -- `.github/workflows/validate-architecture.yml` doesn't trigger on
  `screening/**` changes alone and its fixed pytest path list doesn't include
  `tests/screening/`; no CI workflow runs root-level mypy. Confirmed real, filed for
  Founder review since `.github/workflows/` is both CODEOWNERS-protected and outside
  this sprint's delegated scope (`docs/sprints/SPRINT-006.yaml`'s `must_not_modify`).

No other open issues were created this sprint; the issue_gate's creation policy
(confirmed defect, missing approved capability, or unresolved architectural dependency
only) was followed throughout -- #143 (architecture decision, closed) and #147 (CI gap,
open) are the only issues this sprint produced.

## 11. Recommendations for SPRINT-007

1. Resolve the implied-forward-volatility computation gap (Section 8, item 2) before
   attempting a live Forward Factor run -- this blocks live data for that strategy
   specifically, not the framework.
2. Decide and implement the `Opportunity`/`ranking` bridge only after real signal
   history exists to calibrate the verdict-to-confidence mapping against, per the #143
   decision's own reasoning.
3. Wire `--live` to the existing Market Data Platform's bounded acquisition path
   (`backend/src/asa/market_data_ops`) and its existing request-budget ceilings --
   SPRINT-007's own scope already anticipates this ("bounded live market-data
   acquisition").
4. Address issue #147 (CI coverage) as a Founder-reviewed `.github/workflows/` change,
   independent of SPRINT-007's own work items.

## 12. Deliverables

- `project/reports/SPRINT-006.md` -- this report.
- `screening/` package: `registry.py`, `results.py`, `runner.py`, `fixtures.py`,
  `adapters.py`, `cli.py`, `serialization.py`, `clock.py`, `errors.py`.
- `tests/screening/`: 75 tests across registry, results, runner, adapters, CLI, and
  sprint-integration evidence.
- `tests/architecture/test_screening_boundaries.py`: 57 architecture boundary tests.
- `docs/sprints/SPRINT-006.yaml`: the Founder Sprint Delegation record (#141).
- `project/reports/SCREEN-001-strategy-inventory.md` / `.json`: the strategy audit
  (#142).
