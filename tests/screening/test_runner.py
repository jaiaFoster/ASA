from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal

import pytest

from domain import EvidenceKind, EvidenceReference, MarketCapability
from screening.clock import Clock
from screening.errors import UnknownScreeningStrategyIdError
from screening.registry import ScreeningRegistry, ScreeningStrategyDefinition
from screening.results import ScreeningOutcomeStatus, ScreeningResult
from screening.runner import StrategyAdapterError, run_screening

AS_OF = datetime(2026, 7, 22, 16, 0, tzinfo=UTC)
EVIDENCE = (EvidenceReference(EvidenceKind.OBSERVATION, "screening:test-evidence"),)


@dataclass(frozen=True)
class FixedClock:
    fixed_at: datetime = AS_OF

    def now(self) -> datetime:
        return self.fixed_at


def _definition(strategy_id: str) -> ScreeningStrategyDefinition:
    return ScreeningStrategyDefinition(
        strategy_id, "1.0.0", f"asa.stonk.{strategy_id}", (MarketCapability.OPTION_CHAIN_V1,)
    )


def _pass_adapter(
    definition: ScreeningStrategyDefinition, clock: Clock, run_id: str
) -> ScreeningResult:
    return ScreeningResult(
        run_id,
        definition.strategy_id,
        definition.strategy_version,
        "figi:BBG000B9XRY4",
        clock.now(),
        ScreeningOutcomeStatus.PASS,
        "PASS",
        Decimal("1.25"),
        EVIDENCE,
        EVIDENCE,
        None,
        None,
    )


def _no_signal_adapter(
    definition: ScreeningStrategyDefinition, clock: Clock, run_id: str
) -> ScreeningResult:
    return ScreeningResult(
        run_id,
        definition.strategy_id,
        definition.strategy_version,
        "figi:BBG000B9XRY4",
        clock.now(),
        ScreeningOutcomeStatus.NO_SIGNAL,
        None,
        None,
        (),
        EVIDENCE,
        None,
        None,
    )


def _missing_data_adapter(
    definition: ScreeningStrategyDefinition, clock: Clock, run_id: str
) -> ScreeningResult:
    raise StrategyAdapterError(
        ScreeningOutcomeStatus.MISSING_DATA, "required OptionChain unavailable for subject"
    )


def _malformed_via_error_adapter(
    definition: ScreeningStrategyDefinition, clock: Clock, run_id: str
) -> ScreeningResult:
    raise StrategyAdapterError(ScreeningOutcomeStatus.MALFORMED_OUTPUT, "graph produced no checks")


def _malformed_via_bad_return_adapter(
    definition: ScreeningStrategyDefinition, clock: Clock, run_id: str
) -> ScreeningResult:
    return None  # type: ignore[return-value]


def _mismatched_identity_adapter(
    definition: ScreeningStrategyDefinition, clock: Clock, run_id: str
) -> ScreeningResult:
    return ScreeningResult(
        run_id,
        "wrong_strategy_id",
        definition.strategy_version,
        "figi:BBG000B9XRY4",
        clock.now(),
        ScreeningOutcomeStatus.PASS,
        "PASS",
        None,
        EVIDENCE,
        EVIDENCE,
        None,
        None,
    )


def _exception_adapter(
    definition: ScreeningStrategyDefinition, clock: Clock, run_id: str
) -> ScreeningResult:
    raise RuntimeError("boom -- unexpected adapter bug")


class TestRunScreeningFiveOutcomeCases:
    def test_pass(self) -> None:
        registry = ScreeningRegistry((_definition("forward_factor"),))
        (result,) = run_screening(registry, {"forward_factor": _pass_adapter}, FixedClock())
        assert result.outcome_status is ScreeningOutcomeStatus.PASS
        assert result.signal_classification == "PASS"
        assert result.strategy_native_score == Decimal("1.25")

    def test_no_signal(self) -> None:
        registry = ScreeningRegistry((_definition("skew_momentum"),))
        (result,) = run_screening(registry, {"skew_momentum": _no_signal_adapter}, FixedClock())
        assert result.outcome_status is ScreeningOutcomeStatus.NO_SIGNAL
        assert result.signal_classification is None
        assert result.strategy_native_score is None

    def test_missing_data(self) -> None:
        registry = ScreeningRegistry((_definition("earnings_calendar"),))
        (result,) = run_screening(
            registry, {"earnings_calendar": _missing_data_adapter}, FixedClock()
        )
        assert result.outcome_status is ScreeningOutcomeStatus.MISSING_DATA
        assert result.failure_detail == "required OptionChain unavailable for subject"
        assert result.signal_classification is None
        assert result.strategy_native_score is None

    def test_malformed_output_via_explicit_error(self) -> None:
        registry = ScreeningRegistry((_definition("forward_factor"),))
        (result,) = run_screening(
            registry, {"forward_factor": _malformed_via_error_adapter}, FixedClock()
        )
        assert result.outcome_status is ScreeningOutcomeStatus.MALFORMED_OUTPUT
        assert result.failure_detail == "graph produced no checks"

    def test_malformed_output_via_bad_return_type(self) -> None:
        registry = ScreeningRegistry((_definition("forward_factor"),))
        (result,) = run_screening(
            registry, {"forward_factor": _malformed_via_bad_return_adapter}, FixedClock()
        )
        assert result.outcome_status is ScreeningOutcomeStatus.MALFORMED_OUTPUT
        assert result.strategy_native_score is None

    def test_malformed_output_via_mismatched_identity(self) -> None:
        registry = ScreeningRegistry((_definition("forward_factor"),))
        (result,) = run_screening(
            registry, {"forward_factor": _mismatched_identity_adapter}, FixedClock()
        )
        assert result.outcome_status is ScreeningOutcomeStatus.MALFORMED_OUTPUT
        assert result.strategy_id == "forward_factor"

    def test_strategy_exception(self) -> None:
        registry = ScreeningRegistry((_definition("forward_factor"),))
        (result,) = run_screening(registry, {"forward_factor": _exception_adapter}, FixedClock())
        assert result.outcome_status is ScreeningOutcomeStatus.STRATEGY_EXCEPTION
        assert result.signal_classification is None
        assert result.strategy_native_score is None
        assert result.failure_detail is not None
        assert "RuntimeError" in result.failure_detail
        assert "boom" not in result.failure_detail  # raw exception text is not leaked


class TestFailureIsolation:
    def test_one_strategy_exception_does_not_abort_the_run(self) -> None:
        registry = ScreeningRegistry(
            (_definition("forward_factor"), _definition("earnings_calendar"), _definition("skew_momentum"))
        )
        adapters = {
            "forward_factor": _pass_adapter,
            "earnings_calendar": _exception_adapter,
            "skew_momentum": _no_signal_adapter,
        }
        results = run_screening(registry, adapters, FixedClock())
        statuses = {result.strategy_id: result.outcome_status for result in results}
        assert statuses == {
            "forward_factor": ScreeningOutcomeStatus.PASS,
            "earnings_calendar": ScreeningOutcomeStatus.STRATEGY_EXCEPTION,
            "skew_momentum": ScreeningOutcomeStatus.NO_SIGNAL,
        }

    def test_results_are_grouped_by_strategy_id_in_sorted_order(self) -> None:
        registry = ScreeningRegistry(
            (_definition("skew_momentum"), _definition("earnings_calendar"), _definition("forward_factor"))
        )
        adapters = {
            "forward_factor": _pass_adapter,
            "earnings_calendar": _no_signal_adapter,
            "skew_momentum": _no_signal_adapter,
        }
        results = run_screening(registry, adapters, FixedClock())
        assert [result.strategy_id for result in results] == [
            "earnings_calendar",
            "forward_factor",
            "skew_momentum",
        ]


class TestDeterminism:
    def test_identical_inputs_and_clock_produce_identical_output(self) -> None:
        registry = ScreeningRegistry((_definition("forward_factor"),))
        adapters = {"forward_factor": _pass_adapter}
        first = run_screening(registry, adapters, FixedClock())
        second = run_screening(registry, adapters, FixedClock())
        assert first == second
        assert first[0].run_id == second[0].run_id

    def test_different_as_of_produces_a_different_run_id(self) -> None:
        registry = ScreeningRegistry((_definition("forward_factor"),))
        adapters = {"forward_factor": _pass_adapter}
        first = run_screening(registry, adapters, FixedClock())
        second = run_screening(registry, adapters, FixedClock(fixed_at=AS_OF.replace(hour=17)))
        assert first[0].run_id != second[0].run_id


class TestUnknownStrategyRequests:
    def test_unregistered_strategy_id_raises(self) -> None:
        registry = ScreeningRegistry()
        with pytest.raises(UnknownScreeningStrategyIdError):
            run_screening(registry, {}, FixedClock(), strategy_ids=("does_not_exist",))

    def test_registered_but_missing_adapter_raises(self) -> None:
        registry = ScreeningRegistry((_definition("forward_factor"),))
        with pytest.raises(UnknownScreeningStrategyIdError):
            run_screening(registry, {}, FixedClock())

    def test_strategy_ids_filters_to_a_subset(self) -> None:
        registry = ScreeningRegistry((_definition("forward_factor"), _definition("skew_momentum")))
        adapters = {"forward_factor": _pass_adapter, "skew_momentum": _no_signal_adapter}
        results = run_screening(registry, adapters, FixedClock(), strategy_ids=("forward_factor",))
        assert [result.strategy_id for result in results] == ["forward_factor"]
