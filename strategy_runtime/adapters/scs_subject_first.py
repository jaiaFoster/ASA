"""SCS sealed-evidence preparation and read-only adapter."""

from collections.abc import Mapping
from datetime import date, datetime
from decimal import Decimal
from functools import partial
from types import MappingProxyType

from analytics.calendar_facts import TradingCalendarView, first_trading_day_of_month
from domain import (
    MarketCapability,
    OptionChain,
    OptionLegPosition,
    OptionType,
    Quote,
    UnknownReason,
)
from market_data.session_calendar import NEW_YORK, UsEquitySessionCalendar
from market_data.snapshot import MarketSnapshot
from screening.subject_fact_projection import resolution_for
from screening.subject_planning import ResolvedEvidenceView, SubjectPlanConsumer
from strategies.knowledge_contracts import KnowledgeMapping
from strategies.scs_evaluation import NO_ACTION, SCSDecision, evaluate_scs
from strategies.scs_knowledge import SCSPayload, build_scs_knowledge_mapping
from strategies.scs_planning import bootstrap_demands, expand_demands
from strategies.tristate_components import PASS
from strategy_runtime.adapters.scs import SCS_CONTRACT
from strategy_runtime.context import RuntimeContext
from strategy_runtime.contract import StructureKind
from strategy_runtime.executable_structures import ExecutableStructureAssessment
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


def _prepare(
    now: datetime,
    snapshot: MarketSnapshot,
    projected: ResolvedEvidenceView,
    selections: tuple[tuple[str, object], ...],
    subject: str,
) -> KnowledgeMapping[SCSPayload] | UnknownReason:
    del projected
    expiration_value = dict(selections).get("expiration")
    if not isinstance(expiration_value, str):
        return UnknownReason("G_SCS_EXPIRY_UNIQUE_UNKNOWN")
    try:
        quote_r = resolution_for(snapshot, MarketCapability.REAL_TIME_QUOTE_V1)
        chain_r = resolution_for(snapshot, MarketCapability.OPTION_CHAIN_V1)
    except ValueError:
        return UnknownReason("SCS_REQUIRED_EVIDENCE_UNUSABLE")
    quote_o, chain_o = quote_r.selected_observation, chain_r.selected_observation
    if quote_o is None or not isinstance(quote_o.value, Quote) or quote_o.value.last is None:
        return UnknownReason("G_SCS_STRIKE_UNIQUE_UNKNOWN")
    if chain_o is None or not isinstance(chain_o.value, OptionChain):
        return UnknownReason("G_SCS_STRIKE_UNIQUE_UNKNOWN")
    return build_scs_knowledge_mapping(
        subject=subject,
        quote_observation_id=quote_o.observation_id,
        chain_observation_id=chain_o.observation_id,
        chain=chain_o.value,
        spot=quote_o.value.last,
        selected_expiration=date.fromisoformat(expiration_value),
    )


def _entry_state(now: datetime) -> str:
    day = now.astimezone(NEW_YORK).date()
    first = day.replace(day=1)
    following = date(first.year + (first.month == 12), first.month % 12 + 1, 1)
    sessions = UsEquitySessionCalendar()
    selected = first_trading_day_of_month(
        TradingCalendarView(lambda value: sessions.session(value) is not None, first, following),
        day.year,
        day.month,
    )
    if isinstance(selected, UnknownReason):
        return "UNKNOWN"
    return PASS if selected == day else "FAIL"


def _decision(payload: SCSPayload, now: datetime) -> SCSDecision:
    return evaluate_scs(
        decision_date=now.date(),
        entry_date_state=_entry_state(now),
        selected_expiration=payload.selected_expiration,
        spot=payload.spot,
        chain=payload.chain,
        rate=payload.rate,
        dividend_yield=payload.dividend_yield,
    )


def build_scs_structure_intent(subject: str, decision: SCSDecision) -> OptionStructureIntent:
    if decision.verdict != PASS or decision.selected_call is None or decision.selected_put is None:
        raise ValueError("SCS structure intent requires a passing exact pair")
    return OptionStructureIntent(
        subject,
        StructureKind.STRADDLE,
        (
            OptionLegIntent(
                "short_call",
                OptionType.CALL,
                decision.selected_call.expiration,
                OptionLegPosition.SHORT,
                Decimal(1),
                selected_contract_identity=decision.selected_call.identity,
            ),
            OptionLegIntent(
                "short_put",
                OptionType.PUT,
                decision.selected_put.expiration,
                OptionLegPosition.SHORT,
                Decimal(1),
                selected_contract_identity=decision.selected_put.identity,
            ),
        ),
    )


def build_scs_subject_first_adapter(
    knowledge_by_subject: Mapping[str, ReadOnlyStrategyInput[SCSPayload]],
) -> StrategyAdapter[UniversalScreeningResult]:
    frozen = MappingProxyType(dict(knowledge_by_subject))

    def _adapter(context: RuntimeContext) -> UniversalScreeningResult:
        knowledge = frozen[context.subject]
        decision = _decision(knowledge.payload, context.clock.now())
        state = (
            EvaluationState.PASS
            if decision.verdict == PASS
            else EvaluationState.NO_SIGNAL
            if decision.verdict == NO_ACTION
            else EvaluationState.MISSING_DATA
        )
        return UniversalScreeningResult(
            SCS_CONTRACT.strategy_id,
            SCS_CONTRACT.version,
            context.subject,
            compute_observation_id(context.run_id, SCS_CONTRACT.strategy_id, context.subject),
            compute_opportunity_id(SCS_CONTRACT.strategy_id, context.subject)
            if state is EvaluationState.PASS
            else None,
            RowType.RESULT,
            None if state is EvaluationState.MISSING_DATA else decision.verdict,
            state,
            "identified" if state is EvaluationState.PASS else None,
            None,
            None,
            {
                "decision.reason": TypedValue.of_string(decision.reason),
                "decision.assumption": TypedValue.of_string(
                    "RA-SV-01:standard_monthly_SPX_expirations_only"
                ),
                "quote_filter.rate_state": TypedValue.of_string(
                    "UNKNOWN_CANONICAL_RATE_NOT_BOUND"
                ),
                "quote_filter.dividend_yield_state": TypedValue.of_string(
                    "UNKNOWN_CANONICAL_SPX_DIVIDEND_YIELD_NOT_AVAILABLE"
                ),
            },
            {},
            () if state is not EvaluationState.MISSING_DATA else (decision.reason,),
            (
                "allocation_not_defined_by_source",
                "no_fallback_strike_when_ATM_pair_is_unusable",
            ),
            (
                f"snapshot_id:{knowledge.snapshot_id}",
                f"snapshot_digest:{knowledge.snapshot_digest}",
            ),
            knowledge.effective_time,
        )

    return _adapter


def _assessment(
    knowledge: ReadOnlyStrategyInput[SCSPayload],
    result: UniversalScreeningResult,
    assessed_at: datetime,
) -> ExecutableStructureAssessment:
    decision = _decision(knowledge.payload, assessed_at)
    return resolve_option_structure(
        intent=build_scs_structure_intent(result.symbol, decision),
        chain=knowledge.payload.chain,
        originating_result_identity=result.observation_id,
        evidence_snapshot_identity=knowledge.snapshot_digest,
        assessed_at=assessed_at,
    )


def build_scs_subject_preparation_binding(now: datetime) -> SubjectPreparationBinding[SCSPayload]:
    return SubjectPreparationBinding(
        SubjectPlanConsumer(
            SCS_CONTRACT.strategy_id, bootstrap_demands(now), partial(expand_demands, now=now)
        ),
        partial(_prepare, now),
        build_scs_subject_first_adapter,
        build_execution_assessment=_assessment,
    )
