"""Regression coverage for SPRINT-011 refresh-integrity defects #246/#247."""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from types import SimpleNamespace
from typing import cast

from domain import FreshnessStatus, MarketCapability, MarketObservation
from market_data.temporal import DEFAULT_FRESHNESS_REQUIREMENT
from strategy_runtime.persistence import UniversalSignalRow, should_replace_latest
from strategy_runtime.result import (
    EvaluationState,
    ResultTemporalMetadata,
    RowType,
    UniversalScreeningResult,
)
from strategy_runtime.service import _temporal_metadata

EVALUATED = datetime(2026, 7, 27, 18, 0, tzinfo=UTC)


def _temporal(*, source: datetime, evaluated: datetime) -> ResultTemporalMetadata:
    return ResultTemporalMetadata(
        observed_at=source,
        received_at=evaluated,
        evaluated_at=evaluated,
        persisted_at=evaluated,
        market_session_date=date(2026, 7, 27),
        market_session_status="open",
        age_seconds=max(0, int((evaluated - source).total_seconds())),
        last_refresh_attempt_at=evaluated,
        last_successful_refresh_at=evaluated,
        next_refresh_at=evaluated + timedelta(hours=1),
        data_advanced_on_last_refresh=True,
        freshness_status="live",
        usability_status="usable",
        usability_reason="observation is current",
        warning_codes=(),
        acquisition_started_at=evaluated,
        acquisition_completed_at=evaluated,
        input_time_skew_seconds=0,
    )


def _row(
    *, observation_id: str, source: datetime, evaluated: datetime
) -> UniversalSignalRow:
    return UniversalSignalRow.from_result(
        UniversalScreeningResult(
            strategy_id="alpha",
            strategy_version="1.0.0",
            symbol="AAPL",
            observation_id=observation_id,
            opportunity_id=None,
            row_type=RowType.RESULT,
            verdict="pass",
            evaluation_state=EvaluationState.PASS,
            lifecycle_stage=None,
            recommendation_state=None,
            data_quality="fresh",
            metrics={},
            economics={},
            blockers=(),
            warnings=(),
            provenance=(),
            observed_at=evaluated,
            temporal=_temporal(source=source, evaluated=evaluated),
        )
    )


def test_later_same_source_evaluation_wins_even_with_lower_hash_identity() -> None:
    source = EVALUATED - timedelta(minutes=1)
    existing = _row(observation_id="zzz", source=source, evaluated=EVALUATED)
    later = _row(
        observation_id="aaa",
        source=source,
        evaluated=EVALUATED + timedelta(hours=1),
    )

    assert should_replace_latest(existing, later) is True
    assert should_replace_latest(later, existing) is False


def test_later_evaluation_cannot_regress_an_older_source_observation() -> None:
    existing = _row(
        observation_id="aaa",
        source=EVALUATED,
        evaluated=EVALUATED,
    )
    older_source = _row(
        observation_id="zzz",
        source=EVALUATED - timedelta(days=1),
        evaluated=EVALUATED + timedelta(hours=1),
    )

    assert should_replace_latest(existing, older_source) is False


def _observation(
    *, capability: MarketCapability, effective_time: datetime, observation_id: str
) -> MarketObservation:
    freshness = SimpleNamespace(
        status=FreshnessStatus.FRESH,
        age_seconds=max(0, int((EVALUATED - effective_time).total_seconds())),
    )
    return cast(
        MarketObservation,
        SimpleNamespace(
            capability=capability,
            effective_time=effective_time,
            recorded_time=EVALUATED,
            observation_id=observation_id,
            freshness=freshness,
            subject=SimpleNamespace(subject_identity="AAPL"),
            provenance=SimpleNamespace(provider_id="fixture"),
        ),
    )


def test_historical_coverage_does_not_become_current_age_or_input_skew() -> None:
    oldest_bar = _observation(
        capability=MarketCapability.HISTORICAL_BARS_V1,
        effective_time=EVALUATED - timedelta(days=45),
        observation_id="oldest-bar",
    )
    latest_bar = _observation(
        capability=MarketCapability.HISTORICAL_BARS_V1,
        effective_time=EVALUATED - timedelta(minutes=5),
        observation_id="latest-bar",
    )
    quote = _observation(
        capability=MarketCapability.REAL_TIME_QUOTE_V1,
        effective_time=EVALUATED - timedelta(seconds=2),
        observation_id="quote",
    )
    fulfillment = SimpleNamespace(
        completed_results=(
            SimpleNamespace(observations=(oldest_bar, latest_bar, quote)),
        )
    )
    registry = SimpleNamespace(
        contract_for=lambda _strategy_id: SimpleNamespace(
            freshness_requirement=DEFAULT_FRESHNESS_REQUIREMENT
        )
    )

    temporal = _temporal_metadata(
        registry,
        "alpha",
        EVALUATED,
        fulfillment,
        previous=None,
    )

    assert temporal is not None
    assert temporal.age_seconds == 300
    assert temporal.input_time_skew_seconds == 298
    assert temporal.freshness_status == "live"
    assert temporal.usability_status == "usable"
