# Legacy screening runtime deprecation plan

SPRINT-009R/EPIC-R5. As of this cutover, `POST /api/v1/screening/{signal}/{symbol}/refresh`
and every `GET /api/v1/screening*` read endpoint execute through `strategy_runtime` (see
`asa/api/screening_routes.py`, `asa/bootstrap.py`, `asa/scheduled_screening.py`), reading and
writing `universal_screening_state` (`asa/integrations/universal_screening_postgres.py`)
instead of `screening_state`. The public HTTP contract is unchanged --
`tests/asa/test_screening_engine_parity.py` proves the legacy and strategy_runtime-backed
paths translate identical execution output to an identical wire response.

## What is not deprecated yet

`screening/` (the package) is **not removed or frozen** by this cutover:

- `strategy_runtime/adapters/{forward_factor,skew_momentum_vertical,earnings_calendar}.py`
  each still call the exact same, unmodified execution graph
  (`screening.adapters.TARGET_STRATEGY_REGISTRY`, `screening.runner.run_screening()`) --
  `screening/` is now infrastructure `strategy_runtime` depends on, not a parallel system.
- `screening/cli.py` (`python -m screening`) is untouched and still fully functional, for
  local diagnostics and the same manual workflows it has always supported.
- `screening_state` (the Postgres table) and `PostgresScreeningStateRepository` are untouched.
  They are simply no longer read or written by the production API or the scheduled runner as
  of this cutover -- existing rows remain queryable directly (`psql`, an ad hoc script) for as
  long as an operator wants historical reference, and nothing in this repository writes to
  that table anymore going forward.

## What genuinely is deprecated

- `asa/integrations/screening_postgres.py`'s `PostgresScreeningStateRepository` has no more
  production callers (`asa/bootstrap.py`, `asa/scheduled_screening.py` both moved to
  `PostgresLatestResultRepository`). It remains only for its own direct repository tests
  (`tests/asa/test_screening_postgres.py`) and any future ad hoc migration tooling.
- `screening.service.get_state()`/`refresh()` have no more production callers either --
  `strategy_runtime.service.get_state()`/`refresh()` replace them at every call site that used
  to invoke them. `screening.service` remains directly tested
  (`tests/asa/test_screening_service_postgres_integration.py`) and directly usable by
  `screening/cli.py`.

## Recommended follow-up (not part of this cutover)

1. **Backfill or accept a cold start.** `universal_screening_state` starts empty in any
   deployment that already had rows in `screening_state` -- the first scheduled run (or the
   first `refresh()` call per signal/symbol) repopulates it exactly the way the very first
   scheduled run ever did for `screening_state`. A one-time backfill script (read
   `screening_state`, translate through `strategy_runtime.result.UniversalScreeningResult`,
   write through `PostgresLatestResultRepository`) is straightforward if a cold start is
   undesirable, but is intentionally not built here -- SPRINT-009R's own `non_goals` rule out
   speculative infrastructure with no proven need yet, and a production deployment's actual
   downtime tolerance for this is a Founder decision, not an engineering default.
2. **Retire `screening_state`** (drop the table, delete `PostgresScreeningStateRepository` and
   its test) once an operator confirms no deployment still needs to read the old table
   directly. Not scheduled here -- this is a data-retention decision, not a code change this
   sprint's own `platform_before_features` guardrail should make unilaterally.
3. **Retire `screening.service.get_state()`/`refresh()`** (the two now-production-dead
   functions) in the same pass as (2), once `screening/cli.py`'s own manual workflows (if
   still wanted) are confirmed to work equally well against `strategy_runtime.service`
   instead, or are retired alongside them.
4. **`/api/v1/capabilities` still reads `screening.registry.signal_catalog()`** (not cut over
   in this epic -- it serves static catalog metadata, including `manifest_id`, which
   `strategy_runtime.contract.StrategyContract` has no field for, and it executes nothing).
   Adding a `manifest_id`-equivalent to `StrategyContract` and cutting this one remaining
   endpoint over is a small, separate follow-up, not blocking anything in this plan.

None of the above is scheduled or required before this cutover is considered complete --
SPRINT-009R's own success criterion is "Existing Screening API executes through
strategy_runtime; public API contract remains unchanged; output parity is verified before
cutover," all three of which this PR satisfies today.
