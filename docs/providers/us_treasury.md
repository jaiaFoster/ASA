<!-- GENERATED: run python -m market_data.documentation --write -->
# us_treasury Market Data Provider

## Capabilities

- `rate_observation_v1`

## Configuration names

- None

## Environments

- `production`

## Rate limits

- no documented limit; bounded by configured request budgets

Configured runtime and validation budgets remain authoritative safety ceilings.

## Bounded validation

Dry run:

```text
python -m market_data.validation --provider us_treasury
```

Explicit opt-in execution:

```text
python -m market_data.validation --provider us_treasury --execute
```

## Known limitations

- Public U.S. Treasury Daily Treasury Bill Rates feed; no credential or fee.
- Serves Treasury bill bank-discount and coupon-equivalent series only.
- IA-RATE-01: a day-D value is treated as available at 18:00 ET on D.
- Test fixtures are synthetic and mirror the feed structure.

## Fixture coverage

- `rate_observation_v1`

Last live validation: not recorded in generated source; consult secret-free validation artifacts.
