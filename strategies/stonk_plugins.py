"""Static SPRINT-003 Plugin registrations for extracted Stonk vocabulary."""

from strategies.plugins import PluginMetadata, StrategyPlugin
from strategies.stonk_components import OPTIONS_STONK_COMPONENTS, SHARED_STONK_COMPONENTS

STONK_SHARED_PLUGIN = StrategyPlugin(
    PluginMetadata(
        "asa.stonk.shared",
        "stonk_shared_components",
        "1.0.0",
        "Provider-neutral evidence, universe, scoring, and verdict primitives.",
    ),
    SHARED_STONK_COMPONENTS,
)

STONK_OPTIONS_PLUGIN = StrategyPlugin(
    PluginMetadata(
        "asa.stonk.options",
        "stonk_options_components",
        "1.2.0",
        "Provider-neutral earnings, expiration, option-leg, and structure primitives.",
    ),
    OPTIONS_STONK_COMPONENTS,
)

STONK_STRATEGY_PLUGINS = (STONK_SHARED_PLUGIN, STONK_OPTIONS_PLUGIN)
