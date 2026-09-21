from __future__ import annotations

from datetime import UTC, date, datetime

import pytest

from strategy_runtime.result import (
    EvaluationState,
    ResultTemporalMetadata,
    RowType,
    UniversalScreeningResult,
)
from strategy_runtime.result_freshness import project_current_result_freshness


def _result(
    *,
    observed_at: datetime,
    market_session_date: date,
    freshness_status: str = "live",
    usability_status: str = "usable",
) -> UniversalScreeningResult:
    temporal = ResultTemporalMetadata(
        subject_snapshot_at=observed_at,
        observed_at=observed_at,
        received_at=observed_at,
        evaluated_at=observed_at,
        persisted_at=observed_at,
        market_session_date=market_session_date,
        market_session_status="open",
        age_seconds=0,
        last_refresh_attempt_at=observed_at,
        last_successful_refresh_at=observed_at,
        next_refresh_at=None,
        data_advanced_on_last_refresh=True,
        freshness_status=freshness_status,
        usability_status=usability_status,
        usability_reason="fixture",
        warning_codes=(),
        acquisition_started_at=observed_at,
        acquisition_completed_at=observed_at,
        input_time_skew_seconds=0,
    )
    return UniversalScreeningResult(
        strategy_id="forward_factor",
        strategy_version="1.0.0",
        symbol="SPY",
        observation_id="obs-1",
        opportunity_id=None,
        row_type=RowType.RESULT,
        verdict="PASS",
        evaluation_state=EvaluationState.PASS,
        lifecycle_stage=None,
        recommendation_state=None,
        data_quality="complete",
        metrics={},
        economics={},
        blockers=(),
        warnings=(),
        provenance=(),
        observed_at=observed_at,
        temporal=temporal,
    )


def test_same_session_refresh_remains_current() -> None:
    observed = datetime(2026, 9, 21, 15, 0, tzinfo=UTC)
    projected = project_current_result_freshness(
        _result(observed_at=observed, market_session_date=date(2026, 9, 21)),
        as_of=datetime(2026, 9, 21, 16, 0, tzinfo=UTC),
    )
    assert projected.current_market_session is True
    assert projected.display_freshness == "fresh"
    assert projected.age_seconds == 3600


def test_friday_result_persisted_or_read_monday_is_stale() -> None:
    friday = datetime(2026, 9, 18, 19, 55, tzinfo=UTC)
    projected = project_current_result_freshness(
        _result(observed_at=friday, market_session_date=date(2026, 9, 18)),
        as_of=datetime(2026, 9, 21, 15, 0, tzinfo=UTC),
    )
    assert projected.current_market_session is False
    assert projected.display_freshness == "stale"
    assert projected.freshness_status == "stale"
    assert projected.age_seconds > 3600


def test_holiday_has_no_current_session_to_claim_fresh() -> None:
    friday = datetime(2026, 9, 4, 19, 55, tzinfo=UTC)
    projected = project_current_result_freshness(
        _result(observed_at=friday, market_session_date=date(2026, 9, 4)),
        as_of=datetime(2026, 9, 7, 16, 0, tzinfo=UTC),
    )
    assert projected.current_market_session is False
    assert projected.display_freshness == "stale"


def test_same_session_after_hours_evidence_keeps_its_economic_session() -> None:
    observed = datetime(2026, 9, 21, 19, 55, tzinfo=UTC)
    projected = project_current_result_freshness(
        _result(observed_at=observed, market_session_date=date(2026, 9, 21)),
        as_of=datetime(2026, 9, 21, 22, 0, tzinfo=UTC),
    )
    assert projected.current_market_session is True
    assert projected.display_freshness == "fresh"


def test_latest_known_good_stale_evidence_remains_stale() -> None:
    observed = datetime(2026, 9, 21, 15, 0, tzinfo=UTC)
    projected = project_current_result_freshness(
        _result(
            observed_at=observed,
            market_session_date=date(2026, 9, 21),
            freshness_status="stale",
            usability_status="usable_with_warning",
        ),
        as_of=datetime(2026, 9, 21, 16, 0, tzinfo=UTC),
    )
    assert projected.display_freshness == "stale"


def test_as_of_must_be_timezone_aware() -> None:
    observed = datetime(2026, 9, 21, 15, 0, tzinfo=UTC)
    with pytest.raises(ValueError, match="timezone-aware"):
        project_current_result_freshness(
            _result(observed_at=observed, market_session_date=date(2026, 9, 21)),
            as_of=datetime(2026, 9, 21, 16, 0),
        )
