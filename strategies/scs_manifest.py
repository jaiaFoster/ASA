"""Frozen Santa-Clara/Saretto short-SPX-straddle manifest."""

from domain import MarketCapability
from strategies.manifest import (
    AssumptionReference,
    CapabilityRequirement,
    ComponentReference,
    EdgeSpec,
    ManifestMetadata,
    NodeSpec,
    OutputSpec,
    ParameterSpec,
    StrategyManifest,
)

STRATEGY_ID = "index_short_vol_scs_near_atm_straddle"
STRATEGY_VERSION = "1.0.0"

SCS_MANIFEST = StrategyManifest(
    "1.1.0",
    STRATEGY_ID,
    STRATEGY_VERSION,
    ManifestMetadata(
        "Santa-Clara/Saretto Short SPX Straddle",
        "Monthly short near-maturity ATM standard SPX straddle.",
        ("index", "options", "short_volatility"),
    ),
    (
        ParameterSpec("target_dte_calendar_days", "Integer", 45),
        ParameterSpec("minimum_iv", "Decimal", "0.01"),
        ParameterSpec("maximum_iv", "Decimal", "1.00"),
        ParameterSpec("margin_alpha", "Decimal", "0.15"),
        ParameterSpec("margin_beta", "Decimal", "0.10"),
        ParameterSpec("expiration_cycle", "String", "standard_monthly"),
    ),
    (),
    (
        NodeSpec("entry_gates", ComponentReference("asa.tristate", "tri_and", "1.0.0")),
        NodeSpec("verdict", ComponentReference("asa.cboe_put", "verdict", "1.0.0")),
    ),
    (EdgeSpec("entry_gates", "result", "verdict", "entry_gates"),),
    (OutputSpec("verdict", "verdict", "verdict", "verdict"),),
    (),
    required_market_capabilities=tuple(
        CapabilityRequirement(item.value, "1.0.0")
        for item in (
            MarketCapability.REAL_TIME_QUOTE_V1,
            MarketCapability.OPTION_CHAIN_V1,
            MarketCapability.TRADING_CALENDAR_V1,
            MarketCapability.RATE_OBSERVATION_V1,
            MarketCapability.INDEX_SETTLEMENT_VALUE_V1,
        )
    ),
    assumptions=(AssumptionReference("RA-SV-01", "research"),),
)
