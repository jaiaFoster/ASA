# ASA-ARCH-007: Market Data Platform Contracts

**Status:** Proposed — Founder merge required
**Date:** 2026-07-22
**Sprint:** SPRINT-005A
**Risk:** R3 architecture and public-contract change

## 1. Decision and boundary

ASA shall acquire market evidence through replaceable adapters, normalize it into immutable
provider-neutral Observations, resolve it deterministically, and seal complete analytical inputs
inside immutable Market Snapshots. Strategies consume Canonical Facts and typed snapshot content;
they never select providers, call adapters, inspect provider payloads, or read configuration.

This document refines ADR-001 and ADR-002 without replacing their Observation/Canonical Fact split.
It reuses `Instrument`, `Security`, `OptionContract`, `OptionChain`, `EarningsEvent`, and Evidence
from existing frozen contracts. It does not create parallel instrument or option identities.

No runtime, provider implementation, persistence schema, live request, strategy integration, or
operational side effect is authorized by this architecture sprint.

## 2. Canonical pipeline and ownership

```text
Central Configuration -> Provider Factory -> Provider Adapter
                                              |
Capability Registry -> Provider selection ----+
                                              v
                                    normalized Observation
                                              |
                                Observation Resolution
                                              |
                                      Canonical Fact
                                              |
                                      Snapshot Builder
                                              |
                                      Market Snapshot
                                              |
                                  Strategy / deterministic Replay
```

Configuration owns secrets and construction inputs. The Factory owns construction. The Provider
Registry owns the inventory and lifecycle. The Capability Registry answers which registered
providers can satisfy a capability. Adapters own transport and translation. Resolution owns
selection and disagreement records. Snapshot Builder owns completeness of the immutable envelope.
No other layer assumes any of those responsibilities.

## 3. Common value and identity rules

All public values are frozen, slot-based records or closed enums. Collections are canonically
ordered tuples. Decimal values are finite; binary float is forbidden. Semantic times are supplied,
timezone-aware UTC values. Wall-clock reads, construction order, retries, latency, process state,
credentials, and serialization formatting are excluded from analytical identity.

Every Observation has an `observation_id` in `asa.market_observation/v1`, `provider_id`, capability,
canonical subject identity, effective time, recorded time, normalized value, schema version,
provider request reference, and Evidence. Identity includes provider, capability, subject,
effective time, normalized content, and schema version. A correction is a new Observation.
Provider request references are opaque redacted identifiers, never payloads or credentials.

## 4. ARCH-MD-001 — Canonical Observation contracts

The following are normalized values carried by Observations, not alternate Observation envelopes:

```text
Quote
  instrument, bid?, ask?, last?, bid_size?, ask_size?, volume?, currency

OHLCVBar
  instrument, interval, start_at, end_at, open, high, low, close, volume

TradingCalendarEvent
  venue, event_type, starts_at, ends_at, trading_date

CorporateActionPlaceholder
  instrument, action_type, effective_date, status, external_reference?
```

At least one Quote price is present; sizes and volume are non-negative; bid may not exceed ask.
An OHLCV Bar has a positive fixed interval, `start_at < end_at`, non-negative volume, and coherent
high/low bounds. Calendar event types are a closed v1 enum: `OPEN`, `CLOSE`, `EARLY_CLOSE`,
`HALT`, `HOLIDAY`. Corporate action types are `DIVIDEND`, `SPLIT`, `MERGER`, `SPINOFF`, `OTHER`;
the placeholder carries observed classification only and authorizes no adjustment behavior.

`OptionContract`, `OptionChain`, and `EarningsEvent` retain the exact semantics and identities in
ASA-ARCH-005. Their market-state instances may be Observation values. The Market Data Platform
must not copy or redefine their fields.

## 5. ARCH-MD-002 — Provider adapter architecture

`MarketDataProvider` is a capability-oriented read port:

```text
provider_id
metadata
capabilities
fetch(request: CapabilityRequest, budget: RequestBudget) -> ProviderFetchResult
health(probe: HealthProbe) -> ProviderHealthReport
validate(plan: ProviderValidationPlan) -> ProviderValidationReport
shutdown() -> ProviderShutdownReport
```

The port contains no provider SDK type. `ProviderAdapter` is the only boundary permitted to import
an SDK, create transport requests, interpret responses, normalize errors, and translate payloads.
It returns canonical Observations or normalized Provider Errors. Provider-specific values never
escape the adapter. Failure creates no fabricated Observation.

Adapters are stateless with respect to analytical data. A constructed adapter may hold immutable
configuration and an injected transport/session resource, but no hidden cache, cursor, retry count,
priority, quota, or mutable analytical state. Request accounting and retry decisions are supplied
by platform services. This narrows ADR-002's adapter retry ownership: the adapter performs an
authorized retry but the versioned policy and budget are explicit inputs.

Normalized error kinds are `AUTHENTICATION`, `AUTHORIZATION`, `RATE_LIMIT`, `TIMEOUT`, `TRANSPORT`,
`SCHEMA`, `UNAVAILABLE`, and `UNKNOWN`. Error records contain safe codes and bounded redacted text;
never raw payloads, headers, URLs, secrets, tokens, cookies, or SDK exceptions.

## 6. ARCH-MD-003 — Provider Factory

`ProviderFactory.create(descriptor, config, dependencies) -> MarketDataProvider` is the sole
production construction path. Registration is static and keyed by immutable adapter type ID and
version. The Factory validates configuration before construction and fails closed on unknown or
duplicate types. It performs no capability selection and no live probe.

Providers receive a complete immutable `ProviderConfig` plus explicit transport, clock, and
accounting dependencies. Providers and adapters never call `getenv`, inspect global settings,
discover plugins dynamically, or construct application dependencies.

## 7. ARCH-MD-004 — Capability Registry

Capabilities are closed, versioned semantic requests, initially:

- `REAL_TIME_QUOTE_V1`
- `HISTORICAL_BARS_V1`
- `OPTION_CHAIN_V1`
- `EARNINGS_CALENDAR_V1`
- `TRADING_CALENDAR_V1`
- `CORPORATE_ACTIONS_V1`

`CapabilityRequest` includes capability, canonical subjects, semantic time/window, required fields,
and freshness/completeness requirements. It never includes a provider name. The immutable registry
maps capabilities to eligible registered provider IDs and declared constraints. Lookup returns a
canonically ordered candidate tuple; it does not contact providers or choose using hidden health.
Selection uses explicit versioned policy outside Strategy code.

## 8. ARCH-MD-005 — Provider Registry and lifecycle

The Provider Registry is the authoritative in-process inventory of explicitly constructed provider
instances. Its frozen operations are `register`, `metadata`, `providers_for`, `health`, `validate`,
and `shutdown`. Registration occurs only during composition and is closed before acquisition.
Runtime registration, discovery, replacement, and mutation are prohibited.

`ProviderMetadata` includes provider ID, adapter type/version, supported capabilities, declared
limits, fixture coverage, and documentation version. `ProviderStatus` is `UNKNOWN`, `AVAILABLE`,
`DEGRADED`, `UNAVAILABLE`, or `SHUTDOWN`. Status is an immutable report, not mutable authority.
Credential presence is never health. Health is a bounded explicit probe and never fetches a full
market snapshot.

## 9. ARCH-MD-006 — Observation Resolution

Resolution consumes an explicit immutable Observation set and `ResolutionPolicy`; it performs no
fetch. It emits a `ResolutionResult` containing selected Observation, all consumed Observation IDs,
freshness, completeness, disagreements, confidence metadata, policy version/parameters, rationale,
and Evidence. Missing required evidence fails closed.

Freshness is computed from explicit `as_of`, observation effective time, and policy threshold.
Completeness compares present fields/subjects with the request. Disagreement records field-level
distinct normalized values and contributing providers. Confidence metadata records inputs and a
classification, not a user-facing probability. SPRINT-005A freezes shapes only: provider priority,
thresholds, weights, and selection heuristics remain implementation configuration and must be
versioned before use. Last-write-wins and input-order selection are prohibited.

## 10. ARCH-MD-007 — Rate-limit architecture

`RateLimitPolicy` declares provider, capability, window, request-unit budget, burst budget, retry
classes, maximum attempts, backoff schedule, and policy version. `RequestBudget` is an immutable
reservation supplied per acquisition. `RequestAccountingEntry` records attempted request units,
outcome kind, provider request reference, and semantic accounting window.

Rate-limit headers may update a new immutable quota observation; they never mutate policy. Retry
requires remaining request and retry budgets, idempotent read semantics, and an explicitly supplied
delay schedule. Jitter/randomness is prohibited. Authentication and schema errors are not retried.
Architecture does not authorize sleeping threads, queues, schedulers, or background work.

## 11. ARCH-MD-008 — Provider validation framework

`ProviderValidationPlan` is an immutable bounded plan with provider ID, capabilities, fixture
references, maximum requests, maximum request units, allowed endpoints, timeout budget, and redaction
policy. `ProviderValidationReport` includes report ID, plan identity, adapter version, started/completed
semantic times, authentication/endpoint/schema/latency/quota/fixture outcomes, request accounting,
redacted failures, and overall status.

Validation is an explicitly invoked development operation. Each check is `PASS`, `FAIL`, `SKIPPED`,
or `NOT_SUPPORTED`. Authentication validation proves an authorized read without exposing credential
material. Latency is diagnostic and excluded from deterministic analytical identity. Fixture
comparison is structural and bounded. Reports contain no raw payload, environment value, secret,
session, token, cookie, authorization header, or full URL. Validation never writes provider state.

## 12. ARCH-MD-009 — Replay architecture

Replay accepts only a sealed `MarketSnapshot` or canonical serialized snapshot fixture. It cannot
receive Provider Factory, Provider Registry, adapter, transport, credentials, configuration loader,
clock, or network dependency. Snapshot identity and canonical digest are verified before use.
Identical snapshot plus identical analytical inputs must produce identical output and provenance.
Missing snapshot content fails closed; replay never fills gaps from a live or cached provider.

## 13. ARCH-MD-010 — Market Snapshot contracts

```text
MarketSnapshot
  snapshot_id
  schema_version
  as_of
  requested_capabilities
  observations
  resolution_results
  provider_metadata
  validation_metadata
  completeness
  evidence
```

A Snapshot is immutable, self-contained, canonically serialized, and ordered by capability,
canonical subject, effective time, provider ID, and Observation ID. Every Resolution Result and
Evidence reference resolves within the envelope or to an immutable canonical external reference.
Provider metadata is the bounded non-secret metadata actually relevant to included Observations.
Validation metadata identifies reports and dispositions; it does not embed credentials or logs.

Snapshot identity namespace is `asa.market_snapshot/v1` and includes every semantic field,
Observation identity, resolution policy/result, validation disposition, and Evidence. It excludes
recording duration and serialization formatting. `as_of` is caller supplied and cannot precede any
included recorded time. A Snapshot is the single sealed market-data input to deterministic Strategy
evaluation and replay; it is not a database row, mutable cache, or implicit current value.

## 14. ARCH-MD-011 — Configuration architecture

`MarketDataConfig` contains enabled provider descriptors, capability selection policy, rate-limit
policies, resolution policies, validation defaults, and secret references. `ProviderConfig` contains
provider ID, adapter type/version, non-secret settings, and opaque secret references. A centralized
composition loader alone reads environment or secret stores, validates values, resolves references,
and supplies sanitized immutable configuration to the Factory.

Configuration identity includes all behavior-affecting non-secret values and stable secret-reference
identities, but never secret values, usernames, tokens, URLs containing authority, cookies, or
sessions. Errors identify the invalid field category only and do not reproduce values.

## 15. ARCH-MD-012 — Documentation architecture

Provider documentation is generated deterministically from `ProviderSpecification`: metadata,
capabilities, normalized schemas, declared rate limits, validation coverage, known limitations,
fixture coverage, adapter version, and last checked validation-report reference. Human notes are
bounded versioned inputs. Generated documents contain no configuration values or secrets.

CI regenerates and checks drift. Documentation generation performs no provider call. “Last
validation” means the semantic report reference committed or supplied to generation, never wall
clock or an unverified health claim.

## 16. ARCH-MD-013 — Testing architecture

Every adapter must pass the same provider compliance suite using deterministic fixtures. Required
layers are canonical-value unit tests, adapter translation tests, normalized-error tests, factory
construction tests, registry/capability tests, budget/retry tests, resolution vectors, snapshot
canonicalization tests, replay-with-provider-prohibited tests, redaction tests, and documentation
drift tests.

Fixture providers implement only the public port and contain no SDK. Mock transports remain inside
adapter tests. Recorded fixtures are sanitized, bounded, versioned, attributed, and contain no
credentials or raw private account data. A compliance result names contract version, adapter
version, fixture set identity, and every pass/fail/skip outcome.

## 17. ARCH-MD-014 — Legacy migration architecture

Legacy Stonk market-data inventory must classify each source and capability as `MIGRATE`, `REPLACE`,
`DEFER`, or `RETIRE`. Inventory records provider/library name, capabilities, authentication shape,
rate-limit knowledge, data shapes, strategy consumers, fixture availability, security concerns,
and recommended disposition. Classification is documentation, not authorization to copy code.

Migration order is contracts and compliance harness, then fixture adapter, then one provider at a
time behind the Factory/registries, then snapshot construction and replay fixtures. No legacy
topology, global configuration, SDK leakage, compatibility shim, dual read, or provider selection
inside Strategy code is permitted.

## 18. Architecture constraints and imports

Provider SDK imports are permitted only in provider-specific adapter packages. Strategy, Facts,
Indicators, Guardrails, Ranking, Portfolio, Risk, Execution Planning, Simulation, presentation,
and domain contracts may import neither adapters nor SDKs. Market Snapshot may reference existing
domain values; domain values cannot import the Market Data Platform.

There is one composition root. Factory and registries are injected dependencies, never module-level
singletons. No dynamic plugin loading, hidden service locator, generic repository framework,
background thread, scheduler, persistence, HTTP route, or live provider is authorized here.

## 19. Alternatives rejected

- Strategies selecting named providers: couples financial logic to availability and vendors.
- A provider-neutral dictionary: evades typed contracts and permits payload leakage.
- Fetch-on-demand replay: destroys reproducibility and creates hidden cost and availability inputs.
- Provider-local environment loading: hides configuration and prevents deterministic composition.
- Mutable central registry: makes runtime behavior depend on execution order.
- Latest-timestamp snapshots: creates implicit current state and weak provenance.
- Architecture-time resolution heuristics: freezes uncalibrated product policy prematurely.

## 20. Implementation sequence and freeze gate

After Founder merge, SPRINT-005B may propose bounded implementation tickets in this order:
canonical contract activation; fixture provider and compliance harness; configuration and Factory;
registries; rate accounting; resolution; Snapshot Builder; replay fixtures; validation framework;
documentation generation; then individually approved live adapters. Tradier, Finnhub, and Alpha
Vantage are not authorized merely by this sequence; each requires explicit scope, secrets review,
bounded validation, and Founder-approved implementation work.

Founder merge freezes this document as the v1 Market Data Platform contract. Any implementation
that needs a provider payload outside an adapter, a Strategy provider name, live replay fetch,
opaque map, hidden configuration, new canonical identity, or changed public contract must stop and
return to architecture review.
