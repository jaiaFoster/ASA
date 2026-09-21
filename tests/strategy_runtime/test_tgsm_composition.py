from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal

import pytest

from analytics.cross_sectional_ranking import EligibilityState
from analytics.features import DerivedFact, DerivedFactQualityStatus, DerivedFactSet
from domain import CanonicalFact, CanonicalInstrumentIdentity, Confidence, Provenance
from screening.universe_membership import (
    EffectiveUniverseMember,
    EffectiveUniverseMembership,
)
from strategies.tgsm_composition import SectorFacts, compose_s001_selection
from strategy_runtime.adapters.tgsm import S001_CONTRACT
from strategy_runtime.adapters.tgsm_subject_first import (
    build_s001_cohort_registry,
    build_s001_subject_preparation_registry,
    evaluate_s001_cohort,
)
from strategy_runtime.cohort_composition import compose_cohort_knowledge, evaluate_cohort
from strategy_runtime.contract import StructureKind
from strategy_runtime.execution import ExecutionStatus, run_strategies
from strategy_runtime.knowledge import ReadOnlyStrategyInput

NOW = datetime(2026, 9, 1, tzinfo=UTC)


def _subject(symbol: str) -> CanonicalInstrumentIdentity:
    return CanonicalInstrumentIdentity("symbol", symbol)


MEMBERSHIP = EffectiveUniverseMembership(
    "sectors",
    "fixture",
    "https://example.test/sectors",
    tuple(
        EffectiveUniverseMember(_subject(symbol), "sector", date(2020, 1, 1), None, "fixture")
        for symbol in ("XLE", "XLF", "XLK", "XLV")
    ),
)


def _facts(symbol: str, momentum: str, observation: str = "110") -> SectorFacts:
    return SectorFacts(
        _subject(symbol),
        Decimal(momentum),
        f"trailing_12m_total_return:{symbol}",
        Decimal(observation),
        f"close:{symbol}",
        Decimal("100"),
        f"sma_10m_completed_months:{symbol}",
        NOW,
    )


def _knowledge(item: SectorFacts) -> ReadOnlyStrategyInput[SectorFacts]:
    canonical = CanonicalFact(
        item.trend_observation_fact_id or "missing",
        1,
        "completed_month_total_return_observation",
        item.trend_observation,
        Confidence(1.0),
        Provenance(("obs",), ("fixture",), "fixture", (), NOW),
        NOW,
        NOW,
    )
    derived = DerivedFactSet(
        (
            DerivedFact(
                item.trailing_return_fact_id or "missing_return",
                item.trailing_return or Decimal(0),
                "decimal",
                "1.0.0",
                NOW,
                (),
                DerivedFactQualityStatus.VALID,
            ),
            DerivedFact(
                item.sma_10m_fact_id or "missing_sma",
                item.sma_10m or Decimal(0),
                "price",
                "1.0.0",
                NOW,
                (),
                DerivedFactQualityStatus.VALID,
            ),
        )
    )
    return ReadOnlyStrategyInput(
        f"snapshot:{item.subject.value}",
        f"digest:{item.subject.value}",
        NOW,
        (canonical,),
        derived,
        item,
    )


def test_s001_contract_declares_bars_without_options_or_lifecycle() -> None:
    assert S001_CONTRACT.strategy_id == "S001"
    assert S001_CONTRACT.structure is StructureKind.NONE
    assert not S001_CONTRACT.capabilities
    assert len(S001_CONTRACT.required_capabilities()) == 1
    binding = build_s001_subject_preparation_registry(NOW).binding_for("S001")
    assert len(binding.consumer.bootstrap_demands) == 1
    assert binding.consumer.bootstrap_demands[0].capability.value == "historical_bars_v1"


def test_s001_ranks_before_trend_and_preserves_failed_selected_sector() -> None:
    facts = (
        _facts("XLE", "0.40", "90"),
        _facts("XLF", "0.30"),
        _facts("XLK", "0.20", "100"),
        _facts("XLV", "0.10"),
    )
    cohort = compose_cohort_knowledge(
        {item.subject.value: _knowledge(item) for item in facts},
        decision_time=NOW,
    )
    selected = evaluate_cohort(cohort, lambda value: evaluate_s001_cohort(value, MEMBERSHIP))
    assert [item.subject.value for item in selected.selected] == ["XLE", "XLF", "XLK"]
    assert [item.trend.state for item in selected.selected] == [
        EligibilityState.FAIL,
        EligibilityState.PASS,
        EligibilityState.FAIL,
    ]
    assert selected.unknown_reason is None

    class _Clock:
        def now(self) -> datetime:
            return NOW

    registry = build_s001_cohort_registry(cohort, MEMBERSHIP)
    (executed,) = run_strategies(registry, _Clock(), subjects=(MEMBERSHIP.universe_id,))
    assert executed.status is ExecutionStatus.COMPLETED
    assert executed.result == selected


def test_missing_eligible_return_cannot_be_economic_bottom_rank() -> None:
    selected = compose_s001_selection(
        tuple(item.instrument for item in MEMBERSHIP.eligible_members(NOW.date())),
        (_facts("XLE", "0.4"), _facts("XLF", "0.3"), _facts("XLK", "0.2")),
        decision_time=NOW,
    )
    assert selected.unknown_reason == "incomplete_sector_returns"
    assert not selected.selected
    assert selected.ranking is not None
    assert selected.ranking.unrankable[0].subject == _subject("XLV")


def test_pre_inception_member_is_not_required() -> None:
    early = datetime(2019, 9, 1, tzinfo=UTC)
    future = EffectiveUniverseMembership(
        "future",
        "fixture",
        "https://example.test/future",
        (EffectiveUniverseMember(_subject("XLC"), "sector", date(2020, 1, 1), None, "fixture"),),
    )
    selected = compose_s001_selection(
        tuple(item.instrument for item in future.eligible_members(early.date())),
        (),
        decision_time=early,
    )
    assert selected.eligible_subjects == ()
    assert selected.unknown_reason == "incomplete_sector_returns"


def test_cohort_rejects_mixed_effective_times() -> None:
    item = _facts("XLE", "0.4")
    later = ReadOnlyStrategyInput(
        "snapshot", "digest", datetime(2026, 9, 2, tzinfo=UTC), (), DerivedFactSet(()), item
    )
    with pytest.raises(ValueError, match="one effective time"):
        compose_cohort_knowledge({"XLE": later}, decision_time=NOW)
