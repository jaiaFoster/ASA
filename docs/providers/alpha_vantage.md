<!-- GENERATED: run python -m market_data.documentation --write -->
# alpha_vantage Market Data Provider

## Capabilities

- `historical_bars_v1`
- `earnings_calendar_v1`

## Configuration names

- `ASA_ALPHA_VANTAGE_API_KEY`

## Environments

- `production`

## Rate limits

- unknown limits remain finite through configured request budgets

Configured runtime and validation budgets remain authoritative safety ceilings.

## Bounded validation

Dry run:

```text
python -m market_data.validation --provider alpha_vantage
```

Explicit opt-in execution:

```text
python -m market_data.validation --provider alpha_vantage --execute
```

## Known limitations

- Daily validation uses compact raw-as-traded output.
- Provider Note and Information payloads are diagnostics, not market data.

## Fixture coverage

- `historical_bars_v1`
- `earnings_calendar_v1`

Last live validation: not recorded in generated source; consult secret-free validation artifacts.
