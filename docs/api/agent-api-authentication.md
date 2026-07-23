# Agent Data API — Authentication

Applies to every route under `/api/v1/capabilities` and `/api/v1/screening*`
(`asa/api/screening_routes.py`, SPRINT-008). This is a separate surface from the existing
`/ops/market-data/validate` operations endpoint (`docs/deployment/railway.md`) and from ASA's
existing `/api/v1/*` portfolio/quote endpoints (`asa/api/routes.py`) — none of these three groups
share a token.

## Scheme

A single static bearer token, compared with `hmac.compare_digest`
(`asa.market_data_ops.auth.token_matches`, reused as-is — this codebase's only existing
authentication precedent, not a new mechanism invented for this API). No JWT, OAuth, session, or
API-key-header support exists.

Send it on every request:

```text
Authorization: Bearer <ASA_AGENT_API_TOKEN value>
```

## Configuration

Set `ASA_AGENT_API_TOKEN` as a sealed Railway service variable (see
`docs/deployment/railway.md`). Locally, set it in `.env` or the process environment; the field is
`asa.config.Settings.agent_api_token` (a `pydantic.SecretStr`, so it is never logged by pydantic's
own repr/str machinery). Do not reuse `ASA_OPERATIONS_TOKEN` or any provider credential for this
value — pick an independent secret.

## Failure behavior — read this before writing a client

Every route in this surface fails closed to a **generic 404**, never a 401 or 403, in all three of
these cases:

1. `ASA_AGENT_API_TOKEN` is not configured on the deployment at all.
2. The request has no `Authorization` header, or it does not start with `Bearer `.
3. The presented token does not match the configured one.

This is deliberate (matching `/ops/market-data/validate`'s own established convention): the
endpoint's existence itself is hidden from an unauthenticated caller rather than confirmed via a
401/403. A client should not distinguish "wrong token" from "this API doesn't exist here" — both
look identical on the wire.

One consequence worth knowing: an authentication failure returns FastAPI's own default 404 body,
`{"detail": "Not Found"}` — **not** this API's `{error_code, message}` error shape (see
`docs/api/agent-api-examples.md`). The structured `AgentApiError` shape only appears for
authenticated requests that fail *after* the auth dependency succeeds (unknown signal, unsupported
symbol, etc.). Do not write a client that assumes every 404 carries an `error_code` field.

## What is never exposed

No response from this surface — success or error — ever contains a provider credential, the
configured `ASA_AGENT_API_TOKEN` value, or any other secret. This is verified by test, not just by
convention: `tests/asa/test_screening_refresh_route.py` and
`tests/asa/test_ai_agent_workflow.py` both assert the fake credential driving a scripted live
refresh never appears in any response body across the full request/response cycle.
