from dataclasses import replace
from datetime import datetime, timezone
from decimal import Decimal

from domain.execution import PlannedOrderStatus, PlannedOrderType, TimeInForce
from domain.operational import MonetaryAmount
from domain.simulation import SimulationFrame, SimulationMarketData, SimulationTerminalReason
from execution_planning.engine import plan_execution
from portfolio.engine import apply_simulation
from simulation.engine import simulate
from tests.execution_planning.helpers import decision, snapshot
from tests.portfolio.helpers import EVIDENCE

AS_OF = datetime(2026, 7, 21, 20, 0, tzinfo=timezone.utc)


def plan():  # type: ignore[no-untyped-def]
    return plan_execution(decision(), snapshot())


def market_data(*, available: Decimal = Decimal("1000"), ask: Decimal = Decimal("101")) -> SimulationMarketData:
    order = plan().planned_orders[0]
    frame = SimulationFrame(
        "frame-1", 1, order.instrument.identity, MonetaryAmount(Decimal("99"), "USD"),
        MonetaryAmount(ask, "USD"), MonetaryAmount(Decimal("100"), "USD"),
        available, EVIDENCE,
    )
    return SimulationMarketData("market-data-1", AS_OF, (frame,), EVIDENCE)


def test_market_order_fills_deterministically_at_ask() -> None:
    execution_plan = plan()
    data = market_data()
    first = simulate(execution_plan, data)
    assert first == simulate(execution_plan, data)
    assert first.simulated_fills[0].price.amount == Decimal("101")
    assert first.ordered_order_states[0].status is PlannedOrderStatus.SIMULATED_FILLED


def test_fok_rejects_without_consuming_partial_liquidity() -> None:
    base = plan()
    order = replace(base.planned_orders[0], time_in_force=TimeInForce.FOK)
    execution_plan = replace(base, planned_orders=(order,))
    result = simulate(execution_plan, market_data(available=Decimal("1")))
    assert result.simulated_fills == ()
    assert result.ordered_order_states[0].terminal_reason is SimulationTerminalReason.FOK_NOT_SATISFIED


def test_limit_not_marketable_expires_without_fill() -> None:
    base = plan()
    order = replace(
        base.planned_orders[0], order_type=PlannedOrderType.LIMIT,
        limit_price=MonetaryAmount(Decimal("90"), "USD"),
    )
    result = simulate(replace(base, planned_orders=(order,)), market_data())
    assert result.simulated_fills == ()
    assert result.ordered_order_states[0].terminal_reason is SimulationTerminalReason.DAY_EXPIRED


def test_frame_liquidity_is_shared_once_across_plan_order_sequence() -> None:
    base = plan()
    first = replace(base.planned_orders[0], quantity=Decimal("3"))
    second = replace(
        first,
        planned_order_id="planned-order-2",
        sequence=2,
        quantity=Decimal("3"),
    )
    execution_plan = replace(
        base,
        planned_orders=(first, second),
        execution_summary=replace(base.execution_summary, order_count=2),
    )
    result = simulate(execution_plan, market_data(available=Decimal("4")))
    assert tuple(fill.quantity for fill in result.simulated_fills) == (Decimal("3"), Decimal("1"))
    assert result.unfilled_quantities == ((first.planned_order_id, Decimal("0")), (second.planned_order_id, Decimal("2")))


def test_portfolio_engine_applies_fills_to_new_immutable_snapshot() -> None:
    execution_plan = plan()
    data = market_data()
    result = simulate(execution_plan, data)
    delta, next_snapshot = apply_simulation(execution_plan, result, data)
    assert next_snapshot.portfolio.revision == execution_plan.source_snapshot.portfolio.revision + 1
    assert next_snapshot.observed_at == AS_OF
    assert next_snapshot.portfolio.positions
    assert delta.target_quantity == result.ordered_order_states[0].filled_quantity
    assert delta.evidence
