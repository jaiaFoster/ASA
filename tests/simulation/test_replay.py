from dataclasses import replace

from execution_planning.engine import build_planning_lifecycle, plan_execution
from portfolio.engine import apply_simulation
from simulation.engine import simulate
from simulation.lifecycle import complete_lifecycle
from simulation.replay import canonical_replay_bytes, record_replay, verify_replay
from tests.execution_planning.helpers import decision, snapshot
from tests.simulation.test_engine import market_data


def replay_record():  # type: ignore[no-untyped-def]
    risk_decision = decision()
    plan = plan_execution(risk_decision, snapshot())
    data = market_data()
    result = simulate(plan, data)
    delta, next_snapshot = apply_simulation(plan, result, data)
    lifecycle = complete_lifecycle(
        build_planning_lifecycle(risk_decision, plan),
        result,
        delta,
        next_snapshot,
    )
    return record_replay(plan, data, result, delta, next_snapshot, lifecycle)


def test_complete_execution_replay_is_exact_and_stable() -> None:
    record = replay_record()
    first = verify_replay(record)
    assert first == verify_replay(record)
    assert first.verified
    assert first.mismatch_reasons == ()


def test_tampered_expected_output_fails_closed() -> None:
    record = replay_record()
    verification = verify_replay(replace(record, output_digest="tampered"))
    assert not verification.verified
    assert verification.mismatch_reasons == ("output digest mismatch",)


def test_canonical_serialization_is_byte_identical() -> None:
    record = replay_record()
    assert canonical_replay_bytes(record) == canonical_replay_bytes(record)


def test_lifecycle_is_complete_and_contiguous() -> None:
    lifecycle = replay_record().expected_lifecycle
    assert tuple(event.sequence for event in lifecycle.events) == tuple(
        range(1, len(lifecycle.events) + 1)
    )
    assert lifecycle.events[-1].event_type.value == "portfolio_transition_applied"
