<!-- GENERATED: run python -m market_data.documentation --write -->
# finnhub Market Data Provider

## Capabilities

- `real_time_quote_v1`
- `historical_bars_v1`
- `earnings_calendar_v1`

## Configuration names

- `ASA_FINNHUB_API_KEY`

## Environments

- `production`

## Rate limits

- global calls: 30/second (documented)

Configured runtime and validation budgets remain authoritative safety ceilings.

## Bounded validation

Dry run:

```text
python -m market_data.validation --provider finnhub
```

Explicit opt-in execution:

```text
python -m market_data.validation --provider finnhub --execute
```

## Known limitations

- Daily candles use resolution D and UTC epoch request bounds.
- HTTP 200 with no_data is a normalized no_data failure.
- HTTP 200 with empty arrays is a normalized empty_payload failure.
- Candle availability may depend on subscription entitlement.

## Fixture coverage

- `real_time_quote_v1`
- `historical_bars_v1`
- `earnings_calendar_v1`

Last live validation: not recorded in generated source; consult secret-free validation artifacts.
