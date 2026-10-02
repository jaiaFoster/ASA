"""Subject-first Heston production binding over sealed canonical evidence."""

from collections.abc import Mapping
from dataclasses import replace
from datetime import date, datetime
from functools import partial
from types import MappingProxyType

from analytics.calendar_facts import TradingCalendarView, monthly_expiration_day, new_york_time
from domain import (
    HistoricalOptionPanel,
    MarketCapability,
    MarketObservation,
    OptionChain,
    UnknownReason,
)
from market_data.session_calendar import UsEquitySessionCalendar
from market_data.snapshot import MarketSnapshot
from screening.subject_planning import ResolvedEvidenceView, SubjectPlanConsumer
from strategies.heston_knowledge import build_heston_knowledge_mapping
from strategies.heston_planning import bootstrap_demands, expand_demands
from strategies.heston_portfolio import HestonSubjectCandidate
from strategies.knowledge_contracts import KnowledgeMapping
from strategy_runtime.adapters.heston import HESTON_CONTRACT
from strategy_runtime.adapters.heston_portfolio import (
    HestonSubjectMaterialization,
    materialize_heston_family,
)
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
from strategy_runtime.values import TypedValue

_STRATEGY_ID = HESTON_CONTRACT.strategy_id


def _selected(snapshot: MarketSnapshot, capability: MarketCapability) -> MarketObservation | None:
    return next(
        (
            item.selected_observation
            for item in snapshot.resolution_results
            if item.capability is capability
        ),
        None,
    )


def _formation_state(now: datetime) -> str:
    local = new_york_time(now)
    calendar = UsEquitySessionCalendar()
    view = TradingCalendarView(
        lambda day: calendar.session(day) is not None,
        local.date().replace(day=1),
        local.date().replace(
            year=local.year + (local.month == 12), month=local.month % 12 + 1, day=1
        ),
    )
    expiration = monthly_expiration_day(view, local.year, local.month)
    if isinstance(expiration, UnknownReason):
        return "UNKNOWN"
    session = calendar.session(expiration)
    if local.date() != expiration or session is None or now < session.closes_at:
        return "FAIL"
    return "PASS"


def _formation_due(now: datetime) -> bool:
    return _formation_state(now) == "PASS"


def _prepare(
    now: datetime,
    snapshot: MarketSnapshot,
    projected_evidence: ResolvedEvidenceView,
    selections: tuple[tuple[str, object], ...],
    subject: str,
) -> KnowledgeMapping[HestonSubjectCandidate] | UnknownReason:
    del projected_evidence
    panel_observation = _selected(snapshot, MarketCapability.HISTORICAL_OPTION_PANEL_V1)
    chain_observation = _selected(snapshot, MarketCapability.OPTION_CHAIN_V1)
    if panel_observation is None or not isinstance(panel_observation.value, HistoricalOptionPanel):
        return UnknownReason("insufficient_straddle_return_history")
    if chain_observation is None or not isinstance(chain_observation.value, OptionChain):
        return UnknownReason("G_HES_LOWCOST_PAIR_UNKNOWN")
    expiration_value = dict(selections).get("expiration")
    if not isinstance(expiration_value, str):
        return UnknownReason("G_HES_FORMATION_DATE_UNKNOWN")
    selected_expiration = date.fromisoformat(expiration_value)
    return build_heston_knowledge_mapping(
        subject=subject,
        snapshot_digest=snapshot.snapshot_digest,
        panel_observation_id=panel_observation.observation_id,
        panel=panel_observation.value,
        chain_observation_id=chain_observation.observation_id,
        chain=chain_observation.value,
        selected_expiration=selected_expiration,
        formation_date_state=_formation_state(now),
    )


def _extract(knowledge: ReadOnlyStrategyInput[object]) -> object:
    if not isinstance(knowledge.payload, HestonSubjectCandidate):
        raise TypeError("Heston cross-subject extraction requires candidate knowledge")
    return knowledge.payload


def _bind(
    knowledge: ReadOnlyStrategyInput[object], materialized: object
) -> ReadOnlyStrategyInput[object]:
    if not isinstance(materialized, HestonSubjectMaterialization):
        raise TypeError("Heston cross-subject binding requires family materialization")
    return replace(knowledge, payload=materialized)


def _result(
    knowledge: ReadOnlyStrategyInput[object], context: RuntimeContext
) -> UniversalScreeningResult:
    payload = knowledge.payload
    if not isinstance(payload, HestonSubjectMaterialization):
        raise TypeError("Heston evaluation requires cross-subject materialization")
    success = payload.state == "PASS"
    unknown = payload.state == "UNKNOWN"
    state = (
        EvaluationState.PASS
        if success
        else EvaluationState.MISSING_DATA
        if unknown
        else EvaluationState.NO_SIGNAL
    )
    metrics = {
        "decision.reason": TypedValue.of_string(payload.reason),
        "decision.state": TypedValue.of_string(payload.state),
        "assumption.RA-XR-03": TypedValue.of_string(
            "low_cost_pair_failure_excludes_without_replacement"
        ),
    }
    if payload.quantile is not None:
        metrics["heston.quantile"] = TypedValue.of_integer(payload.quantile)
    if payload.position is not None:
        metrics["structure.position_identity"] = TypedValue.of_string(payload.position.identity)
    if payload.portfolio is not None:
        metrics["portfolio.identity"] = TypedValue.of_string(payload.portfolio.identity)
    return UniversalScreeningResult(
        strategy_id=_STRATEGY_ID,
        strategy_version=HESTON_CONTRACT.version,
        symbol=context.subject,
        observation_id=compute_observation_id(context.run_id, _STRATEGY_ID, context.subject),
        opportunity_id=compute_opportunity_id(
            _STRATEGY_ID, context.subject, payload.position.identity
        )
        if success and payload.position is not None
        else None,
        row_type=RowType.RESULT,
        verdict="PASS" if success else None if unknown else "FAIL",
        evaluation_state=state,
        lifecycle_stage="entered" if success else None,
        recommendation_state=None,
        data_quality=None,
        metrics=metrics,
        economics={},
        blockers=(payload.reason,) if unknown else (),
        warnings=(),
        provenance=(
            f"snapshot_id:{knowledge.snapshot_id}",
            f"snapshot_digest:{knowledge.snapshot_digest}",
        ),
        observed_at=knowledge.effective_time,
    )


def build_heston_subject_first_adapter(
    knowledge_by_subject: Mapping[str, ReadOnlyStrategyInput[object]],
) -> StrategyAdapter[UniversalScreeningResult]:
    frozen = MappingProxyType(dict(knowledge_by_subject))
    return lambda context: _result(frozen[context.subject], context)


def build_heston_subject_preparation_binding(now: datetime) -> SubjectPreparationBinding[object]:
    return SubjectPreparationBinding(
        consumer=SubjectPlanConsumer(
            _STRATEGY_ID, bootstrap_demands(now), partial(expand_demands, now=now)
        ),
        prepare_knowledge_mapping=partial(_prepare, now),
        build_shadow_adapter=build_heston_subject_first_adapter,
        cross_subject_family_id="heston_straddle_momentum_v1",
        bind_cross_subject_facts=_bind,
        extract_cross_subject_candidate=_extract,
        materialize_cross_subject_family=materialize_heston_family,
        requires_complete_cross_subject_universe=True,
        cross_subject_family_due=_formation_due,
    )
