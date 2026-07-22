# Railway backend deployment

## Service layout

Create a Railway service from the ASA GitHub repository with these settings:

- Root directory: `/backend`
- Config-as-code path: `/railway.json` relative to that service root
- Builder: Railpack
- Pre-deploy command: `alembic upgrade head`
- Start command: `python -m asa`
- Healthcheck: `/api/v1/health`

`backend/railway.json` commits the builder and deploy settings. Railway injects `PORT`; the ASA executable binds Uvicorn to `0.0.0.0:$PORT`. Railway runs the pre-deploy command with service variables and prevents rollout if the migration exits nonzero. See Railway’s [pre-deploy command](https://docs.railway.com/deployments/pre-deploy-command), [start command](https://docs.railway.com/deployments/start-command), and [healthcheck](https://docs.railway.com/deployments/healthchecks) documentation.

## PostgreSQL

Add a Railway PostgreSQL service. The backend accepts Railway’s `DATABASE_URL` directly and normalizes `postgres://` or `postgresql://` to SQLAlchemy’s `postgresql+psycopg://` driver form. Use a Railway reference variable such as `${{Postgres.DATABASE_URL}}`; do not copy a database password into repository files. Railway documents the available PostgreSQL connection variables in its [PostgreSQL guide](https://docs.railway.com/databases/postgresql).

## Deterministic deployment

For a deployment that exercises infrastructure without Robinhood:

```text
ASA_ENVIRONMENT=development
ASA_BROKER_PORTFOLIO_PROVIDER=deterministic_fake_broker
```

No Robinhood variables are required in this mode.

## Read-only Robinhood deployment

Set the following Railway service variables:

```text
ASA_BROKER_PORTFOLIO_PROVIDER=robinhood
ASA_ROBINHOOD_USERNAME=<sealed variable>
ASA_ROBINHOOD_PASSWORD=<sealed variable>
ASA_ROBINHOOD_TOTP_SECRET=<optional sealed variable>
ASA_ROBINHOOD_ACCOUNT_NUMBERS=<optional comma-separated account numbers>
```

Seal username, password, and TOTP values in Railway. Do not store them in `.env`, service commands, screenshots, tickets, or logs. Railway’s [sealed variables](https://docs.railway.com/variables) remain available to deployments without being retrievable through its UI or API.

When `robinhood` is selected, ASA validates username and password during startup and exits before serving if either is absent. The optional TOTP secret produces an MFA code in memory. The adapter disables robin_stocks session-file storage and suppresses SDK output; ASA never persists or returns credentials, tokens, cookies, or raw broker payloads.

## Bounded live Market Data validation endpoint

`POST /ops/market-data/validate` runs the existing bounded Market Data validation
framework (`market_data.validation`, `market_data.factory`, `market_data.budget`)
against live Tradier/Finnhub/Alpha Vantage APIs, using only fixed, safe, pre-reviewed
validation subjects (never symbols or endpoints from the request body).

Set `ASA_OPERATIONS_TOKEN` as a sealed Railway service variable to enable it; it must
never be reused for provider credentials. Requests must send
`Authorization: Bearer <ASA_OPERATIONS_TOKEN>`; a missing, invalid, or absent-configuration
token all return a generic 404. The endpoint is bounded to 3 runs per hour and one
concurrent run, and it never widens the market_data validation ceilings (at most 12
requests per provider run, 3 per capability, 1 retry, 10s timeout). Its JSON response
never contains secret values, authorization headers, provider tokens, raw
secret-bearing URLs, or unrestricted provider payloads; see
`docs/deployment/market-data-provider-diagnostics.md` for how to interpret the
`normalized_check_status` / `diagnostic_detail_code` fields it returns.

## Verification

After deployment:

1. Confirm the pre-deploy migration completed.
2. Confirm `/api/v1/health` returns 200 and `/api/v1/readiness` reports `ready`.
3. In deterministic mode, POST one run and verify `/api/v1/portfolio` and `/api/v1/positions`.
4. In Robinhood mode, POST one run, approve any Robinhood challenge if required, and verify the published account/equity/option facts through those same endpoints.
5. Review structured logs only for request, run, step, provider, and account correlation fields. Stop if credential, token, cookie, or raw response material appears.

Robinhood authentication is an unofficial integration and may require interactive approval. ASA remains synchronous and preserves the prior successful publication if authentication or acquisition fails.
