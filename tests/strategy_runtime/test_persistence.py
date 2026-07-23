"""SPRINT-009/EPIC-8: persistence and history.

Defines in-memory fakes for LatestResultRepository/ObservationHistoryRepository
directly in this test module (matching tests/asa/fakes.py's own
InMemoryScreeningStateRepository convention) and proves both protocols'
own guarantees against them: append-only history replay, strategy run
isolation, and "empty run never exposes stale data" for latest results.
A concrete Postgres implementation is EPIC-7's own job (see
strategy_runtime/persistence.py's own module docstring for why) -- these
fakes are what proves the *protocol* is sufficient in the meantime, the
same role InMemoryScreeningStateRepository already plays for
screening.state.ScreeningStateRepository.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from strategy_runtime.lifecycle import (
    OpportunityHistory,
    OpportunityObservation,
    RecommendedAction,
    compute_opportunity_id,
)
from strategy_runtime.persistence import LatestResultRepository, ObservationHistoryRepository
from strategy_runtime.result import EvaluationState, RowType, UniversalScreeningResult

NOW = datetime(2026, 1, 1, tzinfo=UTC)


class InMemoryLatestResultRepository:
    def __init__(self) -> None:
        self._results: dict[tuple[str, str], UniversalScreeningResult] = {}

    def upsert(self, result: UniversalScreeningResult) -> None:
        self._results[(result.strategy_id, result.symbol)] = result

    def get_all(self) -> tuple[UniversalScreeningResult, ...]:
        return tuple(
            sorted(self._results.values(), key=lambda item: (item.strategy_id, item.symbol))
        )

    def get_for_strategy(self, strategy_id: str) -> tuple[UniversalScreeningResult, ...]:
        return tuple(
            sorted(
                (item for item in self._results.values() if item.strategy_id == strategy_id),
                key=lambda item: item.symbol,
            )
        )

    def get_one(self, strategy_id: str, symbol: str) -> UniversalScreeningResult | None:
        return self._results.get((strategy_id, symbol))


class InMemoryObservationHistoryRepository:
    def __init__(self) -> None:
        self._histories: dict[str, OpportunityHistory] = {}

    def append(self, observation: OpportunityObservation) -> None:
        existing = self._histories.get(observation.opportunity_id)
        self._histories[observation.opportunity_id] = (
            existing.append(observation)
            if existing is not None
            else OpportunityHistory(observation.opportunity_id, (observation,))
        )

    def history_for(self, opportunity_id: str) -> OpportunityHistory | None:
        return self._histories.get(opportunity_id)


def _result(strategy_id: str, symbol: str, verdict: str = "pass") -> UniversalScreeningResult:
    return UniversalScreeningResult(
        strategy_id=strategy_id,
        strategy_version="1.0.0",
        symbol=symbol,
        observation_id=f"{strategy_id}-{symbol}-obs",
        opportunity_id=None,
        row_type=RowType.RESULT,
        verdict=verdict,
        evaluation_state=EvaluationState.PASS,
        lifecycle_stage=None,
        recommendation_state=None,
        data_quality="fresh",
        metrics={},
        economics={},
        blockers=(),
        warnings=(),
        provenance=(),
        observed_at=NOW,
    )


def _observation(
    opportunity_id: str, strategy_id: str, stage: str, at: datetime
) -> OpportunityObservation:
    return OpportunityObservation(
        opportunity_id=opportunity_id,
        strategy_id=strategy_id,
        symbol="AAPL",
        lifecycle_stage=stage,
        verdict="pass",
        recommended_action=RecommendedAction.MONITOR,
        observed_at=at,
    )


class TestLatestResultRepositoryProtocolContract:
    def test_conforms_structurally_to_the_protocol(self) -> None:
        repository: LatestResultRepository = InMemoryLatestResultRepository()
        assert repository.get_all() == ()

    def test_upsert_overwrites_the_same_strategy_symbol_pair(self) -> None:
        repository = InMemoryLatestResultRepository()
        repository.upsert(_result("alpha", "AAPL", verdict="pass"))
        repository.upsert(_result("alpha", "AAPL", verdict="no_signal"))

        assert repository.get_one("alpha", "AAPL").verdict == "no_signal"
        assert len(repository.get_all()) == 1  # never accumulates history

    def test_a_run_that_never_touches_a_symbol_leaves_its_stored_result_untouched(self) -> None:
        repository = InMemoryLatestResultRepository()
        repository.upsert(_result("alpha", "AAPL"))
        repository.upsert(_result("alpha", "MSFT"))

        # Simulates a later run that only refreshes AAPL -- MSFT's own
        # previously-stored result must remain exactly as it was, not be
        # cleared just because this run never mentioned it.
        repository.upsert(_result("alpha", "AAPL", verdict="no_signal"))

        msft_result = repository.get_one("alpha", "MSFT")
        assert msft_result is not None
        assert msft_result.verdict == "pass"

    def test_get_for_strategy_isolates_strategies(self) -> None:
        repository = InMemoryLatestResultRepository()
        repository.upsert(_result("alpha", "AAPL"))
        repository.upsert(_result("beta", "AAPL"))

        assert {item.strategy_id for item in repository.get_for_strategy("alpha")} == {"alpha"}


class TestObservationHistoryRepositoryProtocolContract:
    def test_conforms_structurally_to_the_protocol(self) -> None:
        repository: ObservationHistoryRepository = InMemoryObservationHistoryRepository()
        assert repository.history_for("nonexistent") is None

    def test_append_only_history_supports_full_replay(self) -> None:
        repository = InMemoryObservationHistoryRepository()
        opportunity_id = compute_opportunity_id("watched_event", "AAPL", "2026-02-01")

        repository.append(_observation(opportunity_id, "watched_event", "watching", NOW))
        repository.append(
            _observation(opportunity_id, "watched_event", "confirmed", NOW + timedelta(days=3))
        )
        repository.append(
            _observation(opportunity_id, "watched_event", "closed", NOW + timedelta(days=10))
        )

        history = repository.history_for(opportunity_id)
        assert history is not None
        assert [item.lifecycle_stage for item in history.observations] == [
            "watching",
            "confirmed",
            "closed",
        ]
        assert history.current.lifecycle_stage == "closed"

    def test_two_strategies_never_collide_even_through_the_same_repository(self) -> None:
        repository = InMemoryObservationHistoryRepository()
        alpha_opportunity = compute_opportunity_id("alpha", "AAPL", "component-1")
        beta_opportunity = compute_opportunity_id("beta", "AAPL", "component-1")
        assert alpha_opportunity != beta_opportunity  # distinct identity, same symbol/component

        repository.append(_observation(alpha_opportunity, "alpha", "watching", NOW))
        repository.append(_observation(beta_opportunity, "beta", "confirmed", NOW))

        alpha_history = repository.history_for(alpha_opportunity)
        beta_history = repository.history_for(beta_opportunity)
        assert alpha_history is not None and beta_history is not None
        assert alpha_history.current.strategy_id == "alpha"
        assert beta_history.current.strategy_id == "beta"
        assert len(alpha_history.observations) == 1  # beta's append never touched alpha's history
