"""Immutable explicit Component Registry (STRAT-004, ASA-ARCH-003)."""
from __future__ import annotations

import hashlib

from strategies.components import BaseComponent, ComponentDefinition
from strategies.errors import ComponentContractError
from strategies.manifest import ComponentReference, canonical_strategy_json
from strategies.type_system import DEFAULT_TYPE_SYSTEM, StrategyTypeSystem

REGISTRY_IDENTITY_NAMESPACE = "asa.strategy_component_registry"
REGISTRY_IDENTITY_VERSION = "v1"

SUPPORTED_COMPONENT_CAPABILITIES = frozenset(
    {
        "aggregate",
        "boolean_logic",
        "compare",
        "constant",
        "consume_facts",
        "consume_indicators",
        "constrain_portfolio",
        "emit_opportunity",
        "filter",
        "passthrough",
        "rank",
        "score",
        "transform",
    }
)


class ComponentRegistry:
    """Exact immutable catalog built from an explicit finite component tuple."""

    __slots__ = ("_components", "_identity", "_type_system")
    _components: tuple[BaseComponent, ...]
    _identity: str
    _type_system: StrategyTypeSystem

    def __init__(
        self,
        components: tuple[BaseComponent, ...],
        type_system: StrategyTypeSystem = DEFAULT_TYPE_SYSTEM,
    ) -> None:
        if not isinstance(type_system, StrategyTypeSystem):
            raise ComponentContractError("registry requires a StrategyTypeSystem")
        for component in components:
            if not isinstance(component, BaseComponent):
                raise ComponentContractError("registry entries must implement BaseComponent")
            _validate_definition(component.definition, type_system)
        ordered = tuple(
            sorted(
                components,
                key=lambda item: (
                    item.definition.namespace,
                    item.definition.name,
                    item.definition.version,
                ),
            )
        )
        keys = tuple(_definition_key(item.definition) for item in ordered)
        if len(keys) != len(set(keys)):
            raise ComponentContractError("duplicate Component Type registration")
        object.__setattr__(self, "_components", ordered)
        object.__setattr__(self, "_type_system", type_system)
        payload = {
            "identity_namespace": REGISTRY_IDENTITY_NAMESPACE,
            "identity_version": REGISTRY_IDENTITY_VERSION,
            "type_system_identity": type_system.identity,
            "component_ids": [item.definition.component_id for item in ordered],
        }
        object.__setattr__(
            self,
            "_identity",
            hashlib.sha256(canonical_strategy_json(payload)).hexdigest(),
        )

    def __setattr__(self, name: str, value: object) -> None:
        if hasattr(self, name):
            raise AttributeError("ComponentRegistry is immutable")
        object.__setattr__(self, name, value)

    @property
    def components(self) -> tuple[BaseComponent, ...]:
        return self._components

    @property
    def identity(self) -> str:
        return self._identity

    @property
    def type_system(self) -> StrategyTypeSystem:
        return self._type_system

    def resolve(self, reference: ComponentReference) -> BaseComponent:
        key = (reference.namespace, reference.name, reference.version)
        for component in self._components:
            if _definition_key(component.definition) == key:
                return component
        raise ComponentContractError(
            f"unknown Component Type: {reference.namespace}.{reference.name}@{reference.version}"
        )

    def registered_references(self) -> tuple[ComponentReference, ...]:
        return tuple(
            ComponentReference(
                item.definition.namespace,
                item.definition.name,
                item.definition.version,
            )
            for item in self._components
        )


def _definition_key(definition: ComponentDefinition) -> tuple[str, str, str]:
    return definition.namespace, definition.name, definition.version


def _validate_definition(
    definition: ComponentDefinition, type_system: StrategyTypeSystem
) -> None:
    for port in (*definition.input_ports, *definition.output_ports):
        type_system.resolve(port.type_ref)
    for parameter in definition.parameters:
        type_system.resolve(parameter.type_ref)
    for capability in definition.capabilities:
        if capability.name not in SUPPORTED_COMPONENT_CAPABILITIES:
            raise ComponentContractError(
                f"unsupported Component capability: {capability.name}"
            )
