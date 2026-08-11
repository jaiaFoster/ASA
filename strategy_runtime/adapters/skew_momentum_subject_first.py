"""Skew Momentum preparation and read-only runtime binding."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime
from decimal import Decimal
from functools import partial
from types import MappingProxyType
from typing import cast

from domain import (
    CanonicalInstrumentIdentity,
    MarketCapability,
    OHLCVSeries,
    OptionChain,
    OptionType,
    Quote,
    UnknownReason,
)
from market_data.snapshot import MarketSnapshot
from screening.context_builders import build_skew_momentum_context
from screening.explanations import build_graph_explanation
from screening.live_context import select_atm_strike_at_expiration, select_nearest_delta_contract
from screening.subject_fact_projection import resolution_for
from screening.subject_planning import ResolvedEvidenceView, SubjectPlanConsumer
from strategies import (
    CORE_COMPONENTS,
    SKEW_MOMENTUM_VERTICAL_MANIFEST,
    STONK_STRATEGY_PLUGINS,
    compile_strategy_graph,
    execute_strategy_graph,
)
from strategies.knowledge_contracts import KnowledgeMapping
from strategies.plugins import build_plugin_registry
from strategies.skew_momentum_knowledge import (
    SkewMomentumPayload,
    build_skew_momentum_knowledge_mapping,
)
from strategies.skew_momentum_planning import bootstrap_demands, expand_demands
from strategy_runtime.adapters._screening_bridge import explanation_metrics
from strategy_runtime.adapters.skew_momentum_vertical import SKEW_MOMENTUM_VERTICAL_CONTRACT
from strategy_runtime.context import RuntimeContext
from strategy_runtime.historical_evidence import HistoricalSkewRepository
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

_STRATEGY_ID = "skew_momentum"
_COMPONENTS = build_plugin_registry(CORE_COMPONENTS, STONK_STRATEGY_PLUGINS)


def _spot(quote: Quote) -> Decimal:
    if quote.last is not None:
        return quote.last
    if quote.bid is not None and quote.ask is not None:
        return (quote.bid + quote.ask) / Decimal(2)
    raise ValueError("quote has no usable spot")


def _prepare(
    historical_repository: HistoricalSkewRepository | None,
    now: datetime,
    snapshot: MarketSnapshot,
    projected: ResolvedEvidenceView,
    selections: tuple[tuple[str, object], ...],
    subject: str,
) -> KnowledgeMapping[SkewMomentumPayload] | UnknownReason:
    del projected
    quote_resolution = resolution_for(snapshot, MarketCapability.REAL_TIME_QUOTE_V1)
    chain_resolution = resolution_for(snapshot, MarketCapability.OPTION_CHAIN_V1)
    bars_resolution = resolution_for(snapshot, MarketCapability.HISTORICAL_BARS_V1)
    quote_observation = quote_resolution.selected_observation
    chain_observation = chain_resolution.selected_observation
    bars_observation = bars_resolution.selected_observation
    if quote_observation is None or not isinstance(quote_observation.value, Quote):
        return UnknownReason("unusable_quote")
    if chain_observation is None or not isinstance(chain_observation.value, OptionChain):
        return UnknownReason("unusable_option_chain")
    if bars_observation is None or not isinstance(bars_observation.value, OHLCVSeries):
        return UnknownReason("unusable_historical_bars")
    closes = tuple(bar.close for bar in bars_observation.value.bars)
    if len(closes) < 21:
        return UnknownReason("insufficient_historical_bars")
    expiration_text = dict(selections).get("expiration")
    if not isinstance(expiration_text, str):
        return UnknownReason("no_future_expiration")
    expiration = datetime.fromisoformat(expiration_text).date()
    chain = chain_observation.value
    spot = _spot(quote_observation.value)
    call_strike = select_atm_strike_at_expiration(chain, expiration, spot, OptionType.CALL)
    put_strike = select_atm_strike_at_expiration(chain, expiration, spot, OptionType.PUT)
    (call_atm,) = chain.find(expiration=expiration, strike=call_strike, option_type=OptionType.CALL)
    (put_atm,) = chain.find(expiration=expiration, strike=put_strike, option_type=OptionType.PUT)
    call_wing = select_nearest_delta_contract(
        chain, expiration, OptionType.CALL, Decimal("0.25"), exclude_strike=call_strike
    )
    put_wing = select_nearest_delta_contract(
        chain, expiration, OptionType.PUT, Decimal("-0.25"), exclude_strike=put_strike
    )
    values = tuple(item.implied_volatility for item in (call_atm, put_atm, call_wing, put_wing))
    if any(value is None for value in values):
        return UnknownReason("missing_implied_volatility")
    history = (
        ()
        if historical_repository is None
        else historical_repository.history_for(
            CanonicalInstrumentIdentity("symbol", subject),
            as_of=now,
            maximum_observations=60,
        )
    )
    return build_skew_momentum_knowledge_mapping(
        subject=subject,
        snapshot_digest=snapshot.snapshot_digest,
        chain_observation_id=chain_observation.observation_id,
        bars_observation_id=bars_observation.observation_id,
        chain=chain,
        expiration=expiration,
        closes=closes,
        call_atm_iv=cast(Decimal, values[0]),
        put_atm_iv=cast(Decimal, values[1]),
        call_wing_iv=cast(Decimal, values[2]),
        put_wing_iv=cast(Decimal, values[3]),
        history=history,
    )


def build_skew_momentum_subject_preparation_binding(
    now: datetime, historical_repository: HistoricalSkewRepository | None = None
) -> SubjectPreparationBinding[SkewMomentumPayload]:
    return SubjectPreparationBinding(
        SubjectPlanConsumer(_STRATEGY_ID, bootstrap_demands(now), partial(expand_demands, now=now)),
        partial(_prepare, historical_repository, now),
        build_skew_momentum_subject_first_adapter,
    )


def build_skew_momentum_subject_first_adapter(
    knowledge_by_subject: Mapping[str, ReadOnlyStrategyInput[SkewMomentumPayload]],
) -> StrategyAdapter[UniversalScreeningResult]:
    frozen = MappingProxyType(dict(knowledge_by_subject))

    def _adapter(context: RuntimeContext) -> UniversalScreeningResult:
        knowledge = frozen[context.subject]
        payload = knowledge.payload
        graph_context = build_skew_momentum_context(
            payload.chain,
            payload.expiration,
            normalized_call_skew=payload.normalized_call_skew,
            normalized_put_skew=payload.normalized_put_skew,
            call_skew_zscore=payload.call_skew_zscore,
            put_skew_zscore=payload.put_skew_zscore,
            historical_valid_observations=payload.historical_valid_observations,
            call_atm_iv_minus_rv=payload.call_atm_iv_minus_rv,
            put_atm_iv_minus_rv=payload.put_atm_iv_minus_rv,
            call_wing_iv_minus_rv=payload.call_wing_iv_minus_rv,
            put_wing_iv_minus_rv=payload.put_wing_iv_minus_rv,
            call_wing_iv_minus_atm_iv=payload.call_wing_iv_minus_atm_iv,
            put_wing_iv_minus_atm_iv=payload.put_wing_iv_minus_atm_iv,
            time_series_return=payload.time_series_return,
            cross_sectional_percentile=None,
            comparison_peer_count=0,
            sector_relative_return=None,
        )
        outputs = execute_strategy_graph(
            compile_strategy_graph(SKEW_MOMENTUM_VERTICAL_MANIFEST, _COMPONENTS), graph_context
        ).outputs
        verdict = str(outputs.get("verdict").value)
        explanation = build_graph_explanation(SKEW_MOMENTUM_VERTICAL_MANIFEST, outputs)
        metrics = explanation_metrics(explanation)
        score = outputs.get("score").value
        if isinstance(score, Decimal):
            metrics["strategy_native_score"] = TypedValue.of_decimal(score)
        return UniversalScreeningResult(
            strategy_id=_STRATEGY_ID,
            strategy_version=SKEW_MOMENTUM_VERTICAL_CONTRACT.version,
            symbol=context.subject,
            observation_id=compute_observation_id(context.run_id, _STRATEGY_ID, context.subject),
            opportunity_id=None,
            row_type=RowType.RESULT,
            verdict=verdict,
            evaluation_state=EvaluationState.PASS
            if verdict in {"PASS", "WATCH"}
            else EvaluationState.NO_SIGNAL,
            lifecycle_stage=None,
            recommendation_state=None,
            data_quality=None,
            metrics=metrics,
            economics={},
            blockers=(),
            warnings=explanation.warnings,
            provenance=(
                f"snapshot_id:{knowledge.snapshot_id}",
                f"snapshot_digest:{knowledge.snapshot_digest}",
                *(
                    f"canonical_fact:{fact.fact_id}@{fact.version}"
                    for fact in knowledge.canonical_facts
                ),
                *(
                    f"derived_fact:{fact.derived_fact_id}@{fact.formula_version}"
                    for fact in knowledge.derived_facts.facts
                ),
            ),
            observed_at=knowledge.effective_time,
        )

    return _adapter
