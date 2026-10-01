"""Frozen Heston low-cost straddle-momentum manifest (SP-05D)."""

from domain import MarketCapability
from strategies.manifest import (
    AssumptionReference,
    CapabilityRequirement,
    ComponentReference,
    ManifestMetadata,
    NodeSpec,
    OutputSpec,
    ParameterSpec,
    StrategyManifest,
)

STRATEGY_ID = "xs_option_heston_straddle_momentum_lowcost"
STRATEGY_VERSION = "1.0.0-research"

HESTON_MANIFEST = StrategyManifest(
    "1.1.0",
    STRATEGY_ID,
    STRATEGY_VERSION,
    ManifestMetadata(
        "Heston Low-Cost Straddle Momentum",
        "Monthly equal-weight long-high/short-low decile portfolio of zero-delta straddles.",
        ("cross_sectional", "options", "momentum", "research"),
    ),
    (
        ParameterSpec("minimum_call_delta", "Decimal", "0.25"),
        ParameterSpec("maximum_call_delta", "Decimal", "0.75"),
        ParameterSpec("maximum_leg_relative_spread", "Decimal", "0.10"),
        ParameterSpec("formation_lag_start", "Integer", 2),
        ParameterSpec("formation_lag_end", "Integer", 12),
        ParameterSpec("quantiles", "Integer", 10),
        ParameterSpec("long_group", "Integer", 10),
        ParameterSpec("short_group", "Integer", 1),
        ParameterSpec("weighting", "Text", "equal_per_book"),
        ParameterSpec("replacement_policy", "Text", "none"),
    ),
    (),
    (NodeSpec("portfolio", ComponentReference("asa.cross_subject", "portfolio", "1.0.0")),),
    (),
    (OutputSpec("portfolio", "portfolio", "portfolio", "structure"),),
    (),
    required_market_capabilities=tuple(
        CapabilityRequirement(item.value, "1.0.0")
        for item in (
            MarketCapability.OPTION_CHAIN_V1,
            MarketCapability.HISTORICAL_OPTION_PANEL_V1,
            MarketCapability.TRADING_CALENDAR_V1,
        )
    ),
    assumptions=(
        AssumptionReference("RA-XS-01", "research", ("quantiles",)),
        AssumptionReference("RA-XR-03", "research", ("replacement_policy",)),
    ),
)


def heston_parameter(name: str) -> object:
    return next(item.value for item in HESTON_MANIFEST.parameters if item.name == name)
