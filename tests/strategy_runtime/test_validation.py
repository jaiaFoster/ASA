"""SPRINT-009R/EPIC-R1: strategy_runtime.validation.validate_result --
"declared outputs emitted" runtime_validation, in isolation from
run_strategies() (see test_execution.py's TestContractDerivedValidation
for the end-to-end wiring)."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from strategy_runtime import (
    NO_LIFECYCLE,
    DataRequirement,
    EvaluationState,
    LifecycleDeclaration,
    LifecycleModel,
    OutputKind,
    RequirementCategory,
    RowType,
    StrategyContract,
    StrategyContractViolationError,
    StructureKind,
    UniversalScreeningResult,
    validate_result,
)

NOW = datetime(2026, 1, 1, tzinfo=UTC)


def _contract(**overrides: object) -> StrategyContract:
    defaults: dict[str, object] = {
        "strategy_id": "alpha",
        "version": "1.0.0",
        "category": "test",
        "description": "A test contract.",
        "requirements": (DataRequirement(RequirementCategory.CUSTOM, identifier="none"),),
        "lifecycle": NO_LIFECYCLE,
        "structure": StructureKind.NONE,
        "outputs": (OutputKind.METRICS,),
    }
    defaults.update(overrides)
    return StrategyContract(**defaults)  # type: ignore[arg-type]


def _result(**overrides: object) -> UniversalScreeningResult:
    defaults: dict[str, object] = {
        "strategy_id": "alpha",
        "strategy_version": "1.0.0",
        "symbol": "AAPL",
        "observation_id": "obs-1",
        "opportunity_id": None,
        "row_type": RowType.RESULT,
        "verdict": "pass",
        "evaluation_state": EvaluationState.PASS,
        "lifecycle_stage": None,
        "recommendation_state": None,
        "data_quality": None,
        "metrics": {"score": "1"},
        "economics": {},
        "blockers": (),
        "warnings": (),
        "provenance": (),
        "observed_at": NOW,
    }
    defaults.update(overrides)
    return UniversalScreeningResult(**defaults)  # type: ignore[arg-type]


class TestValidateResult:
    def test_non_universal_result_is_ignored(self) -> None:
        validate_result(_contract(), "not a UniversalScreeningResult")  # must not raise

    def test_missing_data_evaluation_state_is_never_a_violation(self) -> None:
        contract = _contract(outputs=(OutputKind.METRICS, OutputKind.ECONOMICS))
        result = _result(
            evaluation_state=EvaluationState.MISSING_DATA, verdict=None, metrics={}, economics={}
        )
        validate_result(contract, result)  # must not raise

    def test_declared_metrics_output_with_empty_metrics_is_a_violation(self) -> None:
        contract = _contract(outputs=(OutputKind.METRICS,))
        result = _result(metrics={})
        with pytest.raises(StrategyContractViolationError, match="OutputKind.METRICS"):
            validate_result(contract, result)

    def test_declared_metrics_output_with_populated_metrics_is_accepted(self) -> None:
        contract = _contract(outputs=(OutputKind.METRICS,))
        validate_result(contract, _result(metrics={"score": "1"}))  # must not raise

    def test_declared_lifecycle_output_without_opportunity_id_is_a_violation(self) -> None:
        contract = _contract(
            outputs=(OutputKind.METRICS, OutputKind.LIFECYCLE),
            lifecycle=LifecycleDeclaration(
                LifecycleModel.OPPORTUNITY, supported_states=("watching",), observation_type="x"
            ),
        )
        result = _result(opportunity_id=None, lifecycle_stage=None)
        with pytest.raises(StrategyContractViolationError, match="OutputKind.LIFECYCLE"):
            validate_result(contract, result)

    def test_declared_lifecycle_output_with_opportunity_id_is_accepted(self) -> None:
        contract = _contract(
            outputs=(OutputKind.METRICS, OutputKind.LIFECYCLE),
            lifecycle=LifecycleDeclaration(
                LifecycleModel.OPPORTUNITY, supported_states=("watching",), observation_type="x"
            ),
        )
        result = _result(opportunity_id="opp-1", lifecycle_stage="watching")
        validate_result(contract, result)  # must not raise

    def test_declared_recommendation_output_without_recommendation_state_is_a_violation(
        self,
    ) -> None:
        contract = _contract(outputs=(OutputKind.METRICS, OutputKind.RECOMMENDATION_SUPPORT))
        result = _result(recommendation_state=None)
        with pytest.raises(
            StrategyContractViolationError, match="OutputKind.RECOMMENDATION_SUPPORT"
        ):
            validate_result(contract, result)

    def test_undeclared_economics_output_never_checked_even_when_empty(self) -> None:
        # Deliberately not enforced yet -- see validation.py's own comment: every currently
        # migrated strategy declares ECONOMICS but always emits economics={} (EPIC-R2's job).
        contract = _contract(outputs=(OutputKind.METRICS, OutputKind.ECONOMICS))
        validate_result(contract, _result(metrics={"score": "1"}, economics={}))  # must not raise
