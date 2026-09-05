# STOCK-RUNTIME-001 — STK-01 contract and capability audit

## Frozen benchmark contracts

| Contract | Subject | Canonical requirements | Structure | Lifecycle |
| --- | --- | --- | --- | --- |
| `B001@1.0.0` | SPY | `real_time_quote_v1` | `NONE` | `NONE` |
| `B002@1.0.0` | SPY | `real_time_quote_v1`, `historical_bars_v1` | `NONE` | `NONE` |

The existing `StrategyContract` expresses both benchmarks without a schema
change. Neither declares `OPTION_STRUCTURES`, economics, recommendations, or
lifecycle authority. Generic runtime behavior therefore remains declaration
driven and needs no benchmark-ID branch.

## Input authorities

- B001 current eligible price: selected canonical `Quote.last` from the sealed
  `REAL_TIME_QUOTE_V1` resolution.
- B002 current eligible price: the same canonical quote authority.
- B002 monthly source: canonical daily `OHLCVSeries` from
  `HISTORICAL_BARS_V1`, reduced before sealing by the existing generic
  historical-series reducer.
- B002 derived value: new registered/versioned
  `sma_10m_completed_months@1.0.0`, materialized through the existing
  `AnalyticsRegistry` and `DerivedFact` identity boundary.
- Replay: persisted sealed evidence and materialized fact identity; never a
  provider call.

## Authorized historical-price clarification

Issue #415 proved that the existing canonical bar carries raw-as-traded
`close` only. Founder authorization permits the narrow backward-compatible
addition required by B002:

- raw OHLCV fields retain their existing meaning and serialization;
- a bar may additionally carry an optional adjusted close;
- adjusted evidence carries a typed adjustment basis;
- the selected observation's existing provider provenance remains the source
  provenance for both values;
- adjusted close and basis are present together or absent together;
- old serialized bars remain readable as raw bars with no adjusted value;
- B002 returns typed missing data when ten qualifying completed-month adjusted
  closes are unavailable; raw close is never substituted.

The adjustment basis is descriptive evidence, not provider selection policy.
Both split-adjusted and split-and-dividend-adjusted observations may be
represented truthfully; the fact records the basis actually consumed.

## Provider path

The existing providers already own `HISTORICAL_BARS_V1`. Alpha Vantage's
current implementation and metadata explicitly use raw `TIME_SERIES_DAILY`.
Its official adjusted endpoint exposes a distinct adjusted-close field and may
require premium entitlement. Finnhub documents daily candles as split-adjusted.
STK-02 may populate the new field only where the provider contract is explicit
and the account is entitled. Provider-specific semantics do not escape the
adapter.

No new canonical capability, provider subsystem, materialization subsystem, or
strategy-local SMA is required. External entitlement remains a production
proof question, not permission to fabricate adjusted history.
