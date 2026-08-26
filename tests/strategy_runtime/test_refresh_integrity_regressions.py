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


def _temporal(
    *, source: datetime, evaluated: datetime, snapshot: datetime | None = None
) -> ResultTemporalMetadata:
    return ResultTemporalMetadata(
        subject_snapshot_at=snapshot or evaluated,
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
    *,
    observation_id: str,
    source: datetime,
    evaluated: datetime,
    snapshot: datetime | None = None,
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
            temporal=_temporal(source=source, evaluated=evaluated, snapshot=snapshot),
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


def test_current_snapshot_recomputation_is_not_vetoed_by_older_source_evidence() -> None:
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

    assert should_replace_latest(existing, older_source) is True


def test_unchanged_source_advances_evaluation_without_claiming_data_advanced() -> None:
    source = EVALUATED - timedelta(minutes=1)
    previous = _row(observation_id="old", source=source, evaluated=EVALUATED)
    temporal = _temporal_metadata(
        _registry(),
        "alpha",
        EVALUATED + timedelta(hours=1),
        (
            _observation(
                capability=MarketCapability.REAL_TIME_QUOTE_V1,
                effective_time=source,
                observation_id="same",
            ),
        ),
        previous=previous,
    )

    assert temporal is not None
    assert temporal.observed_at == source
    assert temporal.evaluated_at == EVALUATED + timedelta(hours=1)
    assert temporal.persisted_at == temporal.evaluated_at
    assert temporal.data_advanced_on_last_refresh is False


def test_snapshot_and_evaluation_never_precede_acquisition_completion() -> None:
    cycle_started = EVALUATED
    acquired = EVALUATED + timedelta(minutes=2)
    observation = _observation(
        capability=MarketCapability.REAL_TIME_QUOTE_V1,
        effective_time=EVALUATED - timedelta(seconds=1),
        observation_id="late-acquisition",
    )
    observation.recorded_time = acquired

    temporal = _temporal_metadata(
        _registry(), "alpha", cycle_started, (observation,), previous=None
    )

    assert temporal is not None
    assert temporal.subject_snapshot_at == acquired
    assert temporal.evaluated_at == acquired
    assert temporal.persisted_at == acquired


def test_replayed_older_snapshot_cannot_replace_current_authoritative_evaluation() -> None:
    existing = _row(
        observation_id="aaa",
        source=EVALUATED,
        evaluated=EVALUATED,
        snapshot=EVALUATED,
    )
    replay = _row(
        observation_id="zzz",
        source=EVALUATED - timedelta(days=1),
        evaluated=EVALUATED + timedelta(hours=1),
        snapshot=EVALUATED - timedelta(days=1),
    )

    assert should_replace_latest(existing, replay) is False


def _observation(
    *,
    capability: MarketCapability,
    effective_time: datetime,
    observation_id: str,
    status: FreshnessStatus = FreshnessStatus.FRESH,
    subject_id: str = "AAPL",
    provider_id: str = "fixture",
) -> MarketObservation:
    freshness = SimpleNamespace(
        status=status,
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
            subject=SimpleNamespace(subject_identity=subject_id),
            provenance=SimpleNamespace(provider_id=provider_id),
        ),
    )


def _registry() -> SimpleNamespace:
    return SimpleNamespace(
        contract_for=lambda _strategy_id: SimpleNamespace(
            freshness_requirement=DEFAULT_FRESHNESS_REQUIREMENT
        )
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
    observations = (oldest_bar, latest_bar, quote)
    registry = SimpleNamespace(
        contract_for=lambda _strategy_id: SimpleNamespace(
            freshness_requirement=DEFAULT_FRESHNESS_REQUIREMENT
        )
    )

    temporal = _temporal_metadata(
        registry,
        "alpha",
        EVALUATED,
        observations,
        previous=None,
    )

    assert temporal is not None
    assert temporal.age_seconds == 300
    assert temporal.input_time_skew_seconds == 298
    assert temporal.freshness_status == "live"
    assert temporal.usability_status == "usable"


def test_exact_duplicate_candidate_is_idempotent() -> None:
    # PATCH-011C: an identical (source, evaluated, observation_id) tuple is
    # not a "later arrival" -- but should_replace_latest's own >= comparison
    # (strategy_runtime/persistence.py) must still treat it as replaceable
    # (a harmless overwrite with identical values), not silently rejected.
    # A future >-only comparison would break the scheduler's own re-run-the-
    # same-slot idempotency guarantee (asa/scheduled_screening.py's claim
    # repository already prevents duplicate *slot* execution; this is the
    # separate, lower-level guarantee that a duplicate *write* of the same
    # observation is never treated as a regression).
    row = _row(observation_id="aaa", source=EVALUATED, evaluated=EVALUATED)
    duplicate = _row(observation_id="aaa", source=EVALUATED, evaluated=EVALUATED)

    assert should_replace_latest(row, duplicate) is True


def test_stale_latest_historical_bar_is_not_masked_as_live() -> None:
    # PATCH-011C: filtering historical bars down to the latest-per-group
    # (#247's own fix) must never suppress genuine staleness -- if even the
    # *latest* available bar is itself classified stale by the provider's
    # own freshness metadata, the aggregate result must say so, not report
    # "live" merely because the 45-day-old peer bars were filtered out.
    stale_latest_bar = _observation(
        capability=MarketCapability.HISTORICAL_BARS_V1,
        effective_time=EVALUATED - timedelta(days=3),
        observation_id="stale-latest-bar",
        status=FreshnessStatus.STALE,
    )
    quote = _observation(
        capability=MarketCapability.REAL_TIME_QUOTE_V1,
        effective_time=EVALUATED - timedelta(seconds=2),
        observation_id="quote",
    )
    observations = (stale_latest_bar, quote)

    temporal = _temporal_metadata(_registry(), "alpha", EVALUATED, observations, previous=None)

    assert temporal is not None
    assert temporal.freshness_status == "stale"


def test_each_subject_provider_group_keeps_its_own_latest_bar() -> None:
    # PATCH-011C: _current_temporal_observations groups historical bars by
    # (subject_identity, provider_id) before picking the latest per group --
    # a strategy pulling historical bars for more than one subject or from
    # more than one provider must not have one series' latest bar crowd out
    # another's, and must not silently collapse to a single global "latest".
    aapl_old = _observation(
        capability=MarketCapability.HISTORICAL_BARS_V1,
        effective_time=EVALUATED - timedelta(days=10),
        observation_id="aapl-old",
        subject_id="AAPL",
    )
    aapl_recent = _observation(
        capability=MarketCapability.HISTORICAL_BARS_V1,
        effective_time=EVALUATED - timedelta(minutes=5),
        observation_id="aapl-recent",
        subject_id="AAPL",
    )
    msft_recent = _observation(
        capability=MarketCapability.HISTORICAL_BARS_V1,
        effective_time=EVALUATED - timedelta(minutes=10),
        observation_id="msft-recent",
        subject_id="MSFT",
    )
    observations = (aapl_old, aapl_recent, msft_recent)

    temporal = _temporal_metadata(_registry(), "alpha", EVALUATED, observations, previous=None)

    assert temporal is not None
    # Oldest surviving effective_time is MSFT's own latest bar (10 minutes
    # back), not AAPL's stale 10-day-old bar -- proving the AAPL group's own
    # old bar was dropped in favor of its own latest, independently of MSFT.
    assert temporal.age_seconds == 600
    assert temporal.input_time_skew_seconds == 300  # 10m - 5m between the two surviving bars


def test_effective_times_stay_utc_normalized_across_timezone_input() -> None:
    # PATCH-011C: a non-UTC-but-tz-aware effective_time must normalize
    # identically to its UTC equivalent -- age/skew must not silently
    # double-count or drop a timezone offset.
    from datetime import timezone

    minus_five = timezone(timedelta(hours=-5))
    quote_in_est = _observation(
        capability=MarketCapability.REAL_TIME_QUOTE_V1,
        effective_time=(EVALUATED - timedelta(seconds=2)).astimezone(minus_five),
        observation_id="quote-est",
    )
    observations = (quote_in_est,)

    temporal = _temporal_metadata(_registry(), "alpha", EVALUATED, observations, previous=None)

    assert temporal is not None
    assert temporal.age_seconds == 2
    assert temporal.observed_at.utcoffset() == timedelta(0)
