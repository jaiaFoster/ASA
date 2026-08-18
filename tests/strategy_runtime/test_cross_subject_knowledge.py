from dataclasses import dataclass, replace
from datetime import UTC, datetime
from decimal import Decimal

from analytics.features import DerivedFactSet
from domain import (
    CanonicalInstrumentIdentity,
    CanonicalReturnObservation,
    EvidenceKind,
    EvidenceReference,
    UnknownReason,
)
from screening.subject_planning import SubjectPlanConsumer
from screening.universe_membership import SP500_MEMBERSHIP, canonical_equity_classifications
from strategy_runtime.comparison_universe import (
    ASSET_TYPE_BY_INSTRUMENT,
    SECTOR_BY_INSTRUMENT,
)
from strategy_runtime.cross_subject_knowledge import compose_cross_subject_knowledge
from strategy_runtime.knowledge import ReadOnlyStrategyInput
from strategy_runtime.subject_preparation import (
    SubjectPreparationBinding,
    SubjectPreparationRegistry,
)

START = datetime(2026, 7, 1, tzinfo=UTC)
END = datetime(2026, 8, 1, tzinfo=UTC)


@dataclass(frozen=True, slots=True)
class _Payload:
    observation: CanonicalReturnObservation


def _observation(symbol: str, value: str) -> CanonicalReturnObservation:
    return CanonicalReturnObservation(
        CanonicalInstrumentIdentity("symbol", symbol),
        Decimal(value),
        START,
        END,
        END,
        (EvidenceReference(EvidenceKind.CANONICAL_FACT, f"closes:{symbol}", 1),),
    )


def _knowledge(observation: CanonicalReturnObservation) -> ReadOnlyStrategyInput[object]:
    return ReadOnlyStrategyInput(
        "snapshot",
        "digest",
        END,
        (),
        DerivedFactSet(()),
        _Payload(observation),
    )


def _extract(knowledge: ReadOnlyStrategyInput[object]) -> CanonicalReturnObservation:
    payload = knowledge.payload
    assert isinstance(payload, _Payload)
    return payload.observation


def _bind(knowledge: ReadOnlyStrategyInput[object], facts: object) -> ReadOnlyStrategyInput[object]:
    from analytics.cross_sectional_materialization import SubjectCrossSectionalFacts

    assert isinstance(facts, SubjectCrossSectionalFacts)
    return replace(knowledge, derived_facts=facts.derived_facts)


def _binding(consumer_id: str) -> SubjectPreparationBinding[object]:
    return SubjectPreparationBinding(
        SubjectPlanConsumer(consumer_id, (), lambda _evidence: None),  # type: ignore[arg-type,return-value]
        lambda *_args: None,  # type: ignore[arg-type]
        lambda _knowledge: lambda _context: None,  # type: ignore[arg-type,return-value]
        "twenty_session_return_v1",
        _extract,
        _bind,
    )


def test_two_consumers_share_one_order_independent_materialization() -> None:
    returns = {
        "AAPL": "0.06",
        "MSFT": "0.05",
        "NVDA": "0.04",
        "AMD": "0.03",
        "AVGO": "0.02",
        "MU": "0.01",
        "XLK": "0.025",
    }
    registry = SubjectPreparationRegistry(
        (("consumer_a", _binding("consumer_a")), ("consumer_b", _binding("consumer_b")))
    )
    knowledge: dict[
        str, dict[str, ReadOnlyStrategyInput[object] | UnknownReason]
    ] = {
        symbol: {
            "consumer_a": _knowledge(_observation(symbol, value)),
            "consumer_b": _knowledge(_observation(symbol, value)),
        }
        for symbol, value in reversed(tuple(returns.items()))
    }

    result = compose_cross_subject_knowledge(
        knowledge,
        registry,
        asset_types=ASSET_TYPE_BY_INSTRUMENT,
        sectors=SECTOR_BY_INSTRUMENT,
    )

    assert result.materialization_count_by_family == (("twenty_session_return_v1", 1),)
    first = result.knowledge_by_subject["AAPL"]["consumer_a"]
    second = result.knowledge_by_subject["AAPL"]["consumer_b"]
    assert isinstance(first, ReadOnlyStrategyInput)
    assert isinstance(second, ReadOnlyStrategyInput)
    assert first.derived_facts == second.derived_facts
    assert len(first.derived_facts.facts) == 2


def test_new_membership_subject_needs_no_runtime_symbol_table_or_consumer_change() -> None:
    returns = {
        "SPGI": "0.06",
        "AAPL": "0.05",
        "MSFT": "0.04",
        "NVDA": "0.03",
        "AVGO": "0.02",
        "MU": "0.01",
        "XLF": "0.025",
    }
    registry = SubjectPreparationRegistry(
        (("consumer_a", _binding("consumer_a")), ("consumer_b", _binding("consumer_b")))
    )
    knowledge: dict[
        str, dict[str, ReadOnlyStrategyInput[object] | UnknownReason]
    ] = {
        symbol: {
            "consumer_a": _knowledge(_observation(symbol, value)),
            "consumer_b": _knowledge(_observation(symbol, value)),
        }
        for symbol, value in reversed(tuple(returns.items()))
    }
    classifications = canonical_equity_classifications(SP500_MEMBERSHIP)

    result = compose_cross_subject_knowledge(
        knowledge,
        registry,
        asset_types=classifications.asset_types,
        sectors=classifications.sectors,
    )

    first = result.knowledge_by_subject["SPGI"]["consumer_a"]
    second = result.knowledge_by_subject["SPGI"]["consumer_b"]
    assert isinstance(first, ReadOnlyStrategyInput)
    assert isinstance(second, ReadOnlyStrategyInput)
    assert first.derived_facts == second.derived_facts
    assert len(first.derived_facts.facts) == 2
    assert result.materialization_count_by_family == (("twenty_session_return_v1", 1),)
