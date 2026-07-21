"""Manifest-only moving-average crossover reference strategy (STRAT-010)."""

from __future__ import annotations

from strategies.manifest import (
    ComponentReference,
    EdgeSpec,
    ManifestMetadata,
    NodeSpec,
    OutputSpec,
    ParameterSpec,
    StrategyManifest,
)

MOVING_AVERAGE_CROSSOVER_MANIFEST = StrategyManifest(
    schema_version="1.0.0",
    strategy_id="asa.reference.moving_average_crossover",
    strategy_version="1.0.0",
    metadata=ManifestMetadata(
        "Moving Average Crossover",
        "Signals when the explicit short moving average is at least the long moving average.",
        ("reference", "trend"),
    ),
    parameters=(),
    required_capabilities=(),
    nodes=(
        NodeSpec(
            "crossover",
            ComponentReference("asa.core", "expression_predicate", "1.0.0"),
            (ParameterSpec("expression", "Text", "left >= right"),),
        ),
        NodeSpec(
            "portfolio_gate",
            ComponentReference("asa.core", "portfolio_constraint", "1.0.0"),
        ),
    ),
    edges=(EdgeSpec("crossover", "result", "portfolio_gate", "allowed"),),
    outputs=(OutputSpec("signal", "portfolio_gate", "allowed"),),
)
