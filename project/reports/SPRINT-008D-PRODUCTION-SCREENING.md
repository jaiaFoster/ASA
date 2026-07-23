# SPRINT-008D — PROD-002: Scheduled Execution & Persistence

Status: Code complete, tested, and merged. **The first production run has not yet executed** —
this agent could not obtain a way to run a one-off command inside the live Railway container;
see Section 3. Requesting Founder action to complete this ticket's own definition of done.

Sprint reference: `docs/sprints/SPRINT-008D.yaml`
Repository commit at report time: `453b541` (`main`)

## 1. Objective

Establish a scheduled or externally-triggered execution workflow that runs
`screening.service.refresh()` for the PROD-001 universe and persists results through the
existing `ScreeningStateRepository` — the same shared execution graph the CLI and API already
use, not a new one. Execute at least one complete production run and confirm the populated
results are visible through the public API.

## 2. What was built

`asa/scheduled_screening.py` (merged, `PR #201`): a standalone module, invoked as
`python -m asa.scheduled_screening [--json]`. For each of the 12 `(signal, symbol)` pairs in
PROD-001's universe (`project/reports/SPRINT-008D-SCREENING-UNIVERSE.md`), it calls
`screening.service.refresh()` directly — the identical function
`POST /api/v1/screening/{signal}/{symbol}/refresh` already calls — and persists through the real
`PostgresScreeningStateRepository`. No execution logic is reimplemented.

Not a background daemon: no loop, no in-process scheduler, no timer. It runs the full universe
once per invocation and exits, per this sprint's own `architecture_principles`
(`docs/sprints/SPRINT-008D.yaml`: "a scheduled execution workflow is not a new background daemon
inside the asa process").

`repository` and `transport_factory` are both injectable (default: the real Postgres repository
and the real live transport), so the full loop — including its own narrow infrastructure-failure
isolation, distinct from `screening/runner.py`'s already-thorough per-signal acquisition
isolation — is directly unit-tested without a live database or network
(`tests/asa/test_scheduled_screening.py`, 4 tests, all passing).

## 3. The first production run — blocked on tooling, not on code

This agent attempted to trigger `python -m asa.scheduled_screening --json` inside the live
production container via Railway's own service-management tooling (the same tooling ACT-001
used successfully to set a sealed variable, and PROD-004 confirmed cannot read an existing
sealed value back). Every attempt to have that tooling **run a command inside the container**
failed with a connection error from the tooling itself, repeated across multiple retries and two
separately worded requests — this appears to be a capability that tooling does not actually
support (Railway's platform does not generally expose arbitrary exec-into-container), not a
transient fluke worth retrying further.

**Requesting Founder action** to actually produce the first production run. The Railway CLI's
`run` command executes a one-off command with the target service's real environment variables
already injected — the standard way to do exactly this:

```bash
railway run --service ASA --environment production python -m asa.scheduled_screening --json
```

(Adjust the flag names to whatever your installed `railway` CLI version expects if they differ;
`railway service`/`railway environment` first, then a bare `railway run python -m
asa.scheduled_screening --json`, works identically if the CLI is already linked to this project.)

Please paste the resulting JSON output back — it contains only `signal_id`/`symbol`/`outcome`/
`request_count`/`error` fields, never a credential — so this report can be completed with real
results, and so `GET /api/v1/screening` can then be confirmed to show populated data through the
public API (this ticket's other own success criterion).

## 4. Scheduling mechanism — documented, not configured

Per your own direction, the ongoing scheduling mechanism (how often this runs going forward) is
documented here for you to set up when ready, rather than configured by this agent.

**Recommended approach**: a second, lightweight Railway service in the same project
(`03a96c3c-4661-4ade-a1f8-b0621fa5db1d`), pointed at the same GitHub repository and branch as the
existing `ASA` service, with:

- **Root Directory**: `.` (same as the existing service)
- **Start command**: `python -m asa.scheduled_screening --json` (overriding whatever `railway.json`
  would otherwise specify for this second service — Railway lets a service's dashboard-level
  start command override Config-as-Code per-service)
- **Cron Schedule**: set in the Railway dashboard (e.g. once daily before market open) — this is
  Railway's own built-in mechanism for exactly this need; no application code change required to
  use it
- **Environment variables**: reference the same `DATABASE_URL` (via `${{Postgres.DATABASE_URL}}`,
  identical to the existing `ASA` service) and the same `ASA_TRADIER_*`/`ASA_FINNHUB_*`/
  `ASA_ALPHA_VANTAGE_*` variables already configured on the `ASA` service — do not duplicate
  credential values by hand; Railway supports referencing another service's variables directly.

This keeps the always-on API service (`ASA`) completely untouched — it does not need a cron
schedule and should not have one, since it must keep serving HTTP traffic continuously. The new
service is small, purpose-built, and only ever runs for the duration of one scheduled invocation.

**Cadence recommendation**: once daily, before U.S. market open, is a reasonable starting point —
frequent enough that `age_seconds` on any given result rarely exceeds about 24 hours, infrequent
enough to stay well within every provider's own rate/request budget across 12 pairs. PROD-003
(cache and freshness policy) will make this precise once real execution timing data exists to
inform it, rather than this ticket guessing at a freshness threshold in isolation.

## 5. Verification once the first run completes

Once Section 3's command has been run, confirm via the public API (no code needed — this is
already-shipped, already-tested behavior from SPRINT-008):

```bash
curl -sS https://asa-production-b2c4.up.railway.app/api/v1/screening \
  -H "Authorization: Bearer $ASA_AGENT_API_TOKEN"
```

Expect `"total": 12` (or fewer, if any pair's acquisition genuinely failed — check each pair's
`outcome`/`error` in Section 3's JSON output first) and populated `results`.

## 6. Conclusion

Code, tests, and documentation for this ticket are complete and merged. The one remaining piece
— actually executing the first production run — requires a capability (running a one-off command
inside the live container) this agent's available tooling does not support; a precise, safe,
standard command is provided in Section 3 for the Founder to run directly. This ticket is not
marked complete in the final SPRINT-008D report until that run has actually happened and been
confirmed via Section 5.
