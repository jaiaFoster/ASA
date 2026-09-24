"""Canonical manifest: SPY 30-DTE put credit spread (SL-02).

Source: Option Alpha, "8 SPY Put Credit Spread Backtest Results Analyzed"
(Du Plessis, Henry, Hysmith; published 2021-11-17, updated 2023-01-11),
https://optionalpha.com/blog/spy-put-credit-spread-backtest -- backtest 1
only: SPY; "30 days to expiration"; "0.30 delta for the short contract and
0.10 delta for the long contract"; "No profit targets or stop-loss levels";
"Hold the position to expiration"; no entry filter. Variants with targets,
stops, or rolling are excluded: the source leaves their bases undefined.

The graph owns the whole judgment. The structure is composed from the
registered vertical component; the source defines no entry gate, so the
verdict is the graph's constant PASS once the exact spread is evaluable.
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

SHORT_PUT_DELTA = "-0.30"
LONG_PUT_DELTA = "-0.10"


def _node(
    node_id: str, namespace: str, component: str, parameters: tuple[ParameterSpec, ...] = ()
) -> NodeSpec:
    return NodeSpec(node_id, ComponentReference(namespace, component, "1.0.0"), parameters)


SPY_PUT_CREDIT_SPREAD_MANIFEST = StrategyManifest(
    "1.1.0",
    "spy_put_credit_spread",
    "1.0.0",
    ManifestMetadata(
        "SPY 30-DTE Put Credit Spread",
        "Option Alpha SPY put credit spread backtest 1: 30 DTE, 0.30/0.10 delta, "
        "held to expiration.",
        ("options", "premium_selling", "sourced"),
    ),
    (),
    (),
    (
        _node(
            "spread",
            "asa.stonk.options",
            "vertical_structure",
            (
                ParameterSpec("option_type", "Enum", "put"),
                ParameterSpec("long_delta_target", "Decimal", LONG_PUT_DELTA),
                ParameterSpec("short_delta_target", "Decimal", SHORT_PUT_DELTA),
            ),
        ),
        _node("entry", "asa.stonk.options", "option_structure_debit"),
        _node("unit", "asa.core", "constant", (ParameterSpec("value", "Decimal", "1"),)),
        _node(
            "verdict",
            "asa.stonk.shared",
            "verdict_classifier",
            (
                ParameterSpec("pass_threshold", "Decimal", "1"),
                ParameterSpec("watch_threshold", "Decimal", "1"),
            ),
        ),
    ),
    (
        EdgeSpec("spread", "structure", "entry", "structure"),
        EdgeSpec("unit", "value", "verdict", "score"),
    ),
    (
        OutputSpec("structure", "spread", "structure", "structure"),
        OutputSpec("mid_debit", "entry", "mid_debit", "fact"),
        OutputSpec("conservative_debit", "entry", "conservative_debit", "fact"),
        OutputSpec("verdict", "verdict", "verdict", "verdict"),
    ),
    required_market_capabilities=(
        CapabilityRequirement(MarketCapability.REAL_TIME_QUOTE_V1.value, "1.0.0"),
        CapabilityRequirement(MarketCapability.OPTION_CHAIN_V1.value, "1.0.0"),
    ),
)
