from dataclasses import replace

from strategy_runtime.health import build_strategy_health
from strategy_runtime.result import EvaluationState
from strategy_runtime.values import TypedValue
from tests.strategy_runtime.test_result_migration_targets import _no_lifecycle_result


def test_health_funnel_and_typed_attrition_are_derived_from_results() -> None:
    passed = replace(
        _no_lifecycle_result("forward_factor", "1.3.0"),
        strategy_id="forward_factor",
        verdict="PASS",
        metrics={"decision.structure": TypedValue.of_string("calendar")},
    )
    watch = replace(
        passed,
        symbol="MSFT",
        verdict="WATCH",
        metrics={
            "decision.structure": TypedValue.of_string("calendar"),
            "decision.reason_codes": TypedValue.of_structured(["momentum_conflict"]),
        },
    )
    missing = replace(
        passed,
        symbol="NVDA",
        verdict=None,
        evaluation_state=EvaluationState.MISSING_DATA,
        metrics={},
        blockers=("historical_bars_unavailable",),
    )

    health = build_strategy_health("forward_factor", (passed, watch, missing))

    assert health.active_subjects == 3
    assert health.evaluated == health.evidence_sufficient == 2
    assert health.structure_eligible_or_constructible == 2
    assert health.gates_passed == 2
    assert health.watch == health.passed == 1
    assert health.typed_unknown_counts == (("historical_bars_unavailable", 1),)
    assert health.typed_rejection_counts == (("momentum_conflict", 1),)
