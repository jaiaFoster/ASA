# Market observation contract

Version: v1

## Canonical owner

PostgreSQL table `market_observations` owns received normalized quote observations. Each ingestion appends an immutable record. The latest canonical quote is the row with the greatest `observed_at`, then `id`, for an uppercase symbol.

## Required fields

| Field | Meaning |
|---|---|
| `symbol` | Uppercase instrument symbol |
| `price` | Non-negative decimal provider price |
| `currency` | Uppercase ISO-style currency code |
| `observed_at` | UTC instant at which the provider observed the quote |
| `received_at` | UTC instant at which ASA normalized the quote |
| `provenance.selected_provider` | Adapter selected by composition |
| `provenance.original_provider` | Source named on the provider quote |
| `provenance.cache_status` | `miss` for this direct ingestion slice |
| `provenance.freshness_status` | `fresh` or `stale`, computed against configured age |
| `provenance.fallback_reason` | Null because fallback is excluded |
| `provenance.provider_request_id` | Correlation ID returned by the provider adapter |

Freshness is recomputed when canonical data is queried. Consequently a record older than the configured threshold can never retain `fresh` in an API response.

## HTTP contract

- `POST /api/v1/market/quotes/ingest` accepts `{ "symbols": ["AAPL"] }`; it is available only when `ASA_ENVIRONMENT=development`.
- `GET /api/v1/market/quotes/{symbol}` returns the latest persisted canonical observation and never contacts a provider.
- `GET /api/v1/health` reports process liveness.
- `GET /api/v1/readiness` returns 503 unless a database query succeeds.

The checked-in OpenAPI document at `frontend/src/api/openapi.json` drives the generated TypeScript client under `frontend/src/api/generated`. CI regenerates it and rejects drift.
