"""Earnings Calendar's own subject-first preparation binding and runtime
adapter (SPRINT-014 S14-PR-05A, Architect checkpoint: twelfth review,
items 5 and 6).

Two distinct pieces, both Earnings-owned (this file's own name says so
plainly -- only the *generic orchestrator*, strategy_runtime/
subject_preparation.py, must stay strategy-blind, never this binding):

1. ``build_earnings_calendar_subject_preparation_binding()`` -- the
   SubjectPreparationBinding this strategy registers with the generic
   seam: its own SubjectPlanConsumer (bootstrap demands + phase-two
   expansion, both already strategy-owned pure functions in
   strategies/earnings_calendar_planning.py) plus a callback that, given
   one sealed snapshot's own resolved evidence, performs every mechanic
   the test-only ``_select_structure()`` harness stood in for: verifying
   the phase-two evidence bundle genuinely belongs to the sealed
   snapshot, extracting plain domain values from its resolutions, and
   handing them to strategies/earnings_calendar_structure.py's own pure
   ATM selection, then strategies/earnings_calendar_knowledge_binding.py's
   own KnowledgeMapping construction.

2. ``build_earnings_calendar_subject_first_adapter()`` -- the new runtime
   adapter (Architect checkpoint item 6), bound only to
   ReadOnlyStrategyInput: closes over an immutable subject -> knowledge
   mapping (already computed upstream, once, by the generic seam), and
   for a given RuntimeContext does nothing but look up that subject's own
   already-prepared input, call
   strategies.earnings_calendar_evaluation.evaluate_earnings_calendar(),
   and project the result. No route back to a plan, fulfillment,
   provider, transport, budget, repository, or raw acquisition
   diagnostic of any kind -- everything it touches was already resolved
   before this adapter is ever called.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import date, datetime
from decimal import Decimal
from functools import partial

from domain import (
    EarningsEvent,
    ExpirationCollection,
    MarketCapability,
    OHLCVSeries,
    OptionChain,
    Quote,
    UnknownReason,
)
from market_data.snapshot import MarketSnapshot
from screening.explanations import build_graph_explanation
from screening.subject_fact_projection import (
    resolution_for,
    verify_resolved_evidence_belongs_to_snapshot,
)
from screening.subject_planning import ResolvedEvidenceView, SubjectPlanConsumer
from strategies import EARNINGS_CALENDAR_MANIFEST
from strategies.earnings_calendar_evaluation import evaluate_earnings_calendar
from strategies.earnings_calendar_knowledge_binding import (
    EarningsCalendarPayload,
    build_earnings_calendar_knowledge_mapping,
)
from strategies.earnings_calendar_planning import (
    earnings_calendar_bootstrap_demands,
    expand_earnings_calendar_demands,
    select_earnings_calendar_phase_two_evidence,
)
from strategies.earnings_calendar_structure import select_earnings_calendar_structure
from strategies.knowledge_contracts import KnowledgeMapping
from strategy_runtime.adapters._screening_bridge import explanation_metrics
from strategy_runtime.adapters.earnings_calendar import EARNINGS_CALENDAR_CONTRACT
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

_STRATEGY_ID = "earnings_calendar"


def _prepare_earnings_calendar_knowledge_mapping(
    snapshot: MarketSnapshot,
    projected_evidence: ResolvedEvidenceView,
    selections: tuple[tuple[str, object], ...],
    subject: str,
) -> KnowledgeMapping[EarningsCalendarPayload] | UnknownReason:
    """Earnings Calendar's own SubjectPreparationBinding callback -- every
    DTE/ATM/analytics decision here is strategy-owned; the generic
    orchestrator that calls this (strategy_runtime/subject_preparation.py)
    never sees any of it.
    """
    phase_two = select_earnings_calendar_phase_two_evidence(
        projected_evidence, dict(selections), now=snapshot.as_of
    )
    if isinstance(phase_two, UnknownReason):
        return phase_two

    for evidence in (
        phase_two.spot_price_evidence,
        phase_two.earnings_evidence,
        phase_two.historical_bars_evidence,
        phase_two.expiration_discovery_evidence,
        phase_two.front_chain_evidence,
        phase_two.back_chain_evidence,
    ):
        verify_resolved_evidence_belongs_to_snapshot(snapshot, evidence)

    selections_by_key = dict(selections)
    front_expiration = date.fromisoformat(str(selections_by_key["front_expiration"]))
    back_expiration = date.fromisoformat(str(selections_by_key["back_expiration"]))

    discovery_value = phase_two.expiration_discovery_evidence.value
    if not isinstance(discovery_value, ExpirationCollection):
        return UnknownReason("unexpected_resolved_value_shape")
    front_cycle = next(
        (item for item in discovery_value.cycles if item.expiration_date == front_expiration),
        None,
    )
    back_cycle = next(
        (item for item in discovery_value.cycles if item.expiration_date == back_expiration),
        None,
    )
    if front_cycle is None or back_cycle is None:
        return UnknownReason("selected_expiration_not_in_discovery_collection")

    quote_resolution = resolution_for(snapshot, MarketCapability.REAL_TIME_QUOTE_V1)
    earnings_resolution = resolution_for(snapshot, MarketCapability.EARNINGS_CALENDAR_V1)
    bars_resolution = resolution_for(snapshot, MarketCapability.HISTORICAL_BARS_V1)
    chain_resolution = resolution_for(snapshot, MarketCapability.OPTION_CHAIN_V1)
    if (
        quote_resolution.selected_observation is None
        or earnings_resolution.selected_observation is None
        or bars_resolution.selected_observation is None
        or chain_resolution.selected_observation is None
    ):
        return UnknownReason("unresolved_earnings_calendar_capability")

    quote = quote_resolution.selected_observation.value
    event = earnings_resolution.selected_observation.value
    bars = bars_resolution.selected_observation.value
    chain = chain_resolution.selected_observation.value
    if (
        not isinstance(quote, Quote)
        or not isinstance(event, EarningsEvent)
        or not isinstance(bars, OHLCVSeries)
        or not isinstance(chain, OptionChain)
    ):
        return UnknownReason("unexpected_resolved_value_shape")

    structural = select_earnings_calendar_structure(
        quote=quote,
        event=event,
        chain=chain,
        bars_closes=tuple(bar.close for bar in bars.bars),
        bars_observation_id=bars_resolution.selected_observation.observation_id,
        quote_observation_id=quote_resolution.selected_observation.observation_id,
        earnings_observation_id=earnings_resolution.selected_observation.observation_id,
        chain_observation_id=chain_resolution.selected_observation.observation_id,
        front_expiration=front_expiration,
        back_expiration=back_expiration,
        front_cycle=front_cycle,
        back_cycle=back_cycle,
        as_of=snapshot.as_of.date(),
        quote_demand_id=phase_two.spot_price_evidence.demand_id,
        historical_bars_demand_id=phase_two.historical_bars_evidence.demand_id,
        front_chain_demand_id=phase_two.front_chain_evidence.demand_id,
        back_chain_demand_id=phase_two.back_chain_evidence.demand_id,
    )
    if isinstance(structural, UnknownReason):
        return structural

    return build_earnings_calendar_knowledge_mapping(
        structural, subject=subject, snapshot_digest=snapshot.snapshot_digest
    )


def build_earnings_calendar_subject_preparation_binding(
    now: datetime,
) -> SubjectPreparationBinding[EarningsCalendarPayload]:
    """One subject-cycle's own binding -- rebuilt per invocation (never
    cached across cycles) because its own bootstrap demands and phase-two
    expansion are both closed over ``now``.
    """
    consumer = SubjectPlanConsumer(
        consumer_id=_STRATEGY_ID,
        bootstrap_demands=earnings_calendar_bootstrap_demands(now),
        expand=partial(expand_earnings_calendar_demands, now=now),
    )
    return SubjectPreparationBinding(
        consumer=consumer,
        prepare_knowledge_mapping=_prepare_earnings_calendar_knowledge_mapping,
    )


def build_earnings_calendar_subject_first_adapter(
    knowledge_by_subject: Mapping[str, ReadOnlyStrategyInput[EarningsCalendarPayload]],
) -> StrategyAdapter[UniversalScreeningResult]:
    """Architect checkpoint item 6: bound only to ReadOnlyStrategyInput.
    ``knowledge_by_subject`` is already-computed, immutable input this
    adapter only ever reads by ``context.subject`` -- it never touches a
    plan, fulfillment, provider, transport, budget, repository, or raw
    acquisition diagnostic.
    """

    def _adapter(context: RuntimeContext) -> UniversalScreeningResult:
        knowledge = knowledge_by_subject[context.subject]
        outputs = evaluate_earnings_calendar(knowledge.derived_facts, knowledge.payload)
        verdict = outputs.get("verdict").value
        score = outputs.get("score").value
        verdict_text = str(verdict)
        metrics = explanation_metrics(build_graph_explanation(EARNINGS_CALENDAR_MANIFEST, outputs))
        if isinstance(score, Decimal):
            metrics["strategy_native_score"] = TypedValue.of_decimal(score)
        observation_id = compute_observation_id(context.run_id, _STRATEGY_ID, context.subject)
        return UniversalScreeningResult(
            strategy_id=_STRATEGY_ID,
            strategy_version=EARNINGS_CALENDAR_CONTRACT.version,
            symbol=context.subject,
            observation_id=observation_id,
            opportunity_id=None,
            row_type=RowType.RESULT,
            verdict=verdict_text,
            evaluation_state=(
                EvaluationState.PASS if verdict_text == "PASS" else EvaluationState.NO_SIGNAL
            ),
            lifecycle_stage=None,
            recommendation_state=None,
            data_quality=None,
            metrics=metrics,
            economics={},
            blockers=(),
            warnings=(),
            provenance=(
                tuple(fact.fact_id for fact in knowledge.canonical_facts)
                + tuple(fact.derived_fact_id for fact in knowledge.derived_facts.facts)
            ),
            observed_at=knowledge.effective_time,
        )

    return _adapter
