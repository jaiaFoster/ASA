<!-- Repository path: architecture/ADR-009-execution-semantics.md -->

# ADR-009: Execution Semantics and Governance Boundary

**Status:** Accepted
**Date:** 2026-07-21

## Context

ADR-008 established immutable provider-neutral portfolio contracts but intentionally stopped
before portfolio decisions or execution semantics. SPRINT-001 initially attempted to implement
Portfolio, Planning, and Broker Abstraction engines without first assigning the transformation
from Ranking to desired exposure or defining the output contracts. GitHub issue #59 records the
resulting ambiguity.

Constitution Law 5 is binding: ASA does not execute trades, place orders, or modify brokerage
state. The architecture may nevertheless analyze how a portfolio decision could be represented
as ordered, broker-neutral instructions, provided those values remain inert domain records and no
component can communicate them to a broker. The boundary between analysis and execution must be
structural, not dependent on naming or developer restraint.

## Decision

The canonical analytical pipeline is:

```text
RankingResult
      │
      ▼
Position Proposal Engine
      │
      ▼
ProposedPosition
      │
      ▼
Portfolio Engine  ◄── PortfolioSnapshot
      │
      ▼
PortfolioDecision
      │
      ▼
Execution Planner
      │
      ▼
ExecutionPlan
      │
      ▼
BrokerRequest
══════════════════════════════════
Future broker-adapter boundary
```

No stage may be skipped. `ProposedPosition` is the canonical term; “PositionProposal” names the
engine responsibility, not a second domain object.

### Semantic ownership

- `RankingResult` answers **what is attractive**. It orders Opportunities with confidence,
  scoring provenance, and Evidence. It never reads portfolio state.
- `ProposedPosition` answers **what exposure Intelligence would want without portfolio
  constraints**. The Position Proposal Engine owns target-allocation and sizing policy and
  propagates the ranked thesis, confidence, effective sizing parameters, rationale, and Evidence.
  It never reads cash, buying power, or holdings.

`ProposedPosition.target_allocation` is a decimal fraction in `(0, 1]` of the Position Proposal
Engine's explicitly parameterized reference capital. It is desired unconstrained allocation, not
a percentage derived from the observed Portfolio Snapshot. The reference-capital and sizing
policy values must be present in the proposal's effective parameters, so replay never depends on
hidden configuration.
- `PortfolioDecision` answers **how much of that proposed exposure survives current portfolio
  constraints**. It references exactly one Proposed Position and Portfolio Snapshot, pins policy
  versions and effective parameters, and records `ACCEPT`, `REJECT`, `REDUCE`, or `HOLD` with
  approved quantity, approved exposure, reasons, and Evidence.
- `ExecutionPlan` answers **how the approved decision would be decomposed and sequenced**. It
  retains the complete Portfolio Decision and owns an ordered tuple of analytical
  `BrokerRequest` records. A rejected or held decision has an empty tuple.
- `BrokerRequest` answers **what broker-neutral order template represents one step of the
  plan**. It contains instrument, account identity, side, quantity, order shape, lifetime,
  bounded metadata, sequence, and reasoning Evidence. It is not an HTTP request, SDK object, or
  provider payload.

`ExecutionPlan` owns its Broker Requests so ASA-CORE-010 has one complete immutable output. This
does not collapse or skip the BrokerRequest stage: each request is independently identified,
ordered, and replayable within the plan. No separate Broker Request engine is implied.

## Law 5 Boundary

For purposes of Constitution Law 5, `RankingResult`, `ProposedPosition`, `PortfolioDecision`,
`ExecutionPlan`, and `BrokerRequest` are analytical values. Constructing, comparing, serializing
for deterministic identity, testing, or presenting these values does not communicate with or
modify a broker.

Operational execution begins only when a component attempts external broker communication. A
broker adapter, SDK call, authentication flow, session, network client, order submission,
cancellation, modification, or transfer is therefore outside the permitted architecture. This
ADR clarifies where the existing law applies; it does not amend the Constitution or authorize a
future adapter. Any adapter proposal requires its own governance review and must resolve Law 5
before implementation.

The `BrokerRequest` contract structurally excludes endpoints, provider payloads, credentials,
tokens, sessions, cookies, callbacks, and executable functions. Nothing in `domain/` can reach an
adapter or cause a side effect.

## Contracts and Identity

The shared `domain/` package adds only `PortfolioDecision`, `ExecutionPlan`, and `BrokerRequest`,
plus closed enums needed to make their states explicit. All are frozen slot-based dataclasses;
nested collections are tuples; numeric quantities and amounts are finite `Decimal` values.

Identity namespaces are `asa.portfolio_decision`, `asa.execution_plan`, and
`asa.broker_request`, each initially versioned `v1`. Their future engines must derive IDs from
complete semantic inputs:

- Portfolio Decision identity includes proposal identity, snapshot identity, decision algorithm
  version, state, approved exposure, policy versions, effective parameters, reasons, and Evidence.
- Execution Plan identity includes decision identity, planning algorithm version, ordered Broker
  Request identities, and reasoning Evidence.
- Broker Request identity includes decision identity, sequence, canonical instrument identity,
  account identity, side, quantity, order type, limit price when applicable, time in force,
  metadata, and reasoning Evidence.

Proposed Position identity remains in the `asa.proposed_position` namespace and includes the
Opportunity, Ranked Opportunity, and Ranking Result identities; proposal algorithm version;
portfolio and account identities; instrument and direction; target allocation; quantity; price;
gross exposure; confidence; rationale; effective parameters; and Evidence.

Identity excludes timestamps, process execution order, serialization order of keyed parameters,
randomness, provider payloads, and broker state. Contract fields contain no timestamps. Engines
must canonicalize keyed parameters by key before hashing and reject duplicate keys.

## State Semantics

- `ACCEPT` approves the complete proposed quantity and gross exposure.
- `REDUCE` approves a smaller positive quantity and gross exposure.
- `REJECT` approves no new exposure because portfolio policy disallows the proposal.
- `HOLD` approves no new exposure because no portfolio change should be planned.

Approved decisions require at least one Broker Request in an Execution Plan. Rejected and held
decisions require none. Broker Request sequence numbers are contiguous from one and are the sole
ordering authority; timestamps never determine sequence.

These are structural coherence rules, not decision or planning algorithms.

## Module and Governance Boundaries

ASA-CORE-008 owns only `RankingResult -> ProposedPosition` and must not inspect portfolio state.
ASA-CORE-009 owns only `(ProposedPosition, PortfolioSnapshot) -> PortfolioDecision` and must not
plan execution. ASA-CORE-010 owns only `PortfolioDecision -> ExecutionPlan`, including its
ordered Broker Requests, and must not import providers, adapters, infrastructure, networking,
authentication, or persistence.

Workers may implement, test, refactor within ticket scope, file issues, and mark a PR ready for
merge. They may not merge. Founder remains the sole merge authority, and every sprint PR requires
Founder approval after tests, replay, dependency, forbidden-import, circularity, and quality gates
pass.

## Alternatives Considered

1. **Let CORE-008 read RankingResult and PortfolioSnapshot together.** Rejected: it combines
   unconstrained investment intent with portfolio policy and leaves no owner for ProposedPosition.
2. **Let BrokerRequest be an adapter API DTO.** Rejected: provider leakage would cross Law 5's
   operational boundary and make the domain depend on infrastructure.
3. **Add a Broker Adapter interface and Robinhood skeleton now.** Rejected: an adapter is not
   required to define analytical contracts and creates unresolved authority to communicate with a
   broker.
4. **Add a fourth Broker Request engine.** Rejected: the Execution Planner already owns order
   decomposition; requests are the ordered leaf records of its plan.
5. **Amend Constitution Law 5.** Rejected: no amendment is required to describe inert analytical
   values, and this ticket has no constitutional amendment authority.

## Consequences

- Issue #59's missing producer and contract ownership are resolved.
- CORE-008 through CORE-010 can be implemented without inventing domain objects or pipeline stages.
- Deterministic identity and replay inputs are complete before engine implementation begins.
- The architecture can describe a hypothetical execution plan while remaining unable to execute it.
- Any future broker adapter is a new, explicitly governed concern beyond this sprint.

## References

- GitHub issue #59
- ADR-007: Deterministic Ranking Model
- ADR-008: Operational Trading Contracts
- Architecture Constitution, Laws 5, 7, 9, and 10
- `roles/shared/AUTHORITY_BOUNDARIES.md`
