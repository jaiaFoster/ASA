from __future__ import annotations

from datetime import datetime

from simulation.tgsm_research import evaluate_tgsm_research_target
from strategies.tgsm_decision import build_s001_target_decision
from strategy_runtime.adapters.tgsm_subject_first import build_s001_cohort_registry
from strategy_runtime.cohort_composition import compose_cohort_knowledge
from strategy_runtime.execution import ExecutionStatus, run_strategies
from tests.strategy_runtime.test_tgsm_composition import NOW as COHORT_TIME
from tests.strategy_runtime.test_tgsm_composition import _facts, _knowledge
from tests.strategy_runtime.test_tgsm_target_decision import (
    MEMBERSHIP,
    NEXT_SESSION,
    _defensive,
)


def test_research_and_runtime_use_identical_s001_interpretation_and_allocation() -> None:
    facts = (
        _facts("XLE", "0.40", "90"),
        _facts("XLF", "0.30", "110"),
        _facts("XLK", "0.20", "110"),
        _facts("XLV", "0.10", "110"),
    )
    cohort = compose_cohort_knowledge(
        {item.subject.value: _knowledge(item) for item in facts},
        decision_time=COHORT_TIME,
    )

    class _Clock:
        def now(self) -> datetime:
            return COHORT_TIME

    (execution,) = run_strategies(
        build_s001_cohort_registry(cohort, MEMBERSHIP),
        _Clock(),
        subjects=(MEMBERSHIP.universe_id,),
    )
    assert execution.status is ExecutionStatus.COMPLETED
    assert execution.result is not None
    runtime_decision = build_s001_target_decision(
        execution.result,
        defensive_evidence=_defensive(),
        next_eligible_session=lambda _: NEXT_SESSION,
    )

    research_decision = evaluate_tgsm_research_target(
        cohort,
        MEMBERSHIP,
        defensive_evidence=_defensive(),
        next_eligible_session=lambda _: NEXT_SESSION,
    )

    assert research_decision == runtime_decision
    assert research_decision.decision_id == runtime_decision.decision_id
