"""SCREEN-006: sprint-level integration evidence.

Complements the per-ticket unit suites (test_registry.py, test_results.py,
test_runner.py, test_adapters.py, test_cli.py) with two pieces of evidence
SCREEN-006 specifically requires: one fixture-backed combined run using the
real target strategy adapters, and one failure-isolation run that breaks a
real adapter deliberately to prove the other two real strategies still
complete -- distinct from SCREEN-003's own isolation tests, which use fully
synthetic fixture adapters for every strategy.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

from screening.adapters import TARGET_STRATEGY_ADAPTERS, TARGET_STRATEGY_REGISTRY
from screening.clock import Clock
from screening.registry import ScreeningStrategyDefinition
from screening.results import ScreeningOutcomeStatus, ScreeningResult
from screening.runner import run_screening

AS_OF = datetime(2026, 7, 22, 16, 0, tzinfo=UTC)


@dataclass(frozen=True)
class FixedClock:
    def now(self) -> datetime:
        return AS_OF


def _broken_adapter(
    definition: ScreeningStrategyDefinition, clock: Clock, run_id: str
) -> ScreeningResult:
    raise RuntimeError("simulated adapter bug for failure-isolation evidence")


class TestOneFixtureBackedCombinedRun:
    def test_all_three_real_target_strategies_pass_together(self) -> None:
        results = run_screening(TARGET_STRATEGY_REGISTRY, TARGET_STRATEGY_ADAPTERS, FixedClock())
        assert len(results) == 3
        assert all(result.outcome_status is ScreeningOutcomeStatus.PASS for result in results)
        assert len({result.run_id for result in results}) == 1


class TestOneFailureIsolationRun:
    def test_a_broken_real_adapter_does_not_abort_the_other_two_real_strategies(self) -> None:
        adapters = dict(TARGET_STRATEGY_ADAPTERS)
        adapters["earnings_calendar"] = _broken_adapter

        results = run_screening(TARGET_STRATEGY_REGISTRY, adapters, FixedClock())

        by_id = {result.strategy_id: result for result in results}
        assert by_id["earnings_calendar"].outcome_status is ScreeningOutcomeStatus.STRATEGY_EXCEPTION
        assert by_id["earnings_calendar"].failure_detail is not None
        assert "simulated adapter bug" not in by_id["earnings_calendar"].failure_detail

        # The other two real adapters (unmodified, using the real manifests) still ran.
        assert by_id["forward_factor"].outcome_status is ScreeningOutcomeStatus.PASS
        assert by_id["forward_factor"].signal_classification == "PASS"
        assert by_id["skew_momentum"].outcome_status is ScreeningOutcomeStatus.PASS
        assert by_id["skew_momentum"].signal_classification == "PASS"

        assert len({result.run_id for result in results}) == 1
