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
    (),
    (),
    (
        NodeSpec(
            "timing",
            ComponentReference("asa.bxm", "entry_timing", "1.0.0"),
            (
                ParameterSpec("reference_time_et", "Text", "11:00:00"),
                ParameterSpec("vwap_window_start_et", "Text", "11:30:00"),
                ParameterSpec("vwap_window_end_et", "Text", "13:30:00"),
                ParameterSpec(
                    "excluded_sale_condition_codes",
                    "Text",
                    "ABCDEFGHfghijklmnopqrst",
                ),
            ),
        ),
        NodeSpec(
            "selection",
            ComponentReference("asa.bxm", "call_selection", "1.0.0"),
            (
                ParameterSpec("contract_root", "Text", "SPX"),
                ParameterSpec("settlement_style", "Text", "am"),
                ParameterSpec("expiration_month_offset", "Decimal", "1"),
                ParameterSpec("strike_operator", "Text", ">="),
            ),
        ),
        NodeSpec("entry_gates", ComponentReference("asa.tristate", "tri_and", "1.0.0")),
        NodeSpec("verdict", ComponentReference("asa.cboe_put", "verdict", "1.0.0")),
        NodeSpec(
            "index_units",
            ComponentReference("asa.core", "constant", "1.0.0"),
            (ParameterSpec("value", "Decimal", "1"),),
        ),
        NodeSpec(
            "short_call_quantity",
            ComponentReference("asa.core", "constant", "1.0.0"),
            (ParameterSpec("value", "Decimal", "1"),),
        ),
    ),
    (
        EdgeSpec("timing", "reference_state", "entry_gates", "left"),
        EdgeSpec("selection", "strike_state", "entry_gates", "right"),
        EdgeSpec("timing", "roll_state", "verdict", "roll_date"),
        EdgeSpec("entry_gates", "result", "verdict", "entry_gates"),
    ),
    (
        OutputSpec("verdict", "verdict", "verdict", "verdict"),
        OutputSpec("selected_call", "selection", "selected_call", "structure"),
        OutputSpec("index_units", "index_units", "value", "structure"),
        OutputSpec("short_call_quantity", "short_call_quantity", "value", "structure"),
        OutputSpec("roll_state", "timing", "roll_state", "gate"),
        OutputSpec("reference_state", "timing", "reference_state", "gate"),
    ),
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
            MarketCapability.HISTORICAL_BARS_V1,
            MarketCapability.HISTORICAL_OPTION_PANEL_V1,
        )
    ),
)


def bxm_parameter(node_id: str, name: str) -> object:
    """Read one financial parameter from the identity-bearing manifest node."""
    node = next(item for item in BXM_MANIFEST.nodes if item.node_id == node_id)
    return next(item.value for item in node.parameters if item.name == name)
