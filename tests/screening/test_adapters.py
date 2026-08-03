from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal

from screening.adapters import (
    TARGET_STRATEGY_ADAPTERS,
    TARGET_STRATEGY_DEFINITIONS,
    TARGET_STRATEGY_REGISTRY,
    run_earnings_calendar,
    run_forward_factor,
    run_skew_momentum,
)
from screening.results import ScreeningOutcomeStatus
from screening.runner import run_screening

AS_OF = datetime(2026, 7, 22, 16, 0, tzinfo=UTC)


@dataclass(frozen=True)
class FixedClock:
    fixed_at: datetime = AS_OF

    def now(self) -> datetime:
        return self.fixed_at


def _definition(strategy_id: str):
    return TARGET_STRATEGY_REGISTRY.get(strategy_id)


class TestForwardFactorAdapter:
    def test_produces_a_valid_pass_result(self) -> None:
        result = run_forward_factor(_definition("forward_factor"), FixedClock(), "run-1")
        assert result.strategy_id == "forward_factor"
        assert result.outcome_status is ScreeningOutcomeStatus.PASS
        assert result.signal_classification == "PASS"
        assert result.strategy_native_score is not None
        assert result.strategy_native_score > Decimal("0")
        assert result.explanation is not None
        assert dict(result.explanation.formula_versions)["forward_factor"] == "1.0.0"
        gates = dict(result.explanation.gate_results)
        assert gates["eligible"] is True
        assert gates["earnings_exclusion_gate"] is True
        assert gates["structure_constructible_gate"] is True
        assert gates["liquidity_gate"] is True
        facts = dict(result.explanation.canonical_facts)
        assert facts["selected_front_expiration"] == "2026-09-21"
        assert facts["selected_back_expiration"] == "2026-10-21"
        assert facts["confirmed_earnings_date_when_relevant"] is None

    def test_is_deterministic(self) -> None:
        first = run_forward_factor(_definition("forward_factor"), FixedClock(), "run-1")
        second = run_forward_factor(_definition("forward_factor"), FixedClock(), "run-1")
        assert first == second


class TestEarningsCalendarAdapter:
    def test_produces_a_valid_pass_result(self) -> None:
        result = run_earnings_calendar(_definition("earnings_calendar"), FixedClock(), "run-1")
        assert result.strategy_id == "earnings_calendar"
        assert result.outcome_status is ScreeningOutcomeStatus.PASS
        assert result.signal_classification == "PASS"
        assert result.strategy_native_score == Decimal("75")
        assert result.explanation is not None
        assert dict(result.explanation.named_derived_facts)["actual_gap_days"] == 30
        assert dict(result.explanation.formula_versions)["actual_gap_days"] == "1.0.0"
        assert dict(result.explanation.gate_results)["liquidity_acceptable"] is True
        facts = dict(result.explanation.canonical_facts)
        derived = dict(result.explanation.named_derived_facts)
        assert facts["earnings_date"] == "2026-08-05"
        assert facts["announcement_timing"] == "after_close"
        assert facts["selected_front_expiration"] == "2026-07-31"
        assert facts["selected_back_expiration"] == "2026-08-30"
        assert facts["volume_downgrade_reason"] == "NONE"
        assert derived["days_to_earnings"] == 14

    def test_is_deterministic(self) -> None:
        first = run_earnings_calendar(_definition("earnings_calendar"), FixedClock(), "run-1")
        second = run_earnings_calendar(_definition("earnings_calendar"), FixedClock(), "run-1")
        assert first == second


class TestSkewMomentumAdapter:
    def test_produces_a_valid_pass_result(self) -> None:
        result = run_skew_momentum(_definition("skew_momentum"), FixedClock(), "run-1")
        assert result.strategy_id == "skew_momentum"
        assert result.outcome_status is ScreeningOutcomeStatus.PASS
        assert result.signal_classification == "PASS"
        assert result.strategy_native_score is not None
        assert result.explanation is not None
        assert dict(result.explanation.gate_results)["bullish_core_gate"] is True
        assert dict(result.explanation.named_derived_facts)["call_skew_zscore"] == Decimal("-2.1")
        assert result.explanation.direction == "BULLISH"
        assert result.explanation.structure

    def test_is_deterministic(self) -> None:
        first = run_skew_momentum(_definition("skew_momentum"), FixedClock(), "run-1")
        second = run_skew_momentum(_definition("skew_momentum"), FixedClock(), "run-1")
        assert first == second


class TestTargetStrategyRegistration:
    def test_all_three_target_strategies_are_registered(self) -> None:
        assert TARGET_STRATEGY_REGISTRY.registered_ids() == (
            "earnings_calendar",
            "forward_factor",
            "skew_momentum",
        )

    def test_every_registered_definition_has_an_adapter(self) -> None:
        for strategy_id in TARGET_STRATEGY_REGISTRY.registered_ids():
            assert strategy_id in TARGET_STRATEGY_ADAPTERS

    def test_strategy_versions_are_pinned_from_the_manifests_not_hardcoded(self) -> None:
        from strategies import (
            EARNINGS_CALENDAR_MANIFEST,
            FORWARD_FACTOR_CALENDAR_MANIFEST,
            SKEW_MOMENTUM_VERTICAL_MANIFEST,
        )

        expected = {
            "forward_factor": FORWARD_FACTOR_CALENDAR_MANIFEST.strategy_version,
            "earnings_calendar": EARNINGS_CALENDAR_MANIFEST.strategy_version,
            "skew_momentum": SKEW_MOMENTUM_VERTICAL_MANIFEST.strategy_version,
        }
        for definition in TARGET_STRATEGY_DEFINITIONS:
            assert definition.strategy_version == expected[definition.strategy_id]


class TestFullRunThroughTheFramework:
    def test_all_three_target_strategies_run_through_run_screening(self) -> None:
        results = run_screening(TARGET_STRATEGY_REGISTRY, TARGET_STRATEGY_ADAPTERS, FixedClock())
        assert [result.strategy_id for result in results] == [
            "earnings_calendar",
            "forward_factor",
            "skew_momentum",
        ]
        assert all(result.outcome_status is ScreeningOutcomeStatus.PASS for result in results)
        assert len({result.run_id for result in results}) == 1

    def test_a_single_strategy_can_be_selected(self) -> None:
        (result,) = run_screening(
            TARGET_STRATEGY_REGISTRY,
            TARGET_STRATEGY_ADAPTERS,
            FixedClock(),
            strategy_ids=("forward_factor",),
        )
        assert result.strategy_id == "forward_factor"
