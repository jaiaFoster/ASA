"""Provider-blind S001 bridge from sealed knowledge to strategy interpretation."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import UTC, datetime

from analytics.derived_facts import SMA_10M_COMPLETED_MONTHS, TRAILING_12M_TOTAL_RETURN
from analytics.features import DerivedFactQualityStatus
from domain import MarketCapability, OHLCVSeries, UnknownReason
from market_data.snapshot import MarketSnapshot
from screening.subject_fact_projection import resolution_for
from screening.subject_planning import ResolvedEvidenceView, SubjectPlanConsumer
from screening.universe_membership import EffectiveUniverseMembership
from strategies.knowledge_contracts import KnowledgeMapping
from strategies.tgsm_composition import S001Selection, SectorFacts, compose_s001_selection
from strategies.tgsm_knowledge import build_s001_knowledge_mapping
from strategies.tgsm_planning import no_phase_two, s001_historical_demand
from strategy_runtime.adapters.tgsm import S001_CONTRACT
from strategy_runtime.cohort_composition import SealedCohortKnowledge
from strategy_runtime.context import RuntimeContext
from strategy_runtime.knowledge import ReadOnlyStrategyInput
from strategy_runtime.registry import StrategyAdapter, StrategyRegistry
from strategy_runtime.result import UniversalScreeningResult
from strategy_runtime.subject_preparation import (
    SubjectPreparationBinding,
    SubjectPreparationRegistry,
)


def _prepare_s001(
    snapshot: MarketSnapshot,
    projected_evidence: ResolvedEvidenceView,
    selections: tuple[tuple[str, object], ...],
    subject: str,
) -> KnowledgeMapping[SectorFacts] | UnknownReason:
    del projected_evidence, selections
    try:
        resolution = resolution_for(snapshot, MarketCapability.HISTORICAL_BARS_V1)
    except ValueError:
        return UnknownReason("unusable_historical_bars")
    observation = resolution.selected_observation
    if observation is None or not isinstance(observation.value, OHLCVSeries):
        return UnknownReason("unusable_historical_bars")
    return build_s001_knowledge_mapping(
        subject=subject,
        snapshot_digest=snapshot.snapshot_digest,
        bars_observation_id=observation.observation_id,
        bars=observation.value.bars,
        as_of=snapshot.as_of,
    )


def _cohort_only_adapter(
    _knowledge: Mapping[str, ReadOnlyStrategyInput[SectorFacts]],
) -> StrategyAdapter[UniversalScreeningResult]:
    raise RuntimeError("S001 must execute from a sealed cohort, not one subject")


def build_s001_subject_preparation_registry(
    now: datetime,
) -> SubjectPreparationRegistry[SectorFacts]:
    """Use the existing generic plan/composer for each eligible sector."""
    binding = SubjectPreparationBinding(
        consumer=SubjectPlanConsumer(
            consumer_id=S001_CONTRACT.strategy_id,
            bootstrap_demands=(s001_historical_demand(now),),
            expand=no_phase_two,
        ),
        prepare_knowledge_mapping=_prepare_s001,
        build_shadow_adapter=_cohort_only_adapter,
    )
    return SubjectPreparationRegistry(((S001_CONTRACT.strategy_id, binding),))


def evaluate_s001_cohort(
    cohort: SealedCohortKnowledge[SectorFacts],
    membership: EffectiveUniverseMembership,
) -> S001Selection:
    """Interpret only payloads already built from the subject evidence boundary."""
    for symbol, knowledge in cohort.subjects:
        if knowledge.payload.subject.value != symbol:
            raise ValueError("cohort subject and canonical fact subject disagree")
        by_derived_id = {item.derived_fact_id: item for item in knowledge.derived_facts.facts}
        momentum = by_derived_id.get(knowledge.payload.trailing_return_fact_id or "")
        sma = by_derived_id.get(knowledge.payload.sma_10m_fact_id or "")
        if (
            momentum is None
            or sma is None
            or momentum.quality_status is not DerivedFactQualityStatus.VALID
            or sma.quality_status is not DerivedFactQualityStatus.VALID
            or not momentum.derived_fact_id.startswith(f"{TRAILING_12M_TOTAL_RETURN}:")
            or not sma.derived_fact_id.startswith(f"{SMA_10M_COMPLETED_MONTHS}:")
            or momentum.value != knowledge.payload.trailing_return
            or sma.value != knowledge.payload.sma_10m
        ):
            raise ValueError("S001 payload must match sealed named derived facts")
        by_canonical_id = {item.fact_id: item for item in knowledge.canonical_facts}
        observed = by_canonical_id.get(knowledge.payload.trend_observation_fact_id or "")
        if observed is None or observed.value != knowledge.payload.trend_observation:
            raise ValueError("S001 trend observation must match a sealed canonical fact")
    return compose_s001_selection(
        tuple(
            item.instrument
            for item in membership.eligible_members(cohort.decision_time.astimezone(UTC).date())
        ),
        tuple(knowledge.payload for _, knowledge in cohort.subjects),
        decision_time=cohort.decision_time,
    )


def build_s001_cohort_registry(
    cohort: SealedCohortKnowledge[SectorFacts],
    membership: EffectiveUniverseMembership,
) -> StrategyRegistry[S001Selection]:
    """Register S001 on the existing universal runtime, over one universe subject.

    The adapter closes over sealed knowledge, never a provider or acquisition
    service. The runtime's subject is the point-in-time universe identifier.
    """

    def _evaluate(context: RuntimeContext) -> S001Selection:
        if context.subject != membership.universe_id:
            raise ValueError("S001 runtime subject must be the declared universe")
        return evaluate_s001_cohort(cohort, membership)

    return StrategyRegistry(((S001_CONTRACT, _evaluate),))
