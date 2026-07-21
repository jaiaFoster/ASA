"""Static immutable Strategy Component Plugin SDK (STRAT-008)."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass

from strategies.component_registry import ComponentRegistry
from strategies.components import BaseComponent
from strategies.errors import ComponentContractError
from strategies.manifest import (
    canonical_strategy_json,
    validate_semantic_version,
    validate_strategy_identifier,
)
from strategies.type_system import DEFAULT_TYPE_SYSTEM, StrategyTypeSystem

PLUGIN_SDK_VERSION = "1.0.0"
PLUGIN_IDENTITY_NAMESPACE = "asa.strategy_plugin"
PLUGIN_IDENTITY_VERSION = "v1"


@dataclass(frozen=True, slots=True)
class PluginMetadata:
    namespace: str
    name: str
    version: str
    description: str

    def __post_init__(self) -> None:
        validate_strategy_identifier(self.namespace, "plugin.namespace")
        validate_strategy_identifier(self.name, "plugin.name")
        validate_semantic_version(self.version, "plugin.version")
        if not self.description.strip():
            raise ComponentContractError("plugin.description must not be empty")


@dataclass(frozen=True, slots=True)
class StrategyPlugin:
    metadata: PluginMetadata
    components: tuple[BaseComponent, ...]

    def __post_init__(self) -> None:
        if not self.components:
            raise ComponentContractError("plugin must contribute at least one component")
        for component in self.components:
            if not isinstance(component, BaseComponent):
                raise ComponentContractError("plugin components must implement BaseComponent")
            if component.definition.namespace != self.metadata.namespace:
                raise ComponentContractError(
                    "plugin component namespace must match plugin namespace"
                )
        keys = tuple(
            (item.definition.namespace, item.definition.name, item.definition.version)
            for item in self.components
        )
        if len(keys) != len(set(keys)):
            raise ComponentContractError("plugin contains duplicate components")
        object.__setattr__(
            self,
            "components",
            tuple(
                sorted(
                    self.components,
                    key=lambda item: (item.definition.name, item.definition.version),
                )
            ),
        )

    @property
    def plugin_id(self) -> str:
        return hashlib.sha256(
            canonical_strategy_json(
                {
                    "namespace": PLUGIN_IDENTITY_NAMESPACE,
                    "identity_version": PLUGIN_IDENTITY_VERSION,
                    "sdk_version": PLUGIN_SDK_VERSION,
                    "metadata": {
                        "namespace": self.metadata.namespace,
                        "name": self.metadata.name,
                        "version": self.metadata.version,
                        "description": self.metadata.description,
                    },
                    "component_ids": [item.definition.component_id for item in self.components],
                }
            )
        ).hexdigest()


def build_plugin_registry(
    core_components: tuple[BaseComponent, ...],
    plugins: tuple[StrategyPlugin, ...],
    type_system: StrategyTypeSystem = DEFAULT_TYPE_SYSTEM,
) -> ComponentRegistry:
    """Build one registry from an explicit, process-startup plugin tuple."""
    ordered = tuple(sorted(plugins, key=lambda item: item.plugin_id))
    if len({item.plugin_id for item in ordered}) != len(ordered):
        raise ComponentContractError("duplicate plugin registration")
    return ComponentRegistry(
        core_components + tuple(component for plugin in ordered for component in plugin.components),
        type_system,
    )
