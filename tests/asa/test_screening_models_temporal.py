from datetime import UTC, datetime

from asa.api.screening_models import ScreeningResultResponse
from strategy_runtime.result import (
    EvaluationState,
    RowType,
    UniversalScreeningResult,
)


def test_missing_temporal_metadata_is_unknown_not_rejected() -> None:
    observed_at = datetime(2026, 8, 21, 12, 0, tzinfo=UTC)
    result = UniversalScreeningResult(
        strategy_id="synthetic",
        strategy_version="1.0.0",
        symbol="AAPL",
        observation_id="observation-1",
        opportunity_id=None,
        row_type=RowType.RESULT,
        verdict=None,
        evaluation_state=EvaluationState.MISSING_DATA,
        lifecycle_stage=None,
        recommendation_state=None,
        data_quality=None,
        metrics={},
        economics={},
        blockers=("typed evidence gap",),
        warnings=(),
        provenance=(),
        observed_at=observed_at,
        temporal=None,
    )

    response = ScreeningResultResponse.from_universal_result(result)

    assert response.usability_status == "unknown"
    assert response.usability_reason == "temporal metadata unavailable"
