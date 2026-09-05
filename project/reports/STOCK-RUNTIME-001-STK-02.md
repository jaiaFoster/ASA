# STOCK-RUNTIME-001 — STK-02 evidence

## Outcome

The canonical historical-bar contract now carries optional adjusted close plus an
explicit adjustment basis. Raw OHLC semantics remain unchanged, old serialized
bars remain readable, and absence is preserved rather than replaced with raw close.

`sma_10m_completed_months@1.0.0` is registered as a provider-neutral derived fact.
It selects the latest adjusted observation from each of the ten UTC calendar months
strictly before `as_of`, requires one consistent declared adjustment basis, and is
deterministic over sealed evidence.

Finnhub daily candles populate `split_adjusted` because that provider documents its
daily candle series as split-adjusted. Other adapters remain absent/unknown until an
authoritative adjusted value is available. Provider provenance remains on the owning
market observation; no provider identity enters the derived fact.

## Compatibility and scope

- Existing raw close values and constructors are preserved.
- Legacy v1 payloads without the new optional fields deserialize unchanged.
- No strategy, acquisition, broker, or execution behavior changed.
- No raw-close fallback is permitted for B002.

## Verification

Contract round-trip/backward-read, provider normalization, completed-month selection,
insufficient-history, registry-version, Ruff import, and mypy checks are pinned in the
corresponding domain, analytics, and Finnhub tests.
