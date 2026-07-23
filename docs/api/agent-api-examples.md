# Agent Data API — Examples

Endpoints, response shapes, and error bodies for `/api/v1/capabilities` and `/api/v1/screening*`.
Every example below is real output captured from the running application (`asa.bootstrap.build_application()`),
against synthetic seeded data — not a hand-written mock of the schema. See
`docs/api/agent-api-authentication.md` first for the token and failure-mode contract these all
depend on, and `tests/asa/test_ai_agent_workflow.py` for a full worked walkthrough exercising every
one of these calls in sequence.

All requests below send `Authorization: Bearer <token>`; omitted here for brevity.

## `GET /api/v1/capabilities`

Lists every registered signal and its declared canonical input requirements. Never changes at
runtime — this is a fixed catalog (`screening.registry.ScreeningRegistry`), not a live query.

```bash
curl -sS https://<host>/api/v1/capabilities \
  -H "Authorization: Bearer $ASA_AGENT_API_TOKEN"
```

```json
{
  "signals": [
    {
      "signal_id": "earnings_calendar",
      "signal_version": "1.0.0",
      "manifest_id": "f349ab40630bc0b319b2f255cfe4a7bdb16a1b220f0845c30ebb9d4541918475",
      "required_capabilities": ["earnings_calendar_v1", "option_chain_v1"]
    },
    {
      "signal_id": "forward_factor",
      "signal_version": "1.1.0",
      "manifest_id": "098822354245d9cfccd8d2b77b2fc185dfb30425429b608a58430807cbf7b857",
      "required_capabilities": ["option_chain_v1"]
    },
    {
      "signal_id": "skew_momentum",
      "signal_version": "1.0.0",
      "manifest_id": "f5ea7d5d16771104bb324b109e75c16672bdbfabdece766be67f8fb4b71caf8c",
      "required_capabilities": ["option_chain_v1"]
    }
  ]
}
```

## `GET /api/v1/screening` — all current results, paginated

`?limit=` (default 100, max 500) and `?offset=` (default 0) are both optional. This route (and
the two below) only ever reads through the injected repository — it never triggers a provider
request, verified by test (`tests/asa/test_screening_routes.py::TestReadsNeverComputeOrPersist`),
not merely by inspection.

```bash
curl -sS "https://<host>/api/v1/screening?limit=50" \
  -H "Authorization: Bearer $ASA_AGENT_API_TOKEN"
```

```json
{
  "results": [
    {
      "updated_at": "2026-07-23T06:00:10.853465Z",
      "age_seconds": 720,
      "signal_id": "forward_factor",
      "signal_version": "1.0.0",
      "symbol": "AAPL",
      "outcome": "pass",
      "explanation": "calendar richness within bounds",
      "metrics": { "strategy_native_score": "0.42" }
    }
  ],
  "total": 1,
  "limit": 100,
  "offset": 0
}
```

`updated_at` and `age_seconds` (computed server-side at request time) appear on every screening
result — this API deliberately exposes only the raw ingredient for a freshness decision, never an
opinion about what counts as "stale." `GET /api/v1/screening/{signal}` narrows the same envelope to
one signal across all symbols.

## `GET /api/v1/screening/{signal}/{symbol}` — one result

```bash
curl -sS https://<host>/api/v1/screening/forward_factor/AAPL \
  -H "Authorization: Bearer $ASA_AGENT_API_TOKEN"
```

```json
{
  "updated_at": "2026-07-23T06:00:10.853465Z",
  "age_seconds": 720,
  "signal_id": "forward_factor",
  "signal_version": "1.0.0",
  "symbol": "AAPL",
  "outcome": "pass",
  "explanation": "calendar richness within bounds",
  "metrics": { "strategy_native_score": "0.42" }
}
```

No result yet for that pair — 404 with this API's structured error shape:

```json
{
  "detail": {
    "error_code": "NO_SCREENING_RESULT",
    "message": "No screening result for 'forward_factor'/'MSFT'"
  }
}
```

Unregistered signal — also 404, different `error_code`:

```json
{
  "detail": {
    "error_code": "UNKNOWN_SIGNAL",
    "message": "No registered signal 'not_real'"
  }
}
```

## `POST /api/v1/screening/{signal}/{symbol}/refresh` — the one write operation

Triggers exactly one live provider acquisition for exactly the requested signal/symbol pair —
never a whole signal or the whole universe. See `docs/api/agent-api-operations.md` for the
current-deployment availability caveat.

```bash
curl -sS -X POST https://<host>/api/v1/screening/skew_momentum/AAPL/refresh \
  -H "Authorization: Bearer $ASA_AGENT_API_TOKEN"
```

Success (200) — a screening result plus `request_count`, the number of live provider requests the
refresh consumed:

```json
{
  "updated_at": "2026-07-23T06:12:11.041Z",
  "age_seconds": 0,
  "signal_id": "skew_momentum",
  "signal_version": "1.0.0",
  "symbol": "AAPL",
  "outcome": "pass",
  "explanation": "...",
  "metrics": { "strategy_native_score": "0.31" },
  "request_count": 1
}
```

Symbol outside the approved live refresh universe (`AAPL`, `MSFT`, `NVDA`, `AMD`, `SPY`, `QQQ`) —
422:

```json
{
  "detail": {
    "error_code": "UNSUPPORTED_SYMBOL",
    "message": "Refresh is bounded to the approved live universe ('AAPL', 'MSFT', 'NVDA', 'AMD', 'SPY', 'QQQ'), not 'NOTREAL'"
  }
}
```

No live market data provider enabled for this deployment — 503:

```json
{
  "detail": {
    "error_code": "NO_LIVE_PROVIDER_CONFIGURED",
    "message": "No live market data provider is enabled for this deployment"
  }
}
```

Unknown signal — the same 404 `UNKNOWN_SIGNAL` shape shown above.

## Every response also carries

- `API-Version: v1` response header (set on every request by `asa.bootstrap`'s own middleware, not
  just this surface) — a caller can confirm which contract it is talking to.
- `X-Request-ID` — echoes the caller's own header if sent, otherwise a generated UUID; useful for
  correlating a report to server-side structured logs.
