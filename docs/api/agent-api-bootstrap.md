# Agent Data API — Bootstrap Guide

What to expect and do on a brand-new deployment, with zero prior knowledge of this codebase and
zero existing screening data. Read `docs/api/agent-api-authentication.md` first for the token
contract; this guide assumes you already have a valid `ASA_AGENT_API_TOKEN` value.

Written and validated against `tests/asa/test_bootstrap_first_run.py`, which exercises every step
below in sequence against a genuinely empty repository — not retrofitted after the fact.

## Before you start: what "empty" looks like

A freshly migrated deployment has run every Alembic migration but has **zero rows** in
`screening_state` — nothing has ever been screened yet. This is the normal, expected starting
state, not an error condition and not a sign anything is broken. The single most common source of
confusion here: **an empty result set is not a 404.** `GET /api/v1/screening` and
`GET /api/v1/screening/{signal}` both return `200` with `{"results": [], "total": 0, ...}` on a
completely empty database — they never 404 just because there is no data yet. Only a lookup for
one specific signal/symbol pair (`GET /api/v1/screening/{signal}/{symbol}`) 404s when that exact
pair has no result, and it does so with this API's own structured error body
(`{"error_code": "NO_SCREENING_RESULT", ...}`), distinguishable from an authentication failure's
bare `{"detail": "Not Found"}`. See `docs/api/agent-api-authentication.md` for why both cases use
404 at all.

## Step 1 — discover what this deployment can do

```bash
curl -sS https://<host>/api/v1/capabilities -H "Authorization: Bearer $ASA_AGENT_API_TOKEN"
```

Always succeeds on any correctly configured deployment, empty or not — this is a fixed catalog,
never a live query. Expect `200` and a `signals` array (three entries as of this writing:
`earnings_calendar`, `forward_factor`, `skew_momentum`). If this 404s, the deployment's token is
missing or wrong — stop here and resolve that before anything else (SPRINT-008D's own ACT-001
investigation found and fixed exactly this failure mode on this deployment; see
`project/reports/SPRINT-008D-API-ACTIVATION.md` if it recurs).

## Step 2 — confirm the empty state, correctly

```bash
curl -sS https://<host>/api/v1/screening -H "Authorization: Bearer $ASA_AGENT_API_TOKEN"
```

Expect `200` and `{"results": [], "total": 0, "limit": 100, "offset": 0}`. This is success, not a
problem to fix — it means authentication and the read path both work; there is simply nothing to
report yet.

## Step 3 — produce your first real result

Nothing populates `screening_state` on its own (no scheduled job exists yet — see
`docs/api/agent-api-operations.md`). To get real data, explicitly refresh one signal/symbol pair
that both (a) the deployment has a live provider configured for, and (b) is within the approved
live-refresh universe (`AAPL`, `MSFT`, `NVDA`, `AMD`, `SPY`, `QQQ` as of this writing):

```bash
curl -sS -X POST https://<host>/api/v1/screening/skew_momentum/AAPL/refresh \
  -H "Authorization: Bearer $ASA_AGENT_API_TOKEN"
```

Three possible outcomes, all documented in `docs/api/agent-api-examples.md`:

- `200` with a screening result and `request_count` — succeeded; proceed to Step 4.
- `503 NO_LIVE_PROVIDER_CONFIGURED` — no live market data provider is enabled on this deployment
  yet. This is a deployment configuration matter (`ASA_TRADIER_ENABLED` etc.), not something a
  caller can work around from the API itself.
- `422 UNSUPPORTED_SYMBOL` — the symbol you chose isn't in the approved universe; pick one from
  the list above.

## Step 4 — confirm your first result is visible

```bash
curl -sS https://<host>/api/v1/screening/skew_momentum/AAPL -H "Authorization: Bearer $ASA_AGENT_API_TOKEN"
```

Expect `200` with the same result Step 3 returned (minus `request_count`, which is specific to
the refresh response, not stored state), `age_seconds` near zero. `GET /api/v1/screening` (no
path parameters) will now also include this one result in its list.

## You now have a working bootstrap

From here, every workflow in `docs/api/agent-api-examples.md` is available, and
`tests/asa/test_ai_agent_workflow.py` demonstrates a fuller session (multiple pre-existing
results, freshness-based refresh decisions, a generated summary) built on exactly this same
foundation. How a production deployment gets a real, continuously useful screening universe
rather than one manually-refreshed pair — a defined symbol universe, a scheduled execution
workflow, and a documented caching policy — is SPRINT-008D's own Phase 2 (PROD-001 through
PROD-005; see `docs/sprints/SPRINT-008D.yaml` and, once merged, `project/reports/SPRINT-008D.md`).
