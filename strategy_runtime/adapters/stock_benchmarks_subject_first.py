"""B001/B002 preparation and read-only runtime binding (STOCK-RUNTIME-001
STK-03). Both benchmarks are StructureKind.NONE/NO_LIFECYCLE with a single
acquisition phase (no expiration selection, no option structure) -- the
smallest subject-first shape the runtime supports, mirroring
tests/strategy_runtime/strat_proof_plugin.py's own minimal adapter rather
than the option-structure strategies' manifest-graph pattern.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime
from types import MappingProxyType
from typing import Any

from domain import MarketCapability, OHLCVSeries, Quote, UnknownReason
from market_data.snapshot import MarketSnapshot
from screening.subject_fact_projection import resolution_for
from screening.subject_planning import ResolvedEvidenceView, SubjectPlanConsumer
from strategies.knowledge_contracts import KnowledgeMapping
from strategies.stock_benchmark_evaluation import evaluate_b001, evaluate_b002
from strategies.stock_benchmark_knowledge import (
    B001Payload,
    B002Payload,
    build_b001_knowledge_mapping,
    build_b002_knowledge_mapping,
)
from strategies.stock_benchmark_planning import (
    b001_bootstrap_demands,
    b002_bootstrap_demands,
    no_op_expand,
)
from strategy_runtime.adapters.stock_benchmarks import B001_CONTRACT, B002_CONTRACT
from strategy_runtime.context import RuntimeContext
from strategy_runtime.knowledge import ReadOnlyStrategyInput
from strategy_runtime.registry import StrategyAdapter
from strategy_runtime.result import (
    EvaluationState,
    RowType,
    UniversalScreeningResult,
    compute_observation_id,
)
from strategy_runtime.subject_preparation import SubjectPreparationBinding
from strategy_runtime.values import TypedValue

_B001_STRATEGY_ID = "B001"
_B002_STRATEGY_ID = "B002"


def _prepare_b001(
    snapshot: MarketSnapshot,
    projected_evidence: ResolvedEvidenceView,
    selections: tuple[tuple[str, object], ...],
    subject: str,
) -> KnowledgeMapping[B001Payload] | UnknownReason:
    del projected_evidence, selections
    quote_resolution = resolution_for(snapshot, MarketCapability.REAL_TIME_QUOTE_V1)
    quote_observation = quote_resolution.selected_observation
    if quote_observation is None or not isinstance(quote_observation.value, Quote):
        return UnknownReason("unusable_quote")
    quote = quote_observation.value
    if quote.last is None:
        return UnknownReason("unusable_quote")
    return build_b001_knowledge_mapping(
        subject=subject,
        quote_observation_id=quote_observation.observation_id,
        price=quote.last,
    )


def _prepare_b002(
    snapshot: MarketSnapshot,
    projected_evidence: ResolvedEvidenceView,
    selections: tuple[tuple[str, object], ...],
    subject: str,
) -> KnowledgeMapping[B002Payload] | UnknownReason:
    del projected_evidence, selections
    quote_resolution = resolution_for(snapshot, MarketCapability.REAL_TIME_QUOTE_V1)
    quote_observation = quote_resolution.selected_observation
    if quote_observation is None or not isinstance(quote_observation.value, Quote):
        return UnknownReason("unusable_quote")
    quote = quote_observation.value
    if quote.last is None:
        return UnknownReason("unusable_quote")
    bars_resolution = resolution_for(snapshot, MarketCapability.HISTORICAL_BARS_V1)
    bars_observation = bars_resolution.selected_observation
    if bars_observation is None or not isinstance(bars_observation.value, OHLCVSeries):
        return UnknownReason("unusable_historical_bars")
    return build_b002_knowledge_mapping(
        subject=subject,
        snapshot_digest=snapshot.snapshot_digest,
        quote_observation_id=quote_observation.observation_id,
        price=quote.last,
        bars_observation_id=bars_observation.observation_id,
        bars=bars_observation.value.bars,
        as_of=snapshot.as_of,
    )


def build_b001_subject_preparation_binding(now: datetime) -> SubjectPreparationBinding[B001Payload]:
    consumer = SubjectPlanConsumer(
        consumer_id=_B001_STRATEGY_ID,
        bootstrap_demands=b001_bootstrap_demands(now),
        expand=no_op_expand,
    )
    return SubjectPreparationBinding(
        consumer=consumer,
        prepare_knowledge_mapping=_prepare_b001,
        build_shadow_adapter=build_b001_subject_first_adapter,
    )


def build_b002_subject_preparation_binding(now: datetime) -> SubjectPreparationBinding[B002Payload]:
    consumer = SubjectPlanConsumer(
        consumer_id=_B002_STRATEGY_ID,
        bootstrap_demands=b002_bootstrap_demands(now),
        expand=no_op_expand,
    )
    return SubjectPreparationBinding(
        consumer=consumer,
        prepare_knowledge_mapping=_prepare_b002,
        build_shadow_adapter=build_b002_subject_first_adapter,
    )


def _provenance(knowledge: ReadOnlyStrategyInput[Any]) -> tuple[str, ...]:
    return (
        f"snapshot_id:{knowledge.snapshot_id}",
        f"snapshot_digest:{knowledge.snapshot_digest}",
        *(f"canonical_fact:{fact.fact_id}@{fact.version}" for fact in knowledge.canonical_facts),
        *(
            f"derived_fact:{fact.derived_fact_id}@{fact.formula_version}"
            for fact in knowledge.derived_facts.facts
        ),
    )


def build_b001_subject_first_adapter(
    knowledge_by_subject: Mapping[str, ReadOnlyStrategyInput[B001Payload]],
) -> StrategyAdapter[UniversalScreeningResult]:
    frozen = MappingProxyType(dict(knowledge_by_subject))

    def _adapter(context: RuntimeContext) -> UniversalScreeningResult:
        knowledge = frozen[context.subject]
        verdict = evaluate_b001(knowledge.payload)
        return UniversalScreeningResult(
            strategy_id=_B001_STRATEGY_ID,
            strategy_version=B001_CONTRACT.version,
            symbol=context.subject,
            observation_id=compute_observation_id(
                context.run_id, _B001_STRATEGY_ID, context.subject
            ),
            opportunity_id=None,
            row_type=RowType.RESULT,
            verdict=verdict,
            evaluation_state=EvaluationState.PASS,
            lifecycle_stage=None,
            recommendation_state=None,
            data_quality=None,
            metrics={
                "price": TypedValue.of_decimal(knowledge.payload.price),
                "direction": TypedValue.of_string("BUY"),
            },
            economics={},
            blockers=(),
            warnings=(),
            provenance=_provenance(knowledge),
            observed_at=knowledge.effective_time,
        )

    return _adapter


def build_b002_subject_first_adapter(
    knowledge_by_subject: Mapping[str, ReadOnlyStrategyInput[B002Payload]],
) -> StrategyAdapter[UniversalScreeningResult]:
    frozen = MappingProxyType(dict(knowledge_by_subject))

    def _adapter(context: RuntimeContext) -> UniversalScreeningResult:
        knowledge = frozen[context.subject]
        payload = knowledge.payload
        verdict = evaluate_b002(payload)
        successful_pass = verdict == "PASS"
        metrics = {
            "price": TypedValue.of_decimal(payload.price),
            "sma_10m_completed_months": TypedValue.of_decimal(payload.sma_10m),
        }
        if successful_pass:
            metrics["direction"] = TypedValue.of_string("BUY")
        return UniversalScreeningResult(
            strategy_id=_B002_STRATEGY_ID,
            strategy_version=B002_CONTRACT.version,
            symbol=context.subject,
            observation_id=compute_observation_id(
                context.run_id, _B002_STRATEGY_ID, context.subject
            ),
            opportunity_id=None,
            row_type=RowType.RESULT,
            verdict=verdict,
            evaluation_state=(
                EvaluationState.PASS if successful_pass else EvaluationState.NO_SIGNAL
            ),
            lifecycle_stage=None,
            recommendation_state=None,
            data_quality=None,
            metrics=metrics,
            economics={},
            blockers=(),
            warnings=(),
            provenance=_provenance(knowledge),
            observed_at=knowledge.effective_time,
        )

    return _adapter
