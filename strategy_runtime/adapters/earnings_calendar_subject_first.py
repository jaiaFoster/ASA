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

Corrective pass (Architect checkpoint: thirteenth review, HOLD): the
adapter now preserves legacy Earnings runtime semantics exactly (a "PASS"
or "WATCH" verdict is a successful, lifecycle-confirmed observation with a
real opportunity_id, matching strategy_runtime/adapters/earnings_calendar.py's
own build_earnings_calendar_adapter()); the binding callback now raises
SealedEvidenceProvenanceError for genuine internal inconsistencies (wrong
resolved-value type, an impossible selected expiration, an unresolved
capability contradicting phase_two's own RESOLVED check) instead of
downgrading them to a typed UnknownReason; the runtime adapter freezes its
own ``knowledge_by_subject`` into an immutable mapping at construction
time; and its provenance now deterministically carries the sealed
snapshot's own id/digest plus every canonical/derived fact's id and
version/formula_version, not bare ids.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import date, datetime
from decimal import Decimal
from functools import partial
from types import MappingProxyType

from domain import (
    EarningsEvent,
    ExpirationCollection,
    MarketCapability,
    OHLCVSeries,
    OptionChain,
    OptionLegPosition,
    OptionType,
    Quote,
    UnknownReason,
)
from market_data.snapshot import MarketSnapshot
from screening.explanations import build_graph_explanation
from screening.subject_fact_projection import (
    SealedEvidenceProvenanceError,
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
from strategy_runtime.contract import StructureKind
from strategy_runtime.executable_structures import ExecutableStructureAssessment
from strategy_runtime.knowledge import ReadOnlyStrategyInput
from strategy_runtime.lifecycle import compute_opportunity_id, validate_lifecycle_stage
from strategy_runtime.option_structure_resolver import (
    OptionLegIntent,
    OptionStructureIntent,
    resolve_option_structure,
)
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

# The legacy live path (screening/live_adapters.py's own _NON_FAIL_VERDICTS)
# treats both a "PASS" and a "WATCH" earnings-calendar verdict as a
# successful, lifecycle-confirmed observation -- only a genuine failure to
# find a valid structure is not. Duplicated here, not imported, because
# _NON_FAIL_VERDICTS is module-private to screening/live_adapters.py and
# this adapter never builds a ScreeningResult/ScreeningOutcomeStatus to key
# off of in the first place (Architect checkpoint: thirteenth review,
# corrective item 2 -- "legacy Earnings maps both PASS and WATCH into
# successful EvaluationState.PASS").
_SUCCESSFUL_VERDICTS = frozenset({"PASS", "WATCH"})


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

    Returns a typed UnknownReason only for the two genuine, expected-gap
    cases already represented by demand/selection semantics: phase-two
    evidence selection itself failing (missing evidence, no valid
    expiration pair), or the strategy's own pure structural selection
    finding a genuine financial-data gap (e.g. missing implied volatility,
    insufficient historical bars). Every other failure here -- a wrong
    normalized domain type, an impossible selected expiration, or any
    other sealed-evidence internal inconsistency -- raises
    SealedEvidenceProvenanceError instead (Architect checkpoint:
    thirteenth review, corrective item 3).
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

    # Everything below is checked against a phase_two selection that
    # select_earnings_calendar_phase_two_evidence and
    # verify_resolved_evidence_belongs_to_snapshot (above) have already
    # confirmed is RESOLVED and genuinely belongs to this sealed snapshot.
    # A mismatch here therefore means this composition's own pipeline is
    # internally inconsistent -- a wrong normalized domain type, an
    # impossible selected expiration, or an unresolved capability the
    # snapshot's own resolution should already guarantee is resolved --
    # never a genuine, expected market-data gap (Architect checkpoint:
    # thirteenth review, corrective item 3). Raise, don't downgrade to a
    # typed UnknownReason.
    discovery_value = phase_two.expiration_discovery_evidence.value
    if not isinstance(discovery_value, ExpirationCollection):
        raise SealedEvidenceProvenanceError(
            f"expiration discovery evidence (demand_id="
            f"{phase_two.expiration_discovery_evidence.demand_id!r}) resolved to "
            f"{type(discovery_value).__name__}, not ExpirationCollection"
        )
    front_cycle = next(
        (item for item in discovery_value.cycles if item.expiration_date == front_expiration),
        None,
    )
    back_cycle = next(
        (item for item in discovery_value.cycles if item.expiration_date == back_expiration),
        None,
    )
    if front_cycle is None or back_cycle is None:
        raise SealedEvidenceProvenanceError(
            f"selected expiration pair ({front_expiration.isoformat()}, "
            f"{back_expiration.isoformat()}) is not present in the expiration "
            "discovery collection this same phase-two selection was computed from"
        )

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
        raise SealedEvidenceProvenanceError(
            "a capability phase_two already verified RESOLVED has no "
            "selected_observation in the sealed snapshot's own resolution"
        )

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
        raise SealedEvidenceProvenanceError(
            "a resolved capability's own selected observation value carries the "
            "wrong normalized domain type"
        )

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
        build_shadow_adapter=build_earnings_calendar_subject_first_adapter,
        build_execution_assessment=_build_execution_assessment,
    )


def _build_execution_assessment(
    knowledge: ReadOnlyStrategyInput[EarningsCalendarPayload],
    result: UniversalScreeningResult,
    assessed_at: datetime,
) -> ExecutableStructureAssessment:
    payload = knowledge.payload
    intent = OptionStructureIntent(
        subject=payload.chain.underlying.symbol,
        intended_structure_kind=StructureKind.CALENDAR,
        legs=(
            OptionLegIntent(
                "short_front",
                OptionType.CALL,
                payload.front_cycle.expiration_date,
                OptionLegPosition.SHORT,
                Decimal(1),
                selected_strike=payload.target_strike,
            ),
            OptionLegIntent(
                "long_back",
                OptionType.CALL,
                payload.back_cycle.expiration_date,
                OptionLegPosition.LONG,
                Decimal(1),
                selected_strike=payload.target_strike,
            ),
        ),
    )
    return resolve_option_structure(
        intent=intent,
        chain=payload.chain,
        originating_result_identity=result.observation_id,
        evidence_snapshot_identity=knowledge.snapshot_digest,
        assessed_at=assessed_at,
    )


def _knowledge_provenance(
    knowledge: ReadOnlyStrategyInput[EarningsCalendarPayload],
) -> tuple[str, ...]:
    """Deterministic provenance for the subject-first result/shadow
    diagnostics (Architect checkpoint: thirteenth review, corrective
    hardening 2): the sealed snapshot's own identity, plus every canonical
    fact's id+version and every derived fact's id+formula_version -- never
    merely bare ids. Intentionally richer than the legacy ScreeningResult-
    shaped path's own provenance (strategy_runtime/adapters/
    _screening_bridge.py's own ``_provenance()``); shadow diagnostics
    compare the two paths on identity fields both carry, not on
    byte-identical provenance tuples.
    """
    return (
        f"snapshot_id:{knowledge.snapshot_id}",
        f"snapshot_digest:{knowledge.snapshot_digest}",
        *(f"canonical_fact:{fact.fact_id}@{fact.version}" for fact in knowledge.canonical_facts),
        *(
            f"derived_fact:{fact.derived_fact_id}@{fact.formula_version}"
            for fact in knowledge.derived_facts.facts
        ),
    )


def build_earnings_calendar_subject_first_adapter(
    knowledge_by_subject: Mapping[str, ReadOnlyStrategyInput[EarningsCalendarPayload]],
) -> StrategyAdapter[UniversalScreeningResult]:
    """Architect checkpoint item 6: bound only to ReadOnlyStrategyInput.
    ``knowledge_by_subject`` is already-computed, immutable input this
    adapter only ever reads by ``context.subject`` -- it never touches a
    plan, fulfillment, provider, transport, budget, repository, or raw
    acquisition diagnostic.

    ``knowledge_by_subject`` is copied into an immutable ``MappingProxyType``
    once, here, rather than trusted as an externally mutable ``Mapping``
    (Architect checkpoint: thirteenth review, corrective hardening 1) -- a
    caller mutating its own dict after construction can never change what
    this adapter's closure sees.

    A successful verdict ("PASS" or "WATCH", mirroring the legacy live
    path's own screening.live_adapters._NON_FAIL_VERDICTS) always carries a
    real opportunity_id and lifecycle_stage, exactly like
    strategy_runtime/adapters/earnings_calendar.py's own
    build_earnings_calendar_adapter() (Architect checkpoint: thirteenth
    review, corrective item 2) -- this adapter never emits a bare None for
    either field.
    """
    frozen_knowledge_by_subject: Mapping[str, ReadOnlyStrategyInput[EarningsCalendarPayload]] = (
        MappingProxyType(dict(knowledge_by_subject))
    )

    def _adapter(context: RuntimeContext) -> UniversalScreeningResult:
        knowledge = frozen_knowledge_by_subject[context.subject]
        outputs = evaluate_earnings_calendar(knowledge.derived_facts, knowledge.payload)
        verdict = outputs.get("verdict").value
        score = outputs.get("score").value
        verdict_text = str(verdict)
        is_successful = verdict_text in _SUCCESSFUL_VERDICTS
        explanation = build_graph_explanation(EARNINGS_CALENDAR_MANIFEST, outputs)
        metrics = explanation_metrics(explanation)
        if isinstance(score, Decimal):
            metrics["strategy_native_score"] = TypedValue.of_decimal(score)
        observation_id = compute_observation_id(context.run_id, _STRATEGY_ID, context.subject)
        stage = "confirmed" if is_successful else "watching"
        validate_lifecycle_stage(EARNINGS_CALENDAR_CONTRACT, stage)
        return UniversalScreeningResult(
            strategy_id=_STRATEGY_ID,
            strategy_version=EARNINGS_CALENDAR_CONTRACT.version,
            symbol=context.subject,
            observation_id=observation_id,
            opportunity_id=compute_opportunity_id(_STRATEGY_ID, context.subject),
            row_type=RowType.RESULT,
            verdict=verdict_text,
            evaluation_state=(
                EvaluationState.PASS if is_successful else EvaluationState.NO_SIGNAL
            ),
            lifecycle_stage=stage,
            recommendation_state=None,
            data_quality=None,
            metrics=metrics,
            economics={},
            blockers=(),
            warnings=explanation.warnings,
            provenance=_knowledge_provenance(knowledge),
            observed_at=knowledge.effective_time,
        )

    return _adapter
