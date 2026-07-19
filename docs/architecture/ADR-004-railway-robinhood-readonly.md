# ADR-004: Railway runtime and read-only Robinhood boundary

## Status

Accepted for ASA-FEAT-003.

## Decision

The backend is deployed as a Railway service rooted at `backend/`. Railway runs
`alembic upgrade head` before starting `python -m asa`; the application binds to
the injected `PORT`. PostgreSQL remains the only canonical product store.

`ASA_BROKER_PORTFOLIO_PROVIDER` explicitly selects either the deterministic test
provider or `robinhood`. Robinhood selection fails startup unless username and
password variables are present. Optional TOTP and account filters are supplied
through variables. Secret values and account identifiers are excluded from the
effective configuration hash.

The Robinhood integration is a narrow read-only facade. It exposes account,
equity-position, option-position, and instrument reads to the existing
`BrokerPortfolioProvider` port. It does not expose order, cancellation, transfer,
or other write operations. SDK imports remain inside `asa.integrations` and the
single `build_application` composition root performs provider selection.

Session persistence is disabled. SDK output, raw responses, exceptions, cookies,
and tokens are not logged or returned. Provider failures are converted to
sanitized errors so a failed run preserves the current successful publication.

## Consequences

- Deterministic mode needs no Robinhood credentials and remains the test default.
- Robinhood authentication can still require provider-side interactive approval;
  such a challenge fails closed because browser automation and session storage
  are outside this decision.
- Portfolio API reads continue to use the published PostgreSQL snapshot and never
  call Robinhood.
