"""Deterministic component-agnostic Strategy Graph Runtime (STRAT-005)."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal

from strategies.component_registry import ComponentRegistry
from strategies.components import BaseComponent, ParameterDefinition, PortCardinality
from strategies.errors import GraphExecutionError, GraphValidationError
from strategies.manifest import (
    EdgeSpec,
    ManifestValue,
    NodeSpec,
    StrategyManifest,
    canonical_strategy_json,
)
from strategies.type_system import ComponentValues, TypedValue

GRAPH_RUNTIME_VERSION = "1.0.0"
GRAPH_IDENTITY_NAMESPACE = "asa.strategy_graph"
GRAPH_IDENTITY_VERSION = "v1"
EVALUATION_IDENTITY_NAMESPACE = "asa.strategy_evaluation"
EVALUATION_IDENTITY_VERSION = "v1"


@dataclass(frozen=True, slots=True)
class CompiledNode:
    node_id: str
    component: BaseComponent
    parameters: ComponentValues


@dataclass(frozen=True, slots=True)
class CompiledStrategyGraph:
    manifest: StrategyManifest
    registry_identity: str
    nodes: tuple[CompiledNode, ...]
    edges: tuple[EdgeSpec, ...]
    execution_order: tuple[str, ...]
    graph_id: str


@dataclass(frozen=True, slots=True)
class TraceEvent:
    sequence: int
    kind: str
    graph_id: str
    evaluation_id: str
    node_id: str | None = None
    input_identities: tuple[tuple[str, str], ...] = ()
    output_identities: tuple[tuple[str, str], ...] = ()


@dataclass(frozen=True, slots=True)
class ExecutionTrace:
    graph_id: str
    evaluation_id: str
    events: tuple[TraceEvent, ...]


@dataclass(frozen=True, slots=True)
class GraphExecutionResult:
    outputs: ComponentValues
    trace: ExecutionTrace


def compile_strategy_graph(
    manifest: StrategyManifest, registry: ComponentRegistry
) -> CompiledStrategyGraph:
    node_specs = {node.node_id: node for node in manifest.nodes}
    resolved = {
        node.node_id: CompiledNode(
            node.node_id,
            registry.resolve(node.component),
            _parameters(node, registry.resolve(node.component)),
        )
        for node in manifest.nodes
    }
    _validate_capabilities(manifest, resolved)
    _validate_edges(manifest.edges, resolved)
    order = _topological_order(tuple(node_specs), manifest.edges)
    _validate_outputs_and_reachability(manifest, resolved)
    semantic = {
        "namespace": GRAPH_IDENTITY_NAMESPACE,
        "version": GRAPH_IDENTITY_VERSION,
        "runtime_version": GRAPH_RUNTIME_VERSION,
        "manifest_id": manifest.manifest_id,
        "registry_id": registry.identity,
        "components": [(name, resolved[name].component.definition.component_id) for name in order],
        "parameters": [(name, _values_data(resolved[name].parameters)) for name in order],
        "edges": [
            edge.__dict__ if hasattr(edge, "__dict__") else _edge_data(edge)
            for edge in manifest.edges
        ],
        "outputs": [(item.name, item.node_id, item.port) for item in manifest.outputs],
    }
    graph_id = hashlib.sha256(canonical_strategy_json(semantic)).hexdigest()
    return CompiledStrategyGraph(
        manifest,
        registry.identity,
        tuple(resolved[name] for name in order),
        manifest.edges,
        order,
        graph_id,
    )


def execute_strategy_graph(
    graph: CompiledStrategyGraph, context: ComponentValues = ComponentValues(())
) -> GraphExecutionResult:
    context_map = dict(context.entries)
    evaluation_id = hashlib.sha256(
        canonical_strategy_json(
            {
                "namespace": EVALUATION_IDENTITY_NAMESPACE,
                "version": EVALUATION_IDENTITY_VERSION,
                "graph_id": graph.graph_id,
                "context": _values_data(context),
            }
        )
    ).hexdigest()
    events: list[TraceEvent] = []
    values: dict[tuple[str, str], TypedValue] = {}
    nodes = {node.node_id: node for node in graph.nodes}
    incoming: dict[str, list[EdgeSpec]] = {name: [] for name in graph.execution_order}
    for edge in graph.edges:
        incoming[edge.target_node_id].append(edge)
    _event(events, "manifest_validated", graph.graph_id, evaluation_id)
    _event(events, "graph_compiled", graph.graph_id, evaluation_id)
    _event(events, "evaluation_started", graph.graph_id, evaluation_id)
    try:
        for node_id in graph.execution_order:
            node = nodes[node_id]
            bound: list[tuple[str, TypedValue]] = []
            for edge in sorted(incoming[node_id], key=lambda item: item.target_port):
                bound.append((edge.target_port, values[(edge.source_node_id, edge.source_port)]))
            connected = {name for name, _ in bound}
            for port in node.component.definition.input_ports:
                key = f"{node_id}.{port.name}"
                if port.name not in connected and key in context_map:
                    bound.append((port.name, context_map[key]))
                    connected.add(port.name)
                if port.name not in connected and port.cardinality is PortCardinality.SINGLE:
                    raise GraphExecutionError(f"missing required input: {key}")
            inputs = ComponentValues(tuple(bound))
            _event(events, "node_started", graph.graph_id, evaluation_id, node_id, inputs)
            outputs = node.component.evaluate(inputs, node.parameters)
            _validate_component_outputs(node.component, outputs)
            for name, value in outputs.entries:
                values[(node_id, name)] = value
            _event(
                events, "node_completed", graph.graph_id, evaluation_id, node_id, inputs, outputs
            )
    except Exception as exc:
        _event(events, "node_failed", graph.graph_id, evaluation_id, node_id)
        _event(events, "evaluation_failed", graph.graph_id, evaluation_id)
        if isinstance(exc, GraphExecutionError):
            raise
        raise GraphExecutionError(f"component evaluation failed at {node_id}") from exc
    selected = ComponentValues(
        tuple((item.name, values[(item.node_id, item.port)]) for item in graph.manifest.outputs)
    )
    _event(events, "evaluation_completed", graph.graph_id, evaluation_id, outputs=selected)
    return GraphExecutionResult(
        selected, ExecutionTrace(graph.graph_id, evaluation_id, tuple(events))
    )


def _parameters(node: NodeSpec, component: BaseComponent) -> ComponentValues:
    supplied = {item.name: item for item in node.parameters}
    definitions = {item.name: item for item in component.definition.parameters}
    if set(supplied) - set(definitions):
        raise GraphValidationError(f"unknown parameter on node {node.node_id}")
    values: list[tuple[str, TypedValue]] = []
    for name, definition in definitions.items():
        if name in supplied:
            raw = supplied[name].value
        elif definition.has_default:
            raw = definition.default
        elif definition.required:
            raise GraphValidationError(f"missing parameter {node.node_id}.{name}")
        else:
            continue
        values.append((name, TypedValue(definition.type_ref, _parameter_value(definition, raw))))
    return ComponentValues(tuple(values))


def _parameter_value(definition: ParameterDefinition, value: ManifestValue) -> object:
    name = definition.type_ref.name
    if name == "Decimal":
        return Decimal(str(value))
    if name == "Date":
        return date.fromisoformat(str(value))
    if name == "Instant":
        return datetime.fromisoformat(str(value))
    return value


def _validate_capabilities(manifest: StrategyManifest, nodes: dict[str, CompiledNode]) -> None:
    available = {item for node in nodes.values() for item in node.component.definition.capabilities}
    if not set(manifest.required_capabilities) <= available:
        raise GraphValidationError("required capability is not supplied by the graph")


def _validate_edges(edges: tuple[EdgeSpec, ...], nodes: dict[str, CompiledNode]) -> None:
    targets: set[tuple[str, str]] = set()
    for edge in edges:
        if edge.source_node_id == edge.target_node_id:
            raise GraphValidationError("self edges are forbidden")
        if edge.source_node_id not in nodes or edge.target_node_id not in nodes:
            raise GraphValidationError("edge references unknown node")
        source = {
            item.name: item for item in nodes[edge.source_node_id].component.definition.output_ports
        }
        target = {
            item.name: item for item in nodes[edge.target_node_id].component.definition.input_ports
        }
        if edge.source_port not in source or edge.target_port not in target:
            raise GraphValidationError("edge references unknown port")
        if source[edge.source_port].type_ref != target[edge.target_port].type_ref:
            raise GraphValidationError("edge types are incompatible")
        key = (edge.target_node_id, edge.target_port)
        if key in targets and target[edge.target_port].cardinality is not PortCardinality.MANY:
            raise GraphValidationError("input port has ambiguous bindings")
        targets.add(key)


def _topological_order(nodes: tuple[str, ...], edges: tuple[EdgeSpec, ...]) -> tuple[str, ...]:
    indegree = {node: 0 for node in nodes}
    outgoing: dict[str, list[str]] = {node: [] for node in nodes}
    for edge in edges:
        indegree[edge.target_node_id] += 1
        outgoing[edge.source_node_id].append(edge.target_node_id)
    ready = sorted(node for node, count in indegree.items() if count == 0)
    result: list[str] = []
    while ready:
        node = ready.pop(0)
        result.append(node)
        for target in sorted(outgoing[node]):
            indegree[target] -= 1
            if indegree[target] == 0:
                ready.append(target)
                ready.sort()
    if len(result) != len(nodes):
        raise GraphValidationError("strategy graph contains a cycle")
    return tuple(result)


def _validate_outputs_and_reachability(
    manifest: StrategyManifest, nodes: dict[str, CompiledNode]
) -> None:
    required: set[str] = set()
    reverse: dict[str, set[str]] = {name: set() for name in nodes}
    for edge in manifest.edges:
        reverse[edge.target_node_id].add(edge.source_node_id)
    stack: list[str] = []
    for output in manifest.outputs:
        if output.node_id not in nodes:
            raise GraphValidationError("output references unknown node")
        ports = {item.name for item in nodes[output.node_id].component.definition.output_ports}
        if output.port not in ports:
            raise GraphValidationError("output references unknown port")
        stack.append(output.node_id)
    while stack:
        node = stack.pop()
        if node not in required:
            required.add(node)
            stack.extend(reverse[node])
    if required != set(nodes):
        raise GraphValidationError("strategy graph contains dead nodes")


def _validate_component_outputs(component: BaseComponent, values: ComponentValues) -> None:
    expected = {item.name: item.type_ref for item in component.definition.output_ports}
    actual = {name: value.type_ref for name, value in values.entries}
    if actual != expected:
        raise GraphExecutionError("component returned outputs that violate its contract")


def _typed_identity(value: TypedValue) -> str:
    return hashlib.sha256(canonical_strategy_json(_typed_data(value))).hexdigest()


def _typed_data(value: TypedValue) -> dict[str, object]:
    raw = value.value
    if isinstance(raw, Decimal):
        encoded: object = format(raw, "f")
    elif isinstance(raw, (date, datetime)):
        encoded = raw.isoformat()
    elif hasattr(raw, "identity"):
        encoded = {"identity": str(raw.identity)}
    elif isinstance(raw, tuple):
        encoded = [_typed_data(TypedValue(value.type_ref.arguments[0], item)) for item in raw]
    else:
        encoded = raw
    return {"type": value.type_ref.name, "version": value.type_ref.version, "value": encoded}


def _values_data(values: ComponentValues) -> list[tuple[str, object]]:
    return [(name, _typed_data(value)) for name, value in values.entries]


def _edge_data(edge: EdgeSpec) -> dict[str, str]:
    return {
        "source_node_id": edge.source_node_id,
        "source_port": edge.source_port,
        "target_node_id": edge.target_node_id,
        "target_port": edge.target_port,
    }


def _event(
    events: list[TraceEvent],
    kind: str,
    graph_id: str,
    evaluation_id: str,
    node_id: str | None = None,
    inputs: ComponentValues = ComponentValues(()),
    outputs: ComponentValues = ComponentValues(()),
) -> None:
    events.append(
        TraceEvent(
            len(events),
            kind,
            graph_id,
            evaluation_id,
            node_id,
            tuple((name, _typed_identity(value)) for name, value in inputs.entries),
            tuple((name, _typed_identity(value)) for name, value in outputs.entries),
        )
    )
