# SPRINT-013 S13-03A Wiring — Notes and Blocker Packet

## What this PR wires

`ProviderRollingWindowTracker` (merged in PR #271, S13-03A core) is now
actually consulted in production:

- `strategy_runtime/market_data_planning.py::build_provider_rolling_window_tracker`
  builds one tracker from `declared_rolling_window_policies()`, which sources
  policies *only* from each provider's own typed, declared limit
  (`tradier_rolling_window_policy()`, `finnhub_rolling_window_policy()` — both
  defined in their own provider modules, reading the exact same module
  constants `ProviderMetadata.declared_limits` already uses, so the two can
  never drift). Alpha Vantage gets no policy function and is reported via
  `no_declared_rolling_limit` — the installed key's plan tier is not knowable
  from configuration, so no limit is invented for it, per explicit instruction.
- `asa/scheduled_screening.py::run_scheduled_refresh` constructs exactly one
  tracker per invocation, beside `screening_cycle_id`, and passes the same
  instance into every pair's `build_shared_market_data_access(...,
  rolling_window=...)` call within that cycle. A fresh call to
  `run_scheduled_refresh` always gets a fresh tracker — no module-global
  singleton.
- `RequestBudgetManager.authorize()` consults the tracker as the **last**
  gate, only after every pair-local check (total ceiling, burst, retry) has
  already passed — a shared-window refusal never burns a pair's own local
  accounting, and a request that was going to be refused locally never wastes
  a shared reservation either.
- Distinct diagnostics (four new `ProviderErrorCode` values —
  `pair_budget_exhausted`, `pair_burst_exhausted`,
  `provider_rolling_window_exhausted`, `provider_cooldown_active`) replace the
  single generic `quota_exhausted` `BudgetExhaustedError` used to always
  normalize to. Folded into S13-02's `LOCAL_QUOTA_EXHAUSTED` aggregate bucket
  (unchanged, still closed), but `AcquisitionAttemptRecord.diagnostic_code`
  preserves the exact reason losslessly.

## BLOCKED_DISTRIBUTED_QUOTA_OWNERSHIP

**Exact blocked action:** claiming `ProviderRollingWindowTracker` enforces a
provider's real external rate limit *globally*, across the whole deployment.
It does not — it is in-process and cycle-local by construction, exactly as
instructed ("continue implementing truthful single-cycle enforcement"), so
this is not a defect in this PR; it is a scope boundary this PR is not
authorized to close, flagged explicitly rather than silently claimed.

**Confirmed root cause / topology** (verified via Railway MCP
`get-status`/`get-service-config` reads, no changes made):

| Service | Replicas | Trigger | Credentials |
|---|---|---|---|
| `ASA` (web) | 1 | always-on (`python -m asa`) | `ASA_TRADIER_ACCESS_TOKEN`, `ASA_FINNHUB_API_KEY`, `ASA_ALPHA_VANTAGE_API_KEY` all configured |
| `trustworthy-education` (cron) | 1 | `*/10 13-20 * * 1-5` (`python -m asa.scheduled_screening --json`, `restartPolicyType: NEVER`) | same three credentials, configured independently |

These are two **separate OS processes**. The always-on web service can serve
a live on-demand refresh at any moment via `screening/live_acquisition.py`'s
own separate provider-wiring (deliberately not touched by this PR — see
`strategy_runtime/market_data_planning.py`'s own docstring on why the two
paths stay independent). If that happens while the cron job is mid-cycle,
each process's own `ProviderRollingWindowTracker` (or, for the web service,
no tracker at all today) has zero visibility into the other's concurrent
usage. Their combined real request rate to Tradier/Finnhub could exceed the
declared external limit even though each process's own internal accounting
believes it is within budget.

**Why current authority/tools cannot resolve it:** a genuinely cross-process
shared rate limiter requires persistent, atomic, externally-visible state —
in-memory Python objects cannot cross process boundaries. The smallest
correct fix is a new piece of shared infrastructure, not a code change to
existing modules.

**Options, with tradeoffs:**

- (a) **Do nothing further** — accept in-process-only enforcement as the
  practical ceiling for now. Real risk: only materializes if a live on-demand
  refresh and a scheduled cycle overlap AND their combined rate exceeds the
  provider's real limit — plausible but not guaranteed on every occurrence.
- (b) **Postgres-backed row/advisory-lock token-bucket table** (recommended),
  reusing the exact persistence pattern S13-02 already established
  (`PostgresAcquisitionAttemptRepository`,
  `PostgresRefreshScheduleClaimRepository`'s `ON CONFLICT DO NOTHING`
  idempotency pattern): one row per `(provider_id, window_start)`, an atomic
  `UPDATE ... SET count = count + 1 WHERE count < limit RETURNING` (or a
  Postgres advisory lock around a read-modify-write) as the reservation
  primitive, consulted by `ProviderRollingWindowTracker.try_reserve()`
  instead of (or in addition to) its in-memory list when a shared connection
  is available. Scoped to Tradier/Finnhub only (the two providers with
  declared limits). Requires a new migration.
- (c) **External rate-limiting proxy or Railway-level throttle** — outside
  this codebase entirely, not evaluated here.

**Recommended option:** (b) — smallest correct fix, reuses an already-proven
pattern from this same sprint, no new infrastructure category introduced.

**Smallest Founder action required:** authorize a follow-up ticket (S13-03A
step 2, or folded into S13-03B) for the Postgres-backed shared token-bucket
table, including its migration — explicitly out of this PR's bounded scope
(no migration in this PR itself, per the PR boundary).

**Work continuing in parallel:** this PR ships truthful single-cycle
enforcement now, per instruction; it does not block on this decision.
