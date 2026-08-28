# PL1-01 Gate 2 — Stonk reuse and broker-boundary record

## Reference inspected

The Gate 1 implementation inspected `jaiaFoster/Stonk` before changing ASA:

- `app/services/broker_provider.py`
- `app/providers/robinhood_provider.py`
- `tests/test_tkt043_dynamic_account_discovery.py`
- `tests/test_tkt040_broker_audit.py`

Stonk is implementation evidence only. ASA governance and current contracts
remain authoritative.

## Behavior retained

- Discover all available Robinhood account profiles when an explicit account
  allow-list is absent.
- Classify tax-account identity from `brokerage_account_type` (and the legacy
  pinnacle marker) rather than confusing cash/margin trading capability with
  account tax type.
- Read equities and option positions across selected/discovered accounts.
- Keep credentials and raw provider records behind a narrow provider adapter.
- Treat exact option instruments and account numbers as broker evidence.

## Behavior deliberately rejected

- Stonk's application architecture, database ownership, and position shapes.
- Provider-specific dictionaries outside the integration boundary.
- Persistent Robinhood login sessions and per-user pickle files.
- Provider calls from API reads or strategy evaluation.
- Live quote acquisition for portfolio rendering.
- Silent per-record exception swallowing and partial publication.
- Retry, order, adjustment, assignment, or execution behavior.
- Estimated account value presented as broker authority.

## ASA owner and boundary proof

ASA retains one `BrokerPortfolioProvider` port, one portfolio snapshot model,
one run/publication path, and one Robinhood adapter. Generic application and
portfolio contracts contain no Robinhood SDK import or Robinhood identity.
Provider account facts are normalized into immutable broker-neutral values;
unavailable values remain `None`. The public provider protocol exposes only
`fetch_accounts` and `fetch_positions`.

The architecture tests enforce SDK confinement, the read-only provider
surface, the approved SDK call set, and absence of Robinhood identity from the
generic application/contract layers.
