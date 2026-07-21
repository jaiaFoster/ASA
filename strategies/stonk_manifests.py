"""Manifest-only migrations of the four production Stonk strategies."""

from __future__ import annotations

from strategies.manifest import (
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


EARNINGS_CALENDAR_MANIFEST = StrategyManifest(
    "1.0.0",
    "asa.stonk.earnings_calendar",
    "1.0.0",
    ManifestMetadata(
        "Earnings Calendar Spread",
        "Confirmed earnings window with a nearest-common-strike calendar and explicit debit.",
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
            ),
        ),
        _node("pair", "asa.stonk.options", "expiration_pair_projection"),
        _node(
            "calendar",
            "asa.stonk.options",
            "nearest_common_strike_calendar",
            (_parameter("option_type", "Enum", "call"),),
        ),
        _node("debit", "asa.stonk.options", "option_structure_debit"),
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
                _parameter("pass_threshold", "Decimal", "70"),
                _parameter("watch_threshold", "Decimal", "55"),
            ),
        ),
    ),
    (
        EdgeSpec("expiration_select", "selected", "pair", "selected"),
        EdgeSpec("pair", "front_expiration", "calendar", "front_expiration"),
        EdgeSpec("pair", "back_expiration", "calendar", "back_expiration"),
        EdgeSpec("calendar", "structure", "debit", "structure"),
        EdgeSpec("score", "score", "verdict", "score"),
    ),
    (
        OutputSpec("eligible", "event_window", "eligible"),
        OutputSpec("selected_expirations", "expiration_select", "selected"),
        OutputSpec("structure", "calendar", "structure"),
        OutputSpec("mid_debit", "debit", "mid_debit"),
        OutputSpec("conservative_debit", "debit", "conservative_debit"),
        OutputSpec("score", "score", "score"),
        OutputSpec("verdict", "verdict", "verdict"),
    ),
)


SKEW_MOMENTUM_VERTICAL_MANIFEST = StrategyManifest(
    "1.0.0",
    "asa.stonk.skew_momentum_vertical",
    "1.0.0",
    ManifestMetadata(
        "Skew Momentum Vertical",
        "Delta-selected vertical with explicit liquidity inputs, debit, score, and verdict.",
        ("migrated", "momentum", "options", "skew"),
    ),
    (),
    (),
    (
        _node(
            "vertical",
            "asa.stonk.options",
            "vertical_structure",
            (
                _parameter("option_type", "Enum", "call"),
                _parameter("long_delta_target", "Decimal", "0.50"),
                _parameter("short_delta_target", "Decimal", "0.25"),
            ),
        ),
        _node("debit", "asa.stonk.options", "option_structure_debit"),
        _node(
            "liquidity",
            "asa.stonk.options",
            "option_leg_liquidity",
            (
                _parameter("maximum_spread_ratio", "Decimal", "0.15"),
                _parameter("minimum_open_interest", "Integer", 50),
                _parameter("minimum_volume", "Integer", 10),
            ),
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
                _parameter("pass_threshold", "Decimal", "70"),
                _parameter("watch_threshold", "Decimal", "55"),
            ),
        ),
    ),
    (
        EdgeSpec("vertical", "structure", "debit", "structure"),
        EdgeSpec("score", "score", "verdict", "score"),
    ),
    (
        OutputSpec("structure", "vertical", "structure"),
        OutputSpec("mid_debit", "debit", "mid_debit"),
        OutputSpec("conservative_debit", "debit", "conservative_debit"),
        OutputSpec("liquid", "liquidity", "liquid"),
        OutputSpec("score", "score", "score"),
        OutputSpec("verdict", "verdict", "verdict"),
    ),
)


FORWARD_FACTOR_CALENDAR_MANIFEST = StrategyManifest(
    "1.0.0",
    "asa.stonk.forward_factor_calendar",
    "1.0.0",
    ManifestMetadata(
        "Forward Factor Calendar",
        "Source-qualified forward factor with a delta-selected double calendar.",
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
        _node("factor", "asa.stonk.options", "forward_factor"),
        _node(
            "verdict",
            "asa.stonk.shared",
            "verdict_classifier",
            (
                _parameter("pass_threshold", "Decimal", "0.20"),
                _parameter("watch_threshold", "Decimal", "0.12"),
            ),
        ),
    ),
    (
        EdgeSpec("expiration_select", "selected", "pair", "selected"),
        EdgeSpec("pair", "front_expiration", "double_calendar", "front_expiration"),
        EdgeSpec("pair", "back_expiration", "double_calendar", "back_expiration"),
        EdgeSpec("factor", "factor", "verdict", "score"),
    ),
    (
        OutputSpec("selected_expirations", "expiration_select", "selected"),
        OutputSpec("structures", "double_calendar", "structures"),
        OutputSpec("forward_factor", "factor", "factor"),
        OutputSpec("verdict", "verdict", "verdict"),
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
