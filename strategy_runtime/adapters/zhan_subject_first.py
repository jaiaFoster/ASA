"""Subject-first Zhan production binding over sealed canonical evidence."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import replace
from datetime import datetime, timedelta
from functools import partial
from types import MappingProxyType

from domain import (
    MarketCapability,
    MarketObservation,
    OHLCVSeries,
    OptionChain,
    RateObservation,
    SecurityMasterRecord,
    UnknownReason,
)
from market_data.session_calendar import NEW_YORK, UsEquitySessionCalendar
from market_data.snapshot import MarketSnapshot
from screening.subject_planning import ResolvedEvidenceView, SubjectPlanConsumer
from strategies.knowledge_contracts import KnowledgeMapping
from strategies.zhan_knowledge import build_zhan_knowledge_mapping
from strategies.zhan_planning import bootstrap_demands, expand_demands
from strategies.zhan_portfolio import ZhanSubjectCandidate
from strategy_runtime.adapters.zhan import ZHAN_CONTRACT
from strategy_runtime.adapters.zhan_portfolio import (
    ZhanSubjectMaterialization,
    materialize_zhan_family,
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

_STRATEGY_ID = ZHAN_CONTRACT.strategy_id


def _last_session_of_month(now: datetime) -> bool:
    local = now.astimezone(NEW_YORK)
    calendar = UsEquitySessionCalendar()
    current = calendar.session(local.date())
    if current is None or now < current.closes_at:
        return False
    day = local.date() + timedelta(days=1)
    for _ in range(8):
        following = calendar.session(day)
        if following is not None:
            return following.trading_date.month != local.month
        day += timedelta(days=1)
    return False


def _selected(snapshot: MarketSnapshot, capability: MarketCapability) -> MarketObservation | None:
    return next(
        (
            item.selected_observation
            for item in snapshot.resolution_results
            if item.capability is capability
        ),
        None,
    )


def _prepare(
    now: datetime,
    snapshot: MarketSnapshot,
    projected_evidence: ResolvedEvidenceView,
    selections: tuple[tuple[str, object], ...],
    subject: str,
) -> KnowledgeMapping[ZhanSubjectCandidate] | UnknownReason:
    del projected_evidence, selections
    bars_observation = _selected(snapshot, MarketCapability.HISTORICAL_BARS_V1)
    security_observation = _selected(snapshot, MarketCapability.SECURITY_MASTER_V1)
    rate_observation = _selected(snapshot, MarketCapability.RATE_OBSERVATION_V1)
    chain_observation = _selected(snapshot, MarketCapability.OPTION_CHAIN_V1)
    if bars_observation is None or not isinstance(bars_observation.value, OHLCVSeries):
        return UnknownReason("G_ZHAN_PRICE_UNKNOWN")
    if security_observation is None or not isinstance(
        security_observation.value, SecurityMasterRecord
    ):
        return UnknownReason("G_ZHAN_SECURITY_MASTER_UNKNOWN")
    if rate_observation is None or not isinstance(rate_observation.value, RateObservation):
        return UnknownReason("G_ZHAN_RATE_UNKNOWN")
    if chain_observation is None or not isinstance(chain_observation.value, OptionChain):
        return UnknownReason("G_ZHAN_OPTION_QUOTE_UNKNOWN")
    bars = bars_observation.value.bars
    if not bars:
        return UnknownReason("G_ZHAN_PRICE_UNKNOWN")
    spot = max(bars, key=lambda item: item.end_at).close
    return build_zhan_knowledge_mapping(
        subject=subject,
        snapshot_digest=snapshot.snapshot_digest,
        bars_observation_id=bars_observation.observation_id,
        spot=spot,
        security_observation_id=security_observation.observation_id,
        security=security_observation.value,
        rate_observation_id=rate_observation.observation_id,
        risk_free_rate=rate_observation.value.value,
        chain_observation_id=chain_observation.observation_id,
        chain=chain_observation.value,
        formation_date_state="PASS" if _last_session_of_month(now) else "FAIL",
    )


def _extract(knowledge: ReadOnlyStrategyInput[object]) -> object:
    if not isinstance(knowledge.payload, ZhanSubjectCandidate):
        raise TypeError("Zhan cross-subject extraction requires candidate knowledge")
    return knowledge.payload


def _bind(
    knowledge: ReadOnlyStrategyInput[object], materialized: object
) -> ReadOnlyStrategyInput[object]:
    if not isinstance(materialized, ZhanSubjectMaterialization):
        raise TypeError("Zhan cross-subject binding requires materialized family result")
    return replace(knowledge, payload=materialized)


def _result(
    knowledge: ReadOnlyStrategyInput[object], context: RuntimeContext
) -> UniversalScreeningResult:
    payload = knowledge.payload
    if not isinstance(payload, ZhanSubjectMaterialization):
        raise TypeError("Zhan evaluation requires cross-subject materialization")
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
    }
    if payload.quantile is not None:
        metrics["zhan.quantile"] = TypedValue.of_integer(payload.quantile)
    if payload.position is not None:
        metrics["structure.position_identity"] = TypedValue.of_string(payload.position.identity)
    if payload.portfolio is not None:
        metrics["portfolio.identity"] = TypedValue.of_string(payload.portfolio.identity)
    return UniversalScreeningResult(
        strategy_id=_STRATEGY_ID,
        strategy_version=ZHAN_CONTRACT.version,
        symbol=context.subject,
        observation_id=compute_observation_id(context.run_id, _STRATEGY_ID, context.subject),
        opportunity_id=(
            compute_opportunity_id(
                _STRATEGY_ID,
                context.subject,
                payload.position.identity if payload.position is not None else "",
            )
            if success
            else None
        ),
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


def build_zhan_subject_first_adapter(
    knowledge_by_subject: Mapping[str, ReadOnlyStrategyInput[object]],
) -> StrategyAdapter[UniversalScreeningResult]:
    frozen = MappingProxyType(dict(knowledge_by_subject))
    return lambda context: _result(frozen[context.subject], context)


def build_zhan_subject_preparation_binding(
    now: datetime,
) -> SubjectPreparationBinding[object]:
    return SubjectPreparationBinding(
        consumer=SubjectPlanConsumer(
            _STRATEGY_ID,
            bootstrap_demands(now),
            partial(expand_demands, now=now),
        ),
        prepare_knowledge_mapping=partial(_prepare, now),
        build_shadow_adapter=build_zhan_subject_first_adapter,
        cross_subject_family_id="zhan_delta_neutral_call_v1",
        bind_cross_subject_facts=_bind,
        extract_cross_subject_candidate=_extract,
        materialize_cross_subject_family=materialize_zhan_family,
    )
