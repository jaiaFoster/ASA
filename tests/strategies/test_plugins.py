"""STRAT-008 static plugin SDK tests."""

from __future__ import annotations

import pytest

from strategies.components import (
    BaseComponent,
    ComponentCategory,
    ComponentDefinition,
    PortDefinition,
)
from strategies.errors import ComponentContractError
from strategies.manifest import ComponentReference
from strategies.plugins import PluginMetadata, StrategyPlugin, build_plugin_registry
from strategies.type_system import ComponentValues, StrategyTypeReference, TypedValue

TEXT = StrategyTypeReference("Text", "1.0.0")


class SamplePluginComponent(BaseComponent):
    __slots__ = ()
    definition = ComponentDefinition(
        "sample",
        "echo",
        "1.0.0",
        ComponentCategory.UTILITY,
        (PortDefinition("value", TEXT),),
        (PortDefinition("result", TEXT),),
    )

    def evaluate(self, inputs: ComponentValues, parameters: ComponentValues) -> ComponentValues:
        return ComponentValues((("result", TypedValue(TEXT, inputs.get("value").value)),))


def plugin() -> StrategyPlugin:
    return StrategyPlugin(
        PluginMetadata("sample", "sample_plugin", "1.0.0", "Static SDK example"),
        (SamplePluginComponent(),),
    )


def test_sample_plugin_registers_without_core_modification():
    registry = build_plugin_registry((), (plugin(),))
    assert isinstance(
        registry.resolve(ComponentReference("sample", "echo", "1.0.0")), SamplePluginComponent
    )


def test_plugin_identity_and_registry_are_order_independent():
    first = plugin()
    second = plugin()
    assert first.plugin_id == second.plugin_id
    assert (
        build_plugin_registry((), (first,)).identity
        == build_plugin_registry((), (second,)).identity
    )


def test_namespace_mismatch_fails_closed():
    with pytest.raises(ComponentContractError, match="namespace"):
        StrategyPlugin(PluginMetadata("other", "bad", "1.0.0", "Bad"), (SamplePluginComponent(),))


def test_no_runtime_loading_or_mutation_api_exists():
    forbidden = {"discover", "load", "reload", "register", "unregister", "patch_runtime"}
    assert not forbidden & set(dir(StrategyPlugin))
