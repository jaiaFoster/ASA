"""Universal screening service (SPRINT-009/EPIC-9).

The universal runtime's get_state() only ever reads through an injected
LatestResultRepository (never triggers acquisition, matching this
sprint's own architecture_principles); refresh() calls run_strategies()
for exactly one requested strategy against one subject, then persists the
result through the same injected repository -- bounded, narrow, no
whole-universe execution.

Both functions translate between UniversalScreeningResult (this module's
own public parameter/return type, same as every adapter's) and
UniversalSignalRow (LatestResultRepository's own storage-boundary shape,
see strategy_runtime/persistence.py's own docstring for why) right here
at the repository call site -- callers of get_state()/refresh() never see
UniversalSignalRow at all.

record_opportunity_observation() (SPRINT-009R/EPIC-R3) is a separate,
explicitly opt-in extension: refresh() itself stays unchanged and usable by
every strategy, lifecycle-tracked or not, so this persists an opportunity's
evolution only for a caller that actually wants it (and can supply the
recommended_action a real recommendation engine would compute -- this
sprint's own explicit non_goal, deliberately never invented here).
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import replace
from datetime import UTC, datetime

from domain import FreshnessStatus, MarketCapability, MarketObservation
from market_data import CapabilityFulfillmentService
from market_data.session_calendar import NEW_YORK, UsEquitySessionCalendar
from market_data.session_schedule import SessionRefreshSchedule
from market_data.temporal import (
    TemporalUsabilityDecision,
    UsabilityStatus,
    evaluate_temporal_usability,
)
from strategy_runtime.clock import Clock
from strategy_runtime.execution import ExecutionStatus, run_strategies
from strategy_runtime.lifecycle import (
    OpportunityObservation,
    RecommendedAction,
    observe_transition,
)
from strategy_runtime.persistence import (
    LatestResultRepository,
    ObservationHistoryRepository,
    UniversalSignalRow,
)
from strategy_runtime.registry import StrategyRegistry
from strategy_runtime.result import ResultTemporalMetadata, UniversalScreeningResult

_FRESHNESS_PRIORITY = {
    FreshnessStatus.FRESH: 0,
    FreshnessStatus.DELAYED: 1,
    FreshnessStatus.PRIOR_SESSION: 2,
    FreshnessStatus.STALE: 3,
    FreshnessStatus.UNKNOWN: 4,
    FreshnessStatus.UNAVAILABLE: 5,
}
_USABILITY_PRIORITY = {
    UsabilityStatus.USABLE: 0,
    UsabilityStatus.USABLE_WITH_WARNING: 1,
    UsabilityStatus.REJECTED: 2,
}


def _current_temporal_observations(
    observations: tuple[MarketObservation, ...],
) -> tuple[MarketObservation, ...]:
    """Return the current effective evidence for temporal classification.

    A historical-bars capability intentionally contributes a time series. Its
    oldest bar defines analytical coverage, not the freshness of the current
    result. Treating every bar as a peer current input made a 45-day lookback
    appear as roughly 45 days of age and cross-input skew. Keep the latest bar
    per subject/provider as the current evidence point while retaining every
    observation for acquisition timing and strategy computation elsewhere.
    Point-in-time capabilities remain unchanged.
    """
    point_in_time: list[MarketObservation] = []
    latest_historical: dict[tuple[str, str], MarketObservation] = {}
    for observation in observations:
        if observation.capability is not MarketCapability.HISTORICAL_BARS_V1:
            point_in_time.append(observation)
            continue
        key = (
            observation.subject.subject_identity,
            observation.provenance.provider_id,
        )
        existing = latest_historical.get(key)
        if existing is None or (
            observation.effective_time,
            observation.observation_id,
        ) > (
            existing.effective_time,
            existing.observation_id,
        ):
            latest_historical[key] = observation
    return tuple(point_in_time) + tuple(
        latest_historical[key] for key in sorted(latest_historical)
    )


def _temporal_metadata(
    registry: StrategyRegistry[UniversalScreeningResult],
    strategy_id: str,
    evaluated_at: datetime,
    fulfillment: CapabilityFulfillmentService,
    previous: UniversalSignalRow | None,
) -> ResultTemporalMetadata | None:
    evaluated = evaluated_at.astimezone(UTC)
    observations: tuple[MarketObservation, ...] = tuple(
        observation
        for completed in fulfillment.completed_results
        for observation in completed.observations
    )
    if not observations:
        return None
    current_observations = _current_temporal_observations(observations)
    effective_times = tuple(
        item.effective_time.astimezone(UTC) for item in current_observations
    )
    recorded_times = tuple(item.recorded_time.astimezone(UTC) for item in observations)
    observed = max(effective_times)
    received = max(recorded_times)
    calendar = UsEquitySessionCalendar()
    session_status = calendar.status_at(evaluated)
    session = calendar.session(evaluated.astimezone(NEW_YORK).date())
    session_date = (
        session.trading_date
        if session is not None and session.opens_at <= evaluated
        else calendar.latest_completed_session(evaluated).trading_date
    )
    requirement = registry.contract_for(strategy_id).freshness_requirement
    decisions: tuple[TemporalUsabilityDecision, ...] = tuple(
        evaluate_temporal_usability(
            item.freshness,
            requirement,
            market_is_open=session_status.value == "open",
        )
        for item in current_observations
    )
    usability = max(decisions, key=lambda item: _USABILITY_PRIORITY[item.status])
    freshness = max(
        (item.freshness.status for item in current_observations),
        key=lambda item: _FRESHNESS_PRIORITY[item],
    )
    previous_observed = (
        previous.temporal.observed_at
        if previous is not None and previous.temporal is not None
        else None
    )
    return ResultTemporalMetadata(
        observed_at=observed,
        received_at=received,
        evaluated_at=evaluated,
        persisted_at=evaluated,
        market_session_date=session_date,
        market_session_status=session_status.value,
        age_seconds=max(0, int((evaluated - min(effective_times)).total_seconds())),
        last_refresh_attempt_at=evaluated,
        last_successful_refresh_at=evaluated,
        next_refresh_at=SessionRefreshSchedule(calendar).next_slot(evaluated).scheduled_at,
        data_advanced_on_last_refresh=(
            previous_observed is None or observed > previous_observed
        ),
        freshness_status=(
            "live" if freshness is FreshnessStatus.FRESH else freshness.value
        ),
        usability_status=usability.status.value,
        usability_reason=usability.reason,
        warning_codes=tuple(
            sorted({code.value for decision in decisions for code in decision.warning_codes})
        ),
        acquisition_started_at=min(recorded_times),
        acquisition_completed_at=max(recorded_times),
        input_time_skew_seconds=max(
            0, int((max(effective_times) - min(effective_times)).total_seconds())
        ),
    )


def get_state(
    repository: LatestResultRepository,
    *,
    strategy_id: str | None = None,
    symbol: str | None = None,
) -> tuple[UniversalScreeningResult, ...]:
    if strategy_id is not None and symbol is not None:
        row = repository.get_one(strategy_id, symbol)
        return (row.to_result(),) if row is not None else ()
    if strategy_id is not None:
        return tuple(row.to_result() for row in repository.get_for_signal(strategy_id))
    return tuple(row.to_result() for row in repository.get_all())


def refresh(
    registry: StrategyRegistry[UniversalScreeningResult],
    repository: LatestResultRepository,
    clock: Clock,
    *,
    strategy_id: str,
    symbol: str,
    fulfillment_by_subject: Mapping[str, CapabilityFulfillmentService],
) -> UniversalScreeningResult:
    """Recompute exactly one strategy against exactly one subject via the
    existing migrated adapters, then persist and return the new state --
    never a whole-universe or whole-strategy-set refresh.
    """
    previous = repository.get_one(strategy_id, symbol)
    (execution_result,) = run_strategies(
        registry,
        clock,
        subjects=(symbol,),
        strategy_ids=(strategy_id,),
        fulfillment_by_subject=fulfillment_by_subject,
    )
    if (
        execution_result.status is ExecutionStatus.ADAPTER_EXCEPTION
        or execution_result.result is None
    ):
        raise RuntimeError(
            f"refresh({strategy_id!r}, {symbol!r}) failed unexpectedly: "
            f"{execution_result.error_detail}"
        )
    result = execution_result.result
    fulfillment = fulfillment_by_subject.get(symbol)
    temporal = (
        None
        if fulfillment is None
        else _temporal_metadata(
            registry, strategy_id, result.observed_at, fulfillment, previous
        )
    )
    if temporal is not None:
        result = replace(result, temporal=temporal)
    repository.upsert(UniversalSignalRow.from_result(result))
    return result


def record_opportunity_observation(
    registry: StrategyRegistry[UniversalScreeningResult],
    history_repository: ObservationHistoryRepository,
    result: UniversalScreeningResult,
    *,
    recommended_action: RecommendedAction,
) -> OpportunityObservation:
    """Persistent opportunity evolution (SPRINT-009R/EPIC-R3): given a
    result already produced by run_strategies()/refresh() (this function
    never executes a strategy itself), record one more durable observation
    of that result's own opportunity. Call this after refresh() for any
    strategy whose contract declares StrategyCapability.LIFECYCLE -- refresh()
    itself never calls this, so a caller with no interest in history pays
    nothing for it.
    """
    contract = registry.contract_for(result.strategy_id)
    observation = observe_transition(contract, result, recommended_action=recommended_action)
    history_repository.append(observation)
    return observation
