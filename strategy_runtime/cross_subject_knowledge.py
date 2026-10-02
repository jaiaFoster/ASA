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
        comparison = select_comparison_universe_returns(subject, period, returns, asset_types)
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
    expected_complete_subjects: tuple[str, ...] | None = None,
) -> CrossSubjectKnowledgeResult:
    """Materialize each declared family once from injected canonical classifications."""

    result = {subject: dict(values) for subject, values in knowledge_by_subject.items()}
    family_entries: dict[str, list[tuple[str, str, ReadOnlyStrategyInput[object]]]] = {}
    for strategy_id in registry.strategy_ids():
        binding = registry.binding_for(strategy_id)
        family_id = binding.cross_subject_family_id
        extractor = binding.extract_cross_subject_return
        candidate_extractor = binding.extract_cross_subject_candidate
        binder = binding.bind_cross_subject_facts
        if (
            family_id is None
            or (extractor is None and candidate_extractor is None)
            or binder is None
        ):
            continue
        for subject, by_strategy in result.items():
            knowledge = by_strategy.get(strategy_id)
            if knowledge is None or isinstance(knowledge, UnknownReason):
                continue
            family_entries.setdefault(family_id, []).append((strategy_id, subject, knowledge))

    counts: list[tuple[str, int]] = []
    for family_id in sorted(family_entries):
        entries = family_entries[family_id]
        first_binding = registry.binding_for(entries[0][0])
        if first_binding.requires_complete_cross_subject_universe:
            # A complete family is ranked only over its whole declared
            # universe. Subjects never admitted to this cycle defer the
            # family (capacity); admitted subjects whose preparation failed
            # keep their own typed reason, and the prepared remainder is
            # typed as an incomplete cohort. Never a partial ranking.
            expected = set(expected_complete_subjects or ())
            family_strategy_ids = {strategy_id for strategy_id, _subject, _k in entries}
            admitted = {
                subject
                for subject, by_strategy in result.items()
                if family_strategy_ids & set(by_strategy)
            }
            prepared = {subject for _strategy_id, subject, _knowledge in entries}
            if not expected or prepared != expected:
                reason = UnknownReason(
                    "INCOMPLETE_COHORT_PREPARATION"
                    if expected and admitted >= expected
                    else "CAPACITY_DEFERRED_INCOMPLETE_COHORT"
                )
                for strategy_id, subject, _knowledge in entries:
                    result[subject][strategy_id] = reason
                counts.append((family_id, 0))
                continue
        candidate_extractor = first_binding.extract_cross_subject_candidate
        family_materializer = first_binding.materialize_cross_subject_family
        if candidate_extractor is not None and family_materializer is not None:
            candidates: dict[str, object] = {}
            for strategy_id, subject, knowledge in entries:
                binding = registry.binding_for(strategy_id)
                if binding.extract_cross_subject_candidate is not candidate_extractor:
                    raise ValueError(
                        f"cross-subject family {family_id!r} has conflicting candidate extractors"
                    )
                if binding.materialize_cross_subject_family is not family_materializer:
                    raise ValueError(
                        f"cross-subject family {family_id!r} has conflicting materializers"
                    )
                candidates[subject] = candidate_extractor(knowledge)
            family_output = family_materializer(candidates)
            if set(family_output) != set(candidates):
                raise ValueError(
                    f"cross-subject family {family_id!r} materializer must return every subject"
                )
            counts.append((family_id, 1))
            for strategy_id, subject, knowledge in entries:
                binder = registry.binding_for(strategy_id).bind_cross_subject_facts
                assert binder is not None
                result[subject][strategy_id] = binder(knowledge, family_output[subject])
            continue
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
        legacy_materialized = materialize_cross_sectional_facts(
            _selected_inputs(returns, asset_types, sectors),
            effective_time=max(item.effective_time for item in returns),
        )
        by_subject = {item.subject: item for item in legacy_materialized}
        counts.append((family_id, 1))
        for strategy_id, subject, knowledge in entries:
            binder = registry.binding_for(strategy_id).bind_cross_subject_facts
            assert binder is not None
            facts: SubjectCrossSectionalFacts = by_subject[_instrument(subject)]
            result[subject][strategy_id] = binder(knowledge, facts)
    return CrossSubjectKnowledgeResult(result, tuple(counts))
