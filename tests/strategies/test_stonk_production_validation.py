"""STONK-007 integrated production-quality Strategy Library validation."""

from __future__ import annotations

from datetime import timedelta
from decimal import Decimal
from time import perf_counter

from domain import (
    ExpirationCollection,
    ExpirationCycle,
    OptionChain,
    OptionType,
    SecurityCollection,
)
from strategies import (
    CORE_COMPONENTS,
    EARNINGS_CALENDAR_MANIFEST,
    FORWARD_FACTOR_CALENDAR_MANIFEST,
    SKEW_MOMENTUM_VERTICAL_MANIFEST,
    STOCK_MOMENTUM_MANIFEST,
    STONK_STRATEGY_LIBRARY,
    STONK_STRATEGY_PLUGINS,
    StrategyManifest,
    compile_strategy_graph,
    execute_strategy_graph,
)
from strategies.component_registry import ComponentRegistry
from strategies.plugins import build_plugin_registry
from strategies.stonk_components import (
    D,
    DATE,
    DECIMAL_LIST,
    EARNINGS_EVENT,
    EXPIRATION_COLLECTION,
    EXPIRATION_CYCLE,
    OPTION_CHAIN,
    OPTION_CONTRACT,
    SECURITY_COLLECTION,
)
from strategies.type_system import ComponentValues, StrategyTypeReference
from tests.strategies.test_stonk_components import (
    AS_OF,
    BACK,
    EVIDENCE,
    FRONT,
    NOW,
    chain,
    contract,
    earnings_event,
    security,
)
from tests.strategies.test_stonk_manifests import context

INTEGER = StrategyTypeReference("Integer", "1.0.0")


def _registry() -> ComponentRegistry:
    return build_plugin_registry(CORE_COMPONENTS, STONK_STRATEGY_PLUGINS)


def _execution_context(manifest: StrategyManifest) -> ComponentValues:
    if manifest is EARNINGS_CALENDAR_MANIFEST:
        front = ExpirationCycle(FRONT, 16, True, False, AS_OF, EVIDENCE)
        back = ExpirationCycle(BACK, 51, True, False, AS_OF, EVIDENCE)
        return context(
            **{
                "event_window.event": (EARNINGS_EVENT, earnings_event()),
                "event_window.front": (EXPIRATION_CYCLE, front),
                "event_window.back": (EXPIRATION_CYCLE, back),
                "expiration_select.expirations": (
                    EXPIRATION_COLLECTION,
                    ExpirationCollection(AS_OF, (front, back)),
                ),
                "expiration_select.event": (EARNINGS_EVENT, earnings_event()),
                "calendar.chain": (OPTION_CHAIN, chain()),
                "calendar.target_strike": (D, Decimal("103")),
                "score.values": (DECIMAL_LIST, (Decimal("80"), Decimal("60"))),
                "score.weights": (DECIMAL_LIST, (Decimal("3"), Decimal("1"))),
            }
        )
    if manifest is SKEW_MOMENTUM_VERTICAL_MANIFEST:
        option_chain = chain()
        return context(
            **{
                "vertical.chain": (OPTION_CHAIN, option_chain),
                "vertical.expiration": (DATE, FRONT),
                "liquidity.contract": (
                    OPTION_CONTRACT,
                    option_chain.find(
                        expiration=FRONT,
                        strike=Decimal("100"),
                        option_type=OptionType.CALL,
                    )[0],
                ),
                "score.values": (DECIMAL_LIST, (Decimal("80"), Decimal("70"))),
                "score.weights": (DECIMAL_LIST, (Decimal("2"), Decimal("1"))),
            }
        )
    if manifest is FORWARD_FACTOR_CALENDAR_MANIFEST:
        front = AS_OF + timedelta(days=60)
        back = AS_OF + timedelta(days=90)
        option_chain = OptionChain(
            "production-forward-chain",
            security(),
            NOW,
            (
                contract("front-call", front, "105", OptionType.CALL, "0.35", "2"),
                contract("back-call", back, "105", OptionType.CALL, "0.38", "3"),
                contract("front-put", front, "95", OptionType.PUT, "-0.35", "2"),
                contract("back-put", back, "95", OptionType.PUT, "-0.38", "3"),
            ),
            EVIDENCE,
        )
        expirations = ExpirationCollection(
            AS_OF,
            (
                ExpirationCycle(front, 60, True, False, AS_OF, EVIDENCE),
                ExpirationCycle(back, 90, True, False, AS_OF, EVIDENCE),
            ),
        )
        return context(
            **{
                "expiration_select.expirations": (EXPIRATION_COLLECTION, expirations),
                "double_calendar.chain": (OPTION_CHAIN, option_chain),
                "forward_iv.front_iv": (D, Decimal("0.48")),
                "forward_iv.back_iv": (
                    D,
                    Decimal("0.4548992562461861547567860943472296"),
                ),
                "forward_iv.front_dte": (INTEGER, 60),
                "forward_iv.back_dte": (INTEGER, 90),
                "factor.front_ex_earnings_iv": (D, Decimal("0.48")),
            }
        )
    if manifest is STOCK_MOMENTUM_MANIFEST:
        return context(
            **{
                "universe.candidates": (
                    SECURITY_COLLECTION,
                    SecurityCollection((security("MSFT"), security())),
                ),
                "score.values": (
                    DECIMAL_LIST,
                    (Decimal("75"), Decimal("65"), Decimal("55")),
                ),
                "score.weights": (
                    DECIMAL_LIST,
                    (Decimal("3"), Decimal("2"), Decimal("1")),
                ),
            }
        )
    raise AssertionError(f"missing production vector for {manifest.strategy_id}")


def test_every_library_strategy_compiles_executes_replays_and_explains() -> None:
    registry = _registry()
    for manifest in STONK_STRATEGY_LIBRARY.manifests:
        graph = compile_strategy_graph(manifest, registry)
        execution_context = _execution_context(manifest)
        first = execute_strategy_graph(graph, execution_context)
        replay = execute_strategy_graph(graph, execution_context)
        assert first == replay
        assert first.trace.graph_id == graph.graph_id
        assert first.trace.evaluation_id
        node_events = tuple(event for event in first.trace.events if event.node_id is not None)
        assert {event.node_id for event in node_events} == set(graph.execution_order)
        assert tuple(event.sequence for event in first.trace.events) == tuple(
            range(len(first.trace.events))
        )
        completed = tuple(event for event in node_events if event.kind == "node_completed")
        assert len(completed) == len(graph.execution_order)
        assert all(event.output_identities for event in completed)


def test_complete_library_replay_has_bounded_runtime_without_cached_state() -> None:
    registry = _registry()
    compiled = tuple(
        (compile_strategy_graph(manifest, registry), _execution_context(manifest))
        for manifest in STONK_STRATEGY_LIBRARY.manifests
    )
    started = perf_counter()
    identities = tuple(
        execute_strategy_graph(graph, execution_context).trace.evaluation_id
        for _ in range(50)
        for graph, execution_context in compiled
    )
    elapsed = perf_counter() - started
    assert len(identities) == 200
    assert len(set(identities)) == 4
    assert elapsed < 5


def test_plugins_are_static_isolated_and_cover_every_manifest_reference() -> None:
    registry = _registry()
    plugin_components = {
        (component.definition.namespace, component.definition.name, component.definition.version)
        for plugin in STONK_STRATEGY_PLUGINS
        for component in plugin.components
    }
    for manifest in STONK_STRATEGY_LIBRARY.manifests:
        for node in manifest.nodes:
            resolved = registry.resolve(node.component)
            assert resolved.definition.component_id
            if node.component.namespace.startswith("asa.stonk"):
                assert (
                    node.component.namespace,
                    node.component.name,
                    node.component.version,
                ) in plugin_components
    assert all(
        not hasattr(component, "__dict__")
        for plugin in STONK_STRATEGY_PLUGINS
        for component in plugin.components
    )
