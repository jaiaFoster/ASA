"""Frozen Cboe BXM production manifest."""

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

STRATEGY_ID = "index_buywrite_cboe_bxm"
STRATEGY_VERSION = "1.0.0"

BXM_MANIFEST = StrategyManifest(
    "1.1.0",
    STRATEGY_ID,
    STRATEGY_VERSION,
    ManifestMetadata(
        "Cboe S&P 500 BuyWrite",
        "Monthly S&P 500 index exposure overlaid with one short standard SPX call.",
        ("index", "options", "buywrite"),
    ),
    (
        ParameterSpec("reference_time_et", "String", "11:00:00"),
        ParameterSpec("vwap_window_start_et", "String", "11:30:00"),
        ParameterSpec("vwap_window_end_et", "String", "13:30:00"),
        ParameterSpec("strike_rule", "String", "minimum_listed_strike_gte_reference"),
        ParameterSpec("index_units", "Decimal", "1"),
        ParameterSpec("short_call_quantity", "Decimal", "1"),
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
            MarketCapability.INDEX_SETTLEMENT_VALUE_V1,
            MarketCapability.OPTION_TRADE_TAPE_V1,
            MarketCapability.INDEX_DIVIDEND_POINTS_V1,
        )
    ),
)
