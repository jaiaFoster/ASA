"""SPRINT-009/EPIC-1: universal strategy execution pipeline.

Uses only fake, generically-named strategies ("alpha", "beta", "gamma") --
proving the runtime and its tests never need to know a real strategy_id
(forward_factor, earnings_calendar, skew_momentum) to be exercised
end to end, exactly matching EPIC-1's own acceptance criterion that the
runtime contains no strategy-named conditional.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

import pytest

from strategy_runtime import (
    NO_LIFECYCLE,
    DataRequirement,
    ExecutionStatus,
    OutputKind,
    RequirementCategory,
    RuntimeContext,
    RuntimeExecutionSummary,
    StrategyContract,
    StrategyRegistry,
    StructureKind,
    UnknownStrategyIdError,
    run_strategies,
)


@dataclass
class _IncrementingClock:
    """Advances by one second on every call to now() -- lets tests observe
    a real, non-zero, deterministic duration_seconds without depending on
    actual wall-clock time.
    """

    current: datetime

    def now(self) -> datetime:
        value = self.current
        self.current = self.current + timedelta(seconds=1)
        return value


def _contract(strategy_id: str, *, lifecycle_output: bool = False) -> StrategyContract:
    from strategy_runtime.contract import LifecycleDeclaration, LifecycleModel

    lifecycle = (
        LifecycleDeclaration(
            LifecycleModel.OPPORTUNITY, supported_states=("open", "closed"), observation_type="x"
        )
        if lifecycle_output
        else NO_LIFECYCLE
    )
    outputs = (
        (OutputKind.METRICS, OutputKind.LIFECYCLE) if lifecycle_output else (OutputKind.METRICS,)
    )
    return StrategyContract(
        strategy_id=strategy_id,
        version="1.0.0",
        category="test",
        description="A test contract.",
        requirements=(DataRequirement(RequirementCategory.CUSTOM, identifier="none"),),
        lifecycle=lifecycle,
        structure=StructureKind.NONE,
        outputs=outputs,
    )


def _succeeding_adapter(context: RuntimeContext) -> str:
    return f"{context.contract.strategy_id}:{context.subject}:{context.run_id[:8]}"


def _failing_adapter(context: RuntimeContext) -> str:
    raise RuntimeError("deliberate adapter failure")


class TestRunStrategies:
    def test_executes_every_registered_strategy_against_every_subject(self) -> None:
        registry = StrategyRegistry(
            ((_contract("alpha"), _succeeding_adapter), (_contract("beta"), _succeeding_adapter))
        )
        clock = _IncrementingClock(datetime(2026, 1, 1, tzinfo=UTC))

        results = run_strategies(registry, clock, subjects=("AAPL", "MSFT"))

        assert len(results) == 4  # 2 strategies x 2 subjects
        pairs = {(item.strategy_id, item.subject) for item in results}
        assert pairs == {("alpha", "AAPL"), ("alpha", "MSFT"), ("beta", "AAPL"), ("beta", "MSFT")}
        assert all(item.status is ExecutionStatus.COMPLETED for item in results)

    def test_deterministically_ordered_strategy_major_subject_minor(self) -> None:
        registry = StrategyRegistry(
            ((_contract("beta"), _succeeding_adapter), (_contract("alpha"), _succeeding_adapter))
        )
        clock = _IncrementingClock(datetime(2026, 1, 1, tzinfo=UTC))

        results = run_strategies(registry, clock, subjects=("MSFT", "AAPL"))

        assert [(item.strategy_id, item.subject) for item in results] == [
            ("alpha", "AAPL"),
            ("alpha", "MSFT"),
            ("beta", "AAPL"),
            ("beta", "MSFT"),
        ]

    def test_one_adapters_exception_never_prevents_another_strategy_from_executing(self) -> None:
        registry = StrategyRegistry(
            (
                (_contract("failing"), _failing_adapter),
                (_contract("succeeding"), _succeeding_adapter),
            )
        )
        clock = _IncrementingClock(datetime(2026, 1, 1, tzinfo=UTC))

        results = run_strategies(registry, clock, subjects=("AAPL",))

        by_id = {item.strategy_id: item for item in results}
        assert by_id["failing"].status is ExecutionStatus.ADAPTER_EXCEPTION
        assert by_id["failing"].result is None
        assert by_id["failing"].error_detail is not None
        assert "RuntimeError" in by_id["failing"].error_detail
        assert by_id["succeeding"].status is ExecutionStatus.COMPLETED
        assert by_id["succeeding"].result is not None

    def test_no_credential_or_internal_exception_detail_leaks_beyond_the_type_name(self) -> None:
        def _adapter_with_a_secret_in_the_message(context: RuntimeContext) -> str:
            raise ValueError("token=sandbox-secret-token")

        registry = StrategyRegistry(((_contract("alpha"), _adapter_with_a_secret_in_the_message),))
        clock = _IncrementingClock(datetime(2026, 1, 1, tzinfo=UTC))

        (result,) = run_strategies(registry, clock, subjects=("AAPL",))

        assert result.error_detail == "ValueError: unhandled adapter exception"
        assert "sandbox-secret-token" not in (result.error_detail or "")

    def test_duration_seconds_reflects_the_injected_clock(self) -> None:
        registry = StrategyRegistry(((_contract("alpha"), _succeeding_adapter),))
        clock = _IncrementingClock(datetime(2026, 1, 1, tzinfo=UTC))

        (result,) = run_strategies(registry, clock, subjects=("AAPL",))

        assert result.duration_seconds == 1.0  # one now() call before, one after

    def test_deterministic_run_id_for_identical_inputs(self) -> None:
        registry = StrategyRegistry(((_contract("alpha"), _succeeding_adapter),))
        fixed_instant = datetime(2026, 1, 1, tzinfo=UTC)

        first = run_strategies(
            registry, _IncrementingClock(fixed_instant), subjects=("AAPL",)
        )
        second = run_strategies(
            registry, _IncrementingClock(fixed_instant), subjects=("AAPL",)
        )

        assert first[0].run_id == second[0].run_id

    def test_requesting_an_unregistered_strategy_id_raises_before_any_execution(self) -> None:
        calls: list[str] = []

        def _tracking_adapter(context: RuntimeContext) -> str:
            calls.append(context.subject)
            return "ok"

        registry = StrategyRegistry(((_contract("alpha"), _tracking_adapter),))
        clock = _IncrementingClock(datetime(2026, 1, 1, tzinfo=UTC))

        with pytest.raises(UnknownStrategyIdError):
            run_strategies(
                registry, clock, subjects=("AAPL",), strategy_ids=("alpha", "nonexistent")
            )
        assert calls == []  # alpha's adapter never ran either -- fail before any side effect

    def test_empty_subjects_is_rejected(self) -> None:
        registry = StrategyRegistry(((_contract("alpha"), _succeeding_adapter),))
        clock = _IncrementingClock(datetime(2026, 1, 1, tzinfo=UTC))

        with pytest.raises(ValueError, match="at least one subject"):
            run_strategies(registry, clock, subjects=())

    def test_strategy_ids_filter_narrows_execution_to_the_requested_subset(self) -> None:
        registry = StrategyRegistry(
            (
                (_contract("alpha"), _succeeding_adapter),
                (_contract("beta"), _succeeding_adapter),
                (_contract("gamma"), _succeeding_adapter),
            )
        )
        clock = _IncrementingClock(datetime(2026, 1, 1, tzinfo=UTC))

        results = run_strategies(registry, clock, subjects=("AAPL",), strategy_ids=("gamma",))

        assert {item.strategy_id for item in results} == {"gamma"}


class TestRuntimeExecutionSummary:
    def test_counts_completed_and_failed_from_real_results(self) -> None:
        registry = StrategyRegistry(
            (
                (_contract("failing"), _failing_adapter),
                (_contract("succeeding"), _succeeding_adapter),
            )
        )
        clock = _IncrementingClock(datetime(2026, 1, 1, tzinfo=UTC))
        results = run_strategies(registry, clock, subjects=("AAPL",))

        summary = RuntimeExecutionSummary.from_results(results[0].run_id, results)

        assert summary.total == 2
        assert summary.completed == 1
        assert summary.failed == 1
        assert summary.total_duration_seconds == pytest.approx(2.0)
