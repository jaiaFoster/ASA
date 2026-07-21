"""Pure deterministic analytical Execution Planning Engine."""

from __future__ import annotations

import hashlib
from decimal import Decimal

from domain.canonicalization import serialize_canonical
from domain.execution import (
    ExecutionPlanningEvent,
    ExecutionPlanningEventType,
    ExecutionPlanningLifecycle,
    ExecutionPlan,
    ExecutionSummary,
    PlannedOrder,
    PlannedOrderSide,
    PlannedOrderStatus,
    PlanningTrace,
    PlanningTraceEvent,
    PlanningTraceEventType,
    RiskDecision,
    RiskDecisionState,
)
from domain.operational import MonetaryAmount, PortfolioSnapshot, PositionDirection
from domain.references import EvidenceReference
from execution_planning.errors import UnplannableDecisionError
from execution_planning.models import (
    EXECUTION_PLAN_IDENTITY_NAMESPACE,
    PLANNED_ORDER_IDENTITY_NAMESPACE,
    PLANNING_ALGORITHM_VERSION,
    PlanningParameters,
)


def _key(item: EvidenceReference) -> tuple[object, ...]:
    return item.kind.value, item.referenced_id, item.version


def _id(namespace: str, *values: object) -> str:
    payload = "\n".join((namespace, *(serialize_canonical(value) for value in values)))
    return hashlib.sha256(payload.encode()).hexdigest()


def _order(
    decision: RiskDecision,
    snapshot: PortfolioSnapshot,
    sequence: int,
    side: PlannedOrderSide,
    quantity: Decimal,
    multiplier: Decimal,
    parameters: PlanningParameters,
) -> PlannedOrder:
    delta = decision.approved_delta
    if delta is None:
        raise UnplannableDecisionError("approved delta is required")
    metadata = parameters.canonical_items()
    reasoning = ("ordered portfolio transition from approved RiskDecision",)
    values = (
        decision.risk_decision_id, snapshot.portfolio_snapshot_id, sequence,
        delta.instrument.identity.scheme, delta.instrument.identity.value,
        side.value, quantity, multiplier, metadata, tuple(_key(item) for item in decision.evidence),
    )
    return PlannedOrder(
        _id(PLANNED_ORDER_IDENTITY_NAMESPACE, values), decision.risk_decision_id,
        snapshot.portfolio_snapshot_id, sequence, snapshot.portfolio.account_id,
        delta.instrument, side, quantity, parameters.order_type, None, None, multiplier,
        parameters.time_in_force, PlannedOrderStatus.PLANNED, metadata, reasoning, decision.evidence,
    )


def _orders(decision: RiskDecision, snapshot: PortfolioSnapshot, parameters: PlanningParameters) -> tuple[PlannedOrder, ...]:
    delta = decision.approved_delta
    if delta is None:
        raise UnplannableDecisionError("REJECT cannot be planned")
    values = tuple(
        item for item in snapshot.instrument_valuations
        if item.instrument.identity == delta.instrument.identity
    )
    if len(values) != 1:
        raise UnplannableDecisionError("planning requires one InstrumentValuation")
    multiplier = values[0].price_multiplier
    current = delta.starting_quantity
    target = delta.target_quantity
    if delta.starting_direction is PositionDirection.SHORT:
        orders = [_order(decision, snapshot, 1, PlannedOrderSide.BUY_TO_COVER, current, multiplier, parameters)]
        if target:
            orders.append(_order(decision, snapshot, 2, PlannedOrderSide.BUY, target, multiplier, parameters))
        return tuple(orders)
    difference = target - current
    if difference == 0:
        raise UnplannableDecisionError("approved decision has no quantity change")
    side = PlannedOrderSide.BUY if difference > 0 else PlannedOrderSide.SELL
    return (_order(decision, snapshot, 1, side, abs(difference), multiplier, parameters),)


def _trace(decision: RiskDecision, orders: tuple[PlannedOrder, ...]) -> PlanningTrace:
    types = (
        PlanningTraceEventType.PLAN_STARTED,
        PlanningTraceEventType.DELTA_VALIDATED,
        PlanningTraceEventType.RISK_DECISION_VALIDATED,
        PlanningTraceEventType.QUANTITY_DERIVED,
        *(PlanningTraceEventType.ORDER_PLANNED for _ in orders),
        PlanningTraceEventType.PLAN_COMPLETED,
    )
    events = tuple(
        PlanningTraceEvent(
            _id("asa.planning_trace_event.v1", decision.risk_decision_id, sequence, event_type.value),
            sequence, event_type, (decision.risk_decision_id,),
            tuple(order.planned_order_id for order in orders) if event_type is PlanningTraceEventType.PLAN_COMPLETED else (),
            PLANNING_ALGORITHM_VERSION, decision.evidence,
        )
        for sequence, event_type in enumerate(types, 1)
    )
    return PlanningTrace(
        _id("asa.planning_trace.v1", PLANNING_ALGORITHM_VERSION, tuple(item.planning_trace_event_id for item in events)),
        PLANNING_ALGORITHM_VERSION, events,
    )


def plan_execution(
    decision: RiskDecision,
    snapshot: PortfolioSnapshot,
    parameters: PlanningParameters | None = None,
) -> ExecutionPlan:
    if decision.decision is RiskDecisionState.REJECT:
        raise UnplannableDecisionError("REJECT produces no ExecutionPlan")
    active = parameters or PlanningParameters()
    orders = _orders(decision, snapshot, active)
    delta = decision.approved_delta
    assert delta is not None
    valuation = next(
        item for item in snapshot.instrument_valuations
        if item.instrument.identity == delta.instrument.identity
    )
    target_exposure = MonetaryAmount(
        delta.target_quantity * valuation.unit_exposure.amount,
        snapshot.portfolio.base_currency,
    )
    summary_values = (delta.portfolio_delta_id, target_exposure.amount, delta.starting_quantity, delta.target_quantity, len(orders))
    summary = ExecutionSummary(
        _id("asa.execution_summary.v1", summary_values), target_exposure,
        delta.starting_quantity, delta.target_quantity,
        delta.target_quantity - delta.starting_quantity, None, len(orders), decision.reasons,
    )
    trace = _trace(decision, orders)
    values = (
        decision.risk_decision_id, snapshot.portfolio_snapshot_id,
        tuple(order.planned_order_id for order in orders), summary.execution_summary_id,
        trace.planning_trace_id, active.canonical_items(), tuple(_key(item) for item in decision.evidence),
    )
    return ExecutionPlan(
        _id(EXECUTION_PLAN_IDENTITY_NAMESPACE, values), PLANNING_ALGORITHM_VERSION,
        decision, snapshot, orders, summary, trace, active.canonical_items(), decision.evidence,
    )


def build_planning_lifecycle(
    decision: RiskDecision,
    plan: ExecutionPlan | None,
) -> ExecutionPlanningLifecycle:
    """Build the immutable pre-simulation lifecycle prefix."""
    risk_type = {
        RiskDecisionState.APPROVE: ExecutionPlanningEventType.RISK_APPROVED,
        RiskDecisionState.REDUCE: ExecutionPlanningEventType.RISK_REDUCED,
        RiskDecisionState.REJECT: ExecutionPlanningEventType.RISK_REJECTED,
    }[decision.decision]
    event_specs: list[tuple[ExecutionPlanningEventType, str, tuple[str, ...], tuple[str, ...]]] = [
        (
            ExecutionPlanningEventType.PORTFOLIO_DELTA_PROPOSED,
            decision.proposed_delta.portfolio_delta_id,
            (decision.proposed_delta.source_snapshot_id,),
            (decision.proposed_delta.portfolio_delta_id,),
        ),
        (
            risk_type,
            decision.risk_decision_id,
            (decision.proposed_delta.portfolio_delta_id,),
            (decision.risk_decision_id,),
        ),
    ]
    if plan is not None:
        if decision.decision is RiskDecisionState.REJECT:
            raise UnplannableDecisionError("rejected lifecycle cannot contain plan")
        event_specs.append((
            ExecutionPlanningEventType.PLAN_CREATED,
            plan.execution_plan_id,
            (decision.risk_decision_id,),
            (plan.execution_plan_id,),
        ))
    events = tuple(
        ExecutionPlanningEvent(
            _id("asa.execution_planning_event.v1", decision.risk_decision_id, sequence, event_type.value, subject),
            decision.risk_decision_id, sequence, event_type, subject, inputs, outputs,
            PLANNING_ALGORITHM_VERSION, decision.evidence,
        )
        for sequence, (event_type, subject, inputs, outputs) in enumerate(event_specs, 1)
    )
    lifecycle_id = _id(
        "asa.execution_planning_lifecycle.v1",
        PLANNING_ALGORITHM_VERSION,
        decision.risk_decision_id,
        tuple(event.execution_planning_event_id for event in events),
    )
    return ExecutionPlanningLifecycle(
        lifecycle_id, PLANNING_ALGORITHM_VERSION, decision.risk_decision_id,
        events, decision.evidence,
    )
