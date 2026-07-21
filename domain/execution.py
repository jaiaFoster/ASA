"""Immutable analytical execution contracts (ASA-ARCH-002).

These records describe decisions and hypothetical broker-neutral actions.
They perform no policy, planning, persistence, networking, or broker work.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from enum import Enum

from domain.operational import (
    CanonicalInstrumentIdentity,
    Instrument,
    MonetaryAmount,
    PositionDirection,
    ProposedPosition,
)
from domain.references import EvidenceReference
from domain.values import DomainInvariantError, require_finite_decimal, require_positive


def _require_text(value: str, owner: str, field_name: str) -> None:
    if not value or value != value.strip():
        raise DomainInvariantError(f"{owner}.{field_name} must be non-empty normalized text")


def _require_non_negative(value: Decimal, owner: str, field_name: str) -> None:
    require_finite_decimal(value, owner, field_name)
    if value < 0:
        raise DomainInvariantError(f"{owner}.{field_name} cannot be negative")


def _require_unique_keys(
    values: tuple[tuple[str, object], ...], owner: str, field_name: str
) -> None:
    keys = tuple(key for key, _ in values)
    if any(not key or key != key.strip() for key in keys):
        raise DomainInvariantError(f"{owner}.{field_name} keys must be normalized text")
    if len(keys) != len(set(keys)):
        raise DomainInvariantError(f"{owner}.{field_name} keys must be unique")
    if keys != tuple(sorted(keys)):
        raise DomainInvariantError(f"{owner}.{field_name} keys must be in canonical order")


class PortfolioDecisionState(str, Enum):
    """Possible deterministic portfolio-policy outcomes for one proposal."""

    ACCEPT = "accept"
    REJECT = "reject"
    REDUCE = "reduce"
    HOLD = "hold"


class BrokerRequestSide(str, Enum):
    """Broker-neutral effect of one analytical request."""

    BUY = "buy"
    SELL = "sell"
    SELL_SHORT = "sell_short"
    BUY_TO_COVER = "buy_to_cover"


class OrderType(str, Enum):
    """Order shape described analytically; not an external broker command."""

    MARKET = "market"
    LIMIT = "limit"


class TimeInForce(str, Enum):
    """Broker-neutral lifetime requested by an analytical order template."""

    DAY = "day"
    GOOD_TIL_CANCELLED = "good_til_cancelled"


@dataclass(frozen=True, slots=True)
class PortfolioDecision:
    """Portfolio-policy result for one immutable ProposedPosition.

    ``approved_allocation`` describes how much of the desired allocation
    survives portfolio constraints. It is a policy output supplied to this
    contract, never a value calculated by it.
    """

    portfolio_decision_id: str
    decision_algorithm_version: str
    portfolio_snapshot_id: str
    proposed_position: ProposedPosition
    state: PortfolioDecisionState
    approved_allocation: Decimal
    policy_versions: tuple[tuple[str, str], ...]
    effective_parameters: tuple[tuple[str, Decimal], ...]
    reasons: tuple[str, ...]
    evidence: tuple[EvidenceReference, ...]

    def __post_init__(self) -> None:
        for field_name in (
            "portfolio_decision_id",
            "decision_algorithm_version",
            "portfolio_snapshot_id",
        ):
            _require_text(getattr(self, field_name), "PortfolioDecision", field_name)
        _require_non_negative(self.approved_allocation, "PortfolioDecision", "approved_allocation")
        if self.approved_allocation > self.proposed_position.target_allocation:
            raise DomainInvariantError(
                "PortfolioDecision approved_allocation cannot exceed proposed allocation"
            )
        if self.state in {PortfolioDecisionState.REJECT, PortfolioDecisionState.HOLD} and (
            self.approved_allocation != 0
        ):
            raise DomainInvariantError("REJECT and HOLD decisions cannot approve new exposure")
        if self.state is PortfolioDecisionState.ACCEPT and (
            self.approved_allocation != self.proposed_position.target_allocation
        ):
            raise DomainInvariantError("ACCEPT must preserve the complete proposed exposure")
        if self.state is PortfolioDecisionState.REDUCE and not (
            0 < self.approved_allocation < self.proposed_position.target_allocation
        ):
            raise DomainInvariantError("REDUCE must approve a smaller positive exposure")
        _require_unique_keys(self.policy_versions, "PortfolioDecision", "policy_versions")
        _require_unique_keys(
            self.effective_parameters, "PortfolioDecision", "effective_parameters"
        )
        for _, value in self.effective_parameters:
            require_finite_decimal(value, "PortfolioDecision", "effective_parameters value")
        if not self.policy_versions:
            raise DomainInvariantError("PortfolioDecision.policy_versions cannot be empty")
        if not self.reasons:
            raise DomainInvariantError("PortfolioDecision.reasons cannot be empty")
        if any(not reason or reason != reason.strip() for reason in self.reasons):
            raise DomainInvariantError("PortfolioDecision.reasons must be normalized text")
        if not self.evidence:
            raise DomainInvariantError("PortfolioDecision.evidence cannot be empty")


@dataclass(frozen=True, slots=True)
class ExecutionContext:
    """Canonical provider-neutral state required to plan one decision.

    ``unit_exposure`` is the portfolio-base-currency exposure represented by
    one quantity unit. It already incorporates instrument-specific valuation
    semantics such as contract multipliers; the planner never derives those
    semantics from symbols or provider data.
    """

    execution_context_id: str
    portfolio_snapshot_id: str
    account_id: str
    instrument_identity: CanonicalInstrumentIdentity
    current_direction: PositionDirection | None
    current_quantity: Decimal
    unit_exposure: MonetaryAmount
    quantity_increment: Decimal
    valuation_evidence: tuple[EvidenceReference, ...]

    def __post_init__(self) -> None:
        for field_name in (
            "execution_context_id",
            "portfolio_snapshot_id",
            "account_id",
        ):
            _require_text(getattr(self, field_name), "ExecutionContext", field_name)
        _require_non_negative(self.current_quantity, "ExecutionContext", "current_quantity")
        _require_non_negative(
            self.unit_exposure.amount,
            "ExecutionContext",
            "unit_exposure.amount",
        )
        _require_non_negative(
            self.quantity_increment,
            "ExecutionContext",
            "quantity_increment",
        )
        if self.unit_exposure.amount == 0:
            raise DomainInvariantError("ExecutionContext.unit_exposure.amount must be positive")
        if self.quantity_increment == 0:
            raise DomainInvariantError("ExecutionContext.quantity_increment must be positive")
        if self.current_quantity % self.quantity_increment != 0:
            raise DomainInvariantError(
                "ExecutionContext.current_quantity must use quantity_increment"
            )
        if self.current_quantity == 0 and self.current_direction is not None:
            raise DomainInvariantError("flat ExecutionContext cannot have current_direction")
        if self.current_quantity > 0 and self.current_direction is None:
            raise DomainInvariantError("non-flat ExecutionContext requires current_direction")
        if not self.valuation_evidence:
            raise DomainInvariantError("ExecutionContext.valuation_evidence cannot be empty")


@dataclass(frozen=True, slots=True)
class BrokerRequest:
    """Last analytical domain object before the future adapter boundary.

    This is an immutable broker-neutral order template, not an API request.
    It contains no endpoint, credentials, session, provider payload, or I/O.
    """

    broker_request_id: str
    portfolio_decision_id: str
    sequence: int
    instrument: Instrument
    account_id: str
    side: BrokerRequestSide
    quantity: Decimal
    order_type: OrderType
    limit_price: MonetaryAmount | None
    time_in_force: TimeInForce
    execution_metadata: tuple[tuple[str, str], ...]
    reasoning: tuple[EvidenceReference, ...]

    def __post_init__(self) -> None:
        for field_name in ("broker_request_id", "portfolio_decision_id", "account_id"):
            _require_text(getattr(self, field_name), "BrokerRequest", field_name)
        require_positive(self.sequence, "BrokerRequest", "sequence")
        _require_non_negative(self.quantity, "BrokerRequest", "quantity")
        if self.quantity == 0:
            raise DomainInvariantError("BrokerRequest.quantity must be greater than zero")
        if self.order_type is OrderType.LIMIT and self.limit_price is None:
            raise DomainInvariantError("LIMIT BrokerRequest requires limit_price")
        if self.order_type is OrderType.MARKET and self.limit_price is not None:
            raise DomainInvariantError("MARKET BrokerRequest cannot contain limit_price")
        if self.limit_price is not None:
            _require_non_negative(self.limit_price.amount, "BrokerRequest", "limit_price.amount")
            if self.limit_price.amount == 0:
                raise DomainInvariantError("BrokerRequest.limit_price must be greater than zero")
            if self.limit_price.currency != self.instrument.currency:
                raise DomainInvariantError(
                    "BrokerRequest.limit_price currency must match instrument currency"
                )
        _require_unique_keys(self.execution_metadata, "BrokerRequest", "execution_metadata")
        if not self.reasoning:
            raise DomainInvariantError("BrokerRequest.reasoning cannot be empty")


@dataclass(frozen=True, slots=True)
class ExecutionPlan:
    """Deterministic ordered decomposition of one PortfolioDecision.

    ``broker_requests`` are analytical templates.  Iterating over this tuple
    has no side effect and no adapter is reachable from this contract.
    """

    execution_plan_id: str
    planning_algorithm_version: str
    portfolio_decision: PortfolioDecision
    execution_context: ExecutionContext
    broker_requests: tuple[BrokerRequest, ...]
    reasoning: tuple[EvidenceReference, ...]

    def __post_init__(self) -> None:
        _require_text(self.execution_plan_id, "ExecutionPlan", "execution_plan_id")
        _require_text(
            self.planning_algorithm_version,
            "ExecutionPlan",
            "planning_algorithm_version",
        )
        if (
            self.execution_context.portfolio_snapshot_id
            != self.portfolio_decision.portfolio_snapshot_id
        ):
            raise DomainInvariantError(
                "ExecutionPlan context must reference its PortfolioDecision snapshot"
            )
        if (
            self.execution_context.instrument_identity
            != self.portfolio_decision.proposed_position.instrument.identity
        ):
            raise DomainInvariantError(
                "ExecutionPlan context instrument must match its PortfolioDecision"
            )
        if (
            self.execution_context.unit_exposure.currency
            != self.portfolio_decision.proposed_position.instrument.currency
        ):
            raise DomainInvariantError(
                "ExecutionPlan context currency must match its PortfolioDecision instrument"
            )
        request_ids = tuple(request.broker_request_id for request in self.broker_requests)
        if len(request_ids) != len(set(request_ids)):
            raise DomainInvariantError("ExecutionPlan contains duplicate broker_request_id values")
        expected_sequences = tuple(range(1, len(self.broker_requests) + 1))
        actual_sequences = tuple(request.sequence for request in self.broker_requests)
        if actual_sequences != expected_sequences:
            raise DomainInvariantError("ExecutionPlan request sequences must be contiguous")
        if any(
            request.portfolio_decision_id
            != self.portfolio_decision.portfolio_decision_id
            for request in self.broker_requests
        ):
            raise DomainInvariantError(
                "ExecutionPlan requests must reference its PortfolioDecision"
            )
        if any(
            request.account_id != self.execution_context.account_id
            for request in self.broker_requests
        ):
            raise DomainInvariantError("ExecutionPlan requests must use its context account")
        if any(
            request.instrument.identity != self.execution_context.instrument_identity
            for request in self.broker_requests
        ):
            raise DomainInvariantError("ExecutionPlan requests must use its context instrument")
        if any(
            request.quantity % self.execution_context.quantity_increment != 0
            for request in self.broker_requests
        ):
            raise DomainInvariantError(
                "ExecutionPlan request quantities must use the context quantity increment"
            )
        if self.portfolio_decision.state in {
            PortfolioDecisionState.REJECT,
            PortfolioDecisionState.HOLD,
        } and self.broker_requests:
            raise DomainInvariantError("REJECT and HOLD decisions cannot produce BrokerRequests")
        if self.portfolio_decision.state in {
            PortfolioDecisionState.ACCEPT,
            PortfolioDecisionState.REDUCE,
        } and not self.broker_requests:
            raise DomainInvariantError("approved decisions require at least one BrokerRequest")
        if not self.reasoning:
            raise DomainInvariantError("ExecutionPlan.reasoning cannot be empty")
