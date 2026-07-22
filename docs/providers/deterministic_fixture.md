<!-- GENERATED: run python -m market_data.documentation --write -->
# deterministic_fixture Market Data Provider

## Capabilities

- `real_time_quote_v1`
- `historical_bars_v1`
- `option_chain_v1`
- `earnings_calendar_v1`

## Configuration names

- None

## Environments

- `offline`

## Rate limits

- network requests: 0 (fixture)

Configured runtime and validation budgets remain authoritative safety ceilings.

## Bounded validation

Dry run:

```text
python -m market_data.validation --provider deterministic_fixture
```

Explicit opt-in execution:

```text
python -m market_data.validation --provider deterministic_fixture --execute
```

## Known limitations

- Deterministic test data only; never represents live market conditions.

## Fixture coverage

- `real_time_quote_v1`
- `historical_bars_v1`
- `option_chain_v1`
- `earnings_calendar_v1`

Last live validation: not recorded in generated source; consult secret-free validation artifacts.
