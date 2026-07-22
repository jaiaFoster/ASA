"""EXEC-009 complete analytical execution validation."""

from execution_planning.engine import build_planning_lifecycle, plan_execution
from portfolio.engine import apply_simulation, evaluate_portfolio, reduction_candidates
from risk.engine import evaluate_risk
from simulation.engine import simulate
from simulation.lifecycle import complete_lifecycle
from simulation.replay import record_replay, verify_replay
from tests.portfolio.helpers import request
from tests.simulation.test_engine import market_data


def _run_path():  # type: ignore[no-untyped-def]
    evaluation_request = request()
    result = evaluate_portfolio(evaluation_request)[0]
    risk = evaluate_risk(
        result,
        evaluation_request.portfolio_snapshot,
        evaluation_request.proposed_positions[0].strategy_risk_policies,
        reduction_candidates(result, evaluation_request.portfolio_snapshot),
    )
    plan = plan_execution(risk, evaluation_request.portfolio_snapshot)
    data = market_data()
    simulation = simulate(plan, data)
    delta, snapshot = apply_simulation(plan, simulation, data)
    lifecycle = complete_lifecycle(
        build_planning_lifecycle(risk, plan), simulation, delta, snapshot
    )
    replay = record_replay(plan, data, simulation, delta, snapshot, lifecycle)
    return result, risk, plan, simulation, delta, snapshot, lifecycle, replay


def test_complete_path_is_deterministic_and_replay_verified() -> None:
    first = _run_path()
    second = _run_path()
    assert first == second
    assert verify_replay(first[-1]).verified


def test_complete_path_has_identity_and_provenance_at_every_boundary() -> None:
    result, risk, plan, simulation, delta, snapshot, lifecycle, replay = _run_path()
    identified = (
        result.portfolio_evaluation_result_id,
        risk.risk_decision_id,
        plan.execution_plan_id,
        simulation.simulation_result_id,
        delta.portfolio_delta_id,
        snapshot.portfolio_snapshot_id,
        lifecycle.execution_planning_lifecycle_id,
        replay.execution_replay_id,
    )
    assert all(identified)
    assert all(
        value.evidence
        for value in (result, risk, plan, simulation, delta, snapshot, lifecycle, replay)
    )


def test_simulation_never_mutates_plan_or_source_snapshot() -> None:
    _, _, plan, _, _, _, _, _ = _run_path()
    before = (plan, plan.source_snapshot)
    data = market_data()
    simulation = simulate(plan, data)
    apply_simulation(plan, simulation, data)
    assert (plan, plan.source_snapshot) == before
