"""BXM sealed-evidence preparation and read-only adapter."""

from collections.abc import Mapping
from datetime import date, datetime, time
from decimal import Decimal
from functools import partial
from types import MappingProxyType

from analytics.calendar_facts import TradingCalendarView, third_friday_roll_date
from domain import (
    IndexDividendPoints,
    IndexSettlementValue,
    MarketCapability,
    OptionChain,
    OptionLeg,
    OptionLegPosition,
    OptionTradeTape,
    Quote,
    UnknownReason,
)
from market_data.session_calendar import NEW_YORK, UsEquitySessionCalendar
from market_data.snapshot import MarketSnapshot
from screening.subject_fact_projection import resolution_for
from screening.subject_planning import ResolvedEvidenceView, SubjectPlanConsumer
from strategies.bxm_evaluation import NO_ACTION, BXMDecision, evaluate_bxm
from strategies.bxm_knowledge import BxmPayload, build_bxm_knowledge_mapping
from strategies.bxm_planning import bootstrap_demands, expand_demands
from strategies.knowledge_contracts import KnowledgeMapping
from strategies.tristate_components import PASS, UNKNOWN
from strategy_runtime.adapters.bxm import BXM_CONTRACT
from strategy_runtime.context import RuntimeContext
from strategy_runtime.knowledge import ReadOnlyStrategyInput
from strategy_runtime.lifecycle import compute_opportunity_id
from strategy_runtime.registry import StrategyAdapter
from strategy_runtime.result import (
    EvaluationState,
    RowType,
    UniversalScreeningResult,
    compute_observation_id,
)
from strategy_runtime.subject_preparation import SubjectPreparationBinding
from strategy_runtime.underlying_overlay import (
    OptionOverlayPosition,
    UnderlyingExposureKind,
    UnderlyingExposureLeg,
)
from strategy_runtime.values import TypedValue


def _prepare(
    now: datetime,
    snapshot: MarketSnapshot,
    projected: ResolvedEvidenceView,
    selections: tuple[tuple[str, object], ...],
    subject: str,
) -> KnowledgeMapping[BxmPayload] | UnknownReason:
    del projected, selections
    try:
        quote_r = resolution_for(snapshot, MarketCapability.REAL_TIME_QUOTE_V1)
        chain_r = resolution_for(snapshot, MarketCapability.OPTION_CHAIN_V1)
    except ValueError:
        return UnknownReason("BXM_REQUIRED_EVIDENCE_UNUSABLE")
    quote_o, chain_o = quote_r.selected_observation, chain_r.selected_observation
    if quote_o is None or not isinstance(quote_o.value, Quote) or quote_o.value.last is None:
        return UnknownReason("G_CBOE_SPX_REF_BEFORE_1100_UNKNOWN")
    if chain_o is None or not isinstance(chain_o.value, OptionChain):
        return UnknownReason("G_BXM_STRIKE_EXISTS_UNKNOWN")
    def _optional(
        capability: MarketCapability, expected: type[object]
    ) -> tuple[str, object] | None:
        try:
            resolution = resolution_for(snapshot, capability)
        except ValueError:
            return None
        observation = resolution.selected_observation
        if observation is None or not isinstance(observation.value, expected):
            return None
        return observation.observation_id, observation.value

    local = now.astimezone(NEW_YORK)
    window_start = local.replace(hour=11, minute=30, second=0, microsecond=0)
    window_end = local.replace(hour=13, minute=30, second=0, microsecond=0)
    tape = _optional(MarketCapability.OPTION_TRADE_TAPE_V1, OptionTradeTape)
    dividends = _optional(MarketCapability.INDEX_DIVIDEND_POINTS_V1, IndexDividendPoints)
    settlement = _optional(MarketCapability.INDEX_SETTLEMENT_VALUE_V1, IndexSettlementValue)
    return build_bxm_knowledge_mapping(
        subject=subject,
        snapshot_digest=snapshot.snapshot_digest,
        quote_observation_id=quote_o.observation_id,
        chain_observation_id=chain_o.observation_id,
        chain=chain_o.value,
        spot=quote_o.value.last,
        quote_effective_time=quote_o.effective_time,
        tape_observation=tape,  # type: ignore[arg-type]
        dividend_observation=dividends,  # type: ignore[arg-type]
        settlement_observation=settlement,  # type: ignore[arg-type]
        vwap_window_start=window_start,
        vwap_window_end=window_end,
    )


def _decision(payload: BxmPayload, now: datetime) -> BXMDecision:
    local = now.astimezone(NEW_YORK)
    first = local.date().replace(day=1)
    following = date(first.year + (first.month == 12), first.month % 12 + 1, 1)
    sessions = UsEquitySessionCalendar()
    roll_date = third_friday_roll_date(
        TradingCalendarView(lambda value: sessions.session(value) is not None, first, following),
        local.year,
        local.month,
    )
    observed = payload.quote_effective_time.astimezone(NEW_YORK)
    reference_state = (
        PASS
        if not isinstance(roll_date, UnknownReason)
        and observed.date() == roll_date
        and observed.time() < time(11)
        else UNKNOWN
    )
    return evaluate_bxm(
        decision_date=local.date(),
        roll_date=roll_date,
        reference_state=reference_state,
        quote_value=payload.spot,
        chain=payload.chain,
    )


def build_bxm_overlay(payload: BxmPayload, decision: BXMDecision) -> OptionOverlayPosition:
    if decision.verdict != PASS or decision.selected_call is None:
        raise ValueError("BXM overlay requires a passing exact call selection")
    call = decision.selected_call
    exposure = UnderlyingExposureLeg(
        call.underlying.instrument,
        Decimal(1),
        UnderlyingExposureKind.INDEX_TOTAL_RETURN,
        False,
    )
    return OptionOverlayPosition(
        exposure,
        (OptionLeg(call, OptionLegPosition.SHORT, Decimal(1), "short_call"),),
    )


def build_bxm_subject_first_adapter(
    knowledge_by_subject: Mapping[str, ReadOnlyStrategyInput[BxmPayload]],
) -> StrategyAdapter[UniversalScreeningResult]:
    frozen = MappingProxyType(dict(knowledge_by_subject))

    def _adapter(context: RuntimeContext) -> UniversalScreeningResult:
        knowledge = frozen[context.subject]
        payload = knowledge.payload
        decision = _decision(knowledge.payload, context.clock.now())
        state = (
            EvaluationState.PASS
            if decision.verdict == PASS
            else EvaluationState.NO_SIGNAL
            if decision.verdict == NO_ACTION
            else EvaluationState.MISSING_DATA
        )
        metrics = {
            "decision.reason": TypedValue.of_string(decision.reason),
            "entry.price_state": TypedValue.of_string(
                payload.entry_vwap.code
                if isinstance(payload.entry_vwap, UnknownReason)
                else "RESOLVED_WINDOWED_OPTION_TRADE_VWAP"
            ),
            "outcome.dividend_state": TypedValue.of_string(
                payload.dividend_points.code
                if isinstance(payload.dividend_points, UnknownReason)
                else "RESOLVED_INDEX_DIVIDEND_POINTS"
            ),
            "lifecycle.soq_state": TypedValue.of_string(
                payload.settlement_value.code
                if isinstance(payload.settlement_value, UnknownReason)
                else "RESOLVED_INDEX_SETTLEMENT_VALUE"
            ),
        }
        if isinstance(payload.entry_vwap, Decimal):
            metrics["entry.windowed_vwap"] = TypedValue.of_decimal(payload.entry_vwap)
        if isinstance(payload.dividend_points, IndexDividendPoints):
            metrics["outcome.index_dividend_points"] = TypedValue.of_decimal(
                payload.dividend_points.points
            )
        if isinstance(payload.settlement_value, IndexSettlementValue):
            metrics["lifecycle.soq_value"] = TypedValue.of_decimal(
                payload.settlement_value.value
            )
        if state is EvaluationState.PASS:
            metrics["structure.overlay_identity"] = TypedValue.of_string(
                build_bxm_overlay(knowledge.payload, decision).identity
            )
            metrics["structure.broker_executable"] = TypedValue.of_boolean(False)
        return UniversalScreeningResult(
            BXM_CONTRACT.strategy_id,
            BXM_CONTRACT.version,
            context.subject,
            compute_observation_id(context.run_id, BXM_CONTRACT.strategy_id, context.subject),
            compute_opportunity_id(BXM_CONTRACT.strategy_id, context.subject)
            if state is EvaluationState.PASS
            else None,
            RowType.RESULT,
            None if state is EvaluationState.MISSING_DATA else decision.verdict,
            state,
            "identified" if state is EvaluationState.PASS else None,
            None,
            None,
            metrics,
            {},
            () if state is not EvaluationState.MISSING_DATA else (decision.reason,),
            (
                "index_exposure_is_analytical_and_non_broker_executable",
                "entry_VWAP_is_UNKNOWN_without_X05_trade_tape",
                "outcome_is_UNKNOWN_without_X07_dividend_points_and_SOQ",
            ),
            (
                f"snapshot_id:{knowledge.snapshot_id}",
                f"snapshot_digest:{knowledge.snapshot_digest}",
            ),
            knowledge.effective_time,
        )

    return _adapter


def build_bxm_subject_preparation_binding(
    now: datetime,
) -> SubjectPreparationBinding[BxmPayload]:
    return SubjectPreparationBinding(
        SubjectPlanConsumer(
            BXM_CONTRACT.strategy_id, bootstrap_demands(now), partial(expand_demands, now=now)
        ),
        partial(_prepare, now),
        build_bxm_subject_first_adapter,
    )
