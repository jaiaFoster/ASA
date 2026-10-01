"""SCS sealed-evidence preparation and read-only adapter."""

from collections.abc import Mapping
from datetime import date, datetime
from decimal import Decimal
from functools import partial
from types import MappingProxyType

from analytics.calendar_facts import TradingCalendarView, first_trading_day_of_month
from domain import (
    EvidenceUsability,
    IndexSettlementValue,
    MarketCapability,
    OptionChain,
    OptionLegPosition,
    OptionType,
    Quote,
    RateBasis,
    RateObservation,
    UnknownReason,
)
from market_data.session_calendar import NEW_YORK, UsEquitySessionCalendar
from market_data.snapshot import MarketSnapshot
from screening.subject_fact_projection import resolution_for
from screening.subject_planning import ResolvedEvidenceView, SubjectPlanConsumer
from strategies.knowledge_contracts import KnowledgeMapping
from strategies.scs_evaluation import NO_ACTION, SCSDecision, evaluate_scs
from strategies.scs_knowledge import SCSPayload, build_scs_knowledge_mapping
from strategies.scs_manifest import scs_parameter
from strategies.scs_planning import (
    bootstrap_demands,
    expand_demands,
    rate_demand,
    settlement_demand,
)
from strategies.tristate_components import PASS
from strategy_runtime.adapters.scs import SCS_CONTRACT
from strategy_runtime.context import RuntimeContext
from strategy_runtime.contract import StructureKind
from strategy_runtime.executable_structures import ExecutableStructureAssessment
from strategy_runtime.knowledge import ReadOnlyStrategyInput
from strategy_runtime.lifecycle import compute_opportunity_id, select_lifecycle_exit_date
from strategy_runtime.option_structure_resolver import (
    OptionLegIntent,
    OptionStructureIntent,
    resolve_option_structure,
)
from strategy_runtime.persistence import LifecyclePositionState
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
    risk = projected.get(rate_demand(now, "risk_free_series").demand_id)
    dividend = projected.get(rate_demand(now, "dividend_yield_series").demand_id)
    settlement = projected.get(settlement_demand(now).demand_id)

    def _rate_value(item: object, basis: RateBasis) -> Decimal | None:
        if item is None or getattr(item, "usability", None) is not EvidenceUsability.RESOLVED:
            return None
        value = getattr(item, "value", None)
        return value.value if isinstance(value, RateObservation) and value.basis is basis else None

    return build_scs_knowledge_mapping(
        subject=subject,
        quote_observation_id=quote_o.observation_id,
        chain_observation_id=chain_o.observation_id,
        chain=chain_o.value,
        spot=quote_o.value.last,
        selected_expiration=date.fromisoformat(expiration_value),
        quote_effective_time=quote_o.effective_time,
        rate=_rate_value(risk, RateBasis.BANK_DISCOUNT),
        dividend_yield=_rate_value(dividend, RateBasis.DIVIDEND_YIELD),
        settlement_value=(
            settlement.value
            if settlement is not None
            and settlement.usability is EvidenceUsability.RESOLVED
            and isinstance(settlement.value, IndexSettlementValue)
            else None
        ),
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
    local = now.astimezone(NEW_YORK)
    first = local.date().replace(day=1)
    following = date(first.year + (first.month == 12), first.month % 12 + 1, 1)
    calendar = UsEquitySessionCalendar()
    entry_day = first_trading_day_of_month(
        TradingCalendarView(lambda value: calendar.session(value) is not None, first, following),
        local.year,
        local.month,
    )
    session = calendar.session(local.date())
    if isinstance(entry_day, UnknownReason) or session is None:
        return SCSDecision("UNKNOWN", "G_SCS_ENTRY_DATE_UNKNOWN")
    return evaluate_scs(
        decision_date=now.astimezone(NEW_YORK).date(),
        selected_expiration=payload.selected_expiration,
        spot=payload.spot,
        chain=payload.chain,
        rate=payload.rate,
        dividend_yield=payload.dividend_yield,
        decision_time=local,
        quote_effective_time=payload.quote_effective_time,
        first_trading_day=entry_day,
        session_close=session.closes_at,
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
                decision.short_call_quantity,
                selected_contract_identity=decision.selected_call.identity,
            ),
            OptionLegIntent(
                "short_put",
                OptionType.PUT,
                decision.selected_put.expiration,
                OptionLegPosition.SHORT,
                decision.short_put_quantity,
                selected_contract_identity=decision.selected_put.identity,
            ),
        ),
    )


def build_scs_subject_first_adapter(
    knowledge_by_subject: Mapping[str, ReadOnlyStrategyInput[SCSPayload]],
    lifecycle_state_by_subject: Mapping[str, LifecyclePositionState] = MappingProxyType({}),
    *,
    exit_policy: str = str(scs_parameter("exit_policy")),
) -> StrategyAdapter[UniversalScreeningResult]:
    frozen = MappingProxyType(dict(knowledge_by_subject))
    lifecycle = MappingProxyType(dict(lifecycle_state_by_subject))

    def _adapter(context: RuntimeContext) -> UniversalScreeningResult:
        knowledge = frozen[context.subject]
        decision = _decision(knowledge.payload, context.clock.now())
        prior = lifecycle.get(context.subject)
        local_now = context.clock.now().astimezone(NEW_YORK)
        previous_identity: str | None = None
        if prior is not None:
            next_month = date(
                prior.entered_on.year + (prior.entered_on.month == 12),
                prior.entered_on.month % 12 + 1,
                1,
            )
            after_next = date(
                next_month.year + (next_month.month == 12),
                next_month.month % 12 + 1,
                1,
            )
            calendar = UsEquitySessionCalendar()
            next_entry = first_trading_day_of_month(
                TradingCalendarView(
                    lambda value: calendar.session(value) is not None,
                    next_month,
                    after_next,
                ),
                next_month.year,
                next_month.month,
            )
            if isinstance(next_entry, UnknownReason):
                decision = SCSDecision("UNKNOWN", "G_SCS_EXIT_DATE_UNKNOWN")
                next_entry = prior.expires_on
            exit_day = select_lifecycle_exit_date(
                exit_policy, (prior.expires_on, next_entry)
            )
            exit_session = calendar.session(exit_day)
            exit_due = local_now.date() > exit_day or (
                local_now.date() == exit_day
                and exit_session is not None
                and context.clock.now() >= exit_session.closes_at
            )
            if not exit_due:
                decision = SCSDecision("HOLD", "SCS_POSITION_HELD")
            elif exit_day == prior.expires_on and (
                knowledge.payload.settlement_value is None
                or knowledge.payload.settlement_value.settlement_date != prior.expires_on
            ):
                decision = SCSDecision("UNKNOWN", "SCS_EXPIRY_SETTLEMENT_UNKNOWN")
            else:
                previous_identity = prior.position_identity
        state = (
            EvaluationState.PASS
            if decision.verdict in (PASS, "HOLD")
            else EvaluationState.NO_SIGNAL
            if decision.verdict == NO_ACTION
            else EvaluationState.MISSING_DATA
        )
        metrics = {
            "decision.reason": TypedValue.of_string(decision.reason),
            "decision.assumption": TypedValue.of_string(
                "RA-SV-01:standard_monthly_SPX_expirations_only"
            ),
            "quote_filter.rate_state": TypedValue.of_string(
                "RESOLVED_CANONICAL_RATE"
                if knowledge.payload.rate is not None
                else "UNKNOWN_CANONICAL_RATE_NOT_BOUND"
            ),
            "quote_filter.dividend_yield_state": TypedValue.of_string(
                "RESOLVED_CANONICAL_SPX_DIVIDEND_YIELD"
                if knowledge.payload.dividend_yield is not None
                else "UNKNOWN_CANONICAL_SPX_DIVIDEND_YIELD_NOT_AVAILABLE"
            ),
        }
        economics = {
            "margin.call.formula": TypedValue.of_string("DF-CBOE-NAKED-MARGIN@1.1.0"),
            "margin.put.formula": TypedValue.of_string("DF-CBOE-NAKED-MARGIN@1.1.0"),
            "margin.straddle.formula": TypedValue.of_string(
                "DF-CBOE-STRADDLE-MARGIN@1.0.0"
            ),
        }
        for name, value in (
            ("margin.call", decision.call_naked_margin),
            ("margin.put", decision.put_naked_margin),
            ("margin.straddle", decision.straddle_margin),
        ):
            economics[name] = (
                TypedValue.of_string(f"UNKNOWN:{value.code}")
                if isinstance(value, UnknownReason)
                else TypedValue.of_decimal(value)
            )
        lifecycle_stage = None
        opportunity_id = None
        if decision.verdict == "HOLD" and prior is not None:
            lifecycle_stage = "entered"
            opportunity_id = compute_opportunity_id(SCS_CONTRACT.strategy_id, context.subject)
            metrics.update(
                {
                    "lifecycle.held_position_identity": TypedValue.of_string(
                        prior.position_identity
                    ),
                    "lifecycle.entered_on": TypedValue.of_string(prior.entered_on.isoformat()),
                    "lifecycle.expires_on": TypedValue.of_string(prior.expires_on.isoformat()),
                }
            )
        elif decision.verdict == PASS and decision.selected_call and decision.selected_put:
            lifecycle_stage = "entered"
            opportunity_id = compute_opportunity_id(SCS_CONTRACT.strategy_id, context.subject)
            identity = "|".join(
                sorted((decision.selected_call.identity, decision.selected_put.identity))
            )
            metrics.update(
                {
                    "lifecycle.held_position_identity": TypedValue.of_string(identity),
                    "lifecycle.entered_on": TypedValue.of_string(local_now.date().isoformat()),
                    "lifecycle.expires_on": TypedValue.of_string(
                        decision.selected_call.expiration.isoformat()
                    ),
                }
            )
            if previous_identity is not None:
                metrics["lifecycle.exited_position_identity"] = TypedValue.of_string(
                    previous_identity
                )
        elif prior is not None and decision.reason == "SCS_EXPIRY_SETTLEMENT_UNKNOWN":
            lifecycle_stage = "expired"
            opportunity_id = compute_opportunity_id(SCS_CONTRACT.strategy_id, context.subject)
        elif prior is not None and previous_identity is not None:
            lifecycle_stage = "expired"
            opportunity_id = compute_opportunity_id(SCS_CONTRACT.strategy_id, context.subject)
            metrics["lifecycle.position_closed"] = TypedValue.of_boolean(True)
            metrics["lifecycle.exited_position_identity"] = TypedValue.of_string(previous_identity)
        return UniversalScreeningResult(
            SCS_CONTRACT.strategy_id,
            SCS_CONTRACT.version,
            context.subject,
            compute_observation_id(context.run_id, SCS_CONTRACT.strategy_id, context.subject),
            opportunity_id,
            RowType.RESULT,
            None if state is EvaluationState.MISSING_DATA else decision.verdict,
            state,
            lifecycle_stage,
            None,
            None,
            metrics,
            economics,
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


def build_scs_subject_preparation_binding(
    now: datetime,
    lifecycle_state_by_subject: Mapping[str, LifecyclePositionState] = MappingProxyType({}),
) -> SubjectPreparationBinding[SCSPayload]:
    return SubjectPreparationBinding(
        SubjectPlanConsumer(
            SCS_CONTRACT.strategy_id, bootstrap_demands(now), partial(expand_demands, now=now)
        ),
        partial(_prepare, now),
        partial(
            build_scs_subject_first_adapter,
            lifecycle_state_by_subject=lifecycle_state_by_subject,
        ),
        build_execution_assessment=_assessment,
    )
