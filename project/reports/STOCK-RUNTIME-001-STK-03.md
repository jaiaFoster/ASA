# STOCK-RUNTIME-001 — STK-03 evidence

## Outcome

B001 and B002 execute through the existing universal strategy runtime as
ordinary, provider-blind subject-first strategies:

- `strategies/stock_benchmark_planning.py` — bootstrap demands
  (`REAL_TIME_QUOTE_V1` for B001; plus `HISTORICAL_BARS_V1` for B002) and a
  no-op phase-two expansion (neither benchmark selects an expiration or any
  other second-phase evidence).
- `strategies/stock_benchmark_knowledge.py` — `KnowledgeMapping` bindings.
  B002's ten completed-month bars are flattened to a normalized
  `(end_at, adjusted_close, basis)` tuple before canonical-fact projection
  (`CanonicalFact.value` must be an immutable normalized scalar/tuple —
  a raw `OHLCVBar` cannot be projected directly) and reconstructed via a
  lightweight `AdjustedCloseBarLike`-satisfying object before calling
  STK-02's own `compute_sma_10m_completed_months` — the same real values,
  never fabricated ones, and the SMA formula itself stays exactly where
  STK-02 put it (`analytics/derived_facts.py`).
- `strategies/stock_benchmark_evaluation.py` — pure verdict logic: B001 is
  always PASS once reached (an unusable quote never reaches it — it is a
  typed `UnknownReason` from preparation, surfaced generically as
  MISSING_DATA); B002 is PASS only strictly above SMA10M, NO_SIGNAL at or
  below.
- `strategy_runtime/adapters/stock_benchmarks_subject_first.py` — the
  preparation callbacks and runtime adapters, mirroring the smallest
  existing subject-first shape in the repo
  (`tests/strategy_runtime/strat_proof_plugin.py`): no manifest, no graph
  evaluation, no option resolver invocation, no lifecycle.
- `strategy_runtime/adapters/__init__.py` — B001/B002 joined the shared
  composition root (`build_migrated_strategy_registry`,
  `build_migrated_shadow_registry`, `migrated_shadow_resolution_policy`,
  `build_migrated_signal_catalog`, `build_migrated_cutover_policy`) beside
  the three existing migrated strategies, with `subject_first_by_strategy_id`
  cutover `True` from the start (there is no legacy adapter for either
  benchmark to shadow against).
- `strategy_runtime/adapters/stock_benchmarks.py` — `B002_CONTRACT` gained
  a second, `RequirementCategory.CUSTOM` requirement documenting its
  `sma_10m_completed_months@1.0.0` dependency, following this repo's own
  established convention for a non-capability-backed requirement.

## Scheduling: a deliberately separate entry point

B001/B002 are **not** added to `PRODUCTION_SCREENING_UNIVERSE` or the
SP500 cohort-claim branch inside `asa/scheduled_screening.py`. Both paths
are pinned by existing fixture-driven tests
(`tests/asa/_fixture_market_data_access.py`'s `MultiExpirationFixtureProvider`)
built around a single-bar-per-request `HISTORICAL_BARS_V1` fixture with no
adjusted-close evidence at all — structurally incapable of ever satisfying
B002's ten-completed-month requirement. Forcing B001/B002 through that
shared fixture would have produced permanent, spurious `missing_data` for
B002 in `test_production_universe_topology_has_no_universal_preparation_failure`
and `test_default_scheduled_cycle_uses_bounded_sp500_cohort`, and required
inflating a 500-name-equity fixture just to serve two SPY-only benchmarks.

Instead, `asa/scheduled_screening.py` gained:

- `STOCK_BENCHMARK_UNIVERSE = (("B001", "SPY"), ("B002", "SPY"))`
- `run_scheduled_stock_benchmark_refresh(...)` — a thin wrapper calling
  `run_scheduled_refresh(STOCK_BENCHMARK_UNIVERSE, ..., enforce_schedule=False)`.
  Both benchmarks evaluate unconditionally on every invocation; there is no
  "stale subject" queue for a benchmark to wait its turn in, so this never
  routes through the SP500 cohort-claim machinery. The production scheduler
  (Railway cron) is expected to invoke this as its own separate trigger,
  independent of the options universe's own scheduled refresh — a Founder/
  deployment decision for STK-06, not implemented here.

## Verification

- `tests/strategies/test_stock_benchmark_planning.py`,
  `test_stock_benchmark_evaluation.py`,
  `test_stock_benchmark_knowledge.py` — unit-level demand/verdict/
  knowledge-mapping pins, including B002's insufficient-history and
  missing-adjusted-close typed-unknown paths.
- `tests/strategy_runtime/adapters/test_stock_benchmarks_subject_first.py`
  — sealed-snapshot integration tests through the real
  `compose_strategy_knowledge` orchestrator: B001 PASS/BUY, B001 unusable-
  quote typed unknown, B002 PASS/BUY, B002 NO_SIGNAL at the SMA boundary,
  B002 insufficient-adjusted-history typed unknown, and a deterministic-
  replay pin (composing the same sealed snapshot twice yields byte-
  identical facts).
- `tests/asa/test_scheduled_stock_benchmark_refresh.py` — a genuine
  end-to-end proof of `run_scheduled_stock_benchmark_refresh` through real
  acquisition → resolution → sealed snapshot → generic knowledge
  composition → subject-first adapter → persistence, against a
  purpose-built fixture provider that (unlike the shared
  `MultiExpirationFixtureProvider`) returns a genuine multi-month adjusted-
  close `OHLCVSeries`.
- `tests/strategy_runtime/adapters/test_registry.py` and
  `tests/architecture/test_migrated_strategy_acquisition_blindness.py`
  updated to expect five registered/shadow-bound strategy IDs instead of
  three; both pinned assertions confirmed the original three strategies'
  own identities and ordering are otherwise unchanged.
- Full `ruff check` and `mypy` clean on every new/modified file.
- Full local regression sweep (`tests/strategies`, `tests/strategy_runtime`,
  `tests/architecture`, `tests/analytics`, relevant `tests/market_data`
  and `tests/domain` suites): 824 passed. The only local failures are a
  pre-existing, unrelated Windows-locale (cp1252) `UnicodeDecodeError`
  reading a UTF-8 markdown fixture in
  `tests/architecture/test_market_data_platform_contract.py`, confirmed
  identical on a clean `main` checkout — not present on Linux CI.

## Compatibility

- No change to `asa/scheduled_screening.py`'s existing scheduled/manual
  universes, cohort-claim behavior, or any of their pinned test
  assertions.
- No change to `RequirementCategory`, `StrategyContract`, or any other
  shared contract primitive beyond the additive B002 requirement entry.
- `analytics/derived_facts.py`'s `compute_sma_10m_completed_months` now
  accepts `Sequence[AdjustedCloseBarLike]` (a structural Protocol) instead
  of `Sequence[OHLCVBar]` — every real `OHLCVBar` still satisfies it
  (confirmed against the full existing `tests/analytics/test_derived_facts.py`
  and `tests/market_data/test_finnhub.py` STK-02 suites, unchanged), widening
  the accepted input rather than narrowing it.
- No migration, no schema change, no broker access, no lifecycle, no
  option resolver invocation for either benchmark.

## Verdict

**COMPLETE.** STK-03 is done. Continuing to STK-04 (Robinhood portfolio
reuse-gap audit) next, per the sprint's uninterrupted execution model.
