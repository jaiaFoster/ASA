"""Graph evaluation for the stock benchmarks (B001/B002).

Both benchmarks reach this function only once their required evidence has
already resolved and (for B002) SMA10M has already been materialized --
an unusable-evidence or insufficient-history gap is a typed UnknownReason
raised earlier in preparation, surfaced generically as MISSING_DATA, and
never reaches these functions at all. The verdict itself is owned by each
benchmark's manifest graph (ADR-010; SL-03-00); this module only assembles
graph inputs and executes the graph.
"""

from __future__ import annotations

from strategies import (
    CORE_COMPONENTS,
    STONK_STRATEGY_PLUGINS,
    compile_strategy_graph,
    execute_strategy_graph,
)
from strategies.plugins import build_plugin_registry
from strategies.stock_benchmark_knowledge import B001Payload, B002Payload
from strategies.stock_benchmark_manifests import B001_MANIFEST, B002_MANIFEST
from strategies.stonk_components import D
from strategies.type_system import ComponentValues, TypedValue

VERDICT_PASS = "PASS"

_COMPONENT_REGISTRY = build_plugin_registry(CORE_COMPONENTS, STONK_STRATEGY_PLUGINS)
_B001_GRAPH = compile_strategy_graph(B001_MANIFEST, _COMPONENT_REGISTRY)
_B002_GRAPH = compile_strategy_graph(B002_MANIFEST, _COMPONENT_REGISTRY)


def evaluate_b001(payload: B001Payload) -> str:
    """SPY buy-and-hold: usable current price is always a PASS/BUY."""

    del payload
    return str(
        execute_strategy_graph(_B001_GRAPH, ComponentValues(())).outputs.get("verdict").value
    )


def evaluate_b002(payload: B002Payload) -> str:
    """SPY 10-month trend: PASS/BUY only strictly above the SMA10M, else FAIL."""

    context = ComponentValues(
        (
            ("sma_at_or_above_price.left", TypedValue(D, payload.sma_10m)),
            ("sma_at_or_above_price.right", TypedValue(D, payload.price)),
        )
    )
    return str(execute_strategy_graph(_B002_GRAPH, context).outputs.get("verdict").value)
