from __future__ import annotations

import json
from dataclasses import FrozenInstanceError
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

import pytest

from domain import CanonicalInstrumentIdentity
from screening.universe_membership import EffectiveUniverseMember, EffectiveUniverseMembership
from strategies.tgsm_composition import SectorFacts, compose_s001_selection
from strategies.tgsm_decision import (
    SLEEVE_WEIGHT,
    THREE_MONTH_TREASURY_TOTAL_RETURN,
    DefensiveAssetEvidence,
    build_s001_target_decision,
    deserialize_s001_target_decision,
    serialize_s001_target_decision,
)
from strategy_runtime.adapters.tgsm_subject_first import build_s001_cohort_registry
from strategy_runtime.cohort_composition import compose_cohort_knowledge
from strategy_runtime.decision_ledger import InMemoryDecisionLedger, replay_decision
from strategy_runtime.execution import ExecutionStatus, run_strategies
from tests.strategy_runtime.test_tgsm_composition import NOW as COHORT_TIME
from tests.strategy_runtime.test_tgsm_composition import _facts, _knowledge

NOW = datetime(2026, 8, 31, 21, tzinfo=UTC)
NEXT_SESSION = datetime(2026, 9, 1, 13, 30, tzinfo=UTC)


def _instrument(symbol: str) -> CanonicalInstrumentIdentity:
    return CanonicalInstrumentIdentity("symbol", symbol)


MEMBERSHIP = EffectiveUniverseMembership(
    "sectors",
    "fixture",
    "https://example.test/sectors",
    tuple(
        EffectiveUniverseMember(_instrument(symbol), "sector", date(2020, 1, 1), None, "fixture")
        for symbol in ("XLE", "XLF", "XLK", "XLV")
    ),
)


def _fact(symbol: str, momentum: str, trend_value: str) -> SectorFacts:
    return SectorFacts(
        _instrument(symbol),
        Decimal(momentum),
        f"return:{symbol}",
        Decimal(trend_value),
        f"observation:{symbol}",
        Decimal("100"),
        f"sma:{symbol}",
        NOW,
    )


def _selection():
    return compose_s001_selection(
        tuple(item.instrument for item in MEMBERSHIP.eligible_members(NOW.date())),
        (
            _fact("XLE", "0.40", "90"),
            _fact("XLF", "0.30", "110"),
            _fact("XLK", "0.20", "110"),
            _fact("XLV", "0.10", "110"),
        ),
        decision_time=NOW,
    )


def _defensive() -> DefensiveAssetEvidence:
    return DefensiveAssetEvidence(
        THREE_MONTH_TREASURY_TOTAL_RETURN,
        "treasury_total_return:2026-08",
        NOW,
    )


def test_three_equal_sleeves_failed_sector_routes_only_its_sleeve() -> None:
    decision = build_s001_target_decision(
        _selection(),
        defensive_evidence=_defensive(),
        next_eligible_session=lambda _: NEXT_SESSION,
    )
    assert len(decision.sleeves) == 3
    assert all(item.weight == SLEEVE_WEIGHT for item in decision.sleeves)
    assert sum(item.weight[0] for item in decision.sleeves) == 3
    assert {item.weight[1] for item in decision.sleeves} == {3}
    assert [item.target for item in decision.sleeves] == [
        THREE_MONTH_TREASURY_TOTAL_RETURN,
        _instrument("XLF"),
        _instrument("XLK"),
    ]
    assert decision.effective_time == NEXT_SESSION
    assert "treasury_total_return:2026-08" in decision.sleeves[0].evidence_fact_ids
    assert all(
        "treasury_total_return:2026-08" not in item.evidence_fact_ids
        for item in decision.sleeves[1:]
    )


def test_defensive_substitution_never_accepts_proxy_or_missing_evidence() -> None:
    with pytest.raises(ValueError, match="canonical research asset"):
        DefensiveAssetEvidence(_instrument("BIL"), "proxy", NOW)
    with pytest.raises(ValueError, match="canonical defensive evidence"):
        build_s001_target_decision(
            _selection(),
            defensive_evidence=None,
            next_eligible_session=lambda _: NEXT_SESSION,
        )


def test_next_session_must_follow_finalized_evidence() -> None:
    with pytest.raises(ValueError, match="after its evidence time"):
        build_s001_target_decision(
            _selection(),
            defensive_evidence=_defensive(),
            next_eligible_session=lambda value: value,
        )


def test_decision_identity_is_deterministic_and_ledger_is_provider_free() -> None:
    def build():
        return build_s001_target_decision(
            _selection(),
            defensive_evidence=_defensive(),
            next_eligible_session=lambda _: NEXT_SESSION,
        )

    first = build()
    second = build()
    assert first == second
    ledger: InMemoryDecisionLedger = InMemoryDecisionLedger()
    ledger.append(first)
    ledger.append(second)
    assert ledger.all() == (first,)
    assert replay_decision(ledger, first.decision_id) == first
    serialized = serialize_s001_target_decision(first)
    assert deserialize_s001_target_decision(serialized) == first
    tampered = json.loads(serialized)
    tampered["sleeves"][0]["target"][1] = "XLV"
    with pytest.raises(ValueError, match="identity"):
        deserialize_s001_target_decision(
            json.dumps(tampered, sort_keys=True, separators=(",", ":"))
        )
    with pytest.raises(FrozenInstanceError):
        first.strategy_version = "changed"  # type: ignore[misc]


def test_identity_changes_when_effective_session_changes() -> None:
    first = build_s001_target_decision(
        _selection(),
        defensive_evidence=_defensive(),
        next_eligible_session=lambda _: NEXT_SESSION,
    )
    later = build_s001_target_decision(
        _selection(),
        defensive_evidence=_defensive(),
        next_eligible_session=lambda _: NEXT_SESSION + timedelta(days=1),
    )
    assert first.decision_id != later.decision_id


def test_universal_runtime_to_target_ledger_replay_is_deterministic() -> None:
    facts = (
        _facts("XLE", "0.40", "90"),
        _facts("XLF", "0.30", "110"),
        _facts("XLK", "0.20", "110"),
        _facts("XLV", "0.10", "110"),
    )
    cohort = compose_cohort_knowledge(
        {item.subject.value: _knowledge(item) for item in facts},
        decision_time=COHORT_TIME,
    )

    class _Clock:
        def now(self) -> datetime:
            return COHORT_TIME

    (execution,) = run_strategies(
        build_s001_cohort_registry(cohort, MEMBERSHIP),
        _Clock(),
        subjects=(MEMBERSHIP.universe_id,),
    )
    assert execution.status is ExecutionStatus.COMPLETED
    assert execution.result is not None
    decision = build_s001_target_decision(
        execution.result,
        defensive_evidence=_defensive(),
        next_eligible_session=lambda _: NEXT_SESSION,
    )
    ledger: InMemoryDecisionLedger = InMemoryDecisionLedger()
    ledger.append(decision)
    replayed = deserialize_s001_target_decision(
        serialize_s001_target_decision(replay_decision(ledger, decision.decision_id))
    )
    assert replayed == decision
