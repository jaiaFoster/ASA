"""Pinned analytical Execution Planner parameters."""

from dataclasses import dataclass

from domain.execution import PlannedOrderType, TimeInForce
from execution_planning.errors import InvalidPlanningParameterError

PLANNING_ALGORITHM_VERSION = "v2"
EXECUTION_PLAN_IDENTITY_NAMESPACE = "asa.execution_plan.v2"
PLANNED_ORDER_IDENTITY_NAMESPACE = "asa.planned_order.v1"


@dataclass(frozen=True, slots=True)
class PlanningParameters:
    order_type: PlannedOrderType = PlannedOrderType.MARKET
    time_in_force: TimeInForce = TimeInForce.DAY

    def __post_init__(self) -> None:
        if self.order_type is not PlannedOrderType.MARKET:
            raise InvalidPlanningParameterError("v1 planner emits MARKET orders only")

    def canonical_items(self) -> tuple[tuple[str, str], ...]:
        return (("order_type", self.order_type.value), ("time_in_force", self.time_in_force.value))
