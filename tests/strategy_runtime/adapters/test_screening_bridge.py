"""SPRINT-009R/EPIC-R2: strategy_runtime.adapters._screening_bridge emits a
typed strategy_native_score, not a bare str -- the production path every
migrated strategy (forward_factor, skew_momentum, earnings_calendar)
already runs through.
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

from screening.results import ScreeningExplanation, ScreeningOutcomeStatus, ScreeningResult
from strategy_runtime.adapters._screening_bridge import translate_screening_result
from strategy_runtime.values import TypedValue, ValueType

NOW = datetime(2026, 1, 1, tzinfo=UTC)


def _screening_result(**overrides: object) -> ScreeningResult:
    defaults: dict[str, object] = {
        "run_id": "run-1",
        "strategy_id": "alpha",
        "strategy_version": "1.0.0",
        "subject_identity": "AAPL",
        "as_of": NOW,
        "outcome_status": ScreeningOutcomeStatus.PASS,
        "signal_classification": "bullish",
        "strategy_native_score": Decimal("0.75"),
        "evidence": (),
        "input_provenance": (),
        "completeness": None,
        "failure_detail": None,
    }
    defaults.update(overrides)
    return ScreeningResult(**defaults)  # type: ignore[arg-type]


class TestTranslateScreeningResult:
    def test_a_native_score_becomes_a_typed_decimal_metric(self) -> None:
        result = translate_screening_result(
            _screening_result(),
            symbol="AAPL",
            observation_id="obs-1",
            opportunity_id=None,
            lifecycle_stage=None,
        )

        metric = result.metrics["strategy_native_score"]
        assert isinstance(metric, TypedValue)
        assert metric.value_type is ValueType.DECIMAL
        assert metric.native() == Decimal("0.75")

    def test_no_native_score_produces_no_metrics(self) -> None:
        result = translate_screening_result(
            _screening_result(
                outcome_status=ScreeningOutcomeStatus.NO_SIGNAL,
                strategy_native_score=None,
            ),
            symbol="AAPL",
            observation_id="obs-1",
            opportunity_id=None,
            lifecycle_stage=None,
        )

        assert result.metrics == {}

    def test_named_explanation_survives_the_generic_bridge(self) -> None:
        explanation = ScreeningExplanation(
            named_derived_facts=(("forward_factor", Decimal("0.20")),),
            formula_versions=(("forward_factor", "1.0.0"),),
            gate_results=(("eligible", True),),
            direction="BULLISH",
            structure="structure-1",
            reason_codes=("verdict:pass",),
            assumptions=("threshold=0.20",),
            warnings=(),
        )
        result = translate_screening_result(
            _screening_result(explanation=explanation),
            symbol="AAPL",
            observation_id="obs-1",
            opportunity_id=None,
            lifecycle_stage=None,
        )

        assert result.metrics["derived_fact.forward_factor"].native() == Decimal("0.20")
        assert result.metrics["formula_version.forward_factor"].native() == "1.0.0"
        assert result.metrics["gate.eligible"].native() is True
        assert result.metrics["decision.direction"].native() == "BULLISH"
        assert result.metrics["decision.reason_codes"].native() == ["verdict:pass"]
