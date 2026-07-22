"""Pure deterministic interpretation of Execution Plans against explicit frames."""

from __future__ import annotations

import hashlib
from decimal import Decimal

from domain.canonicalization import serialize_canonical
from domain.execution import (
    ExecutionPlan,
    PlannedOrder,
    PlannedOrderSide,
    PlannedOrderStatus,
    PlannedOrderType,
    TimeInForce,
)
from domain.references import EvidenceReference
from domain.simulation import (
    SimulatedFill,
    SimulatedOrderState,
    SimulationFrame,
    SimulationMarketData,
    SimulationResult,
    SimulationTerminalReason,
    SimulationTraceEvent,
    SimulationTraceEventType,
)
from simulation.models import SIMULATION_ALGORITHM_VERSION


def _key(item: EvidenceReference) -> tuple[object, ...]:
    return item.kind.value, item.referenced_id, item.version


def _id(namespace: str, *values: object) -> str:
    payload = "\n".join((namespace, *(serialize_canonical(value) for value in values)))
    return hashlib.sha256(payload.encode()).hexdigest()


def _evidence(*groups: tuple[EvidenceReference, ...]) -> tuple[EvidenceReference, ...]:
    unique = {_key(item): item for group in groups for item in group}
    return tuple(unique[key] for key in sorted(unique))


def _price(order: PlannedOrder, frame: SimulationFrame, triggered: bool) -> tuple[Decimal | None, bool]:
    buy = order.side in {PlannedOrderSide.BUY, PlannedOrderSide.BUY_TO_COVER}
    if order.order_type in {PlannedOrderType.STOP, PlannedOrderType.STOP_LIMIT} and not triggered:
        stop = order.stop_price
        assert stop is not None
        triggered = frame.last.amount >= stop.amount if buy else frame.last.amount <= stop.amount
        if not triggered:
            return None, False
    if order.order_type in {PlannedOrderType.MARKET, PlannedOrderType.STOP}:
        return (frame.ask.amount if buy else frame.bid.amount), triggered
    limit = order.limit_price
    assert limit is not None
    marketable = frame.ask.amount <= limit.amount if buy else frame.bid.amount >= limit.amount
    return ((frame.ask.amount if buy else frame.bid.amount) if marketable else None), triggered


def _terminal(
    order: PlannedOrder,
    filled: Decimal,
    had_frames: bool,
) -> tuple[PlannedOrderStatus, SimulationTerminalReason]:
    if filled == order.quantity:
        return PlannedOrderStatus.SIMULATED_FILLED, SimulationTerminalReason.FILLED
    if order.time_in_force is TimeInForce.FOK:
        return PlannedOrderStatus.SIMULATED_REJECTED, SimulationTerminalReason.FOK_NOT_SATISFIED
    if order.time_in_force is TimeInForce.IOC:
        status = PlannedOrderStatus.SIMULATED_PARTIALLY_FILLED if filled else PlannedOrderStatus.SIMULATED_CANCELLED
        return status, SimulationTerminalReason.IOC_REMAINDER_CANCELLED
    if order.time_in_force is TimeInForce.GTC:
        status = PlannedOrderStatus.SIMULATED_PARTIALLY_FILLED if filled else PlannedOrderStatus.SIMULATED_ACCEPTED
        reason = SimulationTerminalReason.GTC_FRAMES_EXHAUSTED if had_frames else SimulationTerminalReason.NO_MARKET_FRAME
        return status, reason
    status = PlannedOrderStatus.SIMULATED_PARTIALLY_FILLED if filled else PlannedOrderStatus.SIMULATED_CANCELLED
    reason = SimulationTerminalReason.DAY_EXPIRED if had_frames else SimulationTerminalReason.NO_MARKET_FRAME
    return status, reason


def simulate(plan: ExecutionPlan, market_data: SimulationMarketData) -> SimulationResult:
    """Simulate all orders with a shared per-frame liquidity ledger."""
    if market_data.as_of < plan.source_snapshot.observed_at:
        raise ValueError("SimulationMarketData cannot precede source PortfolioSnapshot")
    valuations = {
        item.instrument.identity: item for item in plan.source_snapshot.instrument_valuations
    }
    for frame in market_data.ordered_frames:
        valuation = valuations.get(frame.instrument_identity)
        if valuation is None:
            raise ValueError("Simulation frame has no source InstrumentValuation")
        if frame.available_quantity % valuation.quantity_increment:
            raise ValueError("Simulation liquidity must use Instrument quantity increment")
        if frame.bid.currency != plan.source_snapshot.portfolio.base_currency:
            raise ValueError("Simulation frame must use Portfolio base currency")
    frame_by_order = {
        order.planned_order_id: tuple(
            frame for frame in market_data.ordered_frames
            if frame.instrument_identity == order.instrument.identity
        )
        for order in plan.planned_orders
    }
    liquidity = {frame.simulation_frame_id: frame.available_quantity for frame in market_data.ordered_frames}
    fills: list[SimulatedFill] = []
    states: list[SimulatedOrderState] = []
    trace_specs: list[tuple[SimulationTraceEventType, str | None, int | None, tuple[str, ...]]] = [
        (SimulationTraceEventType.SIMULATION_STARTED, None, None, (plan.execution_plan_id, market_data.simulation_market_data_id))
    ]
    global_fill_sequence = 0
    for order in plan.planned_orders:
        frames = frame_by_order[order.planned_order_id]
        if order.time_in_force in {TimeInForce.IOC, TimeInForce.FOK}:
            frames = frames[:1]
        remaining = order.quantity
        order_fills: list[SimulatedFill] = []
        triggered = order.order_type not in {PlannedOrderType.STOP, PlannedOrderType.STOP_LIMIT}
        trace_specs.append((SimulationTraceEventType.ORDER_EVALUATED, order.planned_order_id, None, (order.planned_order_id,)))
        for frame in frames:
            if order.order_type in {PlannedOrderType.STOP, PlannedOrderType.STOP_LIMIT}:
                trace_specs.append((SimulationTraceEventType.TRIGGER_EVALUATED, order.planned_order_id, frame.sequence, (frame.simulation_frame_id,)))
            price, triggered = _price(order, frame, triggered)
            trace_specs.append((SimulationTraceEventType.PRICE_EVALUATED, order.planned_order_id, frame.sequence, (frame.simulation_frame_id,)))
            if price is None:
                continue
            available = liquidity[frame.simulation_frame_id]
            trace_specs.append((SimulationTraceEventType.LIQUIDITY_EVALUATED, order.planned_order_id, frame.sequence, (frame.simulation_frame_id,)))
            if order.time_in_force is TimeInForce.FOK and available < remaining:
                break
            quantity = min(remaining, available)
            if quantity <= 0:
                continue
            liquidity[frame.simulation_frame_id] -= quantity
            remaining -= quantity
            global_fill_sequence += 1
            evidence = _evidence(order.evidence, frame.evidence, market_data.evidence)
            resulting = PlannedOrderStatus.SIMULATED_FILLED if remaining == 0 else PlannedOrderStatus.SIMULATED_PARTIALLY_FILLED
            fill = SimulatedFill(
                _id("asa.simulated_fill.v1", order.planned_order_id, len(order_fills) + 1, global_fill_sequence, quantity, price, frame.sequence, tuple(_key(item) for item in evidence)),
                order.planned_order_id, len(order_fills) + 1, global_fill_sequence, quantity,
                type(frame.bid)(price, frame.bid.currency), frame.sequence, resulting, evidence,
            )
            order_fills.append(fill)
            fills.append(fill)
            trace_specs.append((SimulationTraceEventType.FILL_CREATED, order.planned_order_id, frame.sequence, (fill.simulated_fill_id,)))
            if remaining == 0 or order.time_in_force in {TimeInForce.IOC, TimeInForce.FOK}:
                break
        filled = order.quantity - remaining
        status, reason = _terminal(order, filled, bool(frames))
        state_evidence = _evidence(order.evidence, *(fill.evidence for fill in order_fills))
        state = SimulatedOrderState(
            _id("asa.simulated_order_state.v1", SIMULATION_ALGORITHM_VERSION, order.planned_order_id, status.value, filled, remaining, tuple(fill.simulated_fill_id for fill in order_fills), reason.value, tuple(_key(item) for item in state_evidence)),
            SIMULATION_ALGORITHM_VERSION, order.planned_order_id, status, filled, remaining,
            tuple(fill.simulated_fill_id for fill in order_fills), reason, state_evidence,
        )
        states.append(state)
        trace_specs.append((SimulationTraceEventType.ORDER_TERMINATED, order.planned_order_id, None, (state.simulated_order_state_id,)))
    trace_specs.append((SimulationTraceEventType.SIMULATION_COMPLETED, None, None, tuple(state.simulated_order_state_id for state in states)))
    trace = tuple(
        SimulationTraceEvent(
            _id("asa.simulation_trace_event.v1", SIMULATION_ALGORITHM_VERSION, sequence, event_type.value, order_id, frame_sequence, identities),
            SIMULATION_ALGORITHM_VERSION, sequence, event_type, order_id, frame_sequence,
            identities, (), _evidence(plan.evidence, market_data.evidence),
        )
        for sequence, (event_type, order_id, frame_sequence, identities) in enumerate(trace_specs, 1)
    )
    unfilled = tuple((state.planned_order_id, state.remaining_quantity) for state in states)
    evidence = _evidence(plan.evidence, market_data.evidence, *(fill.evidence for fill in fills))
    result_id = _id(
        "asa.simulation_result.v1", SIMULATION_ALGORITHM_VERSION, plan.execution_plan_id,
        market_data.simulation_market_data_id, tuple(state.simulated_order_state_id for state in states),
        tuple(fill.simulated_fill_id for fill in fills), unfilled,
        tuple(event.simulation_trace_event_id for event in trace), tuple(_key(item) for item in evidence),
    )
    return SimulationResult(
        result_id, SIMULATION_ALGORITHM_VERSION, plan.execution_plan_id,
        market_data.simulation_market_data_id, tuple(states), tuple(fills), unfilled, trace, evidence,
    )
