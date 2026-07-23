"""SPRINT-009/EPIC-6: UniversalScreeningResult validation."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from strategy_runtime.result import (
    EvaluationState,
    RowType,
    UniversalScreeningResult,
    compute_observation_id,
)


def _result(**overrides: object) -> UniversalScreeningResult:
    defaults: dict[str, object] = {
        "strategy_id": "example",
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
        "metrics": {},
        "economics": {},
        "blockers": (),
        "warnings": (),
        "provenance": (),
        "observed_at": datetime(2026, 1, 1, tzinfo=UTC),
    }
    defaults.update(overrides)
    return UniversalScreeningResult(**defaults)  # type: ignore[arg-type]


class TestComputeObservationId:
    def test_deterministic_for_identical_inputs(self) -> None:
        assert compute_observation_id("run-1", "alpha", "AAPL") == compute_observation_id(
            "run-1", "alpha", "AAPL"
        )

    def test_differs_when_any_input_differs(self) -> None:
        base = compute_observation_id("run-1", "alpha", "AAPL")
        assert compute_observation_id("run-2", "alpha", "AAPL") != base
        assert compute_observation_id("run-1", "beta", "AAPL") != base
        assert compute_observation_id("run-1", "alpha", "MSFT") != base


class TestUniversalScreeningResult:
    def test_success_state_requires_verdict(self) -> None:
        with pytest.raises(ValueError, match="requires verdict"):
            _result(evaluation_state=EvaluationState.PASS, verdict=None)

    def test_non_success_state_rejects_verdict(self) -> None:
        with pytest.raises(ValueError, match="must not carry verdict"):
            _result(evaluation_state=EvaluationState.MISSING_DATA, verdict="pass")

    def test_no_signal_is_also_a_success_state_requiring_verdict(self) -> None:
        result = _result(evaluation_state=EvaluationState.NO_SIGNAL, verdict="no_signal")
        assert result.verdict == "no_signal"

    def test_adapter_exception_state_with_no_verdict_is_valid(self) -> None:
        result = _result(evaluation_state=EvaluationState.ADAPTER_EXCEPTION, verdict=None)
        assert result.verdict is None

    def test_opportunity_id_without_lifecycle_stage_is_rejected(self) -> None:
        with pytest.raises(ValueError, match="must both be present or both be absent"):
            _result(opportunity_id="opp-1", lifecycle_stage=None)

    def test_lifecycle_stage_without_opportunity_id_is_rejected(self) -> None:
        with pytest.raises(ValueError, match="must both be present or both be absent"):
            _result(opportunity_id=None, lifecycle_stage="watching")

    def test_both_opportunity_id_and_lifecycle_stage_present_is_valid(self) -> None:
        result = _result(opportunity_id="opp-1", lifecycle_stage="watching")
        assert result.opportunity_id == "opp-1"
        assert result.lifecycle_stage == "watching"

    def test_both_absent_is_valid_the_common_no_lifecycle_case(self) -> None:
        result = _result(opportunity_id=None, lifecycle_stage=None)
        assert result.opportunity_id is None

    def test_naive_datetime_is_rejected(self) -> None:
        with pytest.raises(ValueError, match="timezone-aware"):
            _result(observed_at=datetime(2026, 1, 1))  # noqa: DTZ001

    def test_blank_strategy_id_is_rejected(self) -> None:
        with pytest.raises(ValueError, match="strategy_id"):
            _result(strategy_id="  ")
