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
STRATEGY_VERSION = "1.2.0"

SCS_MANIFEST = StrategyManifest(
    "1.1.0",
    STRATEGY_ID,
    STRATEGY_VERSION,
    ManifestMetadata(
        "Santa-Clara/Saretto Short SPX Straddle",
        "Monthly short near-maturity ATM standard SPX straddle.",
        ("index", "options", "short_volatility"),
    ),
    (),
    (),
    (
        NodeSpec(
            "policy",
            ComponentReference("asa.scs", "policy", "1.0.0"),
            (
                ParameterSpec("target_dte_calendar_days", "Decimal", "45"),
                ParameterSpec("expiration_cycle", "Text", "standard_monthly"),
                ParameterSpec("contract_root", "Text", "SPX"),
                ParameterSpec("settlement_style", "Text", "am"),
                ParameterSpec("minimum_iv", "Decimal", "0.01"),
                ParameterSpec("maximum_iv", "Decimal", "1"),
                ParameterSpec("low_price_boundary", "Decimal", "3"),
                ParameterSpec("low_price_minimum_spread", "Decimal", "0.05"),
                ParameterSpec("high_price_minimum_spread", "Decimal", "0.10"),
                ParameterSpec("risk_free_series", "Text", "US_TBILL_4WK_BANK_DISCOUNT"),
                ParameterSpec("dividend_yield_series", "Text", "SP500_DIVIDEND_YIELD"),
                ParameterSpec(
                    "exit_policy", "Text", "earliest_candidate_date"
                ),
                ParameterSpec("margin_alpha", "Decimal", "0.15"),
                ParameterSpec("margin_beta", "Decimal", "0.10"),
            ),
        ),
        NodeSpec("entry_gates", ComponentReference("asa.tristate", "tri_and", "1.0.0")),
        NodeSpec("verdict", ComponentReference("asa.tristate", "tri_verdict", "1.0.0")),
        NodeSpec(
            "short_call_quantity",
            ComponentReference("asa.core", "constant", "1.0.0"),
            (ParameterSpec("value", "Decimal", "1"),),
        ),
        NodeSpec(
            "short_put_quantity",
            ComponentReference("asa.core", "constant", "1.0.0"),
            (ParameterSpec("value", "Decimal", "1"),),
        ),
    ),
    (
        EdgeSpec("policy", "entry_state", "entry_gates", "left"),
        EdgeSpec("policy", "pair_state", "entry_gates", "right"),
        EdgeSpec("entry_gates", "result", "verdict", "gate"),
    ),
    (
        OutputSpec("verdict", "verdict", "verdict", "verdict"),
        OutputSpec("selected_call", "policy", "selected_call", "structure"),
        OutputSpec("selected_put", "policy", "selected_put", "structure"),
        OutputSpec("short_call_quantity", "short_call_quantity", "value", "structure"),
        OutputSpec("short_put_quantity", "short_put_quantity", "value", "structure"),
        OutputSpec("entry_state", "policy", "entry_state", "gate"),
        OutputSpec("pair_state", "policy", "pair_state", "gate"),
        OutputSpec("selection_reason", "policy", "selection_reason", "value"),
        OutputSpec("call_naked_margin", "policy", "call_naked_margin", "value"),
        OutputSpec("put_naked_margin", "policy", "put_naked_margin", "value"),
        OutputSpec("straddle_margin", "policy", "straddle_margin", "value"),
        OutputSpec("margin_reason", "policy", "margin_reason", "value"),
    ),
    (),
    required_market_capabilities=tuple(
        CapabilityRequirement(item.value, "1.0.0")
        for item in (
            MarketCapability.REAL_TIME_QUOTE_V1,
            MarketCapability.OPTION_CHAIN_V1,
            MarketCapability.RATE_OBSERVATION_V1,
            MarketCapability.INDEX_SETTLEMENT_VALUE_V1,
        )
    ),
    assumptions=(AssumptionReference("RA-SV-01", "research"),),
)


def scs_parameter(name: str) -> object:
    node = next(item for item in SCS_MANIFEST.nodes if item.node_id == "policy")
    return next(item.value for item in node.parameters if item.name == name)
