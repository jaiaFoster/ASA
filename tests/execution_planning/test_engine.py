"""ASA-CORE-010 deterministic Execution Planner tests."""

from __future__ import annotations

import dataclasses
from decimal import Decimal

import pytest

from domain.execution import (
    BrokerRequestSide,
    OrderType,
    PortfolioDecisionState,
    TimeInForce,
)
from domain.operational import PositionDirection
from execution_planning.engine import plan_execution
from execution_planning.errors import InvalidPlanningParameterError, UnplannableDecisionError
from execution_planning.models import PLANNING_ALGORITHM_VERSION, PlanningParameters
from tests.execution_planning.helpers import context, decision, plan


def test_flat_position_produces_one_buy_request() -> None:
    result = plan()
    assert len(result.broker_requests) == 1
    request = result.broker_requests[0]
    assert request.side is BrokerRequestSide.BUY
    assert request.quantity == Decimal("41")
    assert request.sequence == 1


def test_existing_long_position_produces_buy_delta() -> None:
    result = plan_execution(
        decision(),
        context(
            current_direction=PositionDirection.LONG,
            current_quantity=Decimal("20"),
        ),
    )
    assert result.broker_requests[0].side is BrokerRequestSide.BUY
    assert result.broker_requests[0].quantity == Decimal("21")


def test_existing_long_position_above_target_produces_sell_delta() -> None:
    result = plan_execution(
        decision(),
        context(
            current_direction=PositionDirection.LONG,
            current_quantity=Decimal("50"),
        ),
    )
    assert result.broker_requests[0].side is BrokerRequestSide.SELL
    assert result.broker_requests[0].quantity == Decimal("9")


def test_short_position_is_covered_before_long_target_is_bought() -> None:
    result = plan_execution(
        decision(),
        context(
            current_direction=PositionDirection.SHORT,
            current_quantity=Decimal("10"),
        ),
    )
    assert tuple(item.side for item in result.broker_requests) == (
        BrokerRequestSide.BUY_TO_COVER,
        BrokerRequestSide.BUY,
    )
    assert tuple(item.quantity for item in result.broker_requests) == (
        Decimal("10"),
        Decimal("41"),
    )
    assert tuple(item.sequence for item in result.broker_requests) == (1, 2)


@pytest.mark.parametrize(
    "state",
    [PortfolioDecisionState.REJECT, PortfolioDecisionState.HOLD],
)
def test_reject_and_hold_produce_inert_plans(state: PortfolioDecisionState) -> None:
    inactive = dataclasses.replace(
        decision(),
        state=state,
        approved_allocation=Decimal("0"),
    )
    result = plan_execution(inactive, context())
    assert result.broker_requests == ()


def test_quantity_is_rounded_down_to_context_increment() -> None:
    result = plan_execution(
        decision(),
        context(unit_exposure=Decimal("333"), quantity_increment=Decimal("2")),
    )
    assert result.broker_requests[0].quantity == Decimal("24")


def test_sub_increment_exposure_is_explicitly_unplannable() -> None:
    with pytest.raises(UnplannableDecisionError, match="smaller than one"):
        plan_execution(decision(), context(quantity_increment=Decimal("100")))


def test_approved_decision_with_no_delta_is_explicitly_unplannable() -> None:
    with pytest.raises(UnplannableDecisionError, match="no portfolio delta"):
        plan_execution(
            decision(),
            context(
                current_direction=PositionDirection.LONG,
                current_quantity=Decimal("41"),
            ),
        )


def test_v1_requests_are_inert_market_day_templates() -> None:
    request = plan().broker_requests[0]
    assert request.order_type is OrderType.MARKET
    assert request.limit_price is None
    assert request.time_in_force is TimeInForce.DAY
    assert request.execution_metadata == PlanningParameters().canonical_items()


def test_replay_identity_and_order_are_stable() -> None:
    first = plan_execution(decision(), context())
    second = plan_execution(decision(), context())
    assert first == second
    assert first.execution_plan_id == second.execution_plan_id
    assert tuple(item.broker_request_id for item in first.broker_requests) == tuple(
        item.broker_request_id for item in second.broker_requests
    )


def test_context_change_changes_plan_and_request_identity() -> None:
    first = plan_execution(decision(), context())
    second = plan_execution(decision(), context(unit_exposure=Decimal("201")))
    assert first.execution_plan_id != second.execution_plan_id
    assert first.broker_requests[0].broker_request_id != second.broker_requests[0].broker_request_id


def test_plan_records_complete_context_and_reasoning() -> None:
    result = plan()
    assert result.execution_context == context()
    assert result.reasoning
    assert result.broker_requests[0].reasoning == result.reasoning
    assert result.planning_algorithm_version == PLANNING_ALGORITHM_VERSION == "v1"


def test_output_is_deeply_immutable() -> None:
    result = plan()
    with pytest.raises(dataclasses.FrozenInstanceError):
        result.broker_requests = ()
    with pytest.raises(dataclasses.FrozenInstanceError):
        result.broker_requests[0].quantity = Decimal("1")


@pytest.mark.parametrize(
    "changes",
    [
        {"order_type": OrderType.LIMIT},
        {"time_in_force": TimeInForce.GOOD_TIL_CANCELLED},
        {"quantity_rounding": "nearest"},
    ],
)
def test_v1_planning_policy_rejects_unpinned_values(changes: dict[str, object]) -> None:
    with pytest.raises(InvalidPlanningParameterError):
        dataclasses.replace(PlanningParameters(), **changes)


def test_v1_identity_regression_vector() -> None:
    result = plan()
    assert result.execution_plan_id == (
        "df5c549b5857067547ab32befbc372a2ac68882ede1480dd1c79215d4bf8e5a3"
    )
    assert result.broker_requests[0].broker_request_id == (
        "24ec28a0bd3d3094b1ea244c2e48bc8777b7af79ab9918f7917060383e78e63c"
    )
