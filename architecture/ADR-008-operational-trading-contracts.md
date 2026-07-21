<!-- Repository path: architecture/ADR-008-operational-trading-contracts.md -->

# ADR-008: Operational Trading Contracts

**Status:** Accepted
**Date:** 2026-07-21

## Context

Ranking produces ordered Opportunities, but an Opportunity is deliberately an intelligence
record: it does not identify a broker position, encode an order, or contain the current financial
state of a portfolio. ASA-CORE-008 exposed the missing boundary. Portfolio policy cannot safely
infer an instrument from opaque evidence IDs, treat average cost as current value, or import the
broker-ingestion model from the product backend. Those shortcuts would violate Laws 3, 4, 5, 9,
and 10 of the Constitution.

The domain needs immutable provider-neutral contracts that let Intelligence describe desired
exposure and let an Operational Portfolio layer compare that exposure with an observed portfolio.
This decision defines only data semantics. It introduces no engine, calculation, repository,
provider integration, persistence, broker write, order, or execution capability. In particular,
"operational" does not amend Constitution Law 5: ASA remains read-only and a
`ProposedPosition` is never an order.

## Decision

The shared `domain/` package owns six cross-boundary objects and their supporting value types:

- `Instrument` describes a provider-neutral instrument using a
  `CanonicalInstrumentIdentity`, kind, display symbol, currency, optional pinned sector
  classification, and (for an option) explicit underlying identity.
- `Holding` describes one current, valued position in an account. Direction and absolute
  quantity are separate; no consumer interprets a signed quantity.
- `PortfolioSnapshot` is the complete immutable financial-state input for one portfolio at one
  semantic observation time.
- `ProposedPosition` is Intelligence's evidence-backed description of desired exposure. It
  references the Opportunity, Ranked Opportunity, and Ranking Result that produced it but
  contains no account, portfolio, quantity, market price, order type, route, time-in-force, broker
  identifier, or write operation. It preserves the Opportunity's canonical Instrument and pins
  proposal-algorithm version, target allocation, effective sizing parameters, confidence,
  rationale, lineage, and Evidence.
- `PortfolioDecisionRequest` pairs one snapshot with Proposed Positions in Ranking order. It is
  the input envelope for future deterministic portfolio policy; it contains no policy behavior.
- `ExecutionContext` is the explicit, immutable side input required to turn one analytical
  Portfolio Decision into a replayable execution plan. It pins the matching snapshot and
  canonical instrument identities, canonical account identity, current position direction and
  absolute quantity, monetary exposure per quantity unit, quantity increment, and valuation
  Evidence. It contains no provider identifier, route, credential, payload, or executable client.

All objects are frozen, slot-based dataclasses. Nested collections are tuples. IDs are opaque and
must be supplied by the owning upstream component; downstream consumers never derive meaning by
parsing them.

## Canonical Semantics

### Instrument identity

Identity is the complete `(scheme, value)` pair in `CanonicalInstrumentIdentity`. The scheme
names a stable canonical namespace; the value is opaque within that namespace. Display symbols,
option descriptions, and provider instrument IDs are attributes or adapter concerns, never
identity inputs inferred downstream. Equality compares the complete identity object. Options
carry their underlying identity explicitly, so no consumer parses an option symbol.

### Portfolio snapshot

A snapshot has a stable `portfolio_snapshot_id`, portfolio identity, one base currency, unique
holdings, cash balance, buying power, net liquidation value, gross exposure, semantic
`observed_at`, and source Evidence. Every holding carries its valuation time and Evidence. An
empty holding tuple is valid: an account-only or cash-only portfolio remains representable.

The snapshot is a value, not a mutable aggregate. A changed balance, holding, valuation, or
observation time requires a new snapshot and identity. Persistence ownership is intentionally not
part of this contract.

### Buying power and cash

`cash_balance` is the signed settled ledger cash reported for the snapshot. `buying_power` is the
non-negative amount available for new exposure after external account restrictions. They are
independent supplied values: neither is calculated from the other. A negative cash balance can
therefore coexist with positive buying power. Policy may consume these fields later but this
contract does not decide whether a proposal is affordable.

### Exposure and valuation

Every monetary amount uses finite `Decimal` arithmetic and an explicit currency. Snapshot values
and holding valuations use the snapshot base currency; currency conversion must occur before
construction and must be evidenced upstream.

Holding `market_value` is absolute current value. Holding and Portfolio Snapshot
`gross_exposure` are non-negative policy exposure amounts supplied by the valuation owner.
Direction is carried separately. `net_liquidation_value` is the signed portfolio value supplied
by the same snapshot.
No contract multiplies quantity by price, derives option exposure, substitutes average cost, or
performs currency conversion.

### Sector

Sector is an optional `SectorClassification` containing taxonomy, pinned taxonomy version, and
code. `None` means no classification was supplied; it never means a default sector. Policy must
handle absence explicitly. Options do not infer sector by parsing their symbols; an upstream
normalizer may supply the correct classification while retaining the explicit underlying identity.

### Execution context

Execution context is supplied explicitly to the Execution Planner; it is never recovered by
parsing an ID or consulting a repository, provider, broker, or mutable registry. `account_id` is
ASA's canonical provider-neutral account identity. `current_quantity` is absolute and uses the
same explicit `PositionDirection` semantics as Holding; zero means flat and has no direction.

`unit_exposure` is the base-currency monetary exposure represented by one quantity unit. Its
upstream valuation owner must already incorporate instrument semantics such as option contract
multipliers and cite the valuation Evidence. The planner divides approved monetary exposure by
this supplied unit exposure and applies the supplied positive quantity increment. It never treats
allocation as quantity, parses symbols, invents prices, or performs provider lookup.

## Boundaries

The Intelligence pipeline continues through Ranking. It may produce a `ProposedPosition` from a
`RankedOpportunity`, preserving the Opportunity and Ranking IDs and the Evidence actually used.
ADR-009 assigns that transformation to the Position Proposal Engine; ASA-CORE-008 implements it.

The Operational Portfolio boundary consumes `ProposedPosition` and `PortfolioSnapshot` through a
`PortfolioDecisionRequest`. A provider or broker adapter may normalize read-only account data
into these shared contracts, but provider payload classes, SDK objects, repositories, and
provider identifiers never enter `domain/`. No Operational component may mutate an Opportunity
or place operational logic inside Ranking or Strategies.

This boundary supplies the state needed by portfolio policy and read-only execution-plan
presentation. It does not authorize order creation or broker writes; those remain prohibited by
Constitution Law 5.

PortfolioDecision remains analytical and account-neutral. Account selection, current position
state, and execution valuation enter only through ExecutionContext. Adding this explicit side
input does not add a pipeline stage; it makes the existing Execution Planner boundary complete
and replayable.

## Alternatives Considered

1. **Add instrument and portfolio fields directly to Ranking models.** Rejected: Ranking orders
   Opportunities and must not become the owner of operational financial state.
2. **Reuse the backend broker-ingestion snapshot.** Rejected: it is an integration-specific
   publication model outside the intelligence dependency boundary and lacks the canonical
   valuation semantics required by portfolio policy.
3. **Infer exposure from quantity and average cost.** Rejected: average cost is not current value,
   and option exposure cannot be derived correctly without a valuation policy.
4. **Use symbols as canonical identity.** Rejected: symbols are display/routing attributes,
   ambiguous across markets, and especially unsafe when parsed as option contracts.
5. **Put a repository on the request.** Rejected: it would make replay depend on mutable external
   state and violate the pure contract boundary.

## Consequences

- ASA-CORE-009 can evaluate cash, buying power, duplicate identity, current value, gross
  exposure, and sector without broker or repository access.
- Read-only broker adapters have an explicit normalization target without leaking SDK models.
- Proposed exposure is independently inspectable and traceable to Ranking and Evidence.
- Upstream normalization or valuation must supply canonical identities and financial values;
  absence is represented explicitly rather than hidden behind a fallback calculation.
- Supporting more instrument kinds or a new canonical identity scheme is a deliberate contract
  change, not dynamic parsing.
- Execution planning requires a matching canonical ExecutionContext; missing account or valuation
  state is represented as a missing required input, never a hidden fallback.

## References

- GitHub issue #57
- GitHub issue #70
- ADR-003: Explainable Opportunity Model
- ADR-004: Repository Organization
- ADR-007: Deterministic Ranking Model
- Architecture Constitution, Laws 3, 4, 5, 9, and 10
- ADR-009: Execution Semantics and Governance Boundary
