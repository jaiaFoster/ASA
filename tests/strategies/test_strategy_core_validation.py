"""STRAT-011 integrated Strategy Core validation suite."""

from __future__ import annotations

import ast
from decimal import Decimal
from pathlib import Path

from strategies.component_registry import ComponentRegistry
from strategies.core_components import CORE_COMPONENTS, D
from strategies.manifest import deserialize_manifest, serialize_manifest
from strategies.plugins import build_plugin_registry
from strategies.reference_strategy import MOVING_AVERAGE_CROSSOVER_MANIFEST
from strategies.runtime import compile_strategy_graph, execute_strategy_graph
from strategies.type_system import ComponentValues, TypedValue


def semantic_inputs() -> ComponentValues:
    return ComponentValues(
        (
            ("crossover.left", TypedValue(D, Decimal("101.25"))),
            ("crossover.right", TypedValue(D, Decimal("99.75"))),
        )
    )


def test_complete_strategy_core_replay_pipeline() -> None:
    wire = serialize_manifest(MOVING_AVERAGE_CROSSOVER_MANIFEST)
    manifest = deserialize_manifest(wire)
    registry = build_plugin_registry(CORE_COMPONENTS, ())
    graph = compile_strategy_graph(manifest, registry)
    original = execute_strategy_graph(graph, semantic_inputs())

    replay_manifest = deserialize_manifest(wire)
    replay_registry = ComponentRegistry(tuple(reversed(CORE_COMPONENTS)))
    replay_graph = compile_strategy_graph(replay_manifest, replay_registry)
    replay = execute_strategy_graph(replay_graph, semantic_inputs())

    assert replay_graph.graph_id == graph.graph_id
    assert replay == original
    assert replay.outputs.get("signal").value is True
    assert replay.trace.evaluation_id == original.trace.evaluation_id


def test_trace_has_complete_node_provenance() -> None:
    graph = compile_strategy_graph(
        MOVING_AVERAGE_CROSSOVER_MANIFEST, ComponentRegistry(CORE_COMPONENTS)
    )
    result = execute_strategy_graph(graph, semantic_inputs())
    completed = [event for event in result.trace.events if event.kind == "node_completed"]
    assert [event.node_id for event in completed] == list(graph.execution_order)
    assert all(event.input_identities and event.output_identities for event in completed)


def test_strategy_core_has_no_forbidden_boundary_imports() -> None:
    forbidden = {
        "backend",
        "brokers",
        "execution_planning",
        "infrastructure",
        "observation",
        "providers",
    }
    root = Path(__file__).parents[2] / "strategies"
    violations: list[str] = []
    for path in sorted(root.glob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                names = {alias.name.split(".")[0] for alias in node.names}
            elif isinstance(node, ast.ImportFrom) and node.module:
                names = {node.module.split(".")[0]}
            else:
                continue
            if names & forbidden:
                violations.append(f"{path.name}:{node.lineno}")
    assert violations == []


def test_public_runtime_has_no_mutation_or_dynamic_loading_surface() -> None:
    prohibited = {
        "add_node",
        "remove_node",
        "register_runtime",
        "discover_plugins",
        "load_plugin",
        "patch",
        "retry",
        "run_async",
        "start_worker",
    }
    import strategies.runtime as runtime

    assert not prohibited & set(vars(runtime))
