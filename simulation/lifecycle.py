"""Complete an immutable analytical lifecycle from simulation outputs."""

from __future__ import annotations

import hashlib

from domain.canonicalization import serialize_canonical
from domain.execution import (
    ExecutionPlanningEvent,
    ExecutionPlanningEventType,
    ExecutionPlanningLifecycle,
    PortfolioDelta,
)
from domain.operational import PortfolioSnapshot
from domain.simulation import SimulationResult


def _id(namespace: str, *values: object) -> str:
    value = "\n".join((namespace, *(serialize_canonical(item) for item in values)))
    return hashlib.sha256(value.encode()).hexdigest()


def complete_lifecycle(
    lifecycle: ExecutionPlanningLifecycle,
    result: SimulationResult,
    simulated_delta: PortfolioDelta,
    next_snapshot: PortfolioSnapshot,
) -> ExecutionPlanningLifecycle:
    """Append the exact simulation and transition events without mutation."""
    specs: list[tuple[ExecutionPlanningEventType, str, tuple[str, ...], tuple[str, ...]]] = [
        (
            ExecutionPlanningEventType.SIMULATION_STARTED,
            result.simulation_result_id,
            (result.execution_plan_id, result.market_data_id),
            (),
        ),
        *(
            (
                ExecutionPlanningEventType.ORDER_SIMULATED,
                state.planned_order_id,
                (state.planned_order_id,),
                (state.simulated_order_state_id,),
            )
            for state in result.ordered_order_states
        ),
        (
            ExecutionPlanningEventType.SIMULATION_COMPLETED,
            result.simulation_result_id,
            tuple(state.simulated_order_state_id for state in result.ordered_order_states),
            (result.simulation_result_id,),
        ),
        (
            ExecutionPlanningEventType.PORTFOLIO_TRANSITION_APPLIED,
            next_snapshot.portfolio_snapshot_id,
            (result.simulation_result_id, simulated_delta.portfolio_delta_id),
            (next_snapshot.portfolio_snapshot_id,),
        ),
    ]
    start = len(lifecycle.events) + 1
    appended = tuple(
        ExecutionPlanningEvent(
            _id("asa.execution_planning_event.v1", lifecycle.root_risk_decision_id, sequence, event_type.value, subject, inputs, outputs),
            lifecycle.root_risk_decision_id, sequence, event_type, subject, inputs, outputs,
            result.simulation_algorithm_version, result.evidence,
        )
        for sequence, (event_type, subject, inputs, outputs) in enumerate(specs, start)
    )
    events = (*lifecycle.events, *appended)
    return ExecutionPlanningLifecycle(
        _id("asa.execution_planning_lifecycle.v1", lifecycle.lifecycle_algorithm_version, lifecycle.root_risk_decision_id, tuple(event.execution_planning_event_id for event in events)),
        lifecycle.lifecycle_algorithm_version,
        lifecycle.root_risk_decision_id,
        events,
        result.evidence,
    )
