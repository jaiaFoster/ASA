# ASA-ARCH-005: Financial Domain Contracts

**Status:** Proposed — Founder merge required

**Date:** 2026-07-21

**Patch:** ARCH-005

**Sprint:** SPRINT-003

## Context and decision

STONK-001 found that three legacy strategies require option-chain, earnings, volatility, expiry,
and option-structure knowledge that ASA cannot currently express through its closed Strategy Type
System. Issue #93 records the resulting architecture stop. Opaque Maps, legacy dictionaries,
provider payloads, and hidden symbol parsing are forbidden.

This document freezes the provider-neutral immutable contracts used to normalize that knowledge.
It extends the domain vocabulary without changing the established pipeline:

```text
Provider payload
  -> Observation
  -> reconciliation / CanonicalFact
  -> optional Indicator
  -> typed Strategy evaluation context
  -> Components and Manifests
```

The contracts contain no acquisition, provider selection, reconciliation, persistence, strategy,
portfolio, execution, or presentation behavior.

## Existing identity authority

`Instrument` and `CanonicalInstrumentIdentity` remain ASA's sole canonical instrument identity
owners. ARCH-005 does not create a parallel symbol identity system.

`Security` is the canonical security description associated with one existing `Instrument`. Its
natural normalization key is `(symbol, asset_type, exchange)`, but consumers compare its complete
`instrument.identity`; they never concatenate, parse, or infer identities. The normalization owner
resolves the natural key to a canonical Instrument before the value enters Facts or Strategies.

```text
Security
  instrument: Instrument
  symbol: normalized uppercase text
  asset_type: SecurityAssetType
  exchange: normalized MIC or explicit UNKNOWN code
```

`SecurityAssetType` v1 contains `equity`, `etf`, `index`, and `cash`. Options are modeled by
`OptionContract` and reference an underlying Security. Security is frozen and slot-based. Its
identity namespace is `asa.security`, version `v1`, and includes the canonical Instrument identity,
symbol, asset type, and exchange. Currency remains owned by Instrument.

## Shared numeric and evidence rules

- All financial numerics are finite Decimal values; binary float is forbidden.
- Prices, volume, open interest, implied/historical volatility, rank, and percentile are
  non-negative. Delta, gamma, theta, vega, and rho are finite and may be signed.
- Optional values are represented explicitly as `None`; zero never means missing.
- Every observed value includes timezone-aware `observed_at` and non-empty Evidence references.
- Timestamps, quotes, Greeks, volume, open interest, and volatility are evidence, never identity.
- Collections are immutable tuples with deterministic ordering and hard uniqueness checks.
- Domain construction validates structure only. Financial calculations belong to Indicators or
  Components and must record versions and effective parameters.

## OptionContract

An `OptionContract` is one immutable observed option-contract record:

```text
OptionContract
  option_contract_id: CanonicalInstrumentIdentity
  underlying: Security
  expiration: Date
  strike: Decimal
  option_type: OptionType               # call | put
  bid: Optional[Decimal]
  ask: Optional[Decimal]
  mark: Optional[Decimal]
  volume: Optional[Integer]
  open_interest: Optional[Integer]
  delta: Optional[Decimal]
  gamma: Optional[Decimal]
  theta: Optional[Decimal]
  vega: Optional[Decimal]
  rho: Optional[Decimal]
  implied_volatility: Optional[Decimal]
  observed_at: Instant
  evidence: List[Evidence]
```

The semantic contract identity is `(underlying.instrument.identity, expiration, strike,
option_type)`. The normalization layer assigns `option_contract_id` from that natural key using a
documented canonical scheme; Strategy code never parses an OCC symbol or provider identifier.
`strike` is positive. Expiration is not earlier than the observation's UTC date. When both bid and
ask exist, `bid <= ask`. Mark is an observed provider-neutral value and is not silently derived;
an explicit versioned Component may derive a midpoint when required.

OptionContract identity uses namespace `asa.option_contract`, version `v1`, and includes only the
semantic natural key plus canonical ID scheme/version. Observation-state identity is separate and
includes all populated market fields, `observed_at`, and sorted Evidence references.

## OptionChain

```text
OptionChain
  option_chain_id: Text
  underlying: Security
  observed_at: Instant
  contracts: List[OptionContract]
  evidence: List[Evidence]
```

Every contract references the same underlying and semantic observation instant. Contract natural
keys are unique. Canonical order is `(expiration, strike, option_type, option_contract_id.scheme,
option_contract_id.value)`. Input enumeration order cannot affect chain identity.

The chain exposes deterministic value-level lookup operations by expiration, strike, and option
type. These operations are pure scans or immutable derived indexes; indexes are excluded from
serialization and identity. There is no mutation, lazy provider fetch, cache, runtime discovery,
or hidden current date.

OptionChain identity uses namespace `asa.option_chain`, version `v1`, and includes underlying
identity, observed_at, canonical ordered contract observation identities, and Evidence.

## ExpirationCycle

```text
ExpirationCycle
  expiration_date: Date
  days_to_expiration: Integer
  monthly: Boolean
  weekly: Boolean
  as_of: Date
  evidence: List[Evidence]
```

Days-to-expiration is supplied, not derived from the wall clock. It must equal the deterministic
date difference from explicit `as_of` under UTC calendar semantics. It is non-negative. Monthly
and weekly are independent classifications because provider calendars may label a monthly expiry
as weekly-compatible; at least one must be true in v1. Identity namespace is
`asa.expiration_cycle/v1` and includes every field.

`ExpirationCollection` is a unique tuple ordered by expiration date, classification flags, and
identity. It contains one explicit `as_of` shared by every cycle.

## EarningsEvent and EarningsCalendar

```text
EarningsEvent
  earnings_event_id: Text
  security: Security
  earnings_date: Date
  announcement_time: AnnouncementTime   # before_open | during_market | after_close | unknown
  estimated_move: Optional[Ratio]
  confirmed: Boolean
  historical_sequence: List[EarningsHistoryEntry]
  observed_at: Instant
  evidence: List[Evidence]

EarningsHistoryEntry
  earnings_date: Date
  announcement_time: AnnouncementTime
  realized_move: Optional[Ratio]
  evidence: List[Evidence]
```

The natural event identity is `(security.instrument.identity, earnings_date)`. Announcement time,
estimated move, confirmation, history, and observation time are evidence state and do not change
event identity. Estimated and realized moves are non-negative absolute ratios. Historical entries
must precede the current event, are unique by date, and are ordered newest first.

`EarningsEvent` identity uses namespace `asa.earnings_event/v1`. `EarningsCalendar` is an immutable
collection for an explicit inclusive date window and observation time. Events are unique by
natural identity and ordered by `(earnings_date, security.identity)`. Calendar identity includes
the window, observed_at, ordered event observation identities, and Evidence.

## VolatilityEvidence

```text
VolatilityEvidence
  security: Security
  implied_volatility: Optional[Ratio]
  historical_volatility: Optional[Ratio]
  iv_rank: Optional[Ratio]
  iv_percentile: Optional[Ratio]
  lookback: Duration
  observed_at: Instant
  evidence: List[Evidence]
```

At least one value is required. Rank and percentile are within `[0, 1]`; volatility ratios are
non-negative. Lookback is positive fixed duration and is an identity input because it changes
meaning. No annualization, interpolation, event-variance removal, or percentile calculation occurs
inside the structural contract. Identity namespace is `asa.volatility_evidence/v1` and includes
all semantic fields and Evidence.

## OptionStructure

```text
OptionLeg
  contract: OptionContract
  position: OptionLegPosition            # long | short
  quantity: Quantity
  role: Text                              # normalized explanatory role

OptionStructure
  option_structure_id: Text
  structure_type: OptionStructureType
  underlying: Security
  legs: List[OptionLeg]
  observed_at: Instant
  evidence: List[Evidence]
```

`OptionStructureType` v1 contains `single_leg`, `vertical`, `calendar`, `diagonal`, `straddle`,
`strangle`, `covered_call`, and `cash_secured_put`. Quantity is positive. Leg order is semantic and
canonical: role, expiration, strike, option type, position, then contract identity. Duplicate
contract/position/role legs are invalid.

Structural validation is deliberately narrow:

- every option leg has the structure underlying;
- single-leg has one option leg;
- vertical has two same-expiration, same-option-type legs with different strikes;
- calendar has two same-strike, same-option-type legs with different expirations;
- diagonal has two same-option-type legs with different strikes and expirations;
- straddle has one call and one put at the same strike and expiration;
- strangle has one call and one put at different strikes and the same expiration;
- covered call and cash-secured put describe option legs only; portfolio coverage and cash
  sufficiency remain Portfolio Engine responsibilities and are not asserted by this contract.

Pricing, payoff, liquidity, reward/risk, assignment risk, and strategy suitability are Component
outputs, not structural validation. OptionStructure identity namespace is `asa.option_structure/v1`
and includes type, underlying, canonical legs, observed_at, and Evidence.

## Strategy Type System extension

ARCH-005 authorizes a new exact Strategy Type System version. It adds these nominal v1 types:

- `Security`, `SecurityCollection`;
- `OptionContract`, `OptionCollection`, `OptionChain`;
- `ExpirationCycle`, `ExpirationCollection`;
- `EarningsEvent`, `EarningsCalendar`;
- `VolatilityEvidence`;
- `OptionLeg`, `OptionStructure`.

Named collection types are semantic aliases with exact nominal identity; they validate the same
immutable tuple shapes as their domain contracts and are not interchangeable with arbitrary
`List` values. No implicit conversion exists between Instrument and Security, CanonicalFact and a
financial domain value, collection aliases and generic Lists, or any numeric types. Explicit pure
Components perform every authorized conversion or projection.

The implementation must bump `TYPE_SYSTEM_VERSION`, pin the new catalog identity, add exact value
validation, and update affected registry identities. Unknown versions fail closed.

## Manifest, runtime, and plugin rules

Manifests reference the new types only by exact `(name, version)` and serialize values through the
existing canonical manifest/typed-value rules. Domain values serialize as closed tagged records:
lexicographic object keys, normalized Decimal strings, ISO dates/instants, enum values, canonical
ordered collections, and explicit nulls. Provider fields and Python object representations are
forbidden.

Identity material includes the domain contract version and complete canonical semantic value.
Round-trip serialization must preserve equality and identity. Display labels and derived indexes
are excluded.

Runtime and Plugins:

- never inspect Python types to discover financial behavior;
- never accept opaque Maps in place of these contracts;
- never parse symbols, OCC strings, or provider IDs;
- never perform provider, repository, broker, clock, environment, or network access;
- never apply implicit conversion or fallback;
- validate exact port compatibility before evaluation;
- preserve immutable values and bounded deterministic ordering;
- record typed input/output identities in execution traces.

Plugins may contribute Components consuming these types through static registration. They cannot
extend or mutate the Type System, add alternate serializers, or bypass domain validation.

## Canonical ownership and implementation sequence

1. Domain owns immutable structural contracts, enums, validation, and canonical serialization.
2. Observation/integration normalization owns provider-to-contract structural mapping.
3. Reconciliation owns canonical Fact selection and provenance.
4. Indicators own reusable calculations such as returns, realized volatility, IV relationships,
   or forward volatility when shared across strategies.
5. Strategy Components own bounded strategy-local transformations such as expiration selection,
   leg choice, and option-structure proposal.
6. Guardrails, Ranking, Position Proposal, Portfolio, and Execution retain their existing authority.

Implementation must land as a dedicated contract ticket before STONK-002 resumes. It may add the
domain records, serializer, Strategy Types, tests, and documentation only. Stonk Components and
manifests follow afterward under their existing sprint tickets.

## Acceptance and replay vectors

Acceptance requires tests proving:

- every value is deeply immutable and rejects mutable nested payloads;
- identical semantic values serialize and hash identically across construction order and process;
- observed market fields never alter contract natural identity but do alter observation identity;
- OptionChain and calendar enumeration order cannot alter canonical identity;
- lookback and explicit semantic dates participate in identity;
- invalid prices, crossed markets, duplicate contracts/events/legs, mismatched underlyings, and
  invalid structure shapes fail closed;
- every new Strategy Type resolves and validates only its exact domain value;
- opaque Maps, implicit conversions, provider objects, and runtime discovery remain rejected;
- existing Strategy Core manifests, types, registry, runtime, replay vectors, and analytical
  pipeline remain green.

## Explicit exclusions

ARCH-005 does not define provider adapters, option symbology parsing, reconciliation policy,
pricing models, volatility calculation, options-chain acquisition, persistence, cache behavior,
portfolio coverage, broker fields, order construction, execution, live trading, strategy
thresholds, or Stonk compatibility behavior.

## Disposition

This is a public architecture contract and cannot be self-merged. Founder merge freezes ARCH-005
and authorizes its bounded implementation. After implementation and validation merge, Issue #93
may close and SPRINT-003 resumes at STONK-002.
