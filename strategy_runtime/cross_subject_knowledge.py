"""Registry-driven cross-subject knowledge composition over sealed inputs."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

from analytics.cross_sectional_materialization import (
    CrossSectionalFactInputs,
    SubjectCrossSectionalFacts,
    materialize_cross_sectional_facts,
)
from domain import (
    CanonicalInstrumentIdentity,
    CanonicalReturnObservation,
    SectorClassification,
    SecurityAssetType,
    UnknownReason,
)
from strategy_runtime.comparison_universe import (
    approved_sector_id,
    select_comparison_universe_returns,
    select_sector_reference_returns,
)
from strategy_runtime.knowledge import ReadOnlyStrategyInput
from strategy_runtime.subject_preparation import SubjectPreparationRegistry


@dataclass(frozen=True, slots=True)
class CrossSubjectKnowledgeResult:
    knowledge_by_subject: dict[str, dict[str, ReadOnlyStrategyInput[object] | UnknownReason]]
    materialization_count_by_family: tuple[tuple[str, int], ...]


def _instrument(symbol: str) -> CanonicalInstrumentIdentity:
    return CanonicalInstrumentIdentity("symbol", symbol)


def _selected_inputs(
    returns: tuple[CanonicalReturnObservation, ...],
    asset_types: Mapping[CanonicalInstrumentIdentity, SecurityAssetType],
    sectors: Mapping[CanonicalInstrumentIdentity, SectorClassification],
) -> tuple[CrossSectionalFactInputs, ...]:
    selected: list[CrossSectionalFactInputs] = []
    for item in returns:
        subject = item.instrument
        period = (item.period_start, item.period_end)
        comparison = select_comparison_universe_returns(
            subject, period, returns, asset_types
        )
        sector = select_sector_reference_returns(subject, period, sectors, returns)
        if subject not in asset_types:
            comparison_reason = "missing_instrument_class"
        else:
            comparison_reason = "insufficient_comparison_cohort"
        subject_sector = sectors.get(subject)
        if subject_sector is None:
            sector_reason = "missing_sector_membership"
        elif approved_sector_id(subject_sector) is None:
            sector_reason = "unsupported_sector_membership"
        else:
            sector_reason = "missing_sector_benchmark_return"
        selected.append(
            CrossSectionalFactInputs(
                item,
                comparison,
                sector,
                comparison_reason,
                sector_reason,
            )
        )
    return tuple(selected)


def compose_cross_subject_knowledge(
    knowledge_by_subject: dict[str, dict[str, ReadOnlyStrategyInput[object] | UnknownReason]],
    registry: SubjectPreparationRegistry[object],
    *,
    asset_types: Mapping[CanonicalInstrumentIdentity, SecurityAssetType],
    sectors: Mapping[CanonicalInstrumentIdentity, SectorClassification],
) -> CrossSubjectKnowledgeResult:
    """Materialize each declared family once from injected canonical classifications."""

    result = {subject: dict(values) for subject, values in knowledge_by_subject.items()}
    family_entries: dict[str, list[tuple[str, str, ReadOnlyStrategyInput[object]]]] = {}
    for strategy_id in registry.strategy_ids():
        binding = registry.binding_for(strategy_id)
        family_id = binding.cross_subject_family_id
        extractor = binding.extract_cross_subject_return
        binder = binding.bind_cross_subject_facts
        if family_id is None or extractor is None or binder is None:
            continue
        for subject, by_strategy in result.items():
            knowledge = by_strategy.get(strategy_id)
            if knowledge is None or isinstance(knowledge, UnknownReason):
                continue
            family_entries.setdefault(family_id, []).append((strategy_id, subject, knowledge))

    counts: list[tuple[str, int]] = []
    for family_id in sorted(family_entries):
        entries = family_entries[family_id]
        returns_by_subject: dict[str, CanonicalReturnObservation] = {}
        for strategy_id, subject, knowledge in entries:
            extractor = registry.binding_for(strategy_id).extract_cross_subject_return
            assert extractor is not None
            extracted = extractor(knowledge)
            existing = returns_by_subject.get(subject)
            if existing is not None and existing != extracted:
                raise ValueError(
                    f"cross-subject family {family_id!r} produced conflicting "
                    f"returns for {subject!r}"
                )
            returns_by_subject[subject] = extracted
        returns = tuple(returns_by_subject[subject] for subject in sorted(returns_by_subject))
        if not returns:
            continue
        materialized = materialize_cross_sectional_facts(
            _selected_inputs(returns, asset_types, sectors),
            effective_time=max(item.effective_time for item in returns),
        )
        by_subject = {item.subject: item for item in materialized}
        counts.append((family_id, 1))
        for strategy_id, subject, knowledge in entries:
            binder = registry.binding_for(strategy_id).bind_cross_subject_facts
            assert binder is not None
            facts: SubjectCrossSectionalFacts = by_subject[_instrument(subject)]
            result[subject][strategy_id] = binder(knowledge, facts)
    return CrossSubjectKnowledgeResult(result, tuple(counts))
