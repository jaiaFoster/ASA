"""Earnings Calendar's own pure, acquisition-free evaluation
(SPRINT-014 S14-PR-05A, Architect checkpoint: sixth review corrective
refactor -- "move Earnings-specific extraction, normalization, manifest
choice, and context construction back under strategies/").

Owns every Earnings-specific decision the read-only fact/analytics
composition increment previously placed in screening/, in violation of
ADR-010's "screening must not normalize strategy scores; strategies own
scores, weights, gates, structure selection, assumptions, and verdict
semantics": ATM strike/contract selection, richness normalization,
manifest choice, execution-context construction, and graph compilation/
execution. screening/earnings_calendar_facts.py now only looks up a
sealed snapshot's own resolutions and calls into this module with plain
domain values -- it performs no financial computation of its own.

Receives and returns only domain-owned and analytics-owned types plus
this module's own dataclasses -- never MarketSnapshot, ResolutionResult,
or any other market_data-owned type (this module's own architecture
boundary, tests/architecture/test_strategy_boundaries.py, forbids
market_data/ and screening/ both). Derived and canonical fact identity is
built entirely from caller-supplied ``subject``/``snapshot_digest``/
``effective_time`` -- never wall-clock invocation time -- so the same
sealed snapshot composed twice, at two different real invocation times,
produces byte-identical fact evidence (Architect checkpoint item 4).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal

from analytics.atm_selection import select_atm_strike
from analytics.derived_fact_materialization import materialize_derived_fact
from analytics.derived_facts import (
    ATM_IV_VS_REALIZED,
    DERIVED_FACT_REGISTRY,
    IV_TERM_STRUCTURE_SPREAD,
    REALIZED_VOLATILITY,
    compute_atm_iv_vs_realized_volatility,
    compute_iv_term_structure_spread,
)
from analytics.features import DerivedFactQualityStatus, DerivedFactSet
from analytics.realized_volatility import (
    InsufficientPriceHistoryError,
    compute_realized_volatility,
)
from domain import (
    EarningsEvent,
    EvidenceKind,
    EvidenceReference,
    ExpirationCollection,
    ExpirationCycle,
    OptionChain,
    OptionType,
    Quote,
    UnknownReason,
)
from facts.canonical_projection import canonical_fact_id
from strategies import (
    CORE_COMPONENTS,
    EARNINGS_CALENDAR_MANIFEST,
    STONK_STRATEGY_PLUGINS,
    compile_strategy_graph,
    execute_strategy_graph,
)
from strategies.plugins import build_plugin_registry
from strategies.scoring import normalize_richness
from strategies.stonk_components import DATE as _DATE_TYPE
from strategies.stonk_components import EARNINGS_EVENT as _EARNINGS_EVENT_TYPE
from strategies.stonk_components import EXPIRATION_COLLECTION as _EXPIRATION_COLLECTION_TYPE
from strategies.stonk_components import EXPIRATION_CYCLE as _EXPIRATION_CYCLE_TYPE
from strategies.stonk_components import OPTION_CHAIN as _OPTION_CHAIN_TYPE
from strategies.stonk_components import D
from strategies.type_system import ComponentValues, TypedValue

_COMPONENT_REGISTRY = build_plugin_registry(CORE_COMPONENTS, STONK_STRATEGY_PLUGINS)
_CANONICAL_FACT_VERSION = 1

# The single source of truth for every canonical fact_type this
# evaluation projects -- screening/earnings_calendar_facts.py imports
# these same constants rather than retyping the string literals, so the
# fact IDs this module embeds as derived-fact input_evidence and the
# fact IDs the caller later actually projects can never silently drift
# apart (Architect checkpoint item 2's own required test: two consumers
# projecting the same scalar from the same sealed evidence must receive
# the same ID).
FACT_TYPE_SPOT_PRICE = "spot_price"
FACT_TYPE_EARNINGS_DATE = "earnings_date"
FACT_TYPE_EARNINGS_CONFIRMED = "earnings_confirmed"

# Architect checkpoint (seventh review), item 2: an implied volatility is
# generic canonical knowledge about the exact option contract it was
# observed on, never a "front"/"back" strategy role -- those roles are
# this strategy's own selection parameterization, not canonical fact
# taxonomy. One fact_type is used for both sides; the fact's own
# ``subject`` is the contract's own stable, structural OptionContract.identity
# (never the earnings subject/ticker), so a different valid front/back
# selection within the same sealed snapshot can never collide on one
# fact ID for two different contracts' IVs.
FACT_TYPE_OPTION_IMPLIED_VOLATILITY = "option_implied_volatility"


@dataclass(frozen=True, slots=True)
class EarningsCalendarEvaluation:
    """Everything this pure evaluation produced: the scalars a caller
    projects into CanonicalFacts (never computed here -- CanonicalFact
    construction needs a market_data ResolutionResult this module cannot
    see), the DerivedFactSet analytics/ already materialized, and the
    existing, unmodified manifest/graph's own execution output.

    ``front_contract_identity``/``back_contract_identity`` are each
    selected contract's own stable OptionContract.identity -- the
    canonical *subject* the caller projects the corresponding implied-
    volatility CanonicalFact under (Architect checkpoint item 2), never
    the earnings subject/ticker.
    """

    spot_price: Decimal
    earnings_date: date
    earnings_confirmed: bool
    front_atm_implied_volatility: Decimal
    back_atm_implied_volatility: Decimal
    front_contract_identity: str
    back_contract_identity: str
    derived_facts: DerivedFactSet
    graph_outputs: ComponentValues


def build_earnings_calendar_context(
    chain: OptionChain,
    event: EarningsEvent,
    front: ExpirationCycle,
    back: ExpirationCycle,
    as_of: date,
    *,
    target_strike: Decimal,
    term_structure_richness: Decimal,
    iv_realized_volatility_richness: Decimal,
) -> ComponentValues:
    """The single-source-of-truth Earnings Calendar execution-context
    builder (Architect checkpoint, seventh review, item 4: "do not retain
    two implementations"). screening.context_builders.
    build_earnings_calendar_context is now a compatibility shim that
    delegates here -- owner: this module; deletion gate: S14-PR-07
    (delete the superseded live path), at which point the shim itself is
    deleted along with its only remaining caller,
    screening/live_adapters.py.
    """
    items: dict[str, tuple[object, object]] = {
        "event_window.event": (_EARNINGS_EVENT_TYPE, event),
        "event_projection.event": (_EARNINGS_EVENT_TYPE, event),
        "event_projection.as_of": (_DATE_TYPE, as_of),
        "event_window.front": (_EXPIRATION_CYCLE_TYPE, front),
        "event_window.back": (_EXPIRATION_CYCLE_TYPE, back),
        "expiration_select.expirations": (
            _EXPIRATION_COLLECTION_TYPE,
            ExpirationCollection(as_of, (back, front)),
        ),
        "expiration_select.event": (_EARNINGS_EVENT_TYPE, event),
        "calendar.chain": (_OPTION_CHAIN_TYPE, chain),
        "calendar.target_strike": (D, target_strike),
        "score.primary": (D, term_structure_richness),
        "score.secondary": (D, iv_realized_volatility_richness),
    }
    return ComponentValues(
        tuple((name, TypedValue(type_ref, value)) for name, (type_ref, value) in items.items())
    )


def evaluate_earnings_calendar(
    *,
    quote: Quote,
    event: EarningsEvent,
    chain: OptionChain,
    bars_closes: tuple[Decimal, ...],
    bars_observation_id: str,
    front_expiration: date,
    back_expiration: date,
    front_cycle: ExpirationCycle,
    back_cycle: ExpirationCycle,
    as_of: date,
    subject: str,
    snapshot_digest: str,
    effective_time: datetime,
    quote_demand_id: str,
    historical_bars_demand_id: str,
    front_chain_demand_id: str,
    back_chain_demand_id: str,
) -> EarningsCalendarEvaluation | UnknownReason:
    """Earnings Calendar's own pure, acquisition-free evaluation: ATM
    selection, analytics materialization, richness normalization, and
    execution of the existing, unmodified EARNINGS_CALENDAR_MANIFEST
    graph -- entirely from already-resolved domain values, never a
    provider call, never a MarketSnapshot/ResolutionResult of its own.

    Returns a typed UnknownReason (never raises) for every genuine,
    expected data gap: missing spot price, no CALL contracts at a
    selected expiration (the resolved chain does list expirations that
    simply carry no calls -- select_atm_strike's own empty-strike-set
    ValueError is never let through raw), a missing implied volatility on
    the selected ATM contract, or fewer than two historical daily closes.
    Every UnknownReason carries the exact demand_id(s) it traces back to
    (Architect checkpoint, seventh review, item 3) -- the four
    ``*_demand_id`` parameters exist for exactly this, never consumed for
    any other decision this function makes.
    """
    if quote.last is None:
        return UnknownReason("missing_spot_price", demand_ids=(quote_demand_id,))
    spot_price = quote.last

    front_strikes = tuple(
        item.strike
        for item in chain.find(expiration=front_expiration, option_type=OptionType.CALL)
    )
    back_strikes = tuple(
        item.strike
        for item in chain.find(expiration=back_expiration, option_type=OptionType.CALL)
    )
    if not front_strikes or not back_strikes:
        no_calls_demand_ids = tuple(
            demand_id
            for empty, demand_id in (
                (not front_strikes, front_chain_demand_id),
                (not back_strikes, back_chain_demand_id),
            )
            if empty
        )
        return UnknownReason(
            "no_call_contracts_at_selected_expiration", demand_ids=no_calls_demand_ids
        )
    front_strike = select_atm_strike(front_strikes, spot_price)
    back_strike = select_atm_strike(back_strikes, spot_price)
    (front_contract,) = chain.find(
        expiration=front_expiration, strike=front_strike, option_type=OptionType.CALL
    )
    (back_contract,) = chain.find(
        expiration=back_expiration, strike=back_strike, option_type=OptionType.CALL
    )
    if front_contract.implied_volatility is None or back_contract.implied_volatility is None:
        missing_iv_demand_ids = tuple(
            demand_id
            for missing, demand_id in (
                (front_contract.implied_volatility is None, front_chain_demand_id),
                (back_contract.implied_volatility is None, back_chain_demand_id),
            )
            if missing
        )
        return UnknownReason("missing_implied_volatility", demand_ids=missing_iv_demand_ids)
    front_iv = front_contract.implied_volatility
    back_iv = back_contract.implied_volatility
    front_contract_identity = front_contract.identity
    back_contract_identity = back_contract.identity

    try:
        realized_volatility = compute_realized_volatility(bars_closes)
    except InsufficientPriceHistoryError:
        return UnknownReason(
            "insufficient_historical_bars", demand_ids=(historical_bars_demand_id,)
        )

    # Architect checkpoint item 2: canonical knowledge about an option
    # contract's own implied volatility is keyed by the contract's own
    # stable identity, never by the earnings subject/ticker -- "front"
    # and "back" are this strategy's own selection roles, expressed below
    # only as I-07 parameter identity on the *derived* facts that
    # actually depend on the selection, never smuggled into a canonical
    # fact's subject.
    front_iv_fact_id = canonical_fact_id(
        FACT_TYPE_OPTION_IMPLIED_VOLATILITY, front_contract_identity, snapshot_digest
    )
    back_iv_fact_id = canonical_fact_id(
        FACT_TYPE_OPTION_IMPLIED_VOLATILITY, back_contract_identity, snapshot_digest
    )
    front_iv_evidence = EvidenceReference(
        EvidenceKind.CANONICAL_FACT, front_iv_fact_id, _CANONICAL_FACT_VERSION
    )
    back_iv_evidence = EvidenceReference(
        EvidenceKind.CANONICAL_FACT, back_iv_fact_id, _CANONICAL_FACT_VERSION
    )
    bars_evidence = (EvidenceReference(EvidenceKind.OBSERVATION, bars_observation_id),)

    realized_volatility_fact = materialize_derived_fact(
        DERIVED_FACT_REGISTRY,
        REALIZED_VOLATILITY,
        subject,
        snapshot_digest,
        value=realized_volatility,
        unit="annualized_stdev",
        effective_time=effective_time,
        input_evidence=bars_evidence,
        quality_status=DerivedFactQualityStatus.VALID,
    )
    term_structure_spread = compute_iv_term_structure_spread(front_iv, back_iv)
    # I-07 parameter identity (Architect checkpoint item 1): this
    # feature's own *value* depends on exactly which front/back contracts
    # were selected, so its derived_fact_id must depend on them too --
    # otherwise a different valid selection within the same
    # subject/snapshot would silently reuse this same ID for a different
    # value.
    selection_parameters = (
        ("front_contract_id", front_contract_identity),
        ("back_contract_id", back_contract_identity),
    )
    term_structure_fact = materialize_derived_fact(
        DERIVED_FACT_REGISTRY,
        IV_TERM_STRUCTURE_SPREAD,
        subject,
        snapshot_digest,
        value=term_structure_spread,
        unit="implied_volatility_points",
        effective_time=effective_time,
        input_evidence=(front_iv_evidence, back_iv_evidence),
        quality_status=DerivedFactQualityStatus.VALID,
        parameters=selection_parameters,
    )
    # Owns its own realized-volatility computation end to end (analytics.
    # derived_facts.compute_atm_iv_vs_realized_volatility) rather than
    # reusing the realized_volatility_fact value materialized above --
    # ATM_IV_VS_REALIZED's own registered formula_version must own the
    # entire computation, never silently depend on a separately-versioned
    # intermediate (Architect checkpoint item 3). Also selection-
    # dependent (front contract plus historical window), so it carries
    # its own I-07 parameters too.
    iv_realized_spread = compute_atm_iv_vs_realized_volatility(front_iv, bars_closes)
    iv_realized_fact = materialize_derived_fact(
        DERIVED_FACT_REGISTRY,
        ATM_IV_VS_REALIZED,
        subject,
        snapshot_digest,
        value=iv_realized_spread,
        unit="implied_volatility_points",
        effective_time=effective_time,
        input_evidence=(front_iv_evidence, *bars_evidence),
        quality_status=DerivedFactQualityStatus.VALID,
        parameters=(
            ("front_contract_id", front_contract_identity),
            ("historical_bars_observation_id", bars_observation_id),
        ),
    )
    derived_facts = DerivedFactSet(
        (realized_volatility_fact, term_structure_fact, iv_realized_fact)
    )

    context = build_earnings_calendar_context(
        chain,
        event,
        front_cycle,
        back_cycle,
        as_of,
        target_strike=front_strike,
        term_structure_richness=normalize_richness(term_structure_spread),
        iv_realized_volatility_richness=normalize_richness(iv_realized_spread),
    )
    graph = compile_strategy_graph(EARNINGS_CALENDAR_MANIFEST, _COMPONENT_REGISTRY)
    result = execute_strategy_graph(graph, context)

    return EarningsCalendarEvaluation(
        spot_price=spot_price,
        earnings_date=event.earnings_date,
        earnings_confirmed=event.confirmed,
        front_atm_implied_volatility=front_iv,
        back_atm_implied_volatility=back_iv,
        front_contract_identity=front_contract_identity,
        back_contract_identity=back_contract_identity,
        derived_facts=derived_facts,
        graph_outputs=result.outputs,
    )
