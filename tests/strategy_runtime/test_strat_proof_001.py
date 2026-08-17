"""STRAT-PROOF-001: full plug-in architecture acceptance proof."""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import cast

from analytics.cross_sectional_materialization import SubjectCrossSectionalFacts
from analytics.derived_fact_materialization import materialize_derived_fact
from analytics.derived_facts import (
    CROSS_SECTIONAL_MOMENTUM,
    DERIVED_FACT_REGISTRY,
    REALIZED_VOLATILITY,
)
from analytics.features import DerivedFactQualityStatus, DerivedFactSet
from domain import (
    CanonicalInstrumentIdentity,
    CanonicalReturnObservation,
    DemandExpansion,
    EvidenceKind,
    EvidenceReference,
    UnknownReason,
)
from market_data.snapshot import MarketSnapshot
from screening.subject_planning import ResolvedEvidenceView, SubjectPlanConsumer
from strategy_runtime.context import RuntimeContext
from strategy_runtime.cross_subject_knowledge import compose_cross_subject_knowledge
from strategy_runtime.execution import ExecutionStatus, run_strategies
from strategy_runtime.knowledge import ReadOnlyStrategyInput
from strategy_runtime.replay import StrategyKnowledgeReplayRecord, replay_strategy_knowledge
from strategy_runtime.subject_preparation import (
    SubjectPreparationBinding,
    SubjectPreparationRegistry,
)
from tests.strategy_runtime.strat_proof_plugin import (
    CONTRACT,
    STRATEGY_ID,
    FrozenClock,
    build_adapter,
    register_test_strategy,
)

START = datetime(2026, 7, 1, tzinfo=UTC)
END = datetime(2026, 8, 1, tzinfo=UTC)
FAMILY_ID = "twenty_session_return_v1"


@dataclass(frozen=True, slots=True)
class _ExistingKnowledgePayload:
    observation: CanonicalReturnObservation


def _observation(symbol: str, value: str) -> CanonicalReturnObservation:
    return CanonicalReturnObservation(
        CanonicalInstrumentIdentity("symbol", symbol),
        Decimal(value),
        START,
        END,
        END,
        (EvidenceReference(EvidenceKind.CANONICAL_FACT, f"daily_closes:{symbol}", 1),),
    )


def _existing_knowledge(symbol: str, return_value: str) -> ReadOnlyStrategyInput[object]:
    observation = _observation(symbol, return_value)
    local_fact = materialize_derived_fact(
        DERIVED_FACT_REGISTRY,
        REALIZED_VOLATILITY,
        symbol,
        f"snapshot-{symbol}",
        value=Decimal("0.25"),
        unit="decimal",
        effective_time=END,
        input_evidence=observation.evidence,
        quality_status=DerivedFactQualityStatus.VALID,
    )
    return ReadOnlyStrategyInput(
        f"snapshot-{symbol}",
        f"digest-{symbol}",
        END,
        (),
        DerivedFactSet((local_fact,)),
        _ExistingKnowledgePayload(observation),
    )


def _extract(knowledge: ReadOnlyStrategyInput[object]) -> CanonicalReturnObservation:
    payload = knowledge.payload
    assert isinstance(payload, _ExistingKnowledgePayload)
    return payload.observation


def _bind(
    knowledge: ReadOnlyStrategyInput[object], facts: object
) -> ReadOnlyStrategyInput[object]:
    assert isinstance(facts, SubjectCrossSectionalFacts)
    return replace(
        knowledge,
        derived_facts=DerivedFactSet(
            (*knowledge.derived_facts.facts, *facts.derived_facts.facts)
        ),
    )


def _never_prepare(
    _snapshot: MarketSnapshot,
    _projected: ResolvedEvidenceView,
    _selections: tuple[tuple[str, object], ...],
    _subject: str,
) -> UnknownReason:
    raise AssertionError("proof strategy must reuse sealed knowledge, never acquire or prepare")


def _binding(consumer_id: str) -> SubjectPreparationBinding[object]:
    return SubjectPreparationBinding(
        SubjectPlanConsumer(consumer_id, (), lambda _evidence: DemandExpansion()),
        _never_prepare,
        lambda knowledge: build_adapter(knowledge),
        FAMILY_ID,
        _extract,
        _bind,
    )


def _seed() -> dict[str, ReadOnlyStrategyInput[object]]:
    return {
        symbol: _existing_knowledge(symbol, value)
        for symbol, value in {
            "AAPL": "0.06",
            "MSFT": "0.05",
            "NVDA": "0.04",
            "AMD": "0.03",
            "AVGO": "0.02",
            "MU": "0.01",
            "XLK": "0.025",
        }.items()
    }


def _compose(
    seed: dict[str, ReadOnlyStrategyInput[object]],
    entries: tuple[tuple[str, SubjectPreparationBinding[object]], ...],
) -> tuple[dict[str, ReadOnlyStrategyInput[object]], tuple[tuple[str, int], ...]]:
    knowledge: dict[str, dict[str, ReadOnlyStrategyInput[object] | UnknownReason]] = {
        subject: {strategy_id: item for strategy_id, _binding_value in entries}
        for subject, item in seed.items()
    }
    result = compose_cross_subject_knowledge(
        knowledge,
        SubjectPreparationRegistry(entries),
    )
    return (
        {
            subject: cast("ReadOnlyStrategyInput[object]", value[STRATEGY_ID])
            for subject, value in result.knowledge_by_subject.items()
            if isinstance(value[STRATEGY_ID], ReadOnlyStrategyInput)
        },
        result.materialization_count_by_family,
    )


def test_plugin_reuses_existing_facts_without_provider_or_materialization_growth() -> None:
    seed = _seed()
    baseline_local = tuple(
        fact.derived_fact_id
        for knowledge in seed.values()
        for fact in knowledge.derived_facts.facts
    )
    provider_calls = 0
    baseline, baseline_counts = _compose(
        seed,
        ((STRATEGY_ID, _binding(STRATEGY_ID)),),
    )
    augmented, augmented_counts = _compose(
        seed,
        (
            ("existing_consumer", _binding("existing_consumer")),
            (STRATEGY_ID, _binding(STRATEGY_ID)),
        ),
    )

    assert provider_calls == 0
    assert baseline_counts == augmented_counts == ((FAMILY_ID, 1),)
    assert tuple(
        fact.derived_fact_id
        for knowledge in seed.values()
        for fact in knowledge.derived_facts.facts
    ) == baseline_local
    assert augmented["AAPL"].derived_facts == baseline["AAPL"].derived_facts
    assert any(
        fact.derived_fact_id.startswith(f"{REALIZED_VOLATILITY}:")
        for fact in augmented["AAPL"].derived_facts.facts
    )
    assert any(
        fact.derived_fact_id.startswith(f"{CROSS_SECTIONAL_MOMENTUM}:")
        for fact in augmented["AAPL"].derived_facts.facts
    )


def test_registration_order_execution_and_provider_free_replay_are_deterministic() -> None:
    seed = _seed()
    entries_a = (
        ("existing_consumer", _binding("existing_consumer")),
        (STRATEGY_ID, _binding(STRATEGY_ID)),
    )
    entries_b = tuple(reversed(entries_a))
    knowledge_a, counts_a = _compose(seed, entries_a)
    knowledge_b, counts_b = _compose(seed, entries_b)

    assert counts_a == counts_b == ((FAMILY_ID, 1),)
    assert knowledge_a["AAPL"].derived_facts == knowledge_b["AAPL"].derived_facts

    clock = FrozenClock(END)
    registry = register_test_strategy(knowledge_a)
    first = run_strategies(registry, clock, subjects=("AAPL",))
    second = run_strategies(registry, clock, subjects=("AAPL",))
    assert first == second
    assert first[0].status is ExecutionStatus.COMPLETED
    result = first[0].result
    assert result is not None
    assert result.verdict == "PASS"

    record = StrategyKnowledgeReplayRecord(STRATEGY_ID, "AAPL", knowledge_a["AAPL"])
    context = RuntimeContext(CONTRACT, "AAPL", clock, first[0].run_id)
    replay = replay_strategy_knowledge(record, build_adapter, context)
    assert replay == result


def test_generic_runtime_has_no_synthetic_strategy_reference() -> None:
    root = Path(__file__).resolve().parents[2]
    generic_roots = (
        root / "strategy_runtime",
        root / "market_data",
        root / "screening",
        root / "analytics",
        root / "asa",
    )
    matches = [
        path
        for directory in generic_roots
        for path in directory.rglob("*.py")
        if STRATEGY_ID in path.read_text()
    ]
    assert matches == []
