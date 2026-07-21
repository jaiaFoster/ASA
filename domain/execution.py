"""Immutable analytical execution contracts frozen by ASA-ARCH-006."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from enum import Enum

from domain.operational import (
    Instrument,
    MonetaryAmount,
    PortfolioSnapshot,
    PositionDirection,
)
from domain.references import EvidenceReference
from domain.values import DomainInvariantError, require_finite_decimal


def _text(value: str, owner: str, field: str) -> None:
    if not value or value != value.strip():
        raise DomainInvariantError(f"{owner}.{field} must be normalized text")


def _evidence(value: tuple[EvidenceReference, ...], owner: str) -> None:
    if not value:
        raise DomainInvariantError(f"{owner}.evidence cannot be empty")


class PortfolioEvaluationDisposition(str, Enum):
    DELTA_PRODUCED = "delta_produced"
    NO_CHANGE = "no_change"


class PortfolioDeltaKind(str, Enum):
    PROPOSED = "proposed"
    APPROVED = "approved"
    SIMULATED = "simulated"


class RiskDecisionState(str, Enum):
    APPROVE = "approve"
    REDUCE = "reduce"
    REJECT = "reject"


class PlannedOrderSide(str, Enum):
    BUY = "buy"
    SELL = "sell"
    BUY_TO_COVER = "buy_to_cover"


class PlannedOrderType(str, Enum):
    MARKET = "market"
    LIMIT = "limit"
    STOP = "stop"
    STOP_LIMIT = "stop_limit"


class TimeInForce(str, Enum):
    DAY = "day"
    GTC = "gtc"
    IOC = "ioc"
    FOK = "fok"


class PlannedOrderStatus(str, Enum):
    PLANNED = "planned"
    SIMULATED_ACCEPTED = "simulated_accepted"
    SIMULATED_PARTIALLY_FILLED = "simulated_partially_filled"
    SIMULATED_FILLED = "simulated_filled"
    SIMULATED_CANCELLED = "simulated_cancelled"
    SIMULATED_REJECTED = "simulated_rejected"


class PlanningTraceEventType(str, Enum):
    PLAN_STARTED = "plan_started"
    DELTA_VALIDATED = "delta_validated"
    RISK_DECISION_VALIDATED = "risk_decision_validated"
    QUANTITY_DERIVED = "quantity_derived"
    ORDER_PLANNED = "order_planned"
    PLAN_COMPLETED = "plan_completed"


class ExecutionPlanningEventType(str, Enum):
    PORTFOLIO_DELTA_PROPOSED = "portfolio_delta_proposed"
    RISK_APPROVED = "risk_approved"
    RISK_REDUCED = "risk_reduced"
    RISK_REJECTED = "risk_rejected"
    PLAN_CREATED = "plan_created"
    SIMULATION_STARTED = "simulation_started"
    ORDER_SIMULATED = "order_simulated"
    SIMULATION_COMPLETED = "simulation_completed"
    PORTFOLIO_TRANSITION_APPLIED = "portfolio_transition_applied"


@dataclass(frozen=True, slots=True)
class PortfolioDelta:
    portfolio_delta_id: str
    delta_version: str
    kind: PortfolioDeltaKind
    source_snapshot_id: str
    source_portfolio_identity: str
    proposed_position_id: str
    predecessor_delta_id: str | None
    account_id: str
    instrument: Instrument
    projected_maximum_loss: MonetaryAmount
    starting_direction: PositionDirection | None
    starting_quantity: Decimal
    target_direction: PositionDirection | None
    target_quantity: Decimal
    cash_change: MonetaryAmount
    buying_power_change: MonetaryAmount
    rationale: tuple[str, ...]
    effective_parameters: tuple[tuple[str, str], ...]
    evidence: tuple[EvidenceReference, ...]

    def __post_init__(self) -> None:
        for field in (
            "portfolio_delta_id", "delta_version", "source_snapshot_id",
            "source_portfolio_identity", "proposed_position_id", "account_id",
        ):
            _text(getattr(self, field), "PortfolioDelta", field)
        for field in ("starting_quantity", "target_quantity"):
            value = getattr(self, field)
            require_finite_decimal(value, "PortfolioDelta", field)
            if value < 0:
                raise DomainInvariantError(f"PortfolioDelta.{field} cannot be negative")
        if (self.target_quantity == 0) != (self.target_direction is None):
            raise DomainInvariantError("zero target and target direction must cohere")
        if self.projected_maximum_loss.amount < 0:
            raise DomainInvariantError("projected maximum loss cannot be negative")
        if self.kind is PortfolioDeltaKind.PROPOSED and self.predecessor_delta_id is not None:
            raise DomainInvariantError("PROPOSED delta cannot have predecessor")
        if self.kind is not PortfolioDeltaKind.PROPOSED and self.predecessor_delta_id is None:
            raise DomainInvariantError("later delta requires predecessor")
        if not self.rationale:
            raise DomainInvariantError("PortfolioDelta.rationale cannot be empty")
        _evidence(self.evidence, "PortfolioDelta")


@dataclass(frozen=True, slots=True)
class PortfolioEvaluationResult:
    portfolio_evaluation_result_id: str
    portfolio_algorithm_version: str
    source_snapshot_id: str
    proposed_position_id: str
    disposition: PortfolioEvaluationDisposition
    proposed_delta: PortfolioDelta | None
    rationale: tuple[str, ...]
    evidence: tuple[EvidenceReference, ...]

    def __post_init__(self) -> None:
        if (self.disposition is PortfolioEvaluationDisposition.DELTA_PRODUCED) != (
            self.proposed_delta is not None
        ):
            raise DomainInvariantError("PortfolioEvaluationResult disposition must match delta")
        _evidence(self.evidence, "PortfolioEvaluationResult")


@dataclass(frozen=True, slots=True)
class PolicyOutcome:
    policy_outcome_id: str
    risk_policy_id: str
    policy_version: str
    consumed_inputs: tuple[tuple[str, str], ...]
    comparison_operator: str
    threshold: str
    observed_value: str
    passed: bool
    reasons: tuple[str, ...]
    evidence: tuple[EvidenceReference, ...]

    def __post_init__(self) -> None:
        if not self.reasons:
            raise DomainInvariantError("PolicyOutcome.reasons cannot be empty")
        _evidence(self.evidence, "PolicyOutcome")


@dataclass(frozen=True, slots=True)
class RiskDecision:
    risk_decision_id: str
    risk_algorithm_version: str
    source_snapshot_id: str
    proposed_delta: PortfolioDelta
    decision: RiskDecisionState
    approved_delta: PortfolioDelta | None
    ordered_policy_outcomes: tuple[PolicyOutcome, ...]
    effective_policy_ids: tuple[str, ...]
    effective_parameters: tuple[tuple[str, str], ...]
    reasons: tuple[str, ...]
    evidence: tuple[EvidenceReference, ...]

    def __post_init__(self) -> None:
        approved = self.decision in {RiskDecisionState.APPROVE, RiskDecisionState.REDUCE}
        if approved != (self.approved_delta is not None):
            raise DomainInvariantError("RiskDecision decision must match approved_delta")
        if self.decision is RiskDecisionState.APPROVE and self.approved_delta is not None and (
            self.approved_delta.target_quantity != self.proposed_delta.target_quantity
        ):
            raise DomainInvariantError("APPROVE must preserve proposed target")
        if not self.ordered_policy_outcomes or not self.reasons:
            raise DomainInvariantError("RiskDecision requires outcomes and reasons")
        _evidence(self.evidence, "RiskDecision")


@dataclass(frozen=True, slots=True)
class PlannedOrder:
    planned_order_id: str
    risk_decision_id: str
    source_snapshot_id: str
    sequence: int
    account_id: str
    instrument: Instrument
    side: PlannedOrderSide
    quantity: Decimal
    order_type: PlannedOrderType
    limit_price: MonetaryAmount | None
    stop_price: MonetaryAmount | None
    price_multiplier: Decimal
    time_in_force: TimeInForce
    initial_status: PlannedOrderStatus
    planning_metadata: tuple[tuple[str, str], ...]
    reasoning: tuple[str, ...]
    evidence: tuple[EvidenceReference, ...]

    def __post_init__(self) -> None:
        if self.sequence <= 0 or self.quantity <= 0 or self.price_multiplier <= 0:
            raise DomainInvariantError("PlannedOrder sequence, quantity, and multiplier must be positive")
        required_limit = self.order_type in {PlannedOrderType.LIMIT, PlannedOrderType.STOP_LIMIT}
        required_stop = self.order_type in {PlannedOrderType.STOP, PlannedOrderType.STOP_LIMIT}
        if required_limit != (self.limit_price is not None) or required_stop != (self.stop_price is not None):
            raise DomainInvariantError("PlannedOrder price fields do not match order type")
        if self.initial_status is not PlannedOrderStatus.PLANNED:
            raise DomainInvariantError("PlannedOrder initial status must be PLANNED")
        if not self.reasoning:
            raise DomainInvariantError("PlannedOrder.reasoning cannot be empty")
        _evidence(self.evidence, "PlannedOrder")


@dataclass(frozen=True, slots=True)
class ExecutionSummary:
    execution_summary_id: str
    target_exposure: MonetaryAmount
    starting_quantity: Decimal
    planned_target_quantity: Decimal
    signed_quantity_change: Decimal
    expected_cash_effect: MonetaryAmount | None
    order_count: int
    reasons: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class PlanningTraceEvent:
    planning_trace_event_id: str
    sequence: int
    event_type: PlanningTraceEventType
    input_identities: tuple[str, ...]
    output_identities: tuple[str, ...]
    algorithm_version: str
    evidence: tuple[EvidenceReference, ...]


@dataclass(frozen=True, slots=True)
class PlanningTrace:
    planning_trace_id: str
    trace_algorithm_version: str
    events: tuple[PlanningTraceEvent, ...]

    def __post_init__(self) -> None:
        if tuple(event.sequence for event in self.events) != tuple(range(1, len(self.events) + 1)):
            raise DomainInvariantError("PlanningTrace sequences must be contiguous")


@dataclass(frozen=True, slots=True)
class ExecutionPlan:
    execution_plan_id: str
    planning_algorithm_version: str
    risk_decision: RiskDecision
    source_snapshot: PortfolioSnapshot
    planned_orders: tuple[PlannedOrder, ...]
    execution_summary: ExecutionSummary
    planning_trace: PlanningTrace
    effective_parameters: tuple[tuple[str, str], ...]
    evidence: tuple[EvidenceReference, ...]

    def __post_init__(self) -> None:
        if self.risk_decision.decision is RiskDecisionState.REJECT:
            raise DomainInvariantError("REJECT cannot produce ExecutionPlan")
        if not self.planned_orders:
            raise DomainInvariantError("ExecutionPlan requires PlannedOrders")
        if tuple(order.sequence for order in self.planned_orders) != tuple(range(1, len(self.planned_orders) + 1)):
            raise DomainInvariantError("PlannedOrder sequences must be contiguous")
        _evidence(self.evidence, "ExecutionPlan")


@dataclass(frozen=True, slots=True)
class ExecutionPlanningEvent:
    execution_planning_event_id: str
    root_risk_decision_id: str
    sequence: int
    event_type: ExecutionPlanningEventType
    subject_identity: str
    input_identities: tuple[str, ...]
    output_identities: tuple[str, ...]
    algorithm_version: str
    evidence: tuple[EvidenceReference, ...]


@dataclass(frozen=True, slots=True)
class ExecutionPlanningLifecycle:
    execution_planning_lifecycle_id: str
    lifecycle_algorithm_version: str
    root_risk_decision_id: str
    events: tuple[ExecutionPlanningEvent, ...]
    evidence: tuple[EvidenceReference, ...]

    def __post_init__(self) -> None:
        if tuple(event.sequence for event in self.events) != tuple(range(1, len(self.events) + 1)):
            raise DomainInvariantError("ExecutionPlanningLifecycle sequences must be contiguous")
        if any(event.root_risk_decision_id != self.root_risk_decision_id for event in self.events):
            raise DomainInvariantError("lifecycle events must share root RiskDecision")
        _evidence(self.evidence, "ExecutionPlanningLifecycle")
