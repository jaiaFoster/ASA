# Legacy Stonk Market Data Migration Assessment

Status: MD-019 assessment only. No legacy code, credential, cache, or payload is migrated.

Evidence was reviewed from the legacy Stonk `app/providers`, `MarketDataHub`, market-data
repository, shared-data documentation, strategy call sites, and their tests. ASA's frozen Market
Data Platform contracts remain authoritative whenever legacy behavior differs.

## Provider and capability inventory

| Legacy path | Observed role | Classification | ASA destination or follow-up |
|---|---|---|---|
| `app/providers/tradier_provider.py` | Quotes, histories, expirations, option chains and Greeks | migrate knowledge; retire wrapper | Tradier adapter and provider compliance suite |
| `app/providers/market_data_provider.py` | Finnhub quote/candle access | migrate limitations; retire wrapper | Finnhub adapter and bounded candle diagnostics |
| `app/providers/alpha_vantage_market_data_provider.py` | Daily-candle fallback | migrate safe normalization; retire wrapper | Alpha Vantage historical-bars adapter |
| `app/providers/earnings_provider.py` | Finnhub/Alpha earnings plus composite merge | migrate source knowledge; replace composite | Capability fulfillment with explicit attempts; statistical/implicit merge is excluded |
| `app/providers/news_provider.py` | News retrieval | defer | Separate news architecture and licensing review |
| Robinhood provider market fields | Brokerage-coupled market information | retire as market-data path | Robinhood is prohibited as a Market Data Platform adapter |

Canonical coverage now includes quote, historical bars, earnings events, option chains/contracts,
Greeks, implied volatility, volume, and open interest. Trading calendars, corporate actions,
dividends, splits, reference data, fundamentals, macro data, and news remain placeholders/deferred.

## Legacy environment variables

Legacy provider modules and configuration read provider settings directly or receive values derived
from process environment. Do not migrate values. Replace names at the centralized configuration
boundary with `ASA_TRADIER_ACCESS_TOKEN`, `ASA_TRADIER_ENV`, `ASA_FINNHUB_API_KEY`, and
`ASA_ALPHA_VANTAGE_API_KEY`. Temporary aliases, if present, exist only in that loader and emit a
secret-free deprecation diagnostic.

## MarketDataHub behavior mapping

| Legacy behavior | Decision | Reason / ASA mapping |
|---|---|---|
| Run-context duplicate-fetch prevention | migrate concept | Per-run fulfillment memoization prevents a second provider request |
| Provider-attempt and coverage reporting | migrate concept | Immutable fulfillment attempts, request accounting, provenance and completeness |
| Useful quote/candle/chain normalization details | migrate after review | Canonical immutable observations; no provider payload escapes |
| Provider ordering spread across services/configuration | replace | Capability Registry and versioned priority policy |
| Silent or implicit fallback | replace | Explicit degraded fulfillment with every attempted provider and normalized failure |
| Stale SQLite fallback | replace/defer | No persistent cache in SPRINT-005B; stale data cannot silently satisfy freshness |
| SQLite read-through market cache | defer | Future Market Data Persistence and Research Platform; PostgreSQL requires its own ticket |
| Cache key and JSON report as canonical state | retire | Immutable MarketSnapshot digest and provenance are canonical analytical input |
| Strategy-owned calls to MarketDataHub/provider | retire | Strategies consume MarketSnapshot/canonical capabilities only |
| Raw dictionary strategy-facing metrics | replace | Typed observations, subjects, resolution results and snapshots |

## Candle quality metadata

Migrate the useful distinction among valid rows, explicit no-data, empty payload, inconsistent
arrays, schema failure, stale evidence, entitlement failure, rate limit, and provider outage. Do not
copy legacy success-on-HTTP-status behavior. Finnhub validation fixes resolution to daily (`D`),
uses explicit UTC ranges, and records an actionable cause without high-volume probes.

## Option-chain behavior

Migrate reviewed field mappings for contract identity, expiration, strike, type, bid/ask/last,
volume, open interest, Greeks, and implied volatility. Broader cached-chain reuse and derived
expiration metrics do not enter adapter normalization. Derived financial logic belongs to typed
components; cache behavior is deferred.

## Earnings behavior

Migrate safe event-date, announcement-time, and provider limitation knowledge. Replace composite
dictionary merging with capability fulfillment and explicit provider attempts. Conflicting events
remain separate canonical observations until the frozen non-statistical resolver selects one or
returns unresolved.

## Diagnostics and secrets

Migrate provider failure categories and request-attempt audit concepts. Retire logging of raw
exceptions, responses, URLs, configuration values, or cache paths. ASA diagnostics retain only
provider name, canonical capability, safe endpoint class, request count, status category, latency,
retry count, quota metadata, normalized failure, and secret-free artifact paths.

## Classification summary

### Migrate

- provider capability knowledge and reviewed normalization rules;
- sanitized fixture shapes and known provider limitations;
- duplicate-request prevention and provider-attempt auditing;
- explicit freshness, completeness, candle-quality, chain-liquidity, and earnings provenance.

### Replace

- direct environment reads and provider-specific objects crossing boundaries;
- scattered provider ordering, silent fallback, and strategy-owned provider calls;
- coupled SQLite market-cache behavior and opaque dictionary observations;
- composite earnings merge behavior without explicit conflict resolution.

### Retire

- obsolete provider wrappers and duplicated market-fetch paths;
- secret-bearing diagnostics and unbounded retry patterns;
- Robinhood market-data usage and report JSON as canonical state.

### Defer

- persistent market-data storage, production cache, and historical research datasets;
- news, corporate actions, calendars, fundamentals, macro data, and reference data;
- brokerage position ingestion, streaming feeds, WebSockets, and tick processing.

## Follow-on work

1. Design the separately authorized PostgreSQL market-data persistence/research platform, including
   licensing and replay-retention policy.
2. Add news only after source licensing, relevance, freshness, and confidence architecture.
3. Add corporate actions, calendars, and reference identity under separate canonical contracts.
4. Remove remaining legacy paths only in a dedicated decommissioning ticket with equivalence
   evidence; do not copy unreviewed legacy code.
