# STOCK-RUNTIME-001 — STK-04 pricing-authority follow-up

Founder-authorized narrow exception to PORTFOLIO-LIFECYCLE-001's
`duplicate_live_market_data_pipeline: prohibited` invariant: portfolio
valuation may read (never fetch) from ASA's existing canonical market-data
authority.

## What "existing canonical market-data authority" means here

`asa.application.use_cases.MarketQuoteService.get_latest_quote(symbol)` —
already-shipped, already used by `GET /api/v1/market/quotes/{symbol}`. It
is a pure read against the persisted `market_observations` table
(`asa.application.ports.repositories.MarketObservationRepository.latest_quote`)
and issues no provider/network call itself; only `ingest_quotes()` (a
different method, never called from this delta) does that. This is the
only existing, symbol-agnostic, acquisition-free "current price" read
capability anywhere in the codebase — confirmed by inspection during the
STK-04 audit.

## What was implemented

- `asa/application/portfolio_valuation.py` — `project_portfolio_valuation`
  gained an optional `quotes_by_symbol: Mapping[str, MarketObservation]`
  parameter (default `None`, fully backward compatible). For each equity
  position with a matching, same-currency canonical quote: `market_value =
  quantity * price` (`ValueAuthority.DERIVED`), and `profit_and_loss =
  (price - average_cost) * quantity` (`ValueAuthority.DERIVED`) — or
  explicitly `UNKNOWN` with a typed reason (`canonical_price_unavailable`,
  `canonical_price_currency_mismatch`, or `broker_cost_basis_unavailable`
  when the broker never reported a cost basis) when any input is missing
  or inconsistent. Never silently substitutes, converts currency, or
  invents a cost basis.
- `asa/api/routes.py`'s `get_positions()` — the only caller. Looks up each
  unique held equity symbol via the already-injected `quote_service`
  (already a parameter of this same router-building function, used
  elsewhere for the `/market/quotes/*` routes) and passes the result
  straight through. No new dependency wiring, no new acquisition path.
- `asa/api/models.py`'s `PositionsEnvelope.from_view` — threads the
  optional quotes mapping through to the projection.

**Deliberately unaffected** (smallest generic delta, not a redesign):
- Option legs: no change. `MarketObservationRepository` has no options
  capability at all — extending pricing there would require a genuinely
  new capability, out of scope for this delta.
- Account-level `total_value`/`profit_and_loss`: unchanged, still
  Robinhood's own broker-reported account equity, still explicitly
  `BROKER_OBSERVED`. Never blended with canonical position-level pricing.
- No strategy-ID branching anywhere in this change — it operates on
  symbols generically.
- No broker mutation, no new acquisition/provider pipeline, no schema
  change, no OpenAPI schema change (`MonetaryValueResponse.authority` was
  already a plain `str`, not an enum — `"derived"` is simply a new value
  within the same existing field).

## Verification

- `tests/asa/test_portfolio_valuation.py` — updated the pre-existing
  no-quote-supplied test (now asserts the more specific
  `canonical_price_unavailable` reason for equities, matching what the
  code actually does when nothing is supplied, distinct from option
  legs' unaffected `broker_position_value_unavailable`) and added three
  new tests: canonical-quote-present derives market value and P&L
  correctly (verified against the fake broker's known AAPL position:
  quantity 12, cost basis 172.50, quote 200.00 → market value 2400.00,
  P&L 330.00); a missing cost basis keeps P&L (but not market value)
  explicitly unknown; a currency mismatch refuses to compute rather than
  silently convert. 5/5 passed.
- `ruff check asa tests/asa` and `mypy asa`: clean.
- `tests/asa/test_portfolio_acceptance.py`'s existing pinned assertion
  (`equity_valuations[0]["market_value"]["authority"] == "unknown"`)
  remains correct by inspection: that fixture's injected
  `MarketObservationRepository` (`InMemoryObservationRepository`) starts
  and stays empty for that test, so `get_latest_quote` returns `None` and
  the position stays `UNKNOWN` exactly as before — could not run this
  Postgres-backed suite locally (pre-existing Windows-environment gap,
  documented in earlier STK reports); will be confirmed by CI's real
  Postgres job.
