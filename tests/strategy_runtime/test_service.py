"""SPRINT-009/EPIC-9: strategy_runtime.service.get_state()/refresh()
orchestration, against an in-memory LatestResultRepository fake -- the
same role tests/screening/test_service.py already plays for
screening.service's own get_state()/refresh(). Real Postgres composition
is proven separately in
tests/asa/test_universal_screening_service_postgres_integration.py.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

import pytest

from strategy_runtime import (
    NO_LIFECYCLE,
    DataRequirement,
    LifecycleDeclaration,
    LifecycleModel,
    OutputKind,
    RequirementCategory,
    RuntimeContext,
    StrategyContract,
    StrategyRegistry,
    StructureKind,
    UniversalScreeningResult,
    compute_observation_id,
)
from strategy_runtime.lifecycle import (
    OpportunityHistory,
    OpportunityObservation,
    RecommendedAction,
    compute_opportunity_id,
)
from strategy_runtime.persistence import UniversalSignalRow, replay_opportunity_history
from strategy_runtime.result import EvaluationState, RowType
from strategy_runtime.service import get_state, record_opportunity_observation, refresh


@dataclass
class _FixedClock:
    value: datetime

    def now(self) -> datetime:
        return self.value


class InMemoryLatestResultRepository:
    def __init__(self) -> None:
        self._rows: dict[tuple[str, str], UniversalSignalRow] = {}

    def upsert(self, row: UniversalSignalRow) -> None:
        self._rows[(row.signal_id, row.symbol)] = row

    def get_all(self) -> tuple[UniversalSignalRow, ...]:
        return tuple(sorted(self._rows.values(), key=lambda item: (item.signal_id, item.symbol)))

    def get_for_signal(self, signal_id: str) -> tuple[UniversalSignalRow, ...]:
        return tuple(
            sorted(
                (item for item in self._rows.values() if item.signal_id == signal_id),
                key=lambda item: item.symbol,
            )
        )

    def get_one(self, signal_id: str, symbol: str) -> UniversalSignalRow | None:
        return self._rows.get((signal_id, symbol))


def _contract(strategy_id: str) -> StrategyContract:
    return StrategyContract(
        strategy_id=strategy_id,
        version="1.0.0",
        category="test",
        description="A test contract.",
        requirements=(DataRequirement(RequirementCategory.CUSTOM, identifier="none"),),
        lifecycle=NO_LIFECYCLE,
        structure=StructureKind.NONE,
        outputs=(OutputKind.METRICS,),
    )


def _succeeding_adapter(context: RuntimeContext) -> UniversalScreeningResult:
    return UniversalScreeningResult(
        strategy_id=context.contract.strategy_id,
        strategy_version=context.contract.version,
        symbol=context.subject,
        observation_id=f"{context.run_id}-obs",
        opportunity_id=None,
        row_type=RowType.RESULT,
        verdict="pass",
        evaluation_state=EvaluationState.PASS,
        lifecycle_stage=None,
        recommendation_state=None,
        data_quality=None,
        metrics={"strategy_native_score": "1"},
        economics={},
        blockers=(),
        warnings=(),
        provenance=(),
        observed_at=context.clock.now(),
    )


def _failing_adapter(context: RuntimeContext) -> UniversalScreeningResult:
    raise RuntimeError("deliberate adapter failure")


def _lifecycle_contract(strategy_id: str) -> StrategyContract:
    return StrategyContract(
        strategy_id=strategy_id,
        version="1.0.0",
        category="test",
        description="A test lifecycle-tracking contract.",
        requirements=(DataRequirement(RequirementCategory.CUSTOM, identifier="none"),),
        lifecycle=LifecycleDeclaration(
            LifecycleModel.OPPORTUNITY,
            supported_states=("watching", "confirmed"),
            observation_type="event",
        ),
        structure=StructureKind.NONE,
        outputs=(OutputKind.METRICS, OutputKind.LIFECYCLE),
    )


def _lifecycle_result(
    strategy_id: str, stage: str, run_id: str, observed_at: datetime
) -> UniversalScreeningResult:
    return UniversalScreeningResult(
        strategy_id=strategy_id,
        strategy_version="1.0.0",
        symbol="AAPL",
        observation_id=compute_observation_id(run_id, strategy_id, "AAPL"),
        opportunity_id=compute_opportunity_id(strategy_id, "AAPL", "event-1"),
        row_type=RowType.RESULT,
        verdict="pass",
        evaluation_state=EvaluationState.PASS,
        lifecycle_stage=stage,
        recommendation_state=None,
        data_quality=None,
        metrics={},
        economics={},
        blockers=(),
        warnings=(),
        provenance=(),
        observed_at=observed_at,
    )


class InMemoryObservationHistoryRepository:
    def __init__(self) -> None:
        self._history: dict[str, OpportunityHistory] = {}

    def append(self, observation: OpportunityObservation) -> None:
        existing = self._history.get(observation.opportunity_id)
        self._history[observation.opportunity_id] = (
            existing.append(observation)
            if existing is not None
            else OpportunityHistory(observation.opportunity_id, (observation,))
        )

    def history_for(self, opportunity_id: str) -> OpportunityHistory | None:
        return self._history.get(opportunity_id)


class TestRefresh:
    def test_refresh_persists_and_returns_the_result(self) -> None:
        registry = StrategyRegistry(((_contract("alpha"), _succeeding_adapter),))
        repository = InMemoryLatestResultRepository()
        clock = _FixedClock(datetime(2026, 1, 1, tzinfo=UTC))

        result = refresh(
            registry,
            repository,
            clock,
            strategy_id="alpha",
            symbol="AAPL",
            fulfillment_by_subject={},
        )

        assert result.strategy_id == "alpha"
        assert repository.get_one("alpha", "AAPL").to_result() == result

    def test_refresh_raises_on_an_unexpected_adapter_exception(self) -> None:
        registry = StrategyRegistry(((_contract("alpha"), _failing_adapter),))
        repository = InMemoryLatestResultRepository()
        clock = _FixedClock(datetime(2026, 1, 1, tzinfo=UTC))

        with pytest.raises(RuntimeError, match="failed unexpectedly"):
            refresh(
                registry,
                repository,
                clock,
                strategy_id="alpha",
                symbol="AAPL",
                fulfillment_by_subject={},
            )
        assert repository.get_one("alpha", "AAPL") is None  # nothing persisted on failure


class TestGetState:
    def test_get_state_reads_through_the_repository_only(self) -> None:
        repository = InMemoryLatestResultRepository()
        registry = StrategyRegistry(((_contract("alpha"), _succeeding_adapter),))
        clock = _FixedClock(datetime(2026, 1, 1, tzinfo=UTC))
        refresh(
            registry,
            repository,
            clock,
            strategy_id="alpha",
            symbol="AAPL",
            fulfillment_by_subject={},
        )

        assert len(get_state(repository)) == 1
        assert len(get_state(repository, strategy_id="alpha")) == 1
        assert get_state(repository, strategy_id="alpha", symbol="AAPL")[0].strategy_id == "alpha"
        assert get_state(repository, strategy_id="alpha", symbol="MSFT") == ()

    def test_empty_repository_returns_empty(self) -> None:
        repository = InMemoryLatestResultRepository()
        assert get_state(repository) == ()


class TestRecordOpportunityObservation:
    """SPRINT-009R/EPIC-R3: persistent opportunity evolution -- opt-in,
    separate from refresh(), never invoked automatically.
    """

    def test_recorded_observations_replay_through_history_for(self) -> None:
        registry = StrategyRegistry(((_lifecycle_contract("watched"), _succeeding_adapter),))
        history_repository = InMemoryObservationHistoryRepository()
        start = datetime(2026, 1, 1, tzinfo=UTC)

        watching = record_opportunity_observation(
            registry,
            history_repository,
            _lifecycle_result("watched", "watching", "run-1", start),
            recommended_action=RecommendedAction.MONITOR,
        )
        confirmed = record_opportunity_observation(
            registry,
            history_repository,
            _lifecycle_result("watched", "confirmed", "run-2", start),
            recommended_action=RecommendedAction.ENTER,
        )

        history = replay_opportunity_history(history_repository, watching.opportunity_id)

        assert history is not None
        assert history.observations == (watching, confirmed)

    def test_replay_of_an_unrecorded_opportunity_is_none(self) -> None:
        history_repository = InMemoryObservationHistoryRepository()
        assert replay_opportunity_history(history_repository, "never-recorded") is None
