# SPRINT-014 S14-PR-05: Shadow and Cut Over Earnings Calendar

Self-review packet for the Architect's own required CUTOVER_PASS review. This PR is
**not** auto-merged even on an ordinary architecture PASS, per the Architect's explicit
"PROCEED with S14-PR-05" directive — it is opened and left for the Founder's own
personal review of this packet and the final live composition.

## 1. What changed

Earnings Calendar is cut over from imperative, strategy-driven acquisition
(`screening.live_adapters.build_live_earnings_calendar_adapter`, still present,
untouched) to the subject-first evidence path built by S14-PR-02/03/04:
`SubjectAcquisitionPlan` → `seal_subject_snapshot` → `project_canonical_fact` /
`materialize_derived_fact` → `SubjectSealedEvidence` → `RuntimeContext.sealed_evidence`.

New:
- `screening/earnings_calendar_fact_ids.py` — the 7 derived/canonical fact-ID
  constants, standalone so the adapter never imports the acquisition orchestrator.
- `screening/sealed_earnings_calendar.py` — the acquisition orchestrator
  (`acquire_sealed_earnings_calendar_evidence`), living in `screening/` per ADR-010
  ("screening owns acquisition planning and orchestration"), called only by the
  composition root, never by the adapter.
- `strategy_runtime/evidence.py` — `SubjectSealedEvidence`, the one read-only bundle
  `RuntimeContext` may now carry instead of a live fulfillment object (I-09).

Rewritten:
- `strategy_runtime/context.py` — `RuntimeContext.fulfillment` removed; replaced with
  `sealed_evidence: SubjectSealedEvidence | None`.
- `strategy_runtime/execution.py`, `strategy_runtime/service.py` — threaded
  `sealed_evidence_by_subject` instead of `fulfillment_by_subject` into
  `RuntimeContext`; `refresh()` kept `fulfillment_by_subject` as a required parameter,
  used only for temporal-metadata bookkeeping (unchanged logic).
- `strategy_runtime/adapters/earnings_calendar.py` — acquisition-free
  `earnings_calendar_adapter(context)`; reads only `context.sealed_evidence`.
- `strategy_runtime/adapters/forward_factor.py`, `.../skew_momentum_vertical.py` —
  two-arg (`context`, `fulfillment`), unchanged financial logic, now composed via a
  legacy binding at registry-construction time instead of through `RuntimeContext`.
- `strategy_runtime/adapters/__init__.py` — `build_migrated_strategy_registry()`'s
  legacy composition binding for FF/SM, plus the new `earnings_calendar_cutover_enabled`
  rollback switch (§5).

## 2. Bugs found and fixed, in discovery order (all via running tests, none by
   reasoning alone)

1. `KeyError: 'deterministic_fixture'` — test config needed `live_only_config(...)`.
2. `TypeError: 'OptionChain' object is not iterable` — extracted
   `normalize_expiration_response()` as a shared pure function
   (`screening/live_context.py`) so the plan-backed expiration resolution reuses the
   same response-shape normalization `acquire_expirations()` already had.
3. Missing `cast` import surfaced by the above refactor (`screening/live_context.py`).
4. A redundant `cast(...)` removed once the plan-backed function returned a properly
   typed value directly.
5. `IndexError: pop from empty list` from Finnhub's transport — Finnhub declares
   `REAL_TIME_QUOTE_V1`/`HISTORICAL_BARS_V1`/`EARNINGS_CALENDAR_V1` and is tried before
   Tradier alphabetically (`strategy_runtime/market_data_planning.py`'s own priority
   policy); fixed by giving tests an endpoint-routed transport double instead of a
   finite scripted queue.
6. `MarketObservation.observation_id is not content-derived` — combining front+back
   option-chain observations into one sealed result must recompute the observation id
   from the combined value before `dataclasses.replace()`.
7. `Observation resolution requires one value per provider` — `HISTORICAL_BARS_V1` is
   a genuine time series (30 daily bars), structurally incompatible with
   `ObservationResolver.resolve()`'s one-observation-per-provider design (correct,
   unmodified PR-04 code). Fixed by never sealing `HISTORICAL_BARS_V1` into the
   snapshot at all — the raw closes remain durably recorded via the plan's own attempt
   persistence regardless, and the meaningful derived value (`realized_vol`) is still
   captured as a proper `DerivedFact`.
8. `Snapshot lacks bounded metadata for an included provider` — `seal_subject_snapshot`
   requires real `ProviderMetadata` for every provider whose observations appear.
   Fixed by adding `strategy_runtime.market_data_planning.provider_metadata_for()`, a
   small public helper reused by both the shadow-parity test and the real composition
   root — never a test-only construction.
9. `CanonicalFact.value is not an immutable normalized value (date)` — canonical facts
   require a tz-aware `datetime`, not a bare `date` (unlike `DerivedFact.value`, whose
   type explicitly allows `date`). Fixed by normalizing the earnings date to midnight
   UTC before projection.
10. `ExpirationCycle requires a monthly or weekly classification` — reconstructing an
    `ExpirationCycle` from sealed derived facts had defaulted `monthly=False,
    weekly=False`, which is unread by every strategy component but still fails the
    domain's own construction invariant. Fixed by reusing
    `screening.live_context._is_monthly_expiration`, the exact same classification
    every other `ExpirationCycle` in this codebase is built from.
11. Test-only: `ScreeningResult.strategy_native_score` / `UniversalScreeningResult
    .metrics["strategy_native_score"]` — the shadow-parity test's score comparison used
    a nonexistent `.score` attribute on both sides; fixed to the real field/encoding.
12. **Composition-root regression, found only after wiring `asa/scheduled_screening.py`**:
    `acquire_sealed_earnings_calendar_evidence` was called directly in the composition
    root's own per-pair loop, outside `screening/runner.py`'s generic per-adapter
    exception boundary every other strategy's own acquisition failures are absorbed by.
    A capability with zero enabled providers (`DomainInvariantError: No priority policy
    for earnings_calendar_v1`) then surfaced as a hard `PairOutcome.error` (an
    infrastructure failure) instead of a graceful, non-crashing outcome — a real,
    demonstrated behavioral difference from the pre-cutover path, not a hypothetical
    one. Fixed by isolating the acquisition call in its own try/except: on failure,
    `sealed_evidence_by_subject` stays unset and `refresh()` still runs;
    `earnings_calendar_adapter`'s own existing "requires sealed subject-first evidence"
    guard then reaches `strategy_runtime/execution.py`'s generic per-adapter boundary
    exactly as any other adapter exception would, restoring parity.
13. **Second composition root, found only by running the full suite**:
    `asa/api/screening_routes.py`'s on-demand refresh endpoint
    (`POST /api/v1/screening/{signal}/{symbol}/refresh`) builds its `StrategyRegistry`
    once at app startup, before any request's subject is known — its legacy
    composition binding for forward_factor/skew_momentum therefore closed over an
    *empty* `legacy_fulfillment_by_subject`, unconditionally raising "requires shared
    market data access" for every on-demand refresh of either strategy. Not a
    hypothetical: `tests/asa/test_ai_agent_workflow.py`,
    `tests/asa/test_bootstrap_first_run.py`, and
    `tests/asa/test_screening_refresh_route.py` all failed against skew_momentum
    through this exact endpoint. See §4.

## 3. Legacy composition binding (Forward Factor / Skew Momentum)

Unchanged from the design already reviewed and accepted for this ticket:
`build_migrated_strategy_registry(legacy_fulfillment_by_subject=...)` builds two
wrapper closures matching `StrategyRegistry`'s single-argument adapter type, calling
the real two-argument `forward_factor_adapter`/`skew_momentum_adapter` with
`legacy_fulfillment_by_subject.get(context.subject)`. No strategy conditionals were
added to `strategy_runtime/execution.py`; no parallel top-level subsystem was created.
Owner and deletion condition documented in `strategy_runtime/adapters/__init__.py`'s
own module docstring, unchanged: delete when each strategy is itself migrated.

## 4. Read-set expansion, and why (Architect directive #4)

Beyond `asa/scheduled_screening.py`, this PR also touches `asa/api/screening_routes.py`
and `asa/bootstrap.py` — **not** originally named in the Architect's own scope
enumeration, but a necessary consequence of the same constraint (I-09: RuntimeContext
must be fulfillment-free) applying to *every* composition root, not only the scheduled
one:

- `asa/api/screening_routes.py`'s `refresh_screening_result` now rebuilds the
  `StrategyRegistry` **per request**, after `access` (the request's own
  `SubjectMarketDataAccess`) is built, with the correct
  `legacy_fulfillment_by_subject={symbol: subject_access.fulfillment}` — mirroring
  `asa/scheduled_screening.py`'s own ordering, for the same reason (the legacy binding
  closure needs the request's real subject, unknowable at app-startup time). Without
  this, forward_factor/skew_momentum's own on-demand refresh was completely broken
  (§2.13), not a degraded edge case.
- The same endpoint also gained Earnings Calendar sealed-evidence support (a
  `SubjectAcquisitionPlan` + `acquire_sealed_earnings_calendar_evidence` call scoped to
  one ad-hoc request, `plan_id` built from `on-demand-refresh:{signal}:{symbol}:
  {clock.now().isoformat()}` for per-invocation uniqueness), with the same acquisition-
  failure isolation as the scheduled path (§2.12) — otherwise `POST
  .../earnings_calendar/{symbol}/refresh` would unconditionally raise, since
  `sealed_evidence_by_subject` was never threaded through at all.
- `build_screening_router()` gained a new required `acquisition_attempt_repository`
  parameter (the same repository instance `asa/bootstrap.py` already builds for
  `build_operations_router`) so the on-demand plan has somewhere to durably persist its
  own attempts, matching S14-PR-03's own "every attempt durable" requirement (I-04)
  rather than silently skipping persistence for this one call path.

This expansion was not discovered by reading the ticket text — it was discovered by
running the full test suite (`pytest`, not just the touched-file subset) after the
scheduled-path wiring was already green, which is why it is called out explicitly here
rather than folded silently into §1.

## 5. Rollback switch (Architect directive #5)

`asa.scheduled_screening.run_scheduled_refresh(earnings_calendar_cutover_enabled: bool
= True)`:
- `True` (default): unchanged, as built by this PR.
- `False`: `build_migrated_strategy_registry(earnings_calendar_cutover_enabled=False)`
  registers `strategy_runtime.adapters.legacy_earnings_calendar_adapter` for Earnings
  Calendar instead — a straight two-argument reuse of
  `screening.live_adapters.build_live_earnings_calendar_adapter` (untouched by this
  PR), composed via the exact same legacy-binding closure pattern FF/SM already use.
  The composition root's own sealed-evidence acquisition block is skipped entirely
  (never runs, never persists anything) when the switch is off, so disabling it can
  never discard or shadow any evidence a caller separately, deliberately acquired.

Deletion condition (documented in `strategy_runtime/adapters/earnings_calendar.py`'s
own docstring): delete `legacy_earnings_calendar_adapter` together with
`screening.live_adapters.build_live_earnings_calendar_adapter` in S14-PR-07 — not
before.

**Tested**, not merely built:
- `tests/strategy_runtime/adapters/test_registry.py::TestEarningsCalendarCutoverSwitch`
  — three unit tests proving the switch selects the intended adapter deterministically
  (each path's own distinct missing-dependency error message is the observable signal),
  independent of any live-fixture success/failure.
- `tests/asa/test_scheduled_screening.py::
  test_earnings_calendar_cutover_disabled_restores_the_legacy_attempt_scoping` —
  end-to-end through `run_scheduled_refresh`, proving the disabled switch produces at
  least one real, durably persisted attempt scoped under the cycle's own real
  `screening_cycle_id` (the plan-scoped identity, which stamps its own `plan_id` onto
  both `screening_cycle_id` and `pair_evaluation_id`, never appears).

## 6. Known, accepted limitation (not fixed in this PR)

`SubjectAcquisitionPlan.plan_id` (S14-PR-03's own, already-merged design) stamps a
single string onto *both* `screening_cycle_id` and `pair_evaluation_id` for its
internally persisted attempt records. Earnings Calendar's own plan is built with
`plan_id = pair_id` (this pair's own `screening_cycle_id:earnings_calendar:symbol`
composite) — traceable back to the real cycle (the real `screening_cycle_id` is its own
prefix), but not byte-identical to how every other pair in the same cycle records that
field. Inherited from S14-PR-03, not introduced or altered here; not touched, since
`market_data/subject_plan.py` is already-merged, already-tested code outside this
ticket's own scope.

## 7. CUTOVER_PASS checklist (Architect directive #5, item by item)

- **Exact output parity, or a specifically identified and versioned intentional
  difference.** Shadow-parity test
  (`tests/strategy_runtime/adapters/test_earnings_calendar.py::
  test_full_sealed_acquisition_matches_the_pre_cutover_live_path`) confirms the old and
  new paths reach the same PASS/NO_SIGNAL classification and the same numeric
  `strategy_native_score` for identical scripted evidence — verified genuinely
  reaching a real PASS with a real score (62.5), not a degenerate both-fail case
  (confirmed by direct reproduction, not test-output assumption alone). One
  intentional, documented difference: §2.12/§4 — a capability with literally zero
  enabled providers, and only through the new path, would (absent the fix already
  applied) surface as an infrastructure failure rather than a graceful outcome; this is
  now fixed to match the old path's own behavior exactly, not left as an open
  difference.
- **Zero provider calls originating from the Earnings strategy or its adapter.**
  `strategy_runtime/adapters/earnings_calendar.py` imports no provider, transport, or
  fulfillment type at all (only `market_data.CapabilityFulfillmentService` as a type
  hint for the *legacy* rollback function); its own architecture boundary is enforced
  by `tests/architecture/test_screening_boundaries.py`'s new
  `test_strategy_runtime_dependency_is_not_circular` plus the existing permitted-roots
  sweep.
- **One subject plan and one shared exhausted-failure/UNKNOWN outcome.**
  `SubjectAcquisitionPlan` (S14-PR-03, unmodified) is built once per subject per cycle
  and reused for every capability request the orchestrator makes.
- **Every Earnings evaluation references its sealed snapshot digest and derived-fact
  identities.** Asserted directly in the shadow-parity test
  (`sealed_evidence.snapshot.snapshot_digest` truthy); every derived fact's own ID is
  built via `derived_fact_id(feature_id, subject, snapshot.snapshot_digest)`.
- **A tested rollback switch that restores only the old Earnings path without deleting
  new evidence.** §5.
- **Full suite, production-equivalent cycle, and shadow evidence all green.** Full
  suite: 2895 passed, 45 skipped, 0 failed (`pytest`, excludes nothing but genuinely
  environment-gapped Postgres-integration tests already marked `@pytest.mark.postgres`,
  unrelated to this PR). `ruff check` and `mypy` (strict, `asa` package) both clean
  across every file this PR touches.
- **No residual Earnings acquisition path remains reachable after the switch.** Not yet
  applicable — S14-PR-07 (delete superseded path) is the ticket that removes the old
  path entirely; this PR's own rollback switch is why it must stay reachable until
  then.

## 8. Test-count reconciliation

Prior audit note (2872 vs 2879) was already reconciled and confirmed correct at 2872
before this PR began. This PR adds 1 new test file (`screening/sealed_earnings_calendar.py`
has no direct test file of its own — exercised through
`tests/strategy_runtime/adapters/test_earnings_calendar.py`) and extends 6 existing
ones; current full-suite total is 2895 passed (2321 outside `tests/pos`, 574 inside),
45 skipped, 0 failed, reproduced twice.
