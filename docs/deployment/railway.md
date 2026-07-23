# Railway backend deployment

## Service layout

As of ARCH-MONOREPO-001 (`architecture/ASA-ARCH-MONOREPO-001-Packaging-Consolidation-ADR.md`),
ASA is a single root-level Python project — there is no separate `backend/` subtree. Create a
Railway service from the ASA GitHub repository with these settings, both set in the Railway
dashboard (neither has a documented Config-as-Code field):

- **Root Directory**: repository root (`.`)
- **Config as Code file path**: `/railway.json`

The remaining build/deploy settings are committed in `railway.json` at the repository root:

- Builder: Railpack
- Pre-deploy command: `python -m alembic upgrade head`
- Start command: `python -m alembic upgrade head && exec python -m uvicorn asa.asgi:create_application --factory --host 0.0.0.0 --port "${PORT}"`
- Healthcheck: `/api/v1/health` (300s timeout)
- Restart policy: `ON_FAILURE`, max 3 retries

Railway injects `PORT`; the start command binds Uvicorn to `0.0.0.0:$PORT` via
`asa.asgi:create_application`, the same composition root (`asa.bootstrap.build_application()`)
used everywhere else, including tests. The migration runs twice by design — once as
`preDeployCommand` (so Railway can block the rollout if it fails) and once more at the head of
`startCommand` (defense in depth against a preDeploy/deploy split) — both invocations are
idempotent no-ops if the schema is already current. See Railway's
[pre-deploy command](https://docs.railway.com/deployments/pre-deploy-command), [start
command](https://docs.railway.com/deployments/start-command), and
[healthcheck](https://docs.railway.com/deployments/healthchecks) documentation.

Because the project root now has one `pyproject.toml` with no `uv.lock`, Railpack's Python
provider selects `pip` and installs the one real project's dependencies — this is what fixed
[issue #178](https://github.com/jaiaFoster/ASA/issues/178) (pip-mode install target not on the
runtime container's `sys.path`), whose root cause was a second, unrelated `pyproject.toml`/
`uv.lock` pair elsewhere in the repository confusing Railpack's provider detection. Do not add a
second `pyproject.toml`, `uv.lock`, or `requirements.txt` anywhere else in the repository without
re-reading that ADR first — it explains exactly why that goes wrong on Railway.

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
token all return a generic 404. The endpoint is bounded to 50 runs per hour (uncapped
in `ASA_ENVIRONMENT=development`) and one concurrent run, and it never widens the
market_data validation ceilings (at most 12 requests per provider run, 3 per
capability, 1 retry, 10s timeout). Its JSON response
never contains secret values, authorization headers, provider tokens, raw
secret-bearing URLs, or unrestricted provider payloads; see
`docs/deployment/market-data-provider-diagnostics.md` for how to interpret the
`normalized_check_status` / `diagnostic_detail_code` fields it returns.

## Agent Data API (`/api/v1/capabilities`, `/api/v1/screening*`)

SPRINT-008 (`docs/sprints/SPRINT-008.yaml`) adds a public, read-mostly API surface intended for
AI agents and other automated clients. Set `ASA_AGENT_API_TOKEN` as a sealed Railway service
variable to enable it; it must never be reused for `ASA_OPERATIONS_TOKEN` or any provider
credential — a different consumer, a different token. Same fail-closed convention as the
operations endpoint above: with no token configured, or a missing/invalid `Authorization` header,
every route in this surface returns a generic 404 rather than a 401/403. See
`docs/api/agent-api-authentication.md` for the full authentication contract and
`docs/api/agent-api-examples.md` for example requests and responses.

`POST /api/v1/screening/{signal}/{symbol}/refresh` additionally requires at least one live market
data provider enabled — the same `ASA_TRADIER_*` / `ASA_FINNHUB_*` / `ASA_ALPHA_VANTAGE_*`
variables documented in `docs/deployment/market-data-provider-diagnostics.md`. As of this
writing, per `project/reports/POST-005B-LIVE-VALIDATION.md`, no live provider credentials are
configured in this deployment, so refresh currently returns `503 NO_LIVE_PROVIDER_CONFIGURED` in
production; the read endpoints (`/capabilities`, `/screening*`) do not depend on any provider and
are unaffected. See `docs/api/agent-api-operations.md` for the operational detail.

## Verification

After deployment:

1. Confirm the pre-deploy migration completed.
2. Confirm `/api/v1/health` returns 200 and `/api/v1/readiness` reports `ready`.
3. In deterministic mode, POST one run and verify `/api/v1/portfolio` and `/api/v1/positions`.
4. In Robinhood mode, POST one run, approve any Robinhood challenge if required, and verify the published account/equity/option facts through those same endpoints.
5. Review structured logs only for request, run, step, provider, and account correlation fields. Stop if credential, token, cookie, or raw response material appears.
6. With `ASA_AGENT_API_TOKEN` set, confirm `GET /api/v1/capabilities` with a correct bearer token returns 200 and lists the registered signals, and that an omitted or incorrect token returns 404.

Robinhood authentication is an unofficial integration and may require interactive approval. ASA remains synchronous and preserves the prior successful publication if authentication or acquisition fails.
