from domain.execution import PlannedOrderSide, PlannedOrderStatus, RiskDecisionState
from execution_planning.engine import build_planning_lifecycle, plan_execution
from tests.execution_planning.helpers import decision, snapshot


def test_approved_risk_decision_produces_inert_plan() -> None:
    risk_decision = decision()
    assert risk_decision.decision is RiskDecisionState.APPROVE
    plan = plan_execution(risk_decision, snapshot())
    assert plan.planned_orders
    assert plan.planned_orders[0].side is PlannedOrderSide.BUY
    assert plan.planned_orders[0].initial_status is PlannedOrderStatus.PLANNED


def test_replay_is_identical() -> None:
    risk_decision = decision()
    source = snapshot()
    assert plan_execution(risk_decision, source) == plan_execution(risk_decision, source)


def test_plan_has_summary_trace_and_complete_provenance() -> None:
    plan = plan_execution(decision(), snapshot())
    assert plan.execution_summary.order_count == len(plan.planned_orders)
    assert plan.planning_trace.events
    assert plan.evidence
    assert all(order.evidence for order in plan.planned_orders)


def test_lifecycle_prefix_is_identified_and_contiguous() -> None:
    risk_decision = decision()
    plan = plan_execution(risk_decision, snapshot())
    lifecycle = build_planning_lifecycle(risk_decision, plan)
    assert lifecycle.execution_planning_lifecycle_id
    assert tuple(event.sequence for event in lifecycle.events) == (1, 2, 3)
