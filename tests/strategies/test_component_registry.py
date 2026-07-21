"""STRAT-004: immutable explicit Component Registry tests."""

from __future__ import annotations

import pytest

from strategies import (
    REGISTRY_IDENTITY_NAMESPACE,
    REGISTRY_IDENTITY_VERSION,
    BaseComponent,
    CapabilityRequirement,
    ComponentCategory,
    ComponentContractError,
    ComponentDefinition,
    ComponentReference,
    ComponentRegistry,
    ComponentValues,
    PortDefinition,
    StrategyTypeReference,
)

TEXT = StrategyTypeReference("Text", "1.0.0")


class PassThrough(BaseComponent):
    __slots__ = ()
    definition = ComponentDefinition(
        "asa.core",
        "PassThrough",
        "1.0.0",
        ComponentCategory.UTILITY,
        (PortDefinition("value", TEXT),),
        (PortDefinition("value", TEXT),),
        capabilities=(CapabilityRequirement("passthrough", "1.0.0"),),
    )

    def evaluate(self, inputs: ComponentValues, parameters: ComponentValues) -> ComponentValues:
        return inputs


class Filter(BaseComponent):
    __slots__ = ()
    definition = ComponentDefinition(
        "asa.core",
        "Filter",
        "1.0.0",
        ComponentCategory.TRANSFORM,
        (PortDefinition("value", TEXT),),
        (PortDefinition("value", TEXT),),
        capabilities=(CapabilityRequirement("filter", "1.0.0"),),
    )

    def evaluate(self, inputs: ComponentValues, parameters: ComponentValues) -> ComponentValues:
        return inputs


class TestRegistry:
    def test_explicit_components_are_sorted_and_resolved_exactly(self):
        passthrough = PassThrough()
        filter_component = Filter()
        registry = ComponentRegistry((passthrough, filter_component))
        assert tuple(item.name for item in registry.registered_references()) == (
            "Filter",
            "PassThrough",
        )
        assert (
            registry.resolve(ComponentReference("asa.core", "PassThrough", "1.0.0")) is passthrough
        )

    def test_input_order_does_not_change_identity(self):
        first = ComponentRegistry((PassThrough(), Filter()))
        second = ComponentRegistry((Filter(), PassThrough()))
        assert first.identity == second.identity
        assert first.registered_references() == second.registered_references()

    def test_identity_contract_is_pinned(self):
        registry = ComponentRegistry((PassThrough(), Filter()))
        assert REGISTRY_IDENTITY_NAMESPACE == "asa.strategy_component_registry"
        assert REGISTRY_IDENTITY_VERSION == "v1"
        assert registry.identity == (
            "a00ed33d8bae40ced3ef48d9aa77d450b28e09fa9d1d8f90a4b95a5f93b7dede"
        )

    def test_duplicate_exact_registration_is_rejected(self):
        with pytest.raises(ComponentContractError, match="duplicate"):
            ComponentRegistry((PassThrough(), PassThrough()))

    def test_unknown_and_inexact_version_fail_closed(self):
        registry = ComponentRegistry((PassThrough(),))
        with pytest.raises(ComponentContractError, match="unknown"):
            registry.resolve(ComponentReference("asa.core", "PassThrough", "2.0.0"))

    def test_registry_is_immutable(self):
        registry = ComponentRegistry((PassThrough(),))
        with pytest.raises(AttributeError, match="immutable"):
            registry._components = ()  # type: ignore[misc]

    def test_invalid_type_dependency_is_rejected(self):
        class UnknownTypeComponent(BaseComponent):
            __slots__ = ()
            definition = ComponentDefinition(
                "test",
                "UnknownType",
                "1.0.0",
                ComponentCategory.UTILITY,
                (),
                (PortDefinition("value", StrategyTypeReference("Missing", "1.0.0")),),
            )

            def evaluate(
                self, inputs: ComponentValues, parameters: ComponentValues
            ) -> ComponentValues:
                return inputs

        with pytest.raises(ComponentContractError, match="unknown Strategy Type"):
            ComponentRegistry((UnknownTypeComponent(),))

    def test_unknown_capability_is_rejected(self):
        class UnknownCapabilityComponent(BaseComponent):
            __slots__ = ()
            definition = ComponentDefinition(
                "test",
                "UnknownCapability",
                "1.0.0",
                ComponentCategory.UTILITY,
                (),
                (PortDefinition("value", TEXT),),
                capabilities=(CapabilityRequirement("network", "1.0.0"),),
            )

            def evaluate(
                self, inputs: ComponentValues, parameters: ComponentValues
            ) -> ComponentValues:
                return inputs

        with pytest.raises(ComponentContractError, match="unsupported Component capability"):
            ComponentRegistry((UnknownCapabilityComponent(),))

    def test_no_discovery_or_runtime_mutation_api_exists(self):
        prohibited = {"discover", "scan", "load", "register", "unregister", "patch"}
        assert not prohibited & set(dir(ComponentRegistry))
