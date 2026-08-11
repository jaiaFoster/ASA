"""Earnings Calendar's own truly read-only evaluator (SPRINT-014
S14-PR-05A, Architect checkpoint: ninth review -- "refactor
strategies/earnings_calendar_evaluation.py into a truly read-only
evaluator ... it must no longer import or invoke
materialize_derived_fact(), compute_realized_volatility(),
compute_atm_iv_vs_realized_volatility(), or
compute_iv_term_structure_spread()").

All analytics materialization and ATM structural selection now live
upstream: strategies/earnings_calendar_structure.py (structure) and
strategies/earnings_calendar_knowledge_binding.py (analytics mapping),
composed by the generic strategy_runtime/knowledge_composition.py before
this module ever runs. This module receives the already-materialized
DerivedFactSet and the strategy-owned EarningsCalendarPayload, retrieves
its two named derived facts by their exact precomputed IDs (Architect
checkpoint item 5 -- never rediscovered by value, never recomputed), and
executes the unchanged manifest/graph. It performs no financial
computation of its own beyond strategy-owned richness normalization.

Cannot import strategy_runtime.knowledge.ReadOnlyStrategyInput directly
(strategies/ may not import strategy_runtime -- architecture boundary);
the caller that composed that envelope unpacks its ``derived_facts`` and
``payload`` before calling here.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from analytics.features import DerivedFactSet
from domain import EarningsEvent, ExpirationCollection, ExpirationCycle, OptionChain
from strategies import (
    CORE_COMPONENTS,
    EARNINGS_CALENDAR_MANIFEST,
    STONK_STRATEGY_PLUGINS,
    compile_strategy_graph,
    execute_strategy_graph,
)
from strategies.earnings_calendar_knowledge_binding import EarningsCalendarPayload
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
    derived_facts: DerivedFactSet, payload: EarningsCalendarPayload
) -> ComponentValues:
    """Earnings Calendar's own read-only evaluation: retrieve the two
    named derived facts strategies/earnings_calendar_knowledge_binding.py
    already had materialized (by exact ID, never recomputed), normalize
    their richness, build this manifest's execution context, and execute
    the existing, unmodified EARNINGS_CALENDAR_MANIFEST graph.

    Never materializes a derived fact, never computes realized volatility
    or an IV spread, never selects structure -- all genuine, expected data
    gaps (missing spot price, no CALL contracts, missing implied
    volatility, insufficient historical bars) are resolved upstream, in
    strategies/earnings_calendar_structure.py and
    strategies/earnings_calendar_knowledge_binding.py, before this
    function is ever called.
    """
    term_structure_fact = derived_facts.get(payload.term_structure_fact_id)
    atm_iv_vs_realized_fact = derived_facts.get(payload.atm_iv_vs_realized_fact_id)
    # Both registered features' own definitions always produce a Decimal
    # spread (DerivedFact.value's own type is a wider union covering every
    # registered feature, not just these two) -- narrowed explicitly here
    # rather than widening normalize_richness's own signature.
    assert isinstance(term_structure_fact.value, Decimal)
    assert isinstance(atm_iv_vs_realized_fact.value, Decimal)

    context = build_earnings_calendar_context(
        payload.chain,
        payload.event,
        payload.front_cycle,
        payload.back_cycle,
        payload.as_of,
        target_strike=payload.target_strike,
        term_structure_richness=normalize_richness(term_structure_fact.value),
        iv_realized_volatility_richness=normalize_richness(atm_iv_vs_realized_fact.value),
    )
    graph = compile_strategy_graph(EARNINGS_CALENDAR_MANIFEST, _COMPONENT_REGISTRY)
    result = execute_strategy_graph(graph, context)
    return result.outputs
