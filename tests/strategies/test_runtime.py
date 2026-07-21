"""STRAT-005 deterministic graph compilation and execution tests."""

from __future__ import annotations

from dataclasses import FrozenInstanceError

import pytest

from strategies.component_registry import ComponentRegistry
from strategies.components import (
    BaseComponent,
    ComponentCategory,
    ComponentDefinition,
    PortDefinition,
)
from strategies.errors import GraphValidationError
from strategies.manifest import (
    ComponentReference,
    EdgeSpec,
    ManifestMetadata,
    NodeSpec,
    OutputSpec,
    StrategyManifest,
)
from strategies.runtime import compile_strategy_graph, execute_strategy_graph
from strategies.type_system import ComponentValues, StrategyTypeReference, TypedValue

INTEGER = StrategyTypeReference("Integer", "1.0.0")


class Source(BaseComponent):
    __slots__ = ()
    definition = ComponentDefinition(
        "test", "source", "1.0.0", ComponentCategory.SOURCE, (), (PortDefinition("value", INTEGER),)
    )

    def evaluate(self, inputs: ComponentValues, parameters: ComponentValues) -> ComponentValues:
        return ComponentValues((("value", TypedValue(INTEGER, 3)),))


class Double(BaseComponent):
    __slots__ = ()
    definition = ComponentDefinition(
        "test",
        "double",
        "1.0.0",
        ComponentCategory.TRANSFORM,
        (PortDefinition("value", INTEGER),),
        (PortDefinition("result", INTEGER),),
    )

    def evaluate(self, inputs: ComponentValues, parameters: ComponentValues) -> ComponentValues:
        return ComponentValues((("result", TypedValue(INTEGER, inputs.get("value").value * 2)),))


def manifest(edges: tuple[EdgeSpec, ...] | None = None) -> StrategyManifest:
    return StrategyManifest(
        "1.0.0",
        "test.graph",
        "1.0.0",
        ManifestMetadata("Test"),
        (),
        (),
        (
            NodeSpec("a", ComponentReference("test", "source", "1.0.0")),
            NodeSpec("b", ComponentReference("test", "double", "1.0.0")),
        ),
        edges if edges is not None else (EdgeSpec("a", "value", "b", "value"),),
        (OutputSpec("answer", "b", "result"),),
    )


def test_compile_and_execute_replay_identically():
    registry = ComponentRegistry((Double(), Source()))
    graph = compile_strategy_graph(manifest(), registry)
    assert graph.execution_order == ("a", "b")
    first = execute_strategy_graph(graph)
    second = execute_strategy_graph(graph)
    assert first == second
    assert first.outputs.get("answer").value == 6
    assert tuple(event.kind for event in first.trace.events) == (
        "manifest_validated",
        "graph_compiled",
        "evaluation_started",
        "node_started",
        "node_completed",
        "node_started",
        "node_completed",
        "evaluation_completed",
    )


def test_graph_and_trace_are_immutable():
    graph = compile_strategy_graph(manifest(), ComponentRegistry((Source(), Double())))
    result = execute_strategy_graph(graph)
    with pytest.raises(FrozenInstanceError):
        result.trace.events = ()  # type: ignore[misc]


def test_cycle_is_rejected_before_execution():
    cyclic = manifest(
        (
            EdgeSpec("a", "value", "b", "value"),
            EdgeSpec("b", "result", "a", "missing"),
        )
    )
    with pytest.raises(GraphValidationError):
        compile_strategy_graph(cyclic, ComponentRegistry((Source(), Double())))


def test_dead_node_is_rejected():
    with pytest.raises(GraphValidationError, match="dead"):
        compile_strategy_graph(manifest(()), ComponentRegistry((Source(), Double())))


def test_manifest_enumeration_does_not_change_graph_identity():
    registry = ComponentRegistry((Source(), Double()))
    first = compile_strategy_graph(manifest(), registry)
    original = manifest()
    reversed_manifest = StrategyManifest(
        original.schema_version,
        original.strategy_id,
        original.strategy_version,
        original.metadata,
        original.parameters,
        original.required_capabilities,
        tuple(reversed(original.nodes)),
        original.edges,
        original.outputs,
    )
    assert compile_strategy_graph(reversed_manifest, registry).graph_id == first.graph_id
