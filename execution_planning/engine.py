"""Pure deterministic Execution Planner (ASA-CORE-010)."""

from __future__ import annotations

import hashlib
from decimal import Decimal, ROUND_FLOOR, localcontext

from domain.canonicalization import serialize_canonical
from domain.execution import (
    BrokerRequest,
    BrokerRequestSide,
    ExecutionContext,
    ExecutionPlan,
    PortfolioDecision,
    PortfolioDecisionState,
)
from domain.operational import PositionDirection
from domain.references import EvidenceReference
from execution_planning.errors import UnplannableDecisionError
from execution_planning.models import (
    BROKER_REQUEST_IDENTITY_NAMESPACE,
    EXECUTION_PLAN_IDENTITY_NAMESPACE,
    PLANNING_ALGORITHM_VERSION,
    PlanningParameters,
)


def _evidence_identity(reference: EvidenceReference) -> tuple[object, ...]:
    return (reference.kind.value, reference.referenced_id, reference.version)


def _reasoning(
    decision: PortfolioDecision,
    context: ExecutionContext,
) -> tuple[EvidenceReference, ...]:
    unique = {
        _evidence_identity(reference): reference
        for reference in decision.evidence + context.valuation_evidence
    }
    return tuple(unique[key] for key in sorted(unique))


def _context_identity_inputs(context: ExecutionContext) -> tuple[object, ...]:
    return (
        context.execution_context_id,
        context.portfolio_snapshot_id,
        context.account_id,
        (context.instrument_identity.scheme, context.instrument_identity.value),
        context.current_direction.value if context.current_direction is not None else None,
        context.current_quantity,
        (context.unit_exposure.amount, context.unit_exposure.currency),
        context.quantity_increment,
        tuple(_evidence_identity(item) for item in context.valuation_evidence),
    )


def _request_identity(
    decision: PortfolioDecision,
    context: ExecutionContext,
    sequence: int,
    side: BrokerRequestSide,
    quantity: Decimal,
    parameters: PlanningParameters,
    reasoning: tuple[EvidenceReference, ...],
) -> str:
    instrument = decision.proposed_position.instrument
    payload = "\n".join(
        (
            BROKER_REQUEST_IDENTITY_NAMESPACE,
            PLANNING_ALGORITHM_VERSION,
            serialize_canonical(decision.portfolio_decision_id),
            serialize_canonical(context.execution_context_id),
            serialize_canonical(sequence),
            serialize_canonical((instrument.identity.scheme, instrument.identity.value)),
            serialize_canonical(context.account_id),
            serialize_canonical(side.value),
            serialize_canonical(quantity),
            serialize_canonical(parameters.order_type.value),
            serialize_canonical(None),
            serialize_canonical(parameters.time_in_force.value),
            serialize_canonical(parameters.canonical_items()),
            serialize_canonical(tuple(_evidence_identity(item) for item in reasoning)),
        )
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _make_request(
    decision: PortfolioDecision,
    context: ExecutionContext,
    sequence: int,
    side: BrokerRequestSide,
    quantity: Decimal,
    parameters: PlanningParameters,
    reasoning: tuple[EvidenceReference, ...],
) -> BrokerRequest:
    return BrokerRequest(
        broker_request_id=_request_identity(
            decision,
            context,
            sequence,
            side,
            quantity,
            parameters,
            reasoning,
        ),
        portfolio_decision_id=decision.portfolio_decision_id,
        sequence=sequence,
        instrument=decision.proposed_position.instrument,
        account_id=context.account_id,
        side=side,
        quantity=quantity,
        order_type=parameters.order_type,
        limit_price=None,
        time_in_force=parameters.time_in_force,
        execution_metadata=parameters.canonical_items(),
        reasoning=reasoning,
    )


def _target_quantity(decision: PortfolioDecision, context: ExecutionContext) -> Decimal:
    reference_capital = dict(decision.proposed_position.effective_parameters)[
        "reference_capital"
    ]
    with localcontext() as decimal_context:
        decimal_context.prec = 40
        raw_quantity = (
            decision.approved_allocation
            * reference_capital
            / context.unit_exposure.amount
        )
        increments = (raw_quantity / context.quantity_increment).to_integral_value(
            rounding=ROUND_FLOOR
        )
        return increments * context.quantity_increment


def _approved_requests(
    decision: PortfolioDecision,
    context: ExecutionContext,
    parameters: PlanningParameters,
    reasoning: tuple[EvidenceReference, ...],
) -> tuple[BrokerRequest, ...]:
    target = _target_quantity(decision, context)
    if target == 0:
        raise UnplannableDecisionError(
            "approved exposure is smaller than one context quantity increment"
        )
    current = context.current_quantity
    if context.current_direction is PositionDirection.SHORT:
        return (
            _make_request(
                decision,
                context,
                1,
                BrokerRequestSide.BUY_TO_COVER,
                current,
                parameters,
                reasoning,
            ),
            _make_request(
                decision,
                context,
                2,
                BrokerRequestSide.BUY,
                target,
                parameters,
                reasoning,
            ),
        )
    current_long = current if context.current_direction is PositionDirection.LONG else Decimal("0")
    delta = target - current_long
    if delta == 0:
        raise UnplannableDecisionError("approved decision produces no portfolio delta")
    side = BrokerRequestSide.BUY if delta > 0 else BrokerRequestSide.SELL
    return (
        _make_request(
            decision,
            context,
            1,
            side,
            abs(delta),
            parameters,
            reasoning,
        ),
    )


def _plan_identity(
    decision: PortfolioDecision,
    context: ExecutionContext,
    requests: tuple[BrokerRequest, ...],
    parameters: PlanningParameters,
    reasoning: tuple[EvidenceReference, ...],
) -> str:
    payload = "\n".join(
        (
            EXECUTION_PLAN_IDENTITY_NAMESPACE,
            PLANNING_ALGORITHM_VERSION,
            serialize_canonical(decision.portfolio_decision_id),
            serialize_canonical(_context_identity_inputs(context)),
            serialize_canonical(parameters.canonical_items()),
            serialize_canonical(tuple(item.broker_request_id for item in requests)),
            serialize_canonical(tuple(_evidence_identity(item) for item in reasoning)),
        )
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def plan_execution(
    decision: PortfolioDecision,
    context: ExecutionContext,
    parameters: PlanningParameters | None = None,
) -> ExecutionPlan:
    """Build one inert broker-neutral plan from complete semantic inputs."""
    active_parameters = parameters or PlanningParameters()
    reasoning = _reasoning(decision, context)
    requests: tuple[BrokerRequest, ...] = ()
    if decision.state in {PortfolioDecisionState.ACCEPT, PortfolioDecisionState.REDUCE}:
        requests = _approved_requests(
            decision,
            context,
            active_parameters,
            reasoning,
        )
    return ExecutionPlan(
        execution_plan_id=_plan_identity(
            decision,
            context,
            requests,
            active_parameters,
            reasoning,
        ),
        planning_algorithm_version=PLANNING_ALGORITHM_VERSION,
        portfolio_decision=decision,
        execution_context=context,
        broker_requests=requests,
        reasoning=reasoning,
    )
