# Published portfolio contract

Version: v1

## Runtime and provider

The local and CI runtime is Python 3.12. `BrokerPortfolioProvider` exposes only `fetch_accounts` and `fetch_positions`. Slice 2 statically selects `DeterministicFakeBrokerPortfolioProvider`; it has no credentials or broker write operations.

The sanitized fixture always supplies one taxable USD account, one AAPL equity position, one long AAPL call leg, and one short AAPL call leg. Values and provider request identifiers are stable across executions.

## Run lifecycle

Statuses are `requested`, `running`, `succeeded`, and `failed`. Each run persists these steps:

1. `acquire_portfolio`
2. `normalize_portfolio`
3. `validate_publication`
4. `publish`

A run records request/start/completion timestamps, release SHA, effective configuration hash, and sanitized failure details. Execution is synchronous within `POST /api/v1/runs`.

## Publication invariant

A publication references exactly one successful run and its one snapshot. Snapshot insertion, normalized child insertion, successful run completion, publication insertion, and singleton pointer advancement share one transaction. Failure never changes the pointer.

`GET /api/v1/portfolio` and `GET /api/v1/positions` query only through that pointer. Their envelopes identify the same published run, publication, snapshot, freshness `as_of`, freshness status, and `serving_last_success` disclosure. If the latest run failed after the current successful run, `serving_last_success` is true.

## Normalized facts

Accounts retain external account identity, connection identity, provider, account type, display name, currency, and observation time. Equities retain symbol, quantity, optional average cost, observation time, and original provider. Option legs retain underlying/option symbols, call/put, strike, expiration, quantity, long/short side, optional average price, observation time, and original provider.

No valuation, options-chain data, lifecycle advice, strategy result, trade entry, position entry, or order operation is part of this contract.

## HTTP endpoints

- `POST /api/v1/runs`
- `GET /api/v1/runs/{run_id}`
- `GET /api/v1/runs/current`
- `GET /api/v1/portfolio`
- `GET /api/v1/positions`

Existing quote, health, and readiness endpoints retain their v1 behavior.
