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
      │  ◄── ExecutionContext
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
  canonical Instrument, scoring provenance, and Evidence. It never reads portfolio state.
- `ProposedPosition` answers **what exposure Intelligence would want without portfolio
  constraints**. The Position Proposal Engine owns target-allocation and sizing policy and
  propagates the ranked thesis, confidence, effective sizing parameters, rationale, and Evidence.
  It never reads cash, buying power, or holdings.

`ProposedPosition.target_allocation` is a snapshot-independent decimal fraction in `[0, 1]` that
expresses desired unconstrained allocation. Proposed Position contains its sizing-policy version
and parameters but no reference capital, Portfolio identity, or Portfolio-derived value. Under
ASA-ARCH-006, Portfolio Engine alone derives sizing reference capital from the source Snapshot net
liquidation value. Replay binds the immutable proposal and source Snapshot in the identified
Portfolio Evaluation Result, so no hidden configuration or upstream Portfolio access is required.

- `PortfolioDecision` answers **how much of that proposed exposure survives current portfolio
  constraints**. It references exactly one Proposed Position and Portfolio Snapshot, pins policy
  versions and effective parameters, and records `ACCEPT`, `REJECT`, `REDUCE`, or `HOLD` with
  approved allocation, reasons, and Evidence. Account selection and valuation are later-stage
  portfolio concerns; they are never fields on Proposed Position.
- `ExecutionPlan` answers **how the approved decision would be decomposed and sequenced**. It
  retains the complete Portfolio Decision and matching Execution Context and owns an ordered tuple of analytical
  `BrokerRequest` records. A rejected or held decision has an empty tuple.
- `BrokerRequest` answers **what broker-neutral order template represents one step of the
  plan**. It contains instrument, account identity, side, quantity, order shape, lifetime,
  bounded metadata, sequence, and reasoning Evidence. It is not an HTTP request, SDK object, or
  provider payload.

`ExecutionPlan` owns its Broker Requests so ASA-CORE-010 has one complete immutable output. This
does not collapse or skip the BrokerRequest stage: each request is independently identified,
ordered, and replayable within the plan. No separate Broker Request engine is implied.

`ExecutionContext` is a required provider-neutral side input to the Execution Planner. It owns
canonical account selection, current position state, monetary exposure per quantity unit,
quantity increment, and valuation Evidence for exactly the Portfolio Snapshot and Instrument
referenced by the decision. It contains no broker-specific identifier or behavior. A mismatch is
invalid input, not an occasion for lookup or fallback.

V1 Proposed Position allocation is long gross exposure. The Portfolio Engine may accept or reduce
that exposure, or reject/hold it, but PortfolioDecision remains account-neutral. The Execution
Planner derives target long quantity from approved allocation, the proposal's pinned reference
capital, and ExecutionContext unit exposure. It compares that target with the explicitly supplied
current direction and quantity to derive BUY, SELL, BUY_TO_COVER, or ordered cover-then-buy steps.
It applies the supplied quantity increment deterministically and never invents an account, price,
multiplier, direction, or current position.

## Law 5 Boundary

For purposes of Constitution Law 5, `RankingResult`, `ProposedPosition`, `PortfolioDecision`,
`ExecutionContext`, `ExecutionPlan`, and `BrokerRequest` are analytical values. Constructing, comparing, serializing
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

The shared `domain/` package adds only `PortfolioDecision`, `ExecutionContext`, `ExecutionPlan`,
and `BrokerRequest`, plus closed enums needed to make their states explicit. All are frozen slot-based dataclasses;
nested collections are tuples; numeric quantities and amounts are finite `Decimal` values.

Identity namespaces are `asa.portfolio_decision`, `asa.execution_context`, `asa.execution_plan`,
and `asa.broker_request`, each initially versioned `v1`. Their future engines must derive IDs from
complete semantic inputs:

- Portfolio Decision identity includes proposal identity, snapshot identity, decision algorithm
  version, state, approved exposure, policy versions, effective parameters, reasons, and Evidence.
- Execution Context identity includes snapshot identity, canonical account and instrument
  identities, current direction and quantity, unit exposure, quantity increment, and valuation
  Evidence.
- Execution Plan identity includes decision and context identities, planning algorithm version,
  ordered Broker Request identities, and reasoning Evidence.
- Broker Request identity includes decision identity, sequence, canonical instrument identity,
  account identity, side, quantity, order type, limit price when applicable, time in force,
  metadata, and reasoning Evidence.

Proposed Position identity remains in the `asa.proposed_position` namespace and includes the
Opportunity, Ranked Opportunity, and Ranking Result identities; proposal algorithm version;
canonical Instrument; target allocation; confidence; rationale; effective parameters; and Evidence.

Identity excludes timestamps, process execution order, serialization order of keyed parameters,
randomness, provider payloads, and broker state. Contract fields contain no timestamps. Engines
must canonicalize keyed parameters by key before hashing and reject duplicate keys.

## State Semantics

- `ACCEPT` approves the complete proposed target allocation.
- `REDUCE` approves a smaller positive target allocation.
- `REJECT` approves no new exposure because portfolio policy disallows the proposal.
- `HOLD` approves no new exposure because no portfolio change should be planned.

Approved decisions require at least one Broker Request in an Execution Plan. Rejected and held
decisions require none. Broker Request sequence numbers are contiguous from one and are the sole
ordering authority; timestamps never determine sequence.

These are structural coherence rules, not decision or planning algorithms.

## Module and Governance Boundaries

ASA-CORE-008 owns only `RankingResult -> ProposedPosition` and must not inspect portfolio state.
ASA-CORE-009 owns only `(ProposedPosition, PortfolioSnapshot) -> PortfolioDecision` and must not
plan execution. ASA-CORE-010 owns only `(PortfolioDecision, ExecutionContext) -> ExecutionPlan`, including its
ordered Broker Requests, and must not import providers, adapters, infrastructure, networking,
authentication, or persistence.

Workers may implement, test, refactor within ticket scope, and file issues. Founder remains the
ultimate merge authority. A worker may merge only an enumerated implementation PR while Accepted
GOV-AMD-001 Amendment 013 is active and every sprint gate passes; architecture contract changes
remain Founder-merge-only.

Opportunity is the canonical owner of Instrument identity before the operational boundary.
Strategy evaluation receives an explicit canonical Instrument and includes its identity in
Opportunity identity. Guardrails and Ranking retain the complete immutable Opportunity; neither
copies, resolves, parses, or looks up Instrument data. Position Proposal therefore consumes the
Instrument already present in Ranking Result.

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

## Revision note (Issue #63)

`ProposedPosition` is narrowed to desired analytical allocation. Account, portfolio, quantity,
market price, broker, provider, and order fields belong to later stages. Opportunity now owns the
canonical Instrument and Ranking preserves it through its existing evaluation envelope, closing
the last required source path without hidden mappings.

## Revision note (Issue #70)

ExecutionContext is the explicit canonical side input for account, current-position,
unit-exposure, quantity-increment, and valuation Evidence. PortfolioDecision remains analytical
and account-neutral. CORE-010 no longer needs hidden lookup or fabricated execution inputs.

## References

- GitHub issue #59
- GitHub issue #63
- GitHub issue #70
- ADR-007: Deterministic Ranking Model
- ADR-008: Operational Trading Contracts
- Architecture Constitution, Laws 5, 7, 9, and 10
- `roles/shared/AUTHORITY_BOUNDARIES.md`

## Revision note (GOV-AMD-014 and ASA-ARCH-006)

GOV-AMD-014 replaces the absolute read-only law with an analytical execution boundary while
continuing to prohibit every live brokerage operation. ASA-ARCH-006 evolves this v1 analytical
contract: `BrokerRequest` is superseded by `PlannedOrder`; combined `PortfolioDecision` is split
into `PortfolioDelta` and `RiskDecision`; and Execution Plan v2 owns Planned Orders, summary,
trace, and explicit source state. The implementation migration is atomic—no alias, dual-read, or
compatibility shim is authorized. This revision also supersedes the original reference-capital
semantic: target allocation is snapshot-independent and Portfolio Engine derives reference
capital from source Snapshot state. External broker communication remains prohibited.
