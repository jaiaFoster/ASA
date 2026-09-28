"""Cboe PUT sealed-evidence preparation and read-only adapter."""

from collections.abc import Mapping
from datetime import date, datetime, time
from decimal import Decimal
from functools import partial
from types import MappingProxyType

from analytics.calendar_facts import TradingCalendarView, third_friday_roll_date
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
from strategies.cboe_put_evaluation import NO_ACTION, CboePutDecision, evaluate_cboe_put
from strategies.cboe_put_knowledge import CboePutPayload, build_cboe_put_knowledge_mapping
from strategies.cboe_put_planning import bootstrap_demands, expand_demands
from strategies.knowledge_contracts import KnowledgeMapping
from strategies.tristate_components import PASS, UNKNOWN
from strategy_runtime.adapters.cboe_put import CBOE_PUT_CONTRACT
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


def _spot(quote: Quote) -> Decimal | None:
    # The source requires the last disseminated index value. A quote
    # midpoint is not semantically equivalent and can change the strike.
    return quote.last


def _prepare(
    now: datetime,
    snapshot: MarketSnapshot,
    projected: ResolvedEvidenceView,
    selections: tuple[tuple[str, object], ...],
    subject: str,
) -> KnowledgeMapping[CboePutPayload] | UnknownReason:
    del projected, selections
    try:
        quote_r = resolution_for(snapshot, MarketCapability.REAL_TIME_QUOTE_V1)
        chain_r = resolution_for(snapshot, MarketCapability.OPTION_CHAIN_V1)
    except ValueError:
        return UnknownReason("CBOE_PUT_REQUIRED_EVIDENCE_UNUSABLE")
    quote_o, chain_o = quote_r.selected_observation, chain_r.selected_observation
    if (
        quote_o is None
        or not isinstance(quote_o.value, Quote)
        or (spot := _spot(quote_o.value)) is None
    ):
        return UnknownReason("G_CBOE_SPX_REF_BEFORE_1100_UNKNOWN")
    if chain_o is None or not isinstance(chain_o.value, OptionChain):
        return UnknownReason("G_PUT_STRIKE_EXISTS_UNKNOWN")
    return build_cboe_put_knowledge_mapping(
        subject=subject,
        quote_observation_id=quote_o.observation_id,
        chain_observation_id=chain_o.observation_id,
        chain=chain_o.value,
        spot=spot,
        quote_effective_time=quote_o.effective_time,
    )


def _decision(payload: CboePutPayload, now: datetime) -> CboePutDecision:
    local = now.astimezone(NEW_YORK)
    first = local.date().replace(day=1)
    following = date(first.year + (first.month == 12), first.month % 12 + 1, 1)
    sessions = UsEquitySessionCalendar()
    calendar = TradingCalendarView(
        lambda value: sessions.session(value) is not None, first, following
    )
    roll_date = third_friday_roll_date(calendar, local.year, local.month)
    quote_local = payload.quote_effective_time.astimezone(NEW_YORK)
    reference_state = (
        PASS
        if not isinstance(roll_date, UnknownReason)
        and quote_local.date() == roll_date
        and quote_local.time() < time(11)
        else UNKNOWN
    )
    return evaluate_cboe_put(
        decision_date=local.date(),
        roll_date=roll_date,
        reference_state=reference_state,
        quote_value=payload.spot,
        chain=payload.chain,
    )


def build_cboe_put_subject_first_adapter(
    knowledge_by_subject: Mapping[str, ReadOnlyStrategyInput[CboePutPayload]],
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
            CBOE_PUT_CONTRACT.strategy_id,
            CBOE_PUT_CONTRACT.version,
            context.subject,
            compute_observation_id(context.run_id, CBOE_PUT_CONTRACT.strategy_id, context.subject),
            compute_opportunity_id(CBOE_PUT_CONTRACT.strategy_id, context.subject)
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
                "entry.price_state": TypedValue.of_string("UNKNOWN_OPTION_TRADE_TAPE_UNAVAILABLE"),
                "sizing.rate_state": TypedValue.of_string(
                    "UNKNOWN_CROSS_SUBJECT_TREASURY_RATE_NOT_MATERIALIZED"
                ),
                "lifecycle.soq_state": TypedValue.of_string(
                    "UNKNOWN_INDEX_SETTLEMENT_VALUE_NOT_MATERIALIZED"
                ),
                "decision.assumptions": TypedValue.of_structured(
                    ["IA-PUT-01:proposal_is_one_whole_contract_until_external_capital_is_assigned"]
                ),
            },
            {},
            () if decision.verdict != UNKNOWN else (decision.reason,),
            (
                "source_VWAP_is_UNKNOWN_without_X05_trade_tape",
                "sizing_is_UNKNOWN_without_4w_and_13w_Treasury_facts",
                "settlement_is_UNKNOWN_without_exchange_published_SOQ",
            ),
            (
                f"snapshot_id:{knowledge.snapshot_id}",
                f"snapshot_digest:{knowledge.snapshot_digest}",
            ),
            knowledge.effective_time,
        )

    return _adapter


def _assessment(
    knowledge: ReadOnlyStrategyInput[CboePutPayload],
    result: UniversalScreeningResult,
    assessed_at: datetime,
) -> ExecutableStructureAssessment:
    decision = _decision(knowledge.payload, assessed_at)
    if decision.verdict != PASS or decision.selected_put is None:
        raise ValueError("Cboe PUT assessment requires a passing exact selection")
    return resolve_option_structure(
        intent=build_cboe_put_structure_intent(result.symbol, decision),
        chain=knowledge.payload.chain,
        originating_result_identity=result.observation_id,
        evidence_snapshot_identity=knowledge.snapshot_digest,
        assessed_at=assessed_at,
    )


def build_cboe_put_structure_intent(
    symbol: str, decision: CboePutDecision
) -> OptionStructureIntent:
    """Project the exact source-selected PUT contract onto generic P01."""
    if decision.verdict != PASS or decision.selected_put is None:
        raise ValueError("Cboe PUT structure intent requires a passing exact selection")
    contract = decision.selected_put
    return OptionStructureIntent(
        symbol,
        StructureKind.SINGLE_LEG,
        (
            OptionLegIntent(
                "short_put",
                OptionType.PUT,
                contract.expiration,
                OptionLegPosition.SHORT,
                Decimal(1),
                selected_contract_identity=contract.identity,
            ),
        ),
    )


def build_cboe_put_subject_preparation_binding(
    now: datetime,
) -> SubjectPreparationBinding[CboePutPayload]:
    return SubjectPreparationBinding(
        SubjectPlanConsumer(
            CBOE_PUT_CONTRACT.strategy_id, bootstrap_demands(now), partial(expand_demands, now=now)
        ),
        partial(_prepare, now),
        build_cboe_put_subject_first_adapter,
        build_execution_assessment=_assessment,
    )
