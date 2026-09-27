"""Frozen GXZ pre-earnings hold-to-expiry straddle manifest (SP-02B)."""

from __future__ import annotations

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

GXZ_STRATEGY_ID = "event_vol_gxz_preea_straddle_to_expiry"
GXZ_STRATEGY_VERSION = "1.0.0-research"

# Parameters include the source rules and both closeout assumptions. Financial
# gates enter the manifest as explicit three-state values; the graph owns their
# composition and the frozen entry-session verdict precedence.
GXZ_MANIFEST = StrategyManifest(
    "1.1.0",
    GXZ_STRATEGY_ID,
    GXZ_STRATEGY_VERSION,
    ManifestMetadata(
        "GXZ Pre-Earnings Straddle to Expiry",
        "Delta-neutral ATM straddles entered three sessions before earnings and held to expiry.",
        ("event_volatility", "options", "research"),
    ),
    (
        ParameterSpec("entry_offset_sessions", "Integer", -3),
        ParameterSpec("minimum_stock_price", "Decimal", "5"),
        ParameterSpec("minimum_option_mid", "Decimal", "0.125"),
        ParameterSpec("minimum_abs_delta", "Decimal", "0.375"),
        ParameterSpec("maximum_abs_delta", "Decimal", "0.625"),
        ParameterSpec("minimum_moneyness", "Decimal", "0.95"),
        ParameterSpec("maximum_moneyness", "Decimal", "1.05"),
        ParameterSpec("minimum_calendar_dte", "Integer", 4),
        ParameterSpec("maximum_calendar_dte", "Integer", 10),
        ParameterSpec("entry_effective_spread_fraction", "Decimal", "1"),
    ),
    (),
    (
        NodeSpec("ea_stock", ComponentReference("asa.tristate", "tri_and", "1.0.0")),
        NodeSpec("expiry_pair", ComponentReference("asa.tristate", "tri_and", "1.0.0")),
        NodeSpec("financial_gates", ComponentReference("asa.tristate", "tri_and", "1.0.0")),
        NodeSpec("verdict", ComponentReference("asa.gxz", "verdict", "1.0.0")),
    ),
    (
        EdgeSpec("ea_stock", "result", "financial_gates", "left"),
        EdgeSpec("expiry_pair", "result", "financial_gates", "right"),
        EdgeSpec("financial_gates", "result", "verdict", "financial_gates"),
    ),
    (OutputSpec("verdict", "verdict", "verdict", "verdict"),),
    (),
    required_market_capabilities=tuple(
        CapabilityRequirement(capability.value, "1.0.0")
        for capability in (
            MarketCapability.REAL_TIME_QUOTE_V1,
            MarketCapability.EARNINGS_CALENDAR_V1,
            MarketCapability.TRADING_CALENDAR_V1,
            MarketCapability.OPTION_CHAIN_V1,
        )
    ),
    assumptions=(
        AssumptionReference("RA-EV-01", "research"),
        AssumptionReference(
            "RA-EV-02", "research", ("minimum_calendar_dte", "maximum_calendar_dte")
        ),
        AssumptionReference("IA-GXZ-PROVIDER-DELTA", "implementation"),
        AssumptionReference(
            "IA-GXZ-ENTRY-PRICE", "implementation", ("entry_effective_spread_fraction",)
        ),
    ),
)
