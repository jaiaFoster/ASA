"""GXZ sealed-evidence preparation and read-only production adapter."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime
from decimal import Decimal
from functools import partial
from types import MappingProxyType

from domain import (
    EarningsEvent,
    MarketCapability,
    OptionChain,
    OptionLegPosition,
    OptionType,
    Quote,
    UnknownReason,
)
from market_data.snapshot import MarketSnapshot
from screening.subject_fact_projection import resolution_for
from screening.subject_planning import ResolvedEvidenceView, SubjectPlanConsumer
from strategies.gxz_evaluation import PASS, GXZDecision, evaluate_gxz
from strategies.gxz_knowledge import GXZPayload, build_gxz_knowledge_mapping
from strategies.gxz_planning import bootstrap_demands, expand_demands
from strategies.knowledge_contracts import KnowledgeMapping
from strategy_runtime.adapters.gxz import GXZ_CONTRACT
from strategy_runtime.context import RuntimeContext
from strategy_runtime.contract import StructureKind
from strategy_runtime.executable_structures import (
    ExecutableStructureAssessment,
    structure_not_selected_assessment,
)
from strategy_runtime.knowledge import ReadOnlyStrategyInput
from strategy_runtime.lifecycle import compute_opportunity_id
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

_STRATEGY_ID = GXZ_CONTRACT.strategy_id


def _spot(quote: Quote) -> Decimal | None:
    if quote.last is not None:
        return quote.last
    if quote.bid is not None and quote.ask is not None:
        return (quote.bid + quote.ask) / Decimal(2)
    return None


def _prepare(
    now: datetime,
    snapshot: MarketSnapshot,
    projected: ResolvedEvidenceView,
    selections: tuple[tuple[str, object], ...],
    subject: str,
) -> KnowledgeMapping[GXZPayload] | UnknownReason:
    del projected
    selected = dict(selections)
    # The current canonical TRADING_CALENDAR_V1 observation is singular and
    # cannot prove a three-session offset. Fail closed until the planner can
    # supply an identity-bearing exact session selection; never approximate
    # holidays with calendar weekdays.
    if selected.get("entry_session_state") != PASS:
        return UnknownReason("G_GXZ_ENTRY_SESSION_UNKNOWN")
    try:
        quote_r = resolution_for(snapshot, MarketCapability.REAL_TIME_QUOTE_V1)
        earnings_r = resolution_for(snapshot, MarketCapability.EARNINGS_CALENDAR_V1)
        chain_r = resolution_for(snapshot, MarketCapability.OPTION_CHAIN_V1)
    except ValueError:
        return UnknownReason("GXZ_REQUIRED_EVIDENCE_UNUSABLE")
    quote_o, earnings_o, chain_o = (
        quote_r.selected_observation,
        earnings_r.selected_observation,
        chain_r.selected_observation,
    )
    if (
        quote_o is None
        or not isinstance(quote_o.value, Quote)
        or (spot := _spot(quote_o.value)) is None
    ):
        return UnknownReason("G_GXZ_STOCK_PRICE_MIN_UNKNOWN")
    if earnings_o is None or not isinstance(earnings_o.value, EarningsEvent):
        return UnknownReason("G_GXZ_EA_DATE_KNOWN_UNKNOWN")
    if chain_o is None or not isinstance(chain_o.value, OptionChain):
        return UnknownReason("G_GXZ_PAIR_INPUT_UNKNOWN")
    return build_gxz_knowledge_mapping(
        subject=subject,
        quote_observation_id=quote_o.observation_id,
        earnings_observation_id=earnings_o.observation_id,
        chain_observation_id=chain_o.observation_id,
        chain=chain_o.value,
        event=earnings_o.value,
        spot=spot,
        entry_date=now.date(),
    )


def _decision(payload: GXZPayload):  # type: ignore[no-untyped-def]
    return evaluate_gxz(
        chain=payload.chain,
        spot=payload.spot,
        earnings_date=payload.event.earnings_date,
        earnings_confirmed=payload.event.confirmed,
        entry_date=payload.entry_date,
        entry_session_state=PASS,
    )


def _result(
    knowledge: ReadOnlyStrategyInput[GXZPayload], context: RuntimeContext
) -> UniversalScreeningResult:
    decision = _decision(knowledge.payload)
    passed = decision.verdict == PASS
    state = (
        EvaluationState.PASS
        if passed
        else EvaluationState.NO_SIGNAL
        if decision.verdict in {"FAIL", "NO_ACTION"}
        else EvaluationState.MISSING_DATA
    )
    metrics = {
        "decision.reason": TypedValue.of_string(decision.reason),
        "decision.assumptions": TypedValue.of_structured(
            [
                "RA-EV-01:pair_volume_is_call_plus_put_volume_at_day_minus_3_close",
                "RA-EV-02:listed_expirations_include_weeklies_and_calendar_DTE_is_literal",
                "provider_delta_equivalence_to_OptionMetrics_is_unknown",
                "entry_fill:closing_ask_full_spread_case",
            ]
        ),
        "gxz.pair_count": TypedValue.of_integer(len(decision.pairs)),
    }
    return UniversalScreeningResult(
        strategy_id=_STRATEGY_ID,
        strategy_version=GXZ_CONTRACT.version,
        symbol=context.subject,
        observation_id=compute_observation_id(context.run_id, _STRATEGY_ID, context.subject),
        opportunity_id=(
            compute_opportunity_id(_STRATEGY_ID, context.subject)
            if state is not EvaluationState.MISSING_DATA
            else None
        ),
        row_type=RowType.RESULT,
        verdict=None if state is EvaluationState.MISSING_DATA else decision.verdict,
        evaluation_state=state,
        lifecycle_stage="identified" if state is not EvaluationState.MISSING_DATA else None,
        recommendation_state=None,
        data_quality=None,
        metrics=metrics,
        economics={},
        blockers=() if decision.verdict != "UNKNOWN" else (decision.reason,),
        warnings=(),
        provenance=(
            f"snapshot_id:{knowledge.snapshot_id}",
            f"snapshot_digest:{knowledge.snapshot_digest}",
        ),
        observed_at=knowledge.effective_time,
    )


def build_gxz_subject_first_adapter(
    knowledge_by_subject: Mapping[str, ReadOnlyStrategyInput[GXZPayload]],
) -> StrategyAdapter[UniversalScreeningResult]:
    frozen = MappingProxyType(dict(knowledge_by_subject))
    return lambda context: _result(frozen[context.subject], context)


def build_gxz_structure_intent(symbol: str, decision: GXZDecision) -> OptionStructureIntent:
    """Project the strategy decision onto generic P03 exact-leg intent."""
    if decision.verdict != PASS or not decision.pairs:
        raise ValueError("GXZ structure intent requires a passing decision")
    intents: list[OptionLegIntent] = []
    for pair in decision.pairs:
        intents.extend(
            (
                OptionLegIntent(
                    f"{pair.call.strike}.call",
                    OptionType.CALL,
                    pair.call.expiration,
                    OptionLegPosition.LONG,
                    pair.call_quantity * pair.pair_weight,
                    selected_contract_identity=pair.call.identity,
                ),
                OptionLegIntent(
                    f"{pair.put.strike}.put",
                    OptionType.PUT,
                    pair.put.expiration,
                    OptionLegPosition.LONG,
                    pair.put_quantity * pair.pair_weight,
                    selected_contract_identity=pair.put.identity,
                ),
            )
        )
    return OptionStructureIntent(symbol, StructureKind.STRADDLE, tuple(intents))


def _assessment(
    knowledge: ReadOnlyStrategyInput[GXZPayload],
    result: UniversalScreeningResult,
    assessed_at: datetime,
) -> ExecutableStructureAssessment:
    decision = _decision(knowledge.payload)
    if decision.verdict != PASS or not decision.pairs:
        return structure_not_selected_assessment(
            originating_result_identity=result.observation_id,
            subject=result.symbol,
            intended_structure_kind=StructureKind.STRADDLE,
            evidence_snapshot_identity=knowledge.snapshot_digest,
            assessed_at=assessed_at,
        )
    return resolve_option_structure(
        intent=build_gxz_structure_intent(result.symbol, decision),
        chain=knowledge.payload.chain,
        originating_result_identity=result.observation_id,
        evidence_snapshot_identity=knowledge.snapshot_digest,
        assessed_at=assessed_at,
    )


def build_gxz_subject_preparation_binding(now: datetime) -> SubjectPreparationBinding[GXZPayload]:
    return SubjectPreparationBinding(
        SubjectPlanConsumer(_STRATEGY_ID, bootstrap_demands(now), partial(expand_demands, now=now)),
        partial(_prepare, now),
        build_gxz_subject_first_adapter,
        build_execution_assessment=_assessment,
    )
