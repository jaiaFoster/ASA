"""SPY 30-DTE put credit spread preparation and read-only runtime binding (SL-02)."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import date, datetime
from decimal import Decimal
from functools import partial
from types import MappingProxyType

from domain import (
    MarketCapability,
    OptionChain,
    OptionContract,
    OptionLegPosition,
    OptionStructure,
    OptionType,
    Quote,
    UnknownReason,
)
from market_data.snapshot import MarketSnapshot
from screening.explanations import build_graph_explanation
from screening.subject_fact_projection import resolution_for
from screening.subject_planning import ResolvedEvidenceView, SubjectPlanConsumer
from strategies import (
    CORE_COMPONENTS,
    STONK_STRATEGY_PLUGINS,
    compile_strategy_graph,
    execute_strategy_graph,
)
from strategies.knowledge_contracts import KnowledgeMapping
from strategies.plugins import build_plugin_registry
from strategies.put_credit_spread_knowledge import (
    PutCreditSpreadPayload,
    build_put_credit_spread_knowledge_mapping,
)
from strategies.put_credit_spread_manifest import (
    LONG_PUT_DELTA,
    SHORT_PUT_DELTA,
    SPY_PUT_CREDIT_SPREAD_MANIFEST,
)
from strategies.put_credit_spread_planning import (
    MAXIMUM_EXPIRATION_DISTANCE_DAYS,
    bootstrap_demands,
    expand_demands,
)
from strategies.stonk_components import DATE, OPTION_CHAIN
from strategies.type_system import ComponentValues, TypedValue
from strategy_runtime.adapters._screening_bridge import explanation_metrics
from strategy_runtime.adapters.put_credit_spread import SPY_PUT_CREDIT_SPREAD_CONTRACT
from strategy_runtime.context import RuntimeContext
from strategy_runtime.contract import StructureKind
from strategy_runtime.executable_structures import ExecutableStructureAssessment
from strategy_runtime.knowledge import ReadOnlyStrategyInput
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
from strategy_runtime.values import TypedValue as PersistedValue

_STRATEGY_ID = SPY_PUT_CREDIT_SPREAD_CONTRACT.strategy_id
_GRAPH = compile_strategy_graph(
    SPY_PUT_CREDIT_SPREAD_MANIFEST, build_plugin_registry(CORE_COMPONENTS, STONK_STRATEGY_PLUGINS)
)
# The source's "Only one position active at any time" is portfolio state, not
# screening semantics; every result discloses that ASA does not evaluate it.
_ONE_POSITION_DISCLOSURE = "source_one_active_position_rule_not_evaluated_by_screener"
# ASA constructibility tolerance (not a source rule): a leg whose observed
# delta is farther than this from the source target is not that leg.
MAXIMUM_DELTA_DISTANCE = Decimal("0.05")
_ASSUMPTIONS = (
    _ONE_POSITION_DISCLOSURE,
    f"leg_delta_within_{MAXIMUM_DELTA_DISTANCE}_of_source_target",
    f"expiration_within_{MAXIMUM_EXPIRATION_DISTANCE_DAYS}_days_of_30_dte",
    "legs_selected_by_provider_observed_delta",
)


def _graph_outputs(chain: OptionChain, expiration: date) -> ComponentValues:
    """The manifest graph is the only leg-selection authority."""
    return execute_strategy_graph(
        _GRAPH,
        ComponentValues(
            (
                ("spread.chain", TypedValue(OPTION_CHAIN, chain)),
                ("spread.expiration", TypedValue(DATE, expiration)),
            )
        ),
    ).outputs


def _legs(structure: OptionStructure) -> tuple[OptionContract, OptionContract]:
    by_position = {item.position: item.contract for item in structure.legs}
    return by_position[OptionLegPosition.LONG], by_position[OptionLegPosition.SHORT]


def _selection_blocker(chain: OptionChain, expiration: date) -> UnknownReason | None:
    """Reject any graph selection that is not the source's credit spread."""
    outputs = _graph_outputs(chain, expiration)
    structure = outputs.get("structure").value
    assert isinstance(structure, OptionStructure)
    long, short = _legs(structure)
    candidates = tuple(
        item
        for item in chain.contracts
        if item.expiration == expiration
        and item.option_type is OptionType.PUT
        and item.delta is not None
    )
    for contract, target, excluded in (
        (long, Decimal(LONG_PUT_DELTA), frozenset()),
        (short, Decimal(SHORT_PUT_DELTA), frozenset({long.identity})),
    ):
        assert contract.delta is not None
        distance = abs(abs(contract.delta) - abs(target))
        if distance > MAXIMUM_DELTA_DISTANCE:
            return UnknownReason("no_contract_near_target_delta")
        tied = [
            item
            for item in candidates
            if item.identity not in excluded
            and item.identity != contract.identity
            and abs(abs(item.delta) - abs(target)) == distance  # type: ignore[arg-type]
        ]
        if tied:
            return UnknownReason("ambiguous_delta_tie")
    if not short.strike > long.strike:
        return UnknownReason("inverted_spread")
    mid_debit = outputs.get("mid_debit").value
    if isinstance(mid_debit, Decimal) and mid_debit >= 0:
        return UnknownReason("non_credit_entry")
    return None


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
) -> KnowledgeMapping[PutCreditSpreadPayload] | UnknownReason:
    del projected
    try:
        quote_resolution = resolution_for(snapshot, MarketCapability.REAL_TIME_QUOTE_V1)
        chain_resolution = resolution_for(snapshot, MarketCapability.OPTION_CHAIN_V1)
    except ValueError:
        return UnknownReason("unusable_option_chain")
    quote_observation = quote_resolution.selected_observation
    chain_observation = chain_resolution.selected_observation
    if quote_observation is None or not isinstance(quote_observation.value, Quote):
        return UnknownReason("unusable_quote")
    if chain_observation is None or not isinstance(chain_observation.value, OptionChain):
        return UnknownReason("unusable_option_chain")
    spot = _spot(quote_observation.value)
    if spot is None:
        return UnknownReason("unusable_quote")
    expiration_text = dict(selections).get("expiration")
    if not isinstance(expiration_text, str):
        return UnknownReason("no_future_expiration")
    expiration = datetime.fromisoformat(expiration_text).date()
    chain = chain_observation.value
    puts = tuple(
        item
        for item in chain.contracts
        if item.expiration == expiration and item.option_type is OptionType.PUT
    )
    if not puts:
        return UnknownReason("no_put_contracts_at_selected_expiration")
    # Both source legs are delta-selected; two distinct observed deltas are
    # required, and a missing Greek is never replaced by a proxy.
    if len({item.identity for item in puts if item.delta is not None}) < 2:
        return UnknownReason("missing_actual_delta")
    blocker = _selection_blocker(chain, expiration)
    if blocker is not None:
        return blocker
    return build_put_credit_spread_knowledge_mapping(
        subject=subject,
        quote_observation_id=quote_observation.observation_id,
        chain_observation_id=chain_observation.observation_id,
        chain=chain,
        expiration=expiration,
        underlying_price=spot,
        days_to_expiration=(expiration - now.date()).days,
    )


def _build_execution_assessment(
    knowledge: ReadOnlyStrategyInput[PutCreditSpreadPayload],
    result: UniversalScreeningResult,
    assessed_at: datetime,
) -> ExecutableStructureAssessment:
    payload = knowledge.payload
    # Resolve exactly the graph's contracts; delta selection is never re-run.
    structure = _graph_outputs(payload.chain, payload.expiration).get("structure").value
    assert isinstance(structure, OptionStructure)
    long, short = _legs(structure)
    intent = OptionStructureIntent(
        payload.chain.underlying.symbol,
        StructureKind.VERTICAL,
        (
            OptionLegIntent(
                "long",
                OptionType.PUT,
                payload.expiration,
                OptionLegPosition.LONG,
                Decimal(1),
                selected_contract_identity=long.identity,
            ),
            OptionLegIntent(
                "short",
                OptionType.PUT,
                payload.expiration,
                OptionLegPosition.SHORT,
                Decimal(1),
                selected_contract_identity=short.identity,
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


def build_put_credit_spread_subject_first_adapter(
    knowledge_by_subject: Mapping[str, ReadOnlyStrategyInput[PutCreditSpreadPayload]],
) -> StrategyAdapter[UniversalScreeningResult]:
    frozen = MappingProxyType(dict(knowledge_by_subject))

    def _adapter(context: RuntimeContext) -> UniversalScreeningResult:
        knowledge = frozen[context.subject]
        payload = knowledge.payload
        outputs = _graph_outputs(payload.chain, payload.expiration)
        verdict = str(outputs.get("verdict").value)
        explanation = build_graph_explanation(SPY_PUT_CREDIT_SPREAD_MANIFEST, outputs)
        metrics = explanation_metrics(explanation)
        metrics["decision.assumptions"] = PersistedValue.of_structured(
            [*explanation.assumptions, *_ASSUMPTIONS]
        )
        return UniversalScreeningResult(
            strategy_id=_STRATEGY_ID,
            strategy_version=SPY_PUT_CREDIT_SPREAD_CONTRACT.version,
            symbol=context.subject,
            observation_id=compute_observation_id(context.run_id, _STRATEGY_ID, context.subject),
            opportunity_id=None,
            row_type=RowType.RESULT,
            verdict=verdict,
            evaluation_state=(
                EvaluationState.PASS if verdict in {"PASS", "WATCH"} else EvaluationState.NO_SIGNAL
            ),
            lifecycle_stage=None,
            recommendation_state=None,
            data_quality=None,
            metrics=metrics,
            economics={},
            blockers=(),
            warnings=(*explanation.warnings, _ONE_POSITION_DISCLOSURE),
            provenance=(
                f"snapshot_id:{knowledge.snapshot_id}",
                f"snapshot_digest:{knowledge.snapshot_digest}",
                *(
                    f"canonical_fact:{fact.fact_id}@{fact.version}"
                    for fact in knowledge.canonical_facts
                ),
            ),
            observed_at=knowledge.effective_time,
        )

    return _adapter


def build_put_credit_spread_subject_preparation_binding(
    now: datetime,
) -> SubjectPreparationBinding[PutCreditSpreadPayload]:
    return SubjectPreparationBinding(
        SubjectPlanConsumer(_STRATEGY_ID, bootstrap_demands(now), partial(expand_demands, now=now)),
        partial(_prepare, now),
        build_put_credit_spread_subject_first_adapter,
        build_execution_assessment=_build_execution_assessment,
    )
