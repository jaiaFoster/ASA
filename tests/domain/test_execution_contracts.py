import dataclasses

from domain.execution import (
    ExecutionPlan,
    ExecutionPlanningLifecycle,
    PlannedOrder,
    PlannedOrderStatus,
    PlannedOrderType,
    PlanningTrace,
    PortfolioDelta,
    PortfolioEvaluationResult,
    RiskDecision,
    TimeInForce,
)


def test_arch_006_execution_contracts_are_immutable() -> None:
    for contract in (
        PortfolioDelta, PortfolioEvaluationResult, RiskDecision, PlannedOrder,
        PlanningTrace, ExecutionPlan, ExecutionPlanningLifecycle,
    ):
        assert dataclasses.is_dataclass(contract)
        assert contract.__dataclass_params__.frozen


def test_order_and_lifecycle_enums_are_closed() -> None:
    assert {item.value for item in PlannedOrderType} == {"market", "limit", "stop", "stop_limit"}
    assert {item.value for item in TimeInForce} == {"day", "gtc", "ioc", "fok"}
    assert PlannedOrderStatus.PLANNED.value == "planned"


def test_superseded_execution_contract_names_are_absent() -> None:
    import domain.execution as execution

    for name in ("BrokerRequest", "BrokerRequestSide", "PortfolioDecision", "ExecutionContext"):
        assert not hasattr(execution, name)


def test_planned_order_has_no_parent_plan_id_or_broker_fields() -> None:
    names = {field.name for field in dataclasses.fields(PlannedOrder)}
    assert "execution_plan_id" not in names
    assert "broker" not in " ".join(names)
    assert {"risk_decision_id", "source_snapshot_id", "evidence"} <= names
