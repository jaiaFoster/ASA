from datetime import UTC, datetime
from decimal import Decimal

from asa.api.screening_models import (
    ExecutableStructureAssessmentResponse,
    ModeledPnLSurfaceResponse,
    ScreeningResultResponse,
)
from strategy_runtime.contract import StructureKind
from strategy_runtime.executable_structures import (
    ExecutableStructureAssessment,
    ExecutableStructureStatus,
)
from strategy_runtime.modeled_pnl import MODEL_VERSION, ModeledPnLPoint, ModeledPnLSurface
from strategy_runtime.result import EvaluationState, RowType, UniversalScreeningResult

NOW = datetime(2026, 9, 1, 15, tzinfo=UTC)


def _signal() -> UniversalScreeningResult:
    return UniversalScreeningResult(
        strategy_id="forward_factor",
        strategy_version="1.3.0",
        symbol="AAPL",
        observation_id="result-1",
        opportunity_id=None,
        row_type=RowType.RESULT,
        verdict="PASS",
        evaluation_state=EvaluationState.PASS,
        lifecycle_stage=None,
        recommendation_state=None,
        data_quality=None,
        metrics={},
        economics={},
        blockers=(),
        warnings=(),
        provenance=("snapshot_id:snapshot-1",),
        observed_at=NOW,
    )


def test_execution_assessment_is_additive_to_unchanged_signal_projection() -> None:
    signal = _signal()
    before = ScreeningResultResponse.from_universal_result(signal).model_dump()
    assessment = ExecutableStructureAssessment(
        signal.observation_id,
        signal.symbol,
        StructureKind.CALENDAR,
        ExecutableStructureStatus.NOT_CONSTRUCTIBLE,
        (),
        (),
        None,
        "snapshot-1",
        NOW,
        reason_code="no_compatible_contract",
    )

    projected = ExecutableStructureAssessmentResponse.from_assessment(assessment)
    after = ScreeningResultResponse.from_universal_result(signal).model_dump()

    assert before == after
    assert before["verdict"] == "PASS"
    assert projected.status == "not_constructible"
    assert projected.originating_result_identity == before["observation_id"]
    assert projected.reason_code == "no_compatible_contract"


def test_execution_assessment_schema_uses_exact_decimal_strings() -> None:
    schema = ExecutableStructureAssessmentResponse.model_json_schema()

    assert "exact_legs" in schema["properties"]
    assert "modeled_entry" in schema["properties"]
    assert "status" in schema["properties"]
    surface = ModeledPnLSurface(
        "assessment-1",
        MODEL_VERSION,
        NOW,
        Decimal("200.00"),
        (
            ModeledPnLPoint(Decimal("190.00"), Decimal("-12.34")),
            ModeledPnLPoint(Decimal("200.00"), Decimal("45.60")),
        ),
        "midpoint",
        (("contract-1", Decimal("0.30")),),
        Decimal("0.04"),
        Decimal("0.01"),
        Decimal("100"),
    )
    projected = ModeledPnLSurfaceResponse.from_surface(surface)

    assert projected.spot_reference == "200.00"
    assert projected.points[0].modeled_pnl == "-12.34"
    assert projected.semantics == "modeled_PnL_not_guaranteed_payoff"
