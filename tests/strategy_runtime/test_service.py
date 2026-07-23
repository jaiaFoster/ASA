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
    OutputKind,
    RequirementCategory,
    RuntimeContext,
    StrategyContract,
    StrategyRegistry,
    StructureKind,
    UniversalScreeningResult,
)
from strategy_runtime.persistence import UniversalSignalRow
from strategy_runtime.result import EvaluationState, RowType
from strategy_runtime.service import get_state, refresh


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
