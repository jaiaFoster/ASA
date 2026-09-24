"""Canonical manifests for the SPY stock benchmarks (SL-03-00).

Brings B001/B002 into ADR-010 conformance: the manifest is the only authored
definition and the graph owns every gate and verdict, composed entirely from
already-registered components.
"""

from __future__ import annotations

from domain import MarketCapability
from strategies.manifest import (
    CapabilityRequirement,
    ComponentReference,
    EdgeSpec,
    ManifestMetadata,
    NodeSpec,
    OutputSpec,
    ParameterSpec,
    StrategyManifest,
)


def _node(
    node_id: str, namespace: str, component: str, parameters: tuple[ParameterSpec, ...] = ()
) -> NodeSpec:
    return NodeSpec(node_id, ComponentReference(namespace, component, "1.0.0"), parameters)


def _capabilities(*values: MarketCapability) -> tuple[CapabilityRequirement, ...]:
    return tuple(CapabilityRequirement(value.value, "1.0.0") for value in values)


# A unit score classified at a threshold of one is the graph's constant PASS.
_UNIT = _node("unit", "asa.core", "constant", (ParameterSpec("value", "Decimal", "1"),))
_BASE_VERDICT = _node(
    "base_verdict",
    "asa.stonk.shared",
    "verdict_classifier",
    (
        ParameterSpec("pass_threshold", "Decimal", "1"),
        ParameterSpec("watch_threshold", "Decimal", "1"),
    ),
)

B001_MANIFEST = StrategyManifest(
    "1.1.0",
    "B001",
    "1.0.0",
    ManifestMetadata(
        "SPY Buy and Hold",
        "SPY buy-and-hold benchmark over usable current price evidence.",
        ("benchmark", "equity"),
    ),
    (),
    (),
    (_UNIT, _BASE_VERDICT),
    (EdgeSpec("unit", "value", "base_verdict", "score"),),
    (OutputSpec("verdict", "base_verdict", "verdict", "verdict"),),
    required_market_capabilities=_capabilities(MarketCapability.REAL_TIME_QUOTE_V1),
)

B002_MANIFEST = StrategyManifest(
    "1.1.0",
    "B002",
    "1.1.0",
    ManifestMetadata(
        "SPY 10-Month Trend",
        "SPY 10-month trend benchmark over completed-month adjusted closes.",
        ("benchmark", "equity", "trend"),
    ),
    (),
    (),
    (
        # Strictly above: price > sma  <=>  not (sma >= price).
        _node("sma_at_or_above_price", "asa.core", "compare"),
        _node("above_sma", "asa.core", "boolean_not"),
        _UNIT,
        _BASE_VERDICT,
        _node("verdict", "asa.stonk.shared", "verdict_eligibility_gate"),
    ),
    (
        EdgeSpec("sma_at_or_above_price", "result", "above_sma", "value"),
        EdgeSpec("unit", "value", "base_verdict", "score"),
        EdgeSpec("base_verdict", "verdict", "verdict", "verdict"),
        EdgeSpec("above_sma", "result", "verdict", "eligible"),
    ),
    (
        OutputSpec("above_sma_10m_gate", "above_sma", "result", "gate"),
        OutputSpec("verdict", "verdict", "verdict", "verdict"),
    ),
    required_market_capabilities=_capabilities(
        MarketCapability.REAL_TIME_QUOTE_V1,
        MarketCapability.HISTORICAL_BARS_V1,
    ),
)

STOCK_BENCHMARK_MANIFESTS = (B001_MANIFEST, B002_MANIFEST)
