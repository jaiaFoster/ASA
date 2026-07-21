# ASA-ARCH-006: Analytical Execution Contracts

**Status:** Proposed — Founder merge required  
**Date:** 2026-07-21  
**Sprint:** SPRINT-004  
**Risk:** R3 architecture and public-contract change, governed by the R5 boundary in GOV-AMD-014

## 1. Problem

ASA already produces inert `ExecutionPlan` and `BrokerRequest` v1 values, but it has no complete
analytical lifecycle for portfolio deltas, explicit risk decisions, planned-order simulation,
or replay of resulting portfolio state. The existing `PortfolioDecision` combines portfolio
transition intent with policy disposition, `Holding` is an observed valued position rather than
an engine-owned analytical position, and `BrokerRequest` sounds operational despite being inert.

SPRINT-004 must complete the analytical platform without creating any path to a live broker.
GOV-AMD-014 is controlling: ASA Core may generate plans and simulate them, but cannot authenticate,
submit, modify, cancel, call, or otherwise mutate a brokerage system.

## 2. Binding principles

1. Every object is immutable, canonically serializable, deterministically identified, and
   replayable from complete semantic inputs.
2. Strategy owns investment intent only. It never owns holdings, cash, positions, orders,
   portfolio state, or simulation.
3. Portfolio Engine is the sole calculation owner for position state, cost basis, cash, buying
   power, realized P&L, unrealized P&L, allocation, and portfolio transitions.
4. Risk Engine evaluates declared policy; it does not own portfolio state or plan orders.
5. Execution Planning Engine converts one approved risk decision into inert `PlannedOrder`
   artifacts. It has no operational effect.
6. Simulation Engine interprets a plan only against explicit immutable simulation evidence. It
   contains no network, broker, provider, credentials, clock, randomness, persistence, or hidden
   liquidity.
7. A planned order is not an order submitted anywhere. “Execution” within ASA Core always means
   analytical planning or deterministic simulation.
8. No module may expose an interface named or behaving as live `submit`, `modify`, `cancel`,
   `authenticate`, `connect`, or `place_order`.

## 3. Canonical pipeline and ownership

```text
RankingResult
      │
      ▼
Position Proposal Engine ───────────────► ProposedPosition
                                                │
PortfolioSnapshot ──► Portfolio Engine ◄────────┘
                           │
                           ▼
                    PortfolioDelta (proposed)
                           │
RiskPolicy set ───────► Risk Engine
                           │
                           ▼
                       RiskDecision
                           │ approved/reduced only
                           ▼
                 Execution Planning Engine
                           │
                           ▼
                     ExecutionPlan
                           │
                           ▼
                     PlannedOrder(s)
                           │
SimulationMarketData ─► Simulation Engine
                           │
                           ▼
                     SimulationResult
                           │ simulated fills
                           ▼
                    Portfolio Engine
                           │
                           ▼
            PortfolioDelta (realized) + next PortfolioSnapshot
```

Risk rejection ends the path with no Execution Plan. Planning and simulation never update a
Portfolio directly. The Simulation Engine emits immutable simulated fills; the Portfolio Engine
is the only owner allowed to apply those fills and produce the next immutable portfolio state.

## 4. Contract conventions

All public contracts are frozen slot-based dataclasses or closed enums. Collections are tuples in
canonical order. Decimal values must be finite and normalized. Times are timezone-aware semantic
times supplied as inputs; wall-clock time is never read. IDs are opaque content hashes in the
namespaces defined below. IDs include all semantic parameters and evidence and exclude runtime
duration, input enumeration order where order is non-semantic, process state, and serialization
formatting.

Evidence is a non-empty canonical tuple of `EvidenceReference` values actually consumed. A trace
may cite upstream artifact identities, but it cannot replace field-level evidence. Missing values
fail closed; no engine invents price, multiplier, quantity increment, sector, liquidity, account,
or policy defaults outside its explicit versioned parameters.

## 5. Position and Portfolio contracts

### 5.1 Position

`Position` is the Portfolio Engine's immutable analytical state for one account and canonical
Instrument. It replaces the operational-domain name `Holding` during EXEC-002.

Required fields:

```text
Position
  position_id
  account_id
  instrument
  direction                 LONG | SHORT
  quantity                  positive absolute Decimal
  quantity_increment        positive Decimal
  average_cost_per_unit     MonetaryAmount
  current_price_per_unit    MonetaryAmount
  price_multiplier          positive Decimal
  unit_exposure             positive MonetaryAmount
  market_value              non-negative MonetaryAmount
  gross_exposure            non-negative MonetaryAmount
  realized_pnl              signed MonetaryAmount
  unrealized_pnl            signed MonetaryAmount
  valued_at                 semantic UTC datetime
  valuation_evidence
```

There is no zero-quantity Position. Flat means absence from the position tuple. Direction carries
sign; quantity never does. All monetary fields use the Portfolio base currency. The contract
validates coherence but calculates nothing. Portfolio Engine alone calculates cost basis, market
value, exposure, and P&L using a pinned algorithm version. `unit_exposure` is the current
base-currency policy exposure represented by one quantity unit and already incorporates explicit
instrument semantics such as an option multiplier; no downstream engine parses a symbol or
invents that multiplier. `price_multiplier` is supplied and evidenced instrument semantics
(`1` for one equity share, commonly `100` for one standard option contract); quote price multiplied
by it is economic value per quantity unit.

Position `realized_pnl` is cumulative only for that active Position's uninterrupted lifecycle.
When the Position closes it is removed; Portfolio cumulative `realized_pnl` retains the closed
Position's realized result as specified in Section 5.5.

### 5.2 Portfolio

`Portfolio` is one immutable revision of complete analytical state:

```text
Portfolio
  portfolio_id
  revision                  positive integer
  account_id                one canonical ASA account identity (v1)
  base_currency
  currency_quantum          positive Decimal
  positions                 unique by (account_id, instrument identity)
  cash_balance              signed MonetaryAmount
  buying_power              non-negative MonetaryAmount
  net_liquidation_value     signed MonetaryAmount
  gross_exposure            non-negative MonetaryAmount
  realized_pnl              signed MonetaryAmount
  unrealized_pnl            signed MonetaryAmount
  platform_risk_policies    complete canonical RiskPolicy tuple
  policy_activation_evidence
  portfolio_state_id
```

V1 is explicitly single-account and USD-only: Portfolio `base_currency` must equal `USD`, and
every eligible Instrument and Monetary Amount must use USD. This matches the active upstream
Expected Outcome Metrics contract, whose amount fields are bare Decimals normatively denominated
in USD. A future multi-currency contract requires a separate Founder-approved architecture change
that adds currency-bearing metrics or evidenced conversion; currency is never inferred from a
Decimal. Every Position account must equal the
Portfolio account. `Portfolio` is a value, not a mutable aggregate or repository entity. A
transition preserves `portfolio_id`, increments `revision` by exactly one, and derives a new
`portfolio_state_id` from complete content. Timestamps are not used to select current state. The
complete Platform Risk Policies and the Evidence authorizing their activation are embedded, so
Risk evaluation performs no ID lookup. This architecture introduces no persistence or “current”
pointer.

### 5.3 PortfolioSnapshot

`PortfolioSnapshot` is the evidence-backed observation envelope used by analytical engines:

```text
PortfolioSnapshot
  portfolio_snapshot_id
  portfolio                 complete Portfolio value
  instrument_valuations     complete target InstrumentValuation tuple
  observed_at               semantic UTC datetime
  evidence
```

The embedded Portfolio is complete; a Snapshot never references a mutable object or repository.
Account-only/cash-only portfolios remain valid through an empty Position tuple. Product-backend
publication tables are a separate integration model and are not imported into Strategy Core.

`InstrumentValuation` is the explicit immutable owner of planning inputs for both held and new
instruments:

```text
InstrumentValuation
  instrument_valuation_id
  instrument
  account_id                must equal Portfolio account
  current_price             positive MonetaryAmount in Portfolio base currency
  price_multiplier          positive Decimal
  unit_exposure             positive MonetaryAmount in Portfolio base currency
  quantity_increment        positive Decimal
  valued_at                 semantic UTC datetime
  evidence                  field-level valuation/instrument Evidence
```

Valuations are unique by Instrument identity and canonically ordered. Every Position and every
Proposed Position being evaluated must have exactly one matching valuation. Existing Position
price multiplier, unit exposure, increment, and current price must match it. Missing, duplicate,
stale-by-policy, wrong-account, or wrong-currency valuation fails before a Delta is constructed.
The Portfolio account supplies new-position account selection; no Strategy, proposal, ID parser,
provider, repository, or fallback chooses an account. V1 requires Instrument currency equal the
Portfolio base currency; foreign-currency state is rejected rather than converted implicitly.

### 5.4 PortfolioDelta

`PortfolioDelta` describes one complete intended or realized change without mutating either
endpoint:

```text
PortfolioDelta
  portfolio_delta_id
  delta_version
  kind                      PROPOSED | APPROVED | SIMULATED
  source_snapshot_id
  source_portfolio_identity
  proposed_position_id
  predecessor_delta_id      absent for PROPOSED; required otherwise
  account_id
  instrument
  projected_maximum_loss    non-negative MonetaryAmount
  starting_direction        optional
  starting_quantity         non-negative absolute Decimal
  target_direction          optional
  target_quantity           non-negative absolute Decimal
  cash_change               signed MonetaryAmount
  buying_power_change       signed MonetaryAmount
  rationale
  effective_parameters
  evidence
```

Zero target quantity requires no target direction. A proposed delta comes from Portfolio Engine.
An approved delta is carried by Risk Decision and may only reduce, never enlarge, the proposed
exposure. A simulated delta is derived only from simulated fills and may reflect partial filling.
Every later kind references the immediately preceding delta through `predecessor_delta_id`.
Portfolio Engine returns a `PortfolioEvaluationResult` that contains either a proposed Delta or
an explicit no-change disposition. It estimates proposed and approved cash/buying-power effects from the Snapshot's
explicit valuation and price multiplier; these are policy estimates, not simulated fills.
Simulated deltas replace the estimates with realized effects derived from fill prices.
`projected_maximum_loss` is the non-negative absolute base-currency loss propagated from the
Opportunity's Expected Outcome Metrics through Proposed Position, with its consumed Evidence.

### 5.5 Portfolio Engine v1 calculation semantics

V1 is a cash-account, long-target model. An imported Snapshot may contain an existing short
Position so the platform can plan a cover, but no proposed delta or Planned Order may open or
increase a short. `SELL_SHORT` is therefore not a v1 Planned Order side.

Portfolio Engine uses a fixed Decimal context and these versioned formulas:

- `unit_value = current_price_per_unit × price_multiplier`
- `market_value = quantity × unit_value`
- `gross_exposure = market_value`; Portfolio gross exposure is the sum of Position exposure
- long unrealized P&L is `(current_price - average_cost) × multiplier × quantity`
- short unrealized P&L is `(average_cost - current_price) × multiplier × quantity`
- a same-direction increase computes weighted average cost from old and simulated fill economic
  cost; a reduction preserves average cost on remaining quantity
- realized P&L for a long reduction is `(fill_price - average_cost) × multiplier × filled_quantity`
- realized P&L for a short cover is `(average_cost - fill_price) × multiplier × filled_quantity`
- closing to zero removes the Position; crossing direction is represented by ordered close then
  open operations, never a signed quantity
- BUY and BUY_TO_COVER simulated fills debit cash; SELL fills credit cash; v1 has zero fees
- buying-power change equals cash change, preserving any explicit difference between starting cash
  and starting buying power; Risk must reject a transition that would make either available
  buying power or required reserve negative
- net liquidation value is cash plus long market value minus short market value
- Portfolio unrealized P&L is the sum of active Position unrealized P&L in base currency
- Portfolio realized P&L is cumulative ledger state: source Portfolio realized P&L plus newly
  realized P&L from this transition; it is not the sum of active Position realized P&L

Every multiplication and rounding rule, including Decimal precision and currency quantum, is
pinned by the Portfolio algorithm version in EXEC-003. V1 uses Decimal precision 34 with
`ROUND_HALF_EVEN`; intermediate calculations retain full context precision and each published
Monetary Amount is quantized once to `Portfolio.currency_quantum`. Quantity must already be an
exact multiple of quantity increment and is never rounded by Portfolio Engine.

For a new long Position, average cost and current price are the first simulated fill price. For
an untouched Position, the next Snapshot uses its matching supplied Instrument Valuation current
price. For a filled Position, the last fill by global fill sequence supplies current price. A
short-to-long reversal is exactly BUY_TO_COVER to zero followed by BUY; the new long cost basis
contains no short lots. Source realized P&L plus newly realized P&L becomes next realized P&L.
Unrealized P&L is recalculated from next quantity/cost/current price. The next Snapshot uses
Simulation Market Data `as_of` as `observed_at`, contains the incremented Portfolio revision, and
cites source Snapshot, valuation, Plan, Risk Decision, and simulated-fill Evidence.

Currency conversion remains upstream and evidenced; mixed-currency Portfolio state is invalid.

`portfolio_id` is the stable caller-supplied logical identity. `portfolio_state_id` hashes that
identity, revision, account, base currency, currency quantum, complete ordered Positions, cash,
buying power, valuation/P&L totals, complete Platform policies, and activation Evidence. Snapshot
identity separately hashes the state ID, semantic `observed_at`, ordered Instrument Valuations,
and Snapshot Evidence. Neither identity depends on object construction order or wall-clock time.

### 5.6 Initial target sizing and no-op semantics

Proposed Position `target_allocation` is a snapshot-independent fraction in `[0, 1]`; it contains
no reference capital, Portfolio identity, or Portfolio-derived value. Portfolio Engine reads the
source Snapshot and locally defines `reference_capital` as its Portfolio net liquidation value,
which must be positive. `desired_exposure = target_allocation × reference_capital` and
`raw_target_quantity = desired_exposure / unit_exposure`.
Portfolio Engine rounds toward zero to the greatest non-negative exact multiple of the matching
Instrument Valuation `quantity_increment` that does not exceed the raw quantity. It never rounds
up. A result below one increment is zero. Starting and target quantities produce the Delta; if
they are identical, the pipeline emits an evidenced analytical no-op result and no Delta, Risk
Decision, Plan, or order.

The active Opportunity Expected Outcome Metrics convention supplies positive `capital_required`
and non-positive `maximum_loss` as USD Decimals. Because v1 Portfolio base currency is required to
be USD, compatibility is validated without inference or conversion. The versioned non-negative loss rate
is `abs(maximum_loss) / capital_required`. Proposed Delta `projected_maximum_loss` is loss rate
multiplied by target gross exposure and quantized once to `currency_quantum`. Missing, non-positive, or
currency-incompatible capital input fails closed. Every reduced candidate recomputes this field
from its candidate exposure; it never copies the proposed amount unchanged.

```text
PortfolioEvaluationResult
  portfolio_evaluation_result_id
  portfolio_algorithm_version
  source_snapshot_id
  proposed_position_id
  disposition               DELTA_PRODUCED | NO_CHANGE
  proposed_delta            required only for DELTA_PRODUCED
  rationale
  evidence                  consumed sizing and valuation Evidence
```

NO_CHANGE is required exactly when starting and target direction/quantity are identical. Its ID
hashes the complete fields above, including rationale and Evidence. It is the typed, replayable
representation of the no-op; Risk and Planning accept only DELTA_PRODUCED results.

This clarification does not change Proposed Position identity or permit Position Proposal to read
Portfolio state. Portfolio Evaluation Result identity includes Proposed Position ID, source
Snapshot ID, algorithm version, complete result, rationale, and Evidence, so sizing against a
different Snapshot necessarily produces a different downstream identity.

## 6. Risk contracts

### 6.1 RiskPolicy

`RiskPolicy` is immutable declarative policy data, not executable code:

```text
RiskPolicy
  risk_policy_id
  policy_type               closed v1 enum
  scope                     PLATFORM | STRATEGY
  policy_version
  parameters                typed canonical tuple
  strategy_id               required only for STRATEGY scope
  rationale
  evidence                  field-level policy-authority Evidence
```

V1 policy types are `BUYING_POWER`, `CASH_RESERVE`, `MAX_POSITION_ALLOCATION`,
`MAX_SINGLE_ASSET_EXPOSURE`, `MAX_SECTOR_EXPOSURE`, `DUPLICATE_EXPOSURE`, and
`MAXIMUM_LOSS`. Each type has one registered pure evaluator and a fixed parameter schema.
There is no expression string, arbitrary callback, plugin hook, dynamic import, or generic policy
framework.

The v1 parameter schemas and comparisons are closed:

| Policy type | Typed parameters | Passing comparison |
|---|---|---|
| `BUYING_POWER` | `minimum_remaining_amount: MonetaryAmount` | projected buying power is greater than or equal to the minimum |
| `CASH_RESERVE` | `minimum_cash_ratio: Decimal` in `[0, 1]` | projected cash divided by source net liquidation value is greater than or equal to the minimum |
| `MAX_POSITION_ALLOCATION` | `maximum_ratio: Decimal` in `[0, 1]` | target Position gross exposure divided by source net liquidation value is less than or equal to the maximum |
| `MAX_SINGLE_ASSET_EXPOSURE` | `maximum_ratio: Decimal` in `[0, 1]` | aggregate target Instrument gross exposure divided by source net liquidation value is less than or equal to the maximum |
| `MAX_SECTOR_EXPOSURE` | `maximum_ratio: Decimal` in `[0, 1]` | aggregate target sector gross exposure divided by source net liquidation value is less than or equal to the maximum |
| `DUPLICATE_EXPOSURE` | `allow_increase_existing: bool` | an existing same-Instrument Position may increase only when true |
| `MAXIMUM_LOSS` | `maximum_amount: MonetaryAmount` | projected maximum loss is less than or equal to the maximum |

Money parameters use Portfolio base currency. Ratio denominators use the source Snapshot net
liquidation value; a non-positive denominator rejects every ratio policy. Missing sector data,
currency mismatch, or incomplete parameters fail closed. Composition is exact: the greater
minimum wins for minimum policies, the lesser maximum wins for maximum policies, and `false`
wins for duplicate exposure. Strategy and Platform values of different policy versions or units
are incompatible and fail rather than being coerced.

Platform policies are mandatory and cannot be disabled or weakened by Strategy policy. A Strategy
may omit policy or add stricter limits only. Effective policy composition takes the strictest
compatible limit per policy type; a conflict or incomparable unit is an error, never a fallback.
Portfolio owns the active policy set; Risk Engine owns evaluation.

Strategy-scoped policies have one explicit propagation path. A Strategy may attach an immutable
tuple of Strategy-scoped `RiskPolicy` values to the Opportunity it produces. Guardrails and
Ranking preserve the complete Opportunity, and Position Proposal preserves the same policy
objects on `ProposedPosition`; none evaluates or rewrites them. An empty tuple is valid. Platform
policies come only from the source Portfolio. Strategy policy IDs and parameters participate in
Opportunity, Proposed Position, Risk Decision, and downstream identities. Strategy cannot emit a
Platform-scoped policy, inspect Portfolio, or choose policy based on current holdings.

### 6.2 RiskDecision

```text
RiskDecision
  risk_decision_id
  risk_algorithm_version
  source_snapshot_id
  proposed_delta
  decision                  APPROVE | REDUCE | REJECT
  approved_delta            present for APPROVE or REDUCE
  ordered_policy_outcomes
  effective_policy_ids
  effective_parameters
  reasons
  evidence
```

Each immutable `PolicyOutcome` contains its own content identity, policy identity and version,
canonical consumed inputs,
comparison operator, threshold, observed value, pass/fail result, reasons, and only the Evidence
actually consumed by that evaluator. No outcome copies the complete upstream Evidence chain.

```text
PolicyOutcome
  policy_outcome_id
  risk_policy_id
  policy_version
  consumed_inputs
  comparison_operator
  threshold
  observed_value
  passed
  reasons
  evidence
```

`APPROVE` preserves the proposed target. `REDUCE` contains a strictly smaller non-zero approved
target. `REJECT` contains no approved delta. Outcomes are ordered by `(scope priority,
policy_type, risk_policy_id)`, never execution order. Risk identity includes every effective
policy and parameter. A risk decision cannot be inferred from an Execution Plan.

Risk evaluation is closed and deterministic. It first evaluates the exact proposed target. If all
effective policies pass, the result is APPROVE. Structural errors (missing Evidence, valuation,
sector, policy parameters, incompatible unit/version/currency, or non-positive ratio denominator)
are input-validation failures and produce no Risk Decision. Policy failure is reducible only for
an exposure-increasing proposed target; a target that maintains or decreases starting gross
exposure is either APPROVE or REJECT and is never enlarged in an attempt to pass.

For a reducible failure, Risk enumerates the finite target-quantity lattice from the proposed
quantity downward by the Instrument quantity increment, excluding zero. For each candidate,
Portfolio Engine's pure calculation reconstructs the complete candidate approved Delta from the
source Snapshot and valuation: target exposure, cash change, buying-power change, allocation,
sector and single-asset exposures, and scaled projected maximum loss are all recomputed and
quantized under Section 5. A candidate passes only when every effective policy passes. The first
passing candidate is the greatest permitted target and yields REDUCE. If none passes, including
when duplicate exposure is prohibited at every positive candidate, the result is REJECT. Zero is
not represented as REDUCE; a later explicitly proposed close is a separate deterministic intent.
Every evaluated candidate and outcome is recorded in canonical descending-quantity order.

The existing v1 `PortfolioDecision` combines delta and risk disposition. EXEC-003/004 replace it
atomically with `PortfolioDelta` plus `RiskDecision`; no alias or compatibility shim remains.

## 7. Planned orders and execution plans

### 7.1 PlannedOrder

`PlannedOrder` replaces the misleading v1 name `BrokerRequest`. It is an immutable analytical
artifact and contains no provider or broker identifier.

```text
PlannedOrder
  planned_order_id
  risk_decision_id
  source_snapshot_id
  sequence                  contiguous from 1
  account_id                canonical ASA identity
  instrument
  side                      BUY | SELL | BUY_TO_COVER
  quantity                  positive Decimal on quantity increment
  order_type                MARKET | LIMIT | STOP | STOP_LIMIT
  limit_price               conditional MonetaryAmount
  stop_price                conditional MonetaryAmount
  price_multiplier          positive Decimal
  time_in_force             DAY | GTC | IOC | FOK
  initial_status            PLANNED
  planning_metadata         canonical tuple
  reasoning
  evidence                  field-level planning Evidence
```

Price-field invariants:

| Type | Limit price | Stop price |
|---|---|---|
| MARKET | forbidden | forbidden |
| LIMIT | required | forbidden |
| STOP | forbidden | required |
| STOP_LIMIT | required | required |

Prices are strictly positive and match instrument currency. `PlannedOrderStatus` is a closed
analytical lifecycle enum: `PLANNED`, `SIMULATED_ACCEPTED`, `SIMULATED_PARTIALLY_FILLED`,
`SIMULATED_FILLED`, `SIMULATED_CANCELLED`, `SIMULATED_REJECTED`. The Planned Order itself always
retains `PLANNED`; simulation emits separate immutable order-state records and never mutates it.
`price_multiplier` is copied from the source Position or explicit new-position valuation evidence
and is included in identity. Simulation cash effect is
`quantity × simulated_fill_price × price_multiplier`; no symbol parsing is permitted.

### 7.2 ExecutionPlan

```text
ExecutionPlan
  execution_plan_id
  planning_algorithm_version
  risk_decision
  source_snapshot
  planned_orders            canonical sequence
  execution_summary
  planning_trace
  effective_parameters
  evidence
```

Only APPROVE and REDUCE decisions can produce a plan. A plan contains at least one Planned Order.
REJECT produces no plan, not an empty plan. Every Planned Order uses the
same snapshot, account, instrument, and currency semantics. Multiple orders are permitted only
when position-direction transition requires ordered close-then-open steps.

`ExecutionSummary` has an `execution_summary_id` derived from its complete content and records
target exposure, starting and planned target quantities, signed
quantity change, expected cash effect when a limit/stop-limit supplies a price, order count, and
human-readable reasons. It must not fabricate expected cash for market/stop orders lacking a
deterministic price.

`PlanningTrace` is an immutable identified ordered tuple of `PlanningTraceEvent` values:

```text
PlanningTrace
  planning_trace_id
  trace_algorithm_version
  events                    canonical event sequence

PlanningTraceEvent
  planning_trace_event_id
  sequence                  contiguous from 1
  event_type                closed PlanningTraceEventType
  input_identities
  output_identities
  algorithm_version
  evidence
```

`PlanningTraceEventType` is the closed enum `PLAN_STARTED`, `DELTA_VALIDATED`,
`RISK_DECISION_VALIDATED`, `QUANTITY_DERIVED`, `ORDER_PLANNED`, and `PLAN_COMPLETED`. There is one
`ORDER_PLANNED` event per order. Each event ID hashes its sequence, type, known input/output IDs,
algorithm version, and Evidence. The Trace ID hashes its version and ordered event IDs. Neither
record has a wall-clock timestamp.

Identity construction is acyclic. Each Planned Order hashes the Risk Decision ID, source Snapshot
ID, sequence, complete order content, planning metadata, reasoning, and Evidence; it does not
contain or hash the not-yet-derived Execution Plan ID. Planning Trace events similarly hash only
their sequence, event type, known input/output identities, algorithm version, and Evidence. The
Execution Plan ID is derived last from the complete Risk Decision, Snapshot, ordered Planned Order
IDs, Summary, Trace, and effective parameters.

The v1 `ExecutionPlan`/`BrokerRequest` implementation is replaced atomically by the v2
`ExecutionPlan`/`PlannedOrder` contracts in the single EXEC-001–006 migration cohort. Existing
tests and callers migrate in the same ticket series; no dual-read, alias, deprecation proxy, or
compatibility shim is permitted.

## 8. ExecutionPlanningLifecycle

The complete analytical lifecycle is append-only immutable evidence:

```text
PORTFOLIO_DELTA_PROPOSED
  → RISK_APPROVED | RISK_REDUCED | RISK_REJECTED
  → PLAN_CREATED                         (approved/reduced only)
  → SIMULATION_STARTED
  → ORDER_SIMULATED                      (one or more per Planned Order)
  → SIMULATION_COMPLETED
  → PORTFOLIO_TRANSITION_APPLIED
```

```text
ExecutionPlanningLifecycle
  execution_planning_lifecycle_id
  lifecycle_algorithm_version
  root_risk_decision_id
  events                    canonical ExecutionPlanningEvent sequence
  evidence
```

`ExecutionPlanningEvent` contains root Risk Decision ID, event sequence, event type, subject
identity, input identities, output identities, algorithm version, and evidence. It does not
contain the lifecycle ID or an execution timestamp. Each event identity is derived independently;
the lifecycle identity is derived last from the root ID and ordered event IDs/content. Event
ordering is the contiguous sequence. A rejected path terminates at `RISK_REJECTED`.

The complete event schema adds `execution_planning_event_id` as its first field.
`ExecutionPlanningEventType` is exactly `PORTFOLIO_DELTA_PROPOSED`, `RISK_APPROVED`,
`RISK_REDUCED`, `RISK_REJECTED`, `PLAN_CREATED`, `SIMULATION_STARTED`, `ORDER_SIMULATED`,
`SIMULATION_COMPLETED`, and `PORTFOLIO_TRANSITION_APPLIED`. An `ORDER_SIMULATED` event payload
contains one closed `PlannedOrderStatus`; no status is encoded in the event type. Event ID
hashes root Risk Decision ID, sequence, type, subject, input/output IDs, algorithm version, and
Evidence.

## 9. Deterministic simulation

Simulation consumes an Execution Plan plus explicit `SimulationMarketData`:

```text
SimulationMarketData
  simulation_market_data_id
  as_of
  ordered_frames
  evidence

SimulationFrame
  simulation_frame_id
  sequence
  instrument_identity
  bid
  ask
  last
  available_quantity

SimulatedOrderState
  simulated_order_state_id
  simulation_algorithm_version
  planned_order_id
  status
  filled_quantity
  remaining_quantity
  simulated_fill_ids        canonical fill order
  terminal_reason
  evidence

SimulationTraceEvent
  simulation_trace_event_id
  simulation_algorithm_version
  sequence
  event_type
  planned_order_id          optional
  frame_sequence            optional
  input_identities
  output_identities
  evidence

SimulationResult
  simulation_result_id
  simulation_algorithm_version
  execution_plan_id
  market_data_id
  ordered_order_states
  simulated_fills
  unfilled_quantities
  trace
  evidence
```

Each frame has positive bid, ask, and last Monetary Amounts in the Instrument and Portfolio base
currency, `bid <= ask`, and non-negative available quantity on the Instrument quantity increment.
Frames are unique by `(instrument identity, sequence)` and sequences are contiguous per
Instrument. Market data `as_of` and all frames are explicit replay input; no missing frame is
invented. A local immutable-successor liquidity ledger shares each frame's quantity budget across
orders. Orders consume it once in Plan sequence, then frame sequence.

V1 fill semantics are versioned and closed:

- MARKET fills at the first eligible frame: BUY/BUY_TO_COVER at ask and SELL at bid.
- LIMIT BUY/BUY_TO_COVER is eligible when ask is less than or equal to limit and fills at ask;
  LIMIT SELL is eligible when bid is greater than or equal to limit and fills at bid.
- STOP BUY/BUY_TO_COVER triggers when last is greater than or equal to stop; STOP SELL triggers
  when last is less than or equal to stop. Once triggered it follows MARKET semantics.
- STOP_LIMIT uses the same side-specific trigger and then the side-specific LIMIT rule.
- Filled quantity per frame is the lesser of remaining order quantity and explicit available
  quantity.
- DAY considers all supplied frames; an unfilled remainder terminates as
  `SIMULATED_CANCELLED`, or `SIMULATED_PARTIALLY_FILLED` with `DAY_EXPIRED` after a partial fill.
- IOC considers only the first frame for its Instrument. A failed trigger, non-marketable price,
  or zero quantity cancels; a partial fill terminates `SIMULATED_PARTIALLY_FILLED` with
  `IOC_REMAINDER_CANCELLED`.
- FOK considers only the first frame for its Instrument and fills fully only when its trigger and
  price condition pass and the entire quantity is available. Otherwise it is
  `SIMULATED_REJECTED`, creates no fill, and consumes no liquidity.
- GTC considers every supplied frame. It terminates `SIMULATED_FILLED`,
  `SIMULATED_PARTIALLY_FILLED`, or `SIMULATED_ACCEPTED` while retaining explicit remaining
  quantity; it never invents future frames.
- A STOP or STOP_LIMIT trigger frame may also fill under its market or limit rule.
- Orders are evaluated in plan sequence and frames in frame sequence. There is no randomness,
  slippage model, fee model, queue priority, latency, or implicit liquidity in v1.

`SimulatedFill` contains fill identity, Planned Order identity, order-local contiguous fill
sequence, global fill sequence, quantity, price in Portfolio base currency, frame sequence,
resulting status, and field-level evidence. Global fill order is Planned Order sequence then frame
sequence. `unfilled_quantities` is an ordered tuple of `(planned_order_id, remaining_quantity)` in
Plan order. Order-state filled plus remaining quantity equals Planned Order quantity; fill IDs and
state statuses must cohere. Trace events use a closed event enum, contiguous global sequence, and
only already-known input/output identities. `SimulationTraceEventType` is exactly
`SIMULATION_STARTED`, `ORDER_EVALUATED`, `TRIGGER_EVALUATED`, `PRICE_EVALUATED`,
`LIQUIDITY_EVALUATED`, `FILL_CREATED`, `ORDER_TERMINATED`, and `SIMULATION_COMPLETED`.
`SimulationTerminalReason` is exactly `FILLED`, `DAY_EXPIRED`, `IOC_REMAINDER_CANCELLED`,
`FOK_NOT_SATISFIED`, `GTC_FRAMES_EXHAUSTED`, `NO_MARKET_FRAME`, and `NOT_MARKETABLE`.

Simulated Order State ID hashes simulation algorithm version, complete Planned Order ID, status,
filled/remaining quantities, ordered fill IDs, terminal reason, and Evidence. Simulation Trace
Event ID hashes algorithm version, sequence, type, optional order/frame identities, input/output
IDs, and Evidence. It is not a broker Fill and cannot be sent outside Core.

## 10. Replay and identity

Identity namespaces are versioned:

```text
asa.position.v1
asa.portfolio.v1
asa.portfolio_snapshot.v2
asa.instrument_valuation.v1
asa.portfolio_evaluation_result.v1
asa.portfolio_delta.v1
asa.risk_policy.v1
asa.policy_outcome.v1
asa.risk_decision.v1
asa.planned_order.v1
asa.execution_plan.v2
asa.execution_summary.v1
asa.execution_planning_lifecycle.v1
asa.simulation_market_data.v1
asa.simulation_frame.v1
asa.simulation_result.v1
asa.simulated_fill.v1
asa.planning_trace.v1
asa.planning_trace_event.v1
asa.execution_planning_event.v1
asa.simulated_order_state.v1
asa.simulation_trace_event.v1
```

Replay input is the canonical bytes of source Snapshot, Proposed Position, policies, planning
parameters, Execution Plan, and Simulation Market Data. Replay must reproduce exact IDs, deltas,
decisions, planned orders, traces, simulated fills, and next Portfolio Snapshot. No identity
includes evaluated-at time, process time, duration, random seed, object address, environment,
provider payload, or iteration order not explicitly canonicalized.

## 11. Module boundaries

The implementation modules are:

- `portfolio/`: Position/Portfolio state calculation, proposed and realized delta construction,
  and application of simulated fills.
- `risk/`: policy registry, composition, evaluation, decisions, and explanations.
- `execution_planning/`: approved-delta validation, deterministic quantity/order planning,
  summaries, and planning trace.
- `simulation/`: deterministic interpretation of plans against explicit market frames.
- `domain/`: cross-boundary immutable contracts only; no engine or registry behavior.

The pipeline arrows in Section 3 show value flow, not Python import permission. The exact v1 code
import matrix is closed:

| Importing package | May import |
|---|---|
| `position_proposals` | itself, `domain`, `ranking` and its already-authorized lower Intelligence dependencies |
| `portfolio` | itself, `domain` |
| `risk` | itself, `domain` |
| `execution_planning` | itself, `domain` |
| `simulation` | itself, `domain`, pure public functions from `portfolio` |

All other imports between these operational packages are prohibited. Every package is prohibited
from importing providers, observation, backend, presentation, infrastructure, networking,
authentication, persistence, or broker SDKs. In particular, Portfolio does not import Risk,
Planning, or Simulation; Risk does not import Portfolio, Planning, or Simulation; Planning does
not import Portfolio, Risk, or Simulation; and Simulation cannot mutate or reach Portfolio state.

Strategies, Guardrails, and Ranking cannot import portfolio, risk, planning, or simulation.
Optional Strategy Risk Policy is declarative output carried through Proposed Position; Strategy
cannot invoke Risk Engine or inspect Portfolio.

## 12. Migration and ticket sequence

The existing contracts form one connected public path, so EXEC-001 through EXEC-006 are one
atomic migration cohort and one PR. That PR may use six logical commits, but it cannot merge any
ticket independently. It adds Planned Order, Position/Portfolio/Snapshot, Portfolio Delta, Risk,
Planner, Summary/Trace/Lifecycle contracts and simultaneously removes every `BrokerRequest`,
`Holding`, combined `PortfolioDecision`, and v1 caller/test. Its merge gate runs the complete
repository suite and requires Founder review because it activates frozen public contracts.

After that atomic merge, EXEC-007 adds deterministic simulation and Portfolio application,
EXEC-008 adds complete serialization/replay integration, and EXEC-009 adds the full analytical
validation suite. Those later PRs may use delegated merge only when they conform exactly to this
frozen contract. A contract deviation returns to Founder review.

Temporary duplicate names may exist only on the unmerged cohort branch while callers are changed.
No intermediate commit is deployed, published, or merged; `main` always has exactly one canonical
read/write contract set and never exposes dual state or a compatibility shim.

## 13. Acceptance and validation

- identical semantic inputs produce identical Portfolio Delta, Risk Decision, Execution Plan,
  Planned Orders, simulation result, fills, next Snapshot, identities, and traces
- all public outputs are deeply immutable and canonically serializable
- Strategy cannot import or own portfolio/execution concerns
- Portfolio Engine is the sole owner of position/P&L/cash/buying-power calculations
- Strategy policy can only tighten platform policy
- rejected risk produces no plan; approved risk produces at least one planned order
- all four order types and time-in-force values satisfy explicit invariants and simulation rules
- simulation never reads a clock, random source, provider, network, repository, broker, or hidden
  market state
- no Core import graph can reach broker authentication or write operations
- replay reproduces identities and complete provenance exactly
- v1 superseded names are absent after their migration ticket completes
- architecture, constitutional, unit, integration, replay, provenance, lint, typing, integrity,
  and Lean pre-push gates pass

## 14. Alternatives rejected

1. **Keep `BrokerRequest` as the canonical name.** Rejected because it implies operational
   communication and conflicts with the clarified constitutional vocabulary.
2. **Mutate order status in place.** Rejected because replay and identity would depend on hidden
   lifecycle state. Simulation emits new state records.
3. **Let Simulation update Portfolio directly.** Rejected because Portfolio Engine would cease to
   be the single owner of position and P&L calculation.
4. **Use a generic policy expression engine.** Rejected because the sprint has a finite present
   policy set; a generic framework adds unbounded semantics and plugin risk.
5. **Retain v1 and add v2 aliases.** Rejected because dual contracts create ambiguous canonical
   state and violate stable-contract discipline.
6. **Model broker submission behind an interface for future use.** Rejected by GOV-AMD-014. No
   live-capable port belongs in Core.
7. **Use timestamps for lifecycle order or current Portfolio.** Rejected because ordering and
   current-state selection must be explicit and deterministic.

## 15. Consequences and risks

The migration deliberately breaks the current analytical v1 names and combined decision shape.
Founder merge of this document authorizes that bounded contract migration, not live execution.
The largest implementation risk is temporary duplication; ticket boundaries must keep `main` on
one canonical contract at a time. Simulation fidelity is intentionally limited: v1 proves
determinism and lifecycle semantics, not realistic market microstructure or backtest performance.

No deployment, backend API, database, queue, scheduler, broker adapter, credential system, or live
trading capability is authorized.

## 16. Founder decision

Founder merge freezes these public contracts and authorizes EXEC-001 through EXEC-009 under the
revised SPRINT-004 analytical scope. Any change to contract ownership, public fields, simulation
fill semantics, identity inputs, replay guarantees, or constitutional boundary returns to Founder
review. Implementation details that preserve this document may use the sprint delegation.

## References

- GOV-AMD-014: Analytical Execution Boundary
- Constitution Law 5
- ADR-004: Repository Organization
- ADR-008: Operational Trading Contracts
- ADR-009: Execution Semantics and Governance Boundary
- ASA-ARCH-003: Strategy Composition
- ASA-ARCH-005: Financial Domain Contracts
- Issue #103
