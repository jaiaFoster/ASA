from dataclasses import dataclass, replace
from datetime import UTC, datetime
from decimal import Decimal

from analytics.features import DerivedFactSet
from analytics.quantile_assignment import QuantilePolicy
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
from strategy_runtime.cross_sectional_portfolio import (
    PortfolioWeightPolicy,
    build_cross_sectional_portfolio,
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
    knowledge: dict[str, dict[str, ReadOnlyStrategyInput[object] | UnknownReason]] = {
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
    knowledge: dict[str, dict[str, ReadOnlyStrategyInput[object] | UnknownReason]] = {
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


@dataclass(frozen=True, slots=True)
class _Candidate:
    sort_value: Decimal
    source_weight: Decimal
    identity: str


@dataclass(frozen=True, slots=True)
class _BoundPortfolio:
    candidate: _Candidate
    portfolio_identity: str | None = None
    quantile: int | None = None


def _candidate_knowledge(symbol: str, sort_value: str) -> ReadOnlyStrategyInput[object]:
    return ReadOnlyStrategyInput(
        "snapshot",
        "digest",
        END,
        (),
        DerivedFactSet(()),
        _BoundPortfolio(_Candidate(Decimal(sort_value), Decimal("10"), f"position:{symbol}")),
    )


def _extract_candidate(knowledge: ReadOnlyStrategyInput[object]) -> object:
    payload = knowledge.payload
    assert isinstance(payload, _BoundPortfolio)
    return payload.candidate


def _materialize_candidates(candidates: dict[str, object]) -> dict[str, object]:
    typed = {
        subject: value for subject, value in candidates.items() if isinstance(value, _Candidate)
    }
    portfolio = build_cross_sectional_portfolio(
        as_of=END,
        evidence_identity="sealed-cohort",
        sort_values={subject: value.sort_value for subject, value in typed.items()},
        positions=typed,
        quantile_policy=QuantilePolicy(2),
        included_quantiles=frozenset({1, 2}),
        weight_policy=PortfolioWeightPolicy.SOURCE_DEFINED,
        source_weights={subject: value.source_weight for subject, value in typed.items()},
    )
    assert not isinstance(portfolio, UnknownReason)
    groups = dict(portfolio.quantile_assignment.groups)
    return {subject: (portfolio.identity, groups[subject]) for subject in typed}


def _bind_candidate(
    knowledge: ReadOnlyStrategyInput[object], materialized: object
) -> ReadOnlyStrategyInput[object]:
    payload = knowledge.payload
    assert isinstance(payload, _BoundPortfolio)
    identity, quantile = materialized  # type: ignore[misc]
    return replace(
        knowledge,
        payload=_BoundPortfolio(payload.candidate, str(identity), int(quantile)),
    )


def _generic_binding(consumer_id: str, family_id: str) -> SubjectPreparationBinding[object]:
    return SubjectPreparationBinding(
        consumer=SubjectPlanConsumer(consumer_id, (), lambda _evidence: None),  # type: ignore[arg-type,return-value]
        prepare_knowledge_mapping=lambda *_args: None,  # type: ignore[arg-type]
        build_shadow_adapter=lambda _knowledge: lambda _context: None,  # type: ignore[arg-type,return-value]
        cross_subject_family_id=family_id,
        bind_cross_subject_facts=_bind_candidate,
        extract_cross_subject_candidate=_extract_candidate,
        materialize_cross_subject_family=_materialize_candidates,
    )


def test_generic_family_materializes_one_shared_exact_portfolio_for_zhan_shape() -> None:
    registry = SubjectPreparationRegistry((("zhan", _generic_binding("zhan", "zhan-v1")),))
    knowledge = {
        "LOW": {"zhan": _candidate_knowledge("LOW", "1")},
        "HIGH": {"zhan": _candidate_knowledge("HIGH", "9")},
    }
    result = compose_cross_subject_knowledge(knowledge, registry, asset_types={}, sectors={})
    low = result.knowledge_by_subject["LOW"]["zhan"]
    high = result.knowledge_by_subject["HIGH"]["zhan"]
    assert isinstance(low, ReadOnlyStrategyInput) and isinstance(high, ReadOnlyStrategyInput)
    assert isinstance(low.payload, _BoundPortfolio) and isinstance(high.payload, _BoundPortfolio)
    assert low.payload.portfolio_identity == high.payload.portfolio_identity
    assert {low.payload.quantile, high.payload.quantile} == {1, 2}
    assert result.materialization_count_by_family == (("zhan-v1", 1),)


def test_generic_family_contract_is_reusable_for_heston_shape() -> None:
    registry = SubjectPreparationRegistry((("heston", _generic_binding("heston", "heston-v1")),))
    knowledge = {
        "A": {"heston": _candidate_knowledge("A", "-0.20")},
        "B": {"heston": _candidate_knowledge("B", "0.30")},
    }
    result = compose_cross_subject_knowledge(knowledge, registry, asset_types={}, sectors={})
    assert result.materialization_count_by_family == (("heston-v1", 1),)
