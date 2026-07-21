"""Pinned broker-neutral Execution Planner policy."""

from __future__ import annotations

from dataclasses import dataclass

from domain.execution import OrderType, TimeInForce
from execution_planning.errors import InvalidPlanningParameterError

PLANNING_ALGORITHM_VERSION = "v1"
EXECUTION_PLAN_IDENTITY_NAMESPACE = "asa.execution_plan"
BROKER_REQUEST_IDENTITY_NAMESPACE = "asa.broker_request"
QUANTITY_ROUNDING_POLICY = "floor_to_increment"


@dataclass(frozen=True, slots=True)
class PlanningParameters:
    """Complete v1 planning policy with no hidden runtime defaults."""

    order_type: OrderType = OrderType.MARKET
    time_in_force: TimeInForce = TimeInForce.DAY
    quantity_rounding: str = QUANTITY_ROUNDING_POLICY

    def __post_init__(self) -> None:
        if self.order_type is not OrderType.MARKET:
            raise InvalidPlanningParameterError("v1 supports MARKET planning only")
        if self.time_in_force is not TimeInForce.DAY:
            raise InvalidPlanningParameterError("v1 supports DAY time in force only")
        if self.quantity_rounding != QUANTITY_ROUNDING_POLICY:
            raise InvalidPlanningParameterError("v1 quantity rounding policy is pinned")

    def canonical_items(self) -> tuple[tuple[str, str], ...]:
        return (
            ("order_type", self.order_type.value),
            ("quantity_rounding", self.quantity_rounding),
            ("time_in_force", self.time_in_force.value),
        )
