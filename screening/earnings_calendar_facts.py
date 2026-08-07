"""Read-only Earnings Calendar fact/analytics composition (SPRINT-014
S14-PR-05A, Architect checkpoint: fact/analytics composition increment).

Projects an already-sealed subject snapshot plus provider-blind Earnings
selections/evidence (strategies.earnings_calendar_planning.
EarningsCalendarPhaseTwoEvidence, selections) into canonical facts,
materializes reusable financial calculations through analytics/'s own
registered features into an immutable DerivedFactSet, and executes the
existing, unmodified Earnings Calendar manifest/graph -- acquisition-free,
no production wiring, no RuntimeContext, no composition-root change.

Never reads SubjectPlanResult.diagnostic_fulfillments -- only
snapshot.resolution_results/observations (already-sealed, resolved
evidence) and the phase-two evidence a strategy's own pure expansion
already selected and gated as usable. Structural values (OptionChain,
EarningsEvent, ExpirationCycle) are consumed as sealed resolved knowledge
and handed to the existing graph verbatim -- never forced into
CanonicalFact.value, whose contract accepts only normalized
primitive/tuple scalars. Financial arithmetic lives in analytics/
(realized volatility, the front/back IV term-structure spread, IV-vs-
realized-volatility); richness normalization over those raw analytics
values stays strategy-owned (strategies.scoring.normalize_richness) --
this module performs no financial computation of its own, only wiring.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime

from analytics.atm_selection import select_atm_strike
from analytics.derived_fact_materialization import materialize_derived_fact
from analytics.derived_facts import (
    ATM_IV_VS_REALIZED,
    DERIVED_FACT_REGISTRY,
    IV_TERM_STRUCTURE_SPREAD,
    REALIZED_VOLATILITY,
    compute_iv_realized_spread,
    compute_iv_term_structure_spread,
)
from analytics.features import DerivedFactQualityStatus, DerivedFactSet
from analytics.realized_volatility import InsufficientPriceHistoryError, compute_realized_volatility
from domain import (
    CanonicalFact,
    EarningsEvent,
    EvidenceKind,
    EvidenceReference,
    ExpirationCollection,
    ExpirationCycle,
    MarketCapability,
    OHLCVSeries,
    OptionChain,
    OptionType,
    Quote,
    UnknownReason,
)
from facts.canonical_projection import project_canonical_fact
from market_data.resolution import ResolutionResult
from market_data.snapshot import MarketSnapshot
from screening.context_builders import build_earnings_calendar_context
from strategies import (
    CORE_COMPONENTS,
    EARNINGS_CALENDAR_MANIFEST,
    STONK_STRATEGY_PLUGINS,
    compile_strategy_graph,
    execute_strategy_graph,
)
from strategies.earnings_calendar_planning import EarningsCalendarPhaseTwoEvidence
from strategies.plugins import build_plugin_registry
from strategies.scoring import normalize_richness
from strategies.type_system import ComponentValues

_COMPONENT_REGISTRY = build_plugin_registry(CORE_COMPONENTS, STONK_STRATEGY_PLUGINS)


@dataclass(frozen=True, slots=True)
class EarningsCalendarComposition:
    """Everything the read-only Earnings Calendar path produces from one
    sealed snapshot: the canonical facts extracted from it, the derived
    facts analytics/ computed over them, and the existing manifest/graph's
    own execution output -- never a strategy verdict computed here, only
    what the unmodified graph itself returned.
    """

    canonical_facts: tuple[CanonicalFact, ...]
    derived_facts: DerivedFactSet
    graph_outputs: ComponentValues


def _resolution_for(snapshot: MarketSnapshot, capability: MarketCapability) -> ResolutionResult:
    for item in snapshot.resolution_results:
        if item.capability is capability:
            return item
    raise ValueError(f"snapshot has no resolution for {capability.value}")


def _fact_id(symbol: str, snapshot: MarketSnapshot, fact_type: str) -> str:
    return f"earnings_calendar:{symbol}:{fact_type}:{snapshot.snapshot_digest}"


def _canonical_fact_evidence(fact: CanonicalFact) -> EvidenceReference:
    return EvidenceReference(EvidenceKind.CANONICAL_FACT, fact.fact_id, fact.version)


def compose_earnings_calendar_evaluation(
    symbol: str,
    snapshot: MarketSnapshot,
    phase_two: EarningsCalendarPhaseTwoEvidence,
    selections: dict[str, object],
    *,
    as_of: date,
    created_time: datetime,
) -> EarningsCalendarComposition | UnknownReason:
    """Compose one Earnings Calendar evaluation entirely from an already-
    sealed snapshot -- no acquisition, no provider call, no production
    wiring. Returns a typed UnknownReason (never raises) for the two
    genuine, expected data gaps a fully-resolved phase-two evidence
    bundle can still carry: fewer than two historical daily closes, or a
    missing implied volatility on the selected front/back ATM contract --
    both ordinary outcomes the legacy live path also treats as
    MISSING_DATA, never a defect.
    """
    front_expiration_raw = selections.get("front_expiration")
    back_expiration_raw = selections.get("back_expiration")
    if not isinstance(front_expiration_raw, str) or not isinstance(back_expiration_raw, str):
        return UnknownReason("missing_expiration_pair_selection")
    front_expiration = date.fromisoformat(front_expiration_raw)
    back_expiration = date.fromisoformat(back_expiration_raw)

    expiration_collection = next(
        (
            item.value
            for item in snapshot.observations
            if isinstance(item.value, ExpirationCollection)
        ),
        None,
    )
    if expiration_collection is None:
        return UnknownReason("missing_expiration_collection")
    front_cycle = _cycle_at(expiration_collection, front_expiration)
    back_cycle = _cycle_at(expiration_collection, back_expiration)
    if front_cycle is None or back_cycle is None:
        return UnknownReason("selected_expiration_not_in_discovery_collection")

    quote_resolution = _resolution_for(snapshot, MarketCapability.REAL_TIME_QUOTE_V1)
    earnings_resolution = _resolution_for(snapshot, MarketCapability.EARNINGS_CALENDAR_V1)
    bars_resolution = _resolution_for(snapshot, MarketCapability.HISTORICAL_BARS_V1)
    chain_resolution = _resolution_for(snapshot, MarketCapability.OPTION_CHAIN_V1)

    quote = quote_resolution.selected_observation
    event = earnings_resolution.selected_observation
    bars = bars_resolution.selected_observation
    chain_observation = chain_resolution.selected_observation
    if quote is None or event is None or bars is None or chain_observation is None:
        return UnknownReason("unresolved_earnings_calendar_capability")
    if (
        not isinstance(quote.value, Quote)
        or not isinstance(event.value, EarningsEvent)
        or not isinstance(bars.value, OHLCVSeries)
        or not isinstance(chain_observation.value, OptionChain)
    ):
        return UnknownReason("unexpected_resolved_value_shape")
    spot_price = quote.value.last
    chain = chain_observation.value
    if spot_price is None:
        return UnknownReason("missing_spot_price")

    canonical_facts: list[CanonicalFact] = []

    spot_price_fact = project_canonical_fact(
        quote_resolution,
        value=spot_price,
        fact_id=_fact_id(symbol, snapshot, "spot_price"),
        version=1,
        fact_type="spot_price",
        created_time=created_time,
    )
    earnings_date_fact = project_canonical_fact(
        earnings_resolution,
        value=event.value.earnings_date.isoformat(),
        fact_id=_fact_id(symbol, snapshot, "earnings_date"),
        version=1,
        fact_type="earnings_date",
        created_time=created_time,
    )
    earnings_confirmed_fact = project_canonical_fact(
        earnings_resolution,
        value=event.value.confirmed,
        fact_id=_fact_id(symbol, snapshot, "earnings_confirmed"),
        version=1,
        fact_type="earnings_confirmed",
        created_time=created_time,
    )
    if spot_price_fact is None or earnings_date_fact is None or earnings_confirmed_fact is None:
        return UnknownReason("resolution_unresolved")
    canonical_facts.extend((spot_price_fact, earnings_date_fact, earnings_confirmed_fact))

    front_strike = select_atm_strike(
        tuple(
            contract.strike
            for contract in chain.find(expiration=front_expiration, option_type=OptionType.CALL)
        ),
        spot_price,
    )
    back_strike = select_atm_strike(
        tuple(
            contract.strike
            for contract in chain.find(expiration=back_expiration, option_type=OptionType.CALL)
        ),
        spot_price,
    )
    (front_contract,) = chain.find(
        expiration=front_expiration, strike=front_strike, option_type=OptionType.CALL
    )
    (back_contract,) = chain.find(
        expiration=back_expiration, strike=back_strike, option_type=OptionType.CALL
    )
    if front_contract.implied_volatility is None or back_contract.implied_volatility is None:
        return UnknownReason(
            "missing_implied_volatility",
            demand_ids=(
                phase_two.front_chain_evidence.demand_id,
                phase_two.back_chain_evidence.demand_id,
            ),
        )
    front_iv = front_contract.implied_volatility
    back_iv = back_contract.implied_volatility

    front_iv_fact = project_canonical_fact(
        chain_resolution,
        value=front_iv,
        fact_id=_fact_id(symbol, snapshot, "front_atm_implied_volatility"),
        version=1,
        fact_type="front_atm_implied_volatility",
        created_time=created_time,
    )
    back_iv_fact = project_canonical_fact(
        chain_resolution,
        value=back_iv,
        fact_id=_fact_id(symbol, snapshot, "back_atm_implied_volatility"),
        version=1,
        fact_type="back_atm_implied_volatility",
        created_time=created_time,
    )
    if front_iv_fact is None or back_iv_fact is None:
        return UnknownReason("resolution_unresolved")
    canonical_facts.extend((front_iv_fact, back_iv_fact))

    closes = tuple(bar.close for bar in bars.value.bars)
    try:
        realized_volatility = compute_realized_volatility(closes)
    except InsufficientPriceHistoryError:
        return UnknownReason(
            "insufficient_historical_bars",
            demand_ids=(phase_two.historical_bars_evidence.demand_id,),
        )

    bars_evidence = (EvidenceReference(EvidenceKind.OBSERVATION, bars.observation_id),)
    front_iv_evidence = _canonical_fact_evidence(front_iv_fact)
    back_iv_evidence = _canonical_fact_evidence(back_iv_fact)
    realized_volatility_fact = materialize_derived_fact(
        DERIVED_FACT_REGISTRY,
        REALIZED_VOLATILITY,
        symbol,
        snapshot.snapshot_digest,
        value=realized_volatility,
        unit="annualized_stdev",
        effective_time=created_time,
        input_evidence=bars_evidence,
        quality_status=DerivedFactQualityStatus.VALID,
    )
    term_structure_spread = compute_iv_term_structure_spread(front_iv, back_iv)
    term_structure_fact = materialize_derived_fact(
        DERIVED_FACT_REGISTRY,
        IV_TERM_STRUCTURE_SPREAD,
        symbol,
        snapshot.snapshot_digest,
        value=term_structure_spread,
        unit="implied_volatility_points",
        effective_time=created_time,
        input_evidence=(front_iv_evidence, back_iv_evidence),
        quality_status=DerivedFactQualityStatus.VALID,
    )
    iv_realized_spread = compute_iv_realized_spread(front_iv, realized_volatility)
    iv_realized_fact = materialize_derived_fact(
        DERIVED_FACT_REGISTRY,
        ATM_IV_VS_REALIZED,
        symbol,
        snapshot.snapshot_digest,
        value=iv_realized_spread,
        unit="implied_volatility_points",
        effective_time=created_time,
        input_evidence=(front_iv_evidence, *bars_evidence),
        quality_status=DerivedFactQualityStatus.VALID,
    )
    derived_facts = DerivedFactSet(
        (realized_volatility_fact, term_structure_fact, iv_realized_fact)
    )

    context = build_earnings_calendar_context(
        chain,
        event.value,
        front_cycle,
        back_cycle,
        as_of,
        target_strike=front_strike,
        term_structure_richness=normalize_richness(term_structure_spread),
        iv_realized_volatility_richness=normalize_richness(iv_realized_spread),
    )
    graph = compile_strategy_graph(EARNINGS_CALENDAR_MANIFEST, _COMPONENT_REGISTRY)
    result = execute_strategy_graph(graph, context)

    return EarningsCalendarComposition(
        canonical_facts=tuple(canonical_facts),
        derived_facts=derived_facts,
        graph_outputs=result.outputs,
    )


def _cycle_at(collection: ExpirationCollection, expiration: date) -> ExpirationCycle | None:
    return next(
        (cycle for cycle in collection.cycles if cycle.expiration_date == expiration), None
    )
