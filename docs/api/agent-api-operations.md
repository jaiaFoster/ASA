# Agent Data API — Operational Notes

## No in-process background refresh; scheduling is external (SPRINT-008D)

Nothing inside the `asa` application process refreshes screening state on its own — no daemon,
no in-process timer, no background thread. This was an explicit exclusion in SPRINT-008
(`docs/sprints/SPRINT-008.yaml`: `automatic_scheduling`/`background_refresh_daemon`) and remains
true after SPRINT-008D: `asa/scheduled_screening.py` (PROD-002) is a standalone script that runs
once and exits, not a daemon added to this process.

State changes three ways: an external scheduler invoking `python -m asa.scheduled_screening`
(intended cadence and rationale: `docs/screening/cache-lifecycle.md`), any other direct batch/CLI
run, or a caller explicitly invoking `POST /api/v1/screening/{signal}/{symbol}/refresh`. An agent
(or any caller) is still responsible for deciding when a *specific* result is stale enough to
warrant its own explicit refresh — the API only ever reports `age_seconds`, never an opinion on
staleness — but a scheduled baseline now exists so results are not exclusively dependent on a
caller ever refreshing them at all.

## The refresh endpoint is narrow by construction

`POST /api/v1/screening/{signal}/{symbol}/refresh` always triggers exactly one live acquisition
for exactly one signal/symbol pair. There is no "refresh everything" or "refresh this whole
signal" operation, and none is planned as an extension of this endpoint — a caller that needs
several symbols refreshed must call it once per pair. The endpoint is also bounded to a fixed
approved symbol universe (`AAPL`, `MSFT`, `NVDA`, `AMD`, `SPY`, `QQQ` —
`screening.live_acquisition.APPROVED_LIVE_UNIVERSE`); this list is not configurable per-request
and changing it is an architecture-level decision, not an operational one.

## Current live-provider availability (production)

As of `project/reports/POST-005B-LIVE-VALIDATION.md`, no live market data provider credential
(`ASA_TRADIER_ACCESS_TOKEN`, `ASA_FINNHUB_API_KEY`, `ASA_ALPHA_VANTAGE_API_KEY`) is configured in
the production deployment. Consequently:

- `GET /api/v1/capabilities` and `GET /api/v1/screening*` are fully available and unaffected —
  they never depend on a provider.
- `POST /api/v1/screening/{signal}/{symbol}/refresh` currently returns `503
  NO_LIVE_PROVIDER_CONFIGURED` for every request, regardless of signal or symbol. This is a
  documented, expected external blocker (absent Founder-supplied credentials), not a defect —
  see `docs/deployment/market-data-provider-diagnostics.md` for how to supply them.

Re-check this section's currency against the latest `POST-*-LIVE-VALIDATION` report before
relying on it — provider credentials are operational configuration, not application state, and
can change independently of any code deployment.

## Rate limiting and request budgets

The refresh endpoint has no request-rate limit of its own at the HTTP layer (unlike
`/ops/market-data/validate`, which is capped at 50 runs/hour). What it does have is the market
data layer's own fixed per-refresh acquisition budget (`screening.live_acquisition`'s
`RequestBudgetManager`, shared with the CLI's own refresh path) — each registered signal's own
live adapter (`screening/live_adapters.py`) issues a small, fixed, signal-specific sequence of
provider requests (a spot quote, an expiration-date lookup, and one or more option-chain fetches,
depending on the signal) and never an open-ended or unbounded one. The response's `request_count`
field reports exactly how many were consumed for that call. A caller building a production
integration should still apply its own call-rate discipline, since nothing server-side throttles
*how often* `POST .../refresh` itself can be called.

## Determinism

Read endpoints are deterministic for a given repository state: identical requests against
unchanged state return identical bodies except `age_seconds`, which increases with real elapsed
time by design. `POST .../refresh` is not deterministic in the sense of producing the same
`outcome` every time (it reflects real, changing market data) but is deterministic in structure —
same response shape, same error codes for the same failure conditions, every time. This exact
property (not merely a claim) is enforced by `tests/asa/test_ai_agent_workflow.py`, which asserts
an immediate repeat `GET` after a refresh returns identical field values.

## Logging and observability

Every request is tagged with `X-Request-ID` (caller-supplied or server-generated) via
`asa.bootstrap`'s own middleware, present in structured logs for correlation. As documented in
`docs/api/agent-api-authentication.md`, no request or response for this surface is ever logged
with a credential or token value.

## What a monitoring/alerting integration should watch

- `GET /api/v1/health` / `GET /api/v1/readiness` — existing platform health surface, unrelated to
  this API's own auth; unauthenticated, always reachable.
- A sustained run of `503 NO_LIVE_PROVIDER_CONFIGURED` on refresh is a configuration signal, not
  an application error — do not page on it without also checking current provider-credential
  configuration.
- A sustained run of `404` on every request to `/api/v1/capabilities` or `/api/v1/screening*`
  despite a correct token most likely means `ASA_AGENT_API_TOKEN` is unset or was rotated without
  updating the caller — check the Railway service variable first.
