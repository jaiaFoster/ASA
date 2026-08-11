"""Read-only Forward Factor graph evaluation over materialized knowledge."""

from __future__ import annotations

from analytics.features import DerivedFactSet
from domain import ExpirationCollection
from strategies import (
    CORE_COMPONENTS,
    FORWARD_FACTOR_CALENDAR_MANIFEST,
    STONK_STRATEGY_PLUGINS,
    compile_strategy_graph,
    execute_strategy_graph,
)
from strategies.forward_factor_knowledge import ForwardFactorPayload
from strategies.plugins import build_plugin_registry
from strategies.stonk_components import DATE, EXPIRATION_COLLECTION, OPTION_CHAIN, B, D
from strategies.type_system import ComponentValues, StrategyTypeReference, TypedValue

_COMPONENT_REGISTRY = build_plugin_registry(CORE_COMPONENTS, STONK_STRATEGY_PLUGINS)
_INTEGER = StrategyTypeReference("Integer", "1.0.0")


def evaluate_forward_factor(
    derived_facts: DerivedFactSet, payload: ForwardFactorPayload
) -> ComponentValues:
    front_iv = derived_facts.get(payload.implied_forward_fact_id)
    factor = derived_facts.get(payload.forward_factor_fact_id)
    # Reading both facts proves the graph receives the exact materialized
    # feature set for this selection. Its frozen graph still derives the same
    # values from the canonical front/back IV inputs for explainability.
    assert front_iv.value is not None
    assert factor.value is not None

    optional_date = StrategyTypeReference("Optional", "1.0.0", (DATE,))
    values = {
        "expiration_select.expirations": (
            EXPIRATION_COLLECTION,
            ExpirationCollection(payload.as_of, (payload.front_cycle, payload.back_cycle)),
        ),
        "double_calendar.chain": (OPTION_CHAIN, payload.chain),
        "forward_iv.front_iv": (D, payload.front_implied_volatility),
        "forward_iv.back_iv": (D, payload.back_implied_volatility),
        "forward_iv.front_dte": (_INTEGER, payload.front_cycle.days_to_expiration),
        "forward_iv.back_dte": (_INTEGER, payload.back_cycle.days_to_expiration),
        "factor.front_iv": (D, payload.front_implied_volatility),
        "eligibility.earnings_eligible": (B, payload.earnings_eligible),
        "eligibility.confirmed_earnings_date": (
            optional_date,
            payload.confirmed_earnings_date,
        ),
    }
    context = ComponentValues(
        tuple((name, TypedValue(type_ref, value)) for name, (type_ref, value) in values.items())
    )
    graph = compile_strategy_graph(FORWARD_FACTOR_CALENDAR_MANIFEST, _COMPONENT_REGISTRY)
    return execute_strategy_graph(graph, context).outputs
