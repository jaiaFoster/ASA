"""Manifest-only migrations of the four production Stonk strategies."""

from __future__ import annotations

from domain import MarketCapability
from strategies.manifest import (
    CapabilityRequirement,
    ComponentReference,
    EdgeSpec,
    ManifestMetadata,
    ManifestValue,
    NodeSpec,
    OutputSpec,
    ParameterSpec,
    StrategyManifest,
)


def _node(
    node_id: str,
    namespace: str,
    component: str,
    parameters: tuple[ParameterSpec, ...] = (),
) -> NodeSpec:
    return NodeSpec(
        node_id,
        ComponentReference(namespace, component, "1.0.0"),
        parameters,
    )


def _parameter(name: str, type_ref: str, value: ManifestValue) -> ParameterSpec:
    return ParameterSpec(name, type_ref, value)


def _capabilities(*values: MarketCapability) -> tuple[CapabilityRequirement, ...]:
    return tuple(CapabilityRequirement(value.value, "1.0.0") for value in values)


def _output(
    name: str,
    node_id: str,
    port: str,
    role: str = "value",
    formula_id: str | None = None,
) -> OutputSpec:
    return OutputSpec(name, node_id, port, role, formula_id)


EARNINGS_CALENDAR_MANIFEST = StrategyManifest(
    "1.1.0",
    "earnings_calendar",
    "1.1.0",
    ManifestMetadata(
        "Earnings Calendar Spread",
        "Confirmed earnings calendar targeting a 30-day expiration gap with liquidity evidence.",
        ("earnings", "migrated", "options"),
    ),
    (),
    (),
    (
        _node(
            "event_window",
            "asa.stonk.options",
            "earnings_event_window",
            (_parameter("require_confirmed", "Boolean", True),),
        ),
        _node(
            "expiration_select",
            "asa.stonk.options",
            "expiration_pair_selector",
            (
                _parameter("front_min_dte", "Integer", 7),
                _parameter("front_max_dte", "Integer", 21),
                _parameter("back_min_dte", "Integer", 22),
                _parameter("back_max_dte", "Integer", 75),
                _parameter("target_gap_days", "Integer", 30),
                _parameter("gap_tolerance_days", "Integer", 5),
            ),
        ),
        _node("pair", "asa.stonk.options", "expiration_pair_projection"),
        _node(
            "gap",
            "asa.stonk.options",
            "expiration_gap_projection",
            (_parameter("target_gap_days", "Integer", 30),),
        ),
        _node(
            "calendar",
            "asa.stonk.options",
            "nearest_common_strike_calendar",
            (_parameter("option_type", "Enum", "call"),),
        ),
        _node("debit", "asa.stonk.options", "option_structure_debit"),
        _node(
            "liquidity",
            "asa.stonk.options",
            "earnings_calendar_liquidity",
            (_parameter("minimum_volume_band", "Enum", "ADEQUATE"),),
        ),
        _node("event_gap_eligibility", "asa.core", "boolean_and"),
        _node("eligibility", "asa.core", "boolean_and"),
        _node(
            "score",
            "asa.stonk.shared",
            "two_factor_weighted_score",
            (
                _parameter("primary_weight", "Decimal", "3"),
                _parameter("secondary_weight", "Decimal", "1"),
                _parameter("ceiling", "Decimal", "100"),
            ),
        ),
        _node(
            "verdict",
            "asa.stonk.shared",
            "verdict_classifier",
            (
                _parameter("pass_threshold", "Decimal", "70"),
                _parameter("watch_threshold", "Decimal", "55"),
            ),
        ),
        _node(
            "gated_verdict",
            "asa.stonk.shared",
            "verdict_eligibility_supplement_gate",
        ),
    ),
    (
        EdgeSpec("expiration_select", "selected", "pair", "selected"),
        EdgeSpec("expiration_select", "selected", "gap", "selected"),
        EdgeSpec("pair", "front_expiration", "calendar", "front_expiration"),
        EdgeSpec("pair", "back_expiration", "calendar", "back_expiration"),
        EdgeSpec("calendar", "structure", "debit", "structure"),
        EdgeSpec("calendar", "structure", "liquidity", "structure"),
        EdgeSpec("event_window", "eligible", "event_gap_eligibility", "left"),
        EdgeSpec("expiration_select", "gap_eligible", "event_gap_eligibility", "right"),
        EdgeSpec("event_gap_eligibility", "result", "eligibility", "left"),
        EdgeSpec("liquidity", "acceptable", "eligibility", "right"),
        EdgeSpec("score", "score", "verdict", "score"),
        EdgeSpec("verdict", "verdict", "gated_verdict", "verdict"),
        EdgeSpec("eligibility", "result", "gated_verdict", "eligible"),
        EdgeSpec(
            "liquidity",
            "volume_supplement_strong",
            "gated_verdict",
            "supplement_strong",
        ),
    ),
    (
        _output("earnings_eligible", "event_window", "eligible", "gate"),
        _output("eligible", "eligibility", "result", "gate"),
        _output("gap_eligible", "expiration_select", "gap_eligible", "gate"),
        _output("selected_expirations", "expiration_select", "selected", "fact"),
        _output(
            "actual_gap_days",
            "gap",
            "actual_gap_days",
            "derived_fact",
            "expiration_gap_days",
        ),
        _output(
            "gap_deviation_days",
            "gap",
            "gap_deviation_days",
            "derived_fact",
            "expiration_gap_distance_from_target",
        ),
        _output("structure", "calendar", "structure", "structure"),
        _output("liquidity_acceptable", "liquidity", "acceptable", "gate"),
        _output(
            "option_volume_band",
            "liquidity",
            "volume_band",
            "derived_fact",
            "option_volume_band",
        ),
        _output(
            "volume_supplement_strong",
            "liquidity",
            "volume_supplement_strong",
            "gate",
        ),
        _output("mid_debit", "debit", "mid_debit", "fact"),
        _output("conservative_debit", "debit", "conservative_debit", "fact"),
        _output("score", "score", "score", "score"),
        _output("term_structure_richness", "score", "primary", "fact"),
        _output(
            "front_iv_vs_realized_volatility",
            "score",
            "secondary",
            "derived_fact",
            "atm_iv_vs_realized_volatility",
        ),
        _output("verdict", "gated_verdict", "verdict", "verdict"),
    ),
    required_market_capabilities=_capabilities(
        MarketCapability.REAL_TIME_QUOTE_V1,
        MarketCapability.HISTORICAL_BARS_V1,
        MarketCapability.OPTION_CHAIN_V1,
        MarketCapability.EARNINGS_CALENDAR_V1,
    ),
)


SKEW_MOMENTUM_VERTICAL_MANIFEST = StrategyManifest(
    "1.1.0",
    "skew_momentum",
    "2.0.0-research",
    ManifestMetadata(
        "Skew Momentum v2 Research",
        "Two-sided skew, volatility-value, and three-dimension momentum policy.",
        ("momentum", "options", "research", "skew"),
    ),
    (),
    (),
    (
        _node(
            "decision",
            "asa.stonk.options",
            "skew_momentum_research_decision",
            (
                _parameter("skew_zscore_threshold", "Decimal", "-2.0"),
                _parameter("historical_lookback_observations", "Integer", 60),
                _parameter("minimum_valid_observations", "Integer", 40),
                _parameter("time_series_lookback_sessions", "Integer", 20),
                _parameter("bullish_cross_sectional_minimum", "Decimal", "0.70"),
                _parameter("bearish_cross_sectional_maximum", "Decimal", "0.30"),
                _parameter("required_momentum_alignment", "Integer", 2),
                _parameter("long_delta_target", "Decimal", "0.50"),
                _parameter("short_delta_target", "Decimal", "0.25"),
                _parameter("maximum_spread_ratio", "Decimal", "0.15"),
                _parameter("minimum_open_interest", "Integer", 50),
                _parameter("minimum_volume", "Integer", 10),
            ),
        ),
    ),
    (),
    (
        _output("structure", "decision", "structure", "structure"),
        _output("mid_debit", "decision", "mid_debit", "fact"),
        _output("conservative_debit", "decision", "conservative_debit", "fact"),
        _output("liquidity_acceptable", "decision", "liquidity_acceptable", "gate"),
        _output("direction", "decision", "direction", "direction"),
        _output(
            "normalized_call_skew",
            "decision",
            "normalized_call_skew",
            "derived_fact",
            "normalized_call_skew",
        ),
        _output(
            "normalized_put_skew",
            "decision",
            "normalized_put_skew",
            "derived_fact",
            "normalized_put_skew",
        ),
        _output(
            "call_skew_zscore",
            "decision",
            "call_skew_zscore",
            "derived_fact",
            "skew_historical_zscore",
        ),
        _output(
            "put_skew_zscore",
            "decision",
            "put_skew_zscore",
            "derived_fact",
            "skew_historical_zscore",
        ),
        _output(
            "historical_valid_observations",
            "decision",
            "historical_valid_observations",
            "fact",
        ),
        _output(
            "call_atm_iv_minus_rv",
            "decision",
            "call_atm_iv_minus_rv",
            "derived_fact",
            "atm_iv_vs_realized_volatility",
        ),
        _output(
            "put_atm_iv_minus_rv",
            "decision",
            "put_atm_iv_minus_rv",
            "derived_fact",
            "atm_iv_vs_realized_volatility",
        ),
        _output(
            "call_wing_iv_minus_rv",
            "decision",
            "call_wing_iv_minus_rv",
            "derived_fact",
            "call_wing_iv_vs_realized_volatility",
        ),
        _output(
            "put_wing_iv_minus_rv",
            "decision",
            "put_wing_iv_minus_rv",
            "derived_fact",
            "put_wing_iv_vs_realized_volatility",
        ),
        _output(
            "call_wing_iv_minus_atm_iv",
            "decision",
            "call_wing_iv_minus_atm_iv",
            "fact",
        ),
        _output(
            "put_wing_iv_minus_atm_iv",
            "decision",
            "put_wing_iv_minus_atm_iv",
            "fact",
        ),
        _output(
            "time_series_return",
            "decision",
            "time_series_return",
            "derived_fact",
            "named_momentum_dimensions",
        ),
        _output(
            "cross_sectional_percentile",
            "decision",
            "cross_sectional_percentile",
            "derived_fact",
            "cross_sectional_momentum",
        ),
        _output("comparison_peer_count", "decision", "comparison_peer_count", "fact"),
        _output(
            "sector_relative_return",
            "decision",
            "sector_relative_return",
            "derived_fact",
            "sector_relative_momentum",
        ),
        _output("bullish_core_gate", "decision", "bullish_core_gate", "gate"),
        _output("bearish_core_gate", "decision", "bearish_core_gate", "gate"),
        _output(
            "momentum_alignment_count",
            "decision",
            "momentum_alignment_count",
            "fact",
        ),
        _output("momentum_complete", "decision", "momentum_complete", "gate"),
        _output("score", "decision", "score", "score"),
        _output("verdict", "decision", "verdict", "verdict"),
    ),
    required_market_capabilities=_capabilities(
        MarketCapability.REAL_TIME_QUOTE_V1,
        MarketCapability.HISTORICAL_BARS_V1,
        MarketCapability.OPTION_CHAIN_V1,
    ),
)


FORWARD_FACTOR_CALENDAR_MANIFEST = StrategyManifest(
    "1.1.0",
    "forward_factor",
    "1.2.0",
    ManifestMetadata(
        "Forward Factor Calendar",
        "Raw-front-IV forward factor with confirmed-earnings exclusion and "
        "a liquidity-complete delta-selected double calendar.",
        ("dry_run", "forward_volatility", "migrated", "options"),
    ),
    (),
    (),
    (
        _node(
            "expiration_select",
            "asa.stonk.options",
            "dte_pair_selector",
            (
                _parameter("front_min_dte", "Integer", 35),
                _parameter("front_max_dte", "Integer", 90),
                _parameter("back_min_dte", "Integer", 49),
                _parameter("back_max_dte", "Integer", 139),
                _parameter("minimum_gap_days", "Integer", 14),
                _parameter("maximum_gap_days", "Integer", 49),
                _parameter("target_front_dte", "Integer", 60),
                _parameter("target_gap_days", "Integer", 30),
            ),
        ),
        _node("pair", "asa.stonk.options", "expiration_pair_projection"),
        _node(
            "double_calendar",
            "asa.stonk.options",
            "double_calendar_structure",
            (
                _parameter("put_delta_target", "Decimal", "-0.35"),
                _parameter("call_delta_target", "Decimal", "0.35"),
            ),
        ),
        _node("forward_iv", "asa.stonk.options", "implied_forward_volatility"),
        _node("factor", "asa.stonk.options", "forward_factor"),
        _node(
            "liquidity",
            "asa.stonk.options",
            "option_structure_collection_liquidity",
        ),
        _node("eligibility", "asa.core", "boolean_and"),
        _node(
            "verdict",
            "asa.stonk.shared",
            "verdict_classifier",
            (
                _parameter("pass_threshold", "Decimal", "0.20"),
                _parameter("watch_threshold", "Decimal", "0.12"),
            ),
        ),
        _node("gated_verdict", "asa.stonk.shared", "verdict_eligibility_gate"),
    ),
    (
        EdgeSpec("expiration_select", "selected", "pair", "selected"),
        EdgeSpec("pair", "front_expiration", "double_calendar", "front_expiration"),
        EdgeSpec("pair", "back_expiration", "double_calendar", "back_expiration"),
        EdgeSpec("forward_iv", "implied_forward_iv", "factor", "implied_forward_iv"),
        EdgeSpec("double_calendar", "structures", "liquidity", "structures"),
        EdgeSpec("liquidity", "acceptable", "eligibility", "right"),
        EdgeSpec("factor", "factor", "verdict", "score"),
        EdgeSpec("verdict", "verdict", "gated_verdict", "verdict"),
        EdgeSpec("eligibility", "result", "gated_verdict", "eligible"),
    ),
    (
        _output("selected_expirations", "expiration_select", "selected", "fact"),
        _output("structures", "double_calendar", "structures", "structure"),
        _output("liquidity_acceptable", "liquidity", "acceptable", "gate"),
        _output("eligible", "eligibility", "result", "gate"),
        _output("front_iv", "factor", "front_iv", "fact"),
        _output(
            "implied_forward_volatility",
            "forward_iv",
            "implied_forward_iv",
            "derived_fact",
            "implied_forward_volatility",
        ),
        _output(
            "forward_factor",
            "factor",
            "factor",
            "derived_fact",
            "forward_factor",
        ),
        _output("verdict", "gated_verdict", "verdict", "verdict"),
    ),
    required_market_capabilities=_capabilities(
        MarketCapability.REAL_TIME_QUOTE_V1,
        MarketCapability.OPTION_CHAIN_V1,
        MarketCapability.EARNINGS_CALENDAR_V1,
    ),
)


STOCK_MOMENTUM_MANIFEST = StrategyManifest(
    "1.0.0",
    "asa.stonk.stock_momentum",
    "1.0.0",
    ManifestMetadata(
        "Stock Momentum",
        "Bounded momentum score and desired candidate universe without portfolio policy.",
        ("equity", "migrated", "momentum"),
    ),
    (),
    (),
    (
        _node(
            "universe",
            "asa.stonk.shared",
            "deterministic_security_cap",
            (_parameter("maximum_count", "Integer", 12),),
        ),
        _node(
            "score",
            "asa.stonk.shared",
            "weighted_score_with_ceiling",
            (_parameter("ceiling", "Decimal", "100"),),
        ),
        _node(
            "verdict",
            "asa.stonk.shared",
            "verdict_classifier",
            (
                _parameter("pass_threshold", "Decimal", "62"),
                _parameter("watch_threshold", "Decimal", "45"),
            ),
        ),
    ),
    (EdgeSpec("score", "score", "verdict", "score"),),
    (
        OutputSpec("candidates", "universe", "selected"),
        OutputSpec("score", "score", "score"),
        OutputSpec("verdict", "verdict", "verdict"),
    ),
)


STONK_STRATEGY_MANIFESTS = (
    EARNINGS_CALENDAR_MANIFEST,
    SKEW_MOMENTUM_VERTICAL_MANIFEST,
    FORWARD_FACTOR_CALENDAR_MANIFEST,
    STOCK_MOMENTUM_MANIFEST,
)
