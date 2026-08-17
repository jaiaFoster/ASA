"""Forward Factor preparation and read-only runtime binding."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import date, datetime
from decimal import Decimal
from functools import partial
from types import MappingProxyType

from analytics.option_selection import select_canonical_contract
from domain import (
    EarningsEvent,
    ExpirationCollection,
    MarketCapability,
    OptionChain,
    OptionType,
    Quote,
    UnknownReason,
)
from market_data.snapshot import MarketSnapshot
from screening.explanations import build_graph_explanation
from screening.subject_fact_projection import resolution_for
from screening.subject_planning import ResolvedEvidenceView, SubjectPlanConsumer
from strategies import FORWARD_FACTOR_CALENDAR_MANIFEST
from strategies.forward_factor_evaluation import evaluate_forward_factor
from strategies.forward_factor_knowledge import (
    ForwardFactorPayload,
    build_forward_factor_knowledge_mapping,
)
from strategies.forward_factor_planning import (
    bootstrap_demands,
    expand_demands,
    expirations_demand,
)
from strategies.knowledge_contracts import KnowledgeMapping
from strategy_runtime.adapters._screening_bridge import explanation_metrics
from strategy_runtime.adapters.forward_factor import FORWARD_FACTOR_CONTRACT
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

_STRATEGY_ID = "forward_factor"
_SUCCESSFUL = frozenset({"PASS", "WATCH"})


def _spot(quote: Quote) -> Decimal:
    if quote.last is not None:
        return quote.last
    if quote.bid is not None and quote.ask is not None:
        return (quote.bid + quote.ask) / Decimal(2)
    raise ValueError("quote has no usable spot price")


def _atm_strike(chain: OptionChain, expiration: date, spot: Decimal) -> Decimal:
    strikes = {
        contract.strike
        for contract in chain.contracts
        if contract.expiration == expiration and contract.option_type is OptionType.CALL
    }
    if not strikes:
        raise ValueError("no call contracts at selected expiration")
    return min(strikes, key=lambda strike: (abs(strike - spot), strike))


def _prepare(
    snapshot: MarketSnapshot,
    projected: ResolvedEvidenceView,
    selections: tuple[tuple[str, object], ...],
    subject: str,
) -> KnowledgeMapping[ForwardFactorPayload] | UnknownReason:
    quote_resolution = resolution_for(snapshot, MarketCapability.REAL_TIME_QUOTE_V1)
    chain_resolution = resolution_for(snapshot, MarketCapability.OPTION_CHAIN_V1)
    quote_observation = quote_resolution.selected_observation
    chain_observation = chain_resolution.selected_observation
    if quote_observation is None or not isinstance(quote_observation.value, Quote):
        return UnknownReason("unusable_quote")
    if chain_observation is None or not isinstance(chain_observation.value, OptionChain):
        return UnknownReason("unusable_option_chain")
    discovery = projected.get(expirations_demand(snapshot.as_of).demand_id)
    if discovery is None or not isinstance(discovery.value, ExpirationCollection):
        return UnknownReason("unusable_expiration_collection")

    chain = chain_observation.value
    pair: tuple[date, date] | None = None
    for key, value in sorted(selections):
        if not key.startswith("pair_") or not isinstance(value, str):
            continue
        front_text, back_text = value.split("/", 1)
        candidate = date.fromisoformat(front_text), date.fromisoformat(back_text)
        available = {contract.expiration for contract in chain.contracts}
        if candidate[0] in available and candidate[1] in available:
            pair = candidate
            break
    if pair is None:
        return UnknownReason("no_usable_expiration_pair")
    front_date, back_date = pair
    cycles = {cycle.expiration_date: cycle for cycle in discovery.value.cycles}
    if front_date not in cycles or back_date not in cycles:
        return UnknownReason("selected_expiration_missing")
    spot = _spot(quote_observation.value)
    front_strike = _atm_strike(chain, front_date, spot)
    back_strike = _atm_strike(chain, back_date, spot)
    front_contract = select_canonical_contract(chain, front_date, front_strike, OptionType.CALL)
    back_contract = select_canonical_contract(chain, back_date, back_strike, OptionType.CALL)
    if front_contract.implied_volatility is None or back_contract.implied_volatility is None:
        return UnknownReason("missing_implied_volatility")

    try:
        earnings_resolution = resolution_for(snapshot, MarketCapability.EARNINGS_CALENDAR_V1)
    except ValueError:
        earnings_observation = None
    else:
        earnings_observation = earnings_resolution.selected_observation
    event = (
        earnings_observation.value
        if earnings_observation is not None
        and isinstance(earnings_observation.value, EarningsEvent)
        else None
    )
    return build_forward_factor_knowledge_mapping(
        subject=subject,
        snapshot_digest=snapshot.snapshot_digest,
        quote_observation_id=quote_observation.observation_id,
        chain_observation_id=chain_observation.observation_id,
        earnings_observation_id=(
            earnings_observation.observation_id if earnings_observation is not None else None
        ),
        spot_price=spot,
        chain=chain,
        front_cycle=cycles[front_date],
        back_cycle=cycles[back_date],
        front_strike=front_strike,
        back_strike=back_strike,
        front_iv=front_contract.implied_volatility,
        back_iv=back_contract.implied_volatility,
        event=event,
        as_of=snapshot.as_of.date(),
    )


def build_forward_factor_subject_preparation_binding(
    now: datetime,
) -> SubjectPreparationBinding[ForwardFactorPayload]:
    return SubjectPreparationBinding(
        SubjectPlanConsumer(
            _STRATEGY_ID,
            bootstrap_demands(now),
            partial(expand_demands, now=now),
        ),
        _prepare,
        build_forward_factor_subject_first_adapter,
    )


def _provenance(knowledge: ReadOnlyStrategyInput[ForwardFactorPayload]) -> tuple[str, ...]:
    return (
        f"snapshot_id:{knowledge.snapshot_id}",
        f"snapshot_digest:{knowledge.snapshot_digest}",
        *(f"canonical_fact:{fact.fact_id}@{fact.version}" for fact in knowledge.canonical_facts),
        *(
            f"derived_fact:{fact.derived_fact_id}@{fact.formula_version}"
            for fact in knowledge.derived_facts.facts
        ),
    )


def build_forward_factor_subject_first_adapter(
    knowledge_by_subject: Mapping[str, ReadOnlyStrategyInput[ForwardFactorPayload]],
) -> StrategyAdapter[UniversalScreeningResult]:
    frozen = MappingProxyType(dict(knowledge_by_subject))

    def _adapter(context: RuntimeContext) -> UniversalScreeningResult:
        knowledge = frozen[context.subject]
        outputs = evaluate_forward_factor(knowledge.derived_facts, knowledge.payload)
        verdict_text = str(outputs.get("verdict").value)
        successful = verdict_text in _SUCCESSFUL
        explanation = build_graph_explanation(FORWARD_FACTOR_CALENDAR_MANIFEST, outputs)
        metrics = explanation_metrics(explanation)
        score = outputs.get("forward_factor").value
        if isinstance(score, Decimal):
            metrics["strategy_native_score"] = TypedValue.of_decimal(score)
        return UniversalScreeningResult(
            strategy_id=_STRATEGY_ID,
            strategy_version=FORWARD_FACTOR_CONTRACT.version,
            symbol=context.subject,
            observation_id=compute_observation_id(context.run_id, _STRATEGY_ID, context.subject),
            opportunity_id=None,
            row_type=RowType.RESULT,
            verdict=verdict_text,
            evaluation_state=(EvaluationState.PASS if successful else EvaluationState.NO_SIGNAL),
            lifecycle_stage=None,
            recommendation_state=None,
            data_quality=None,
            metrics=metrics,
            economics={},
            blockers=(),
            warnings=explanation.warnings,
            provenance=_provenance(knowledge),
            observed_at=knowledge.effective_time,
        )

    return _adapter
