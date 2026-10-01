"""Frozen Zhan delta-neutral call-writing manifest (SP-05C)."""

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

STRATEGY_ID = "xs_option_zhan_neg_lnprice_dn_call"
STRATEGY_VERSION = "1.0.0"

ZHAN_MANIFEST = StrategyManifest(
    "1.1.0",
    STRATEGY_ID,
    STRATEGY_VERSION,
    ManifestMetadata(
        "Zhan Negative Log-Price Delta-Neutral Calls",
        "Monthly Stock-VW long high-price and short low-price delta-neutral call portfolio.",
        ("cross_sectional", "options", "delta_neutral"),
    ),
    (
        ParameterSpec("min_price", "Decimal", "5"),
        ParameterSpec("min_mid", "Decimal", "0.125"),
        ParameterSpec("moneyness_min", "Decimal", "0.8"),
        ParameterSpec("moneyness_max", "Decimal", "1.2"),
        ParameterSpec("quantiles", "Integer", 10),
        ParameterSpec("long_group", "Integer", 1),
        ParameterSpec("short_group", "Integer", 10),
        ParameterSpec("weighting", "Text", "stock_market_cap"),
        ParameterSpec("holding_months", "Integer", 1),
        ParameterSpec("hedge_rebalances", "Integer", 0),
        ParameterSpec("margin_alpha_equity", "Decimal", "0.20"),
        ParameterSpec("margin_beta", "Decimal", "0.10"),
    ),
    (),
    (NodeSpec("portfolio", ComponentReference("asa.cross_subject", "portfolio", "1.0.0")),),
    (),
    (OutputSpec("portfolio", "portfolio", "portfolio", "structure"),),
    (),
    required_market_capabilities=tuple(
        CapabilityRequirement(item.value, "1.0.0")
        for item in (
            MarketCapability.HISTORICAL_BARS_V1,
            MarketCapability.OPTION_CHAIN_V1,
            MarketCapability.TRADING_CALENDAR_V1,
            MarketCapability.RATE_OBSERVATION_V1,
            MarketCapability.SECURITY_MASTER_V1,
        )
    ),
    assumptions=(AssumptionReference("RA-XS-01", "research", ("quantiles",)),),
)


def zhan_parameter(name: str) -> object:
    return next(item.value for item in ZHAN_MANIFEST.parameters if item.name == name)
