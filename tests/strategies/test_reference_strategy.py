"""STRAT-010 manifest-only reference strategy acceptance tests."""

from __future__ import annotations

from decimal import Decimal

from strategies.component_registry import ComponentRegistry
from strategies.core_components import CORE_COMPONENTS, D
from strategies.reference_strategy import MOVING_AVERAGE_CROSSOVER_MANIFEST
from strategies.runtime import compile_strategy_graph, execute_strategy_graph
from strategies.type_system import ComponentValues, TypedValue


def context(short: str, long: str) -> ComponentValues:
    return ComponentValues(
        (
            ("crossover.left", TypedValue(D, Decimal(short))),
            ("crossover.right", TypedValue(D, Decimal(long))),
        )
    )


def test_reference_strategy_executes_from_manifest_and_registry():
    graph = compile_strategy_graph(
        MOVING_AVERAGE_CROSSOVER_MANIFEST, ComponentRegistry(CORE_COMPONENTS)
    )
    assert execute_strategy_graph(graph, context("105", "100")).outputs.get("signal").value is True
    assert execute_strategy_graph(graph, context("95", "100")).outputs.get("signal").value is False


def test_reference_strategy_replay_is_identical_and_explainable():
    graph = compile_strategy_graph(
        MOVING_AVERAGE_CROSSOVER_MANIFEST, ComponentRegistry(CORE_COMPONENTS)
    )
    first = execute_strategy_graph(graph, context("105", "100"))
    second = execute_strategy_graph(graph, context("105", "100"))
    assert first == second
    assert first.trace.events
    assert all(event.graph_id == graph.graph_id for event in first.trace.events)


def test_strategy_module_contains_no_component_instantiation_or_logic():
    import strategies.reference_strategy as module

    names = set(vars(module))
    assert not names & {
        "Compare",
        "ExpressionPredicate",
        "PortfolioConstraint",
        "execute_strategy_graph",
    }
