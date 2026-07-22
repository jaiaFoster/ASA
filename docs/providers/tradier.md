<!-- GENERATED: run python -m market_data.documentation --write -->
# tradier Market Data Provider

## Capabilities

- `real_time_quote_v1`
- `historical_bars_v1`
- `option_chain_v1`

## Configuration names

- `ASA_TRADIER_ACCESS_TOKEN`
- `ASA_TRADIER_ENV`

## Environments

- `sandbox`
- `production`

## Rate limits

- market data: 60 requests/minute (documented sandbox)
- market data: 120 requests/minute (documented production)

Configured runtime and validation budgets remain authoritative safety ceilings.

## Bounded validation

Dry run:

```text
python -m market_data.validation --provider tradier
```

Explicit opt-in execution:

```text
python -m market_data.validation --provider tradier --execute
```

## Known limitations

- Option-chain quality is explicit when fields are absent.
- Validation requires an active account and applicable market-data entitlement.

## Fixture coverage

- `real_time_quote_v1`
- `historical_bars_v1`
- `option_chain_v1`

Last live validation: not recorded in generated source; consult secret-free validation artifacts.
