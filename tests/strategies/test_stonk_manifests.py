"""STONK-003 manifest-only migration acceptance and replay vectors."""

from __future__ import annotations

from datetime import timedelta
from decimal import Decimal
from pathlib import Path

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
    STONK_STRATEGY_MANIFESTS,
    STONK_STRATEGY_PLUGINS,
    compile_strategy_graph,
    deserialize_manifest,
    execute_strategy_graph,
    serialize_manifest,
)
from strategies.plugins import build_plugin_registry
from strategies.component_registry import ComponentRegistry
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
from strategies.type_system import ComponentValues, StrategyTypeReference, TypedValue
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


def context(**items: tuple[StrategyTypeReference, object]) -> ComponentValues:
    return ComponentValues(
        tuple((name, TypedValue(type_ref, value)) for name, (type_ref, value) in items.items())
    )


def registry() -> ComponentRegistry:
    return build_plugin_registry(CORE_COMPONENTS, STONK_STRATEGY_PLUGINS)


def test_four_manifest_catalog_is_canonical_serializable_and_identity_pinned() -> None:
    assert tuple(item.strategy_id for item in STONK_STRATEGY_MANIFESTS) == (
        "asa.stonk.earnings_calendar",
        "asa.stonk.skew_momentum_vertical",
        "asa.stonk.forward_factor_calendar",
        "asa.stonk.stock_momentum",
    )
    expected = {
        "asa.stonk.earnings_calendar": "f349ab40630bc0b319b2f255cfe4a7bdb16a1b220f0845c30ebb9d4541918475",
        "asa.stonk.skew_momentum_vertical": "f5ea7d5d16771104bb324b109e75c16672bdbfabdece766be67f8fb4b71caf8c",
        "asa.stonk.forward_factor_calendar": "91090dc54d2007290985b4b580ddf8071e5a354bb6db86aa2f28768c83a9b47a",
        "asa.stonk.stock_momentum": "456a84aa09ca73c65c32490ebaa270beb5b85db273e9d0c10d987f434e13047d",
    }
    graph_ids = {
        "asa.stonk.earnings_calendar": "4b0d862c92302564a9a379d0e05794e8a58d7f2dbb72bcc8e7c4b423a8fe7c56",
        "asa.stonk.skew_momentum_vertical": "7d85e92b281403d5c2aee57732e9bed648b307c77a48b3355d649cdf1ef70c85",
        "asa.stonk.forward_factor_calendar": "a7bb1171e14e677d04b6d84bf768aa5152d41687c1d9c821f518afd2fc3c8e16",
        "asa.stonk.stock_momentum": "9f76991ed4a0bacba87794391f0a3e7e7cc582865d8c5916203d5be4392686e8",
    }
    component_registry = registry()
    for manifest in STONK_STRATEGY_MANIFESTS:
        assert manifest.manifest_id == expected[manifest.strategy_id]
        assert (
            compile_strategy_graph(manifest, component_registry).graph_id
            == graph_ids[manifest.strategy_id]
        )
        assert deserialize_manifest(serialize_manifest(manifest)) == manifest


def test_earnings_calendar_manifest_executes_and_replays() -> None:
    front = ExpirationCycle(FRONT, 16, True, False, AS_OF, EVIDENCE)
    back = ExpirationCycle(BACK, 51, True, False, AS_OF, EVIDENCE)
    execution_context = context(
        **{
            "event_window.event": (EARNINGS_EVENT, earnings_event()),
            "event_window.front": (EXPIRATION_CYCLE, front),
            "event_window.back": (EXPIRATION_CYCLE, back),
            "expiration_select.expirations": (
                EXPIRATION_COLLECTION,
                ExpirationCollection(AS_OF, (back, front)),
            ),
            "expiration_select.event": (EARNINGS_EVENT, earnings_event()),
            "calendar.chain": (OPTION_CHAIN, chain()),
            "calendar.target_strike": (D, Decimal("103")),
            "score.values": (DECIMAL_LIST, (Decimal("80"), Decimal("60"))),
            "score.weights": (DECIMAL_LIST, (Decimal("3"), Decimal("1"))),
        }
    )
    graph = compile_strategy_graph(EARNINGS_CALENDAR_MANIFEST, registry())
    first = execute_strategy_graph(graph, execution_context)
    second = execute_strategy_graph(graph, execution_context)
    assert first == second
    assert first.outputs.get("eligible").value is True
    assert first.outputs.get("score").value == Decimal("75")
    assert first.outputs.get("verdict").value == "PASS"
    assert first.outputs.get("structure").value.identity


def test_skew_vertical_manifest_executes_without_portfolio_or_provider_context() -> None:
    option_chain = chain()
    execution_context = context(
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
    graph = compile_strategy_graph(SKEW_MOMENTUM_VERTICAL_MANIFEST, registry())
    result = execute_strategy_graph(graph, execution_context)
    assert result.outputs.get("structure").value.identity
    assert result.outputs.get("liquid").value is True
    assert result.outputs.get("verdict").value == "PASS"


def _forward_chain() -> tuple[OptionChain, ExpirationCollection]:
    front = AS_OF + timedelta(days=60)
    back = AS_OF + timedelta(days=90)
    contracts = (
        contract("ff-front-call", front, "105", OptionType.CALL, "0.35", "2"),
        contract("ff-back-call", back, "105", OptionType.CALL, "0.38", "3"),
        contract("ff-front-put", front, "95", OptionType.PUT, "-0.35", "2"),
        contract("ff-back-put", back, "95", OptionType.PUT, "-0.38", "3"),
    )
    return (
        OptionChain("forward-chain", security(), NOW, contracts, EVIDENCE),
        ExpirationCollection(
            AS_OF,
            (
                ExpirationCycle(front, 60, True, False, AS_OF, EVIDENCE),
                ExpirationCycle(back, 90, True, False, AS_OF, EVIDENCE),
            ),
        ),
    )


def test_forward_factor_manifest_requires_source_iv_and_builds_double_calendar() -> None:
    option_chain, expirations = _forward_chain()
    execution_context = context(
        **{
            "expiration_select.expirations": (EXPIRATION_COLLECTION, expirations),
            "double_calendar.chain": (OPTION_CHAIN, option_chain),
            "factor.front_ex_earnings_iv": (D, Decimal("0.30")),
            "factor.implied_forward_iv": (D, Decimal("0.25")),
        }
    )
    graph = compile_strategy_graph(FORWARD_FACTOR_CALENDAR_MANIFEST, registry())
    result = execute_strategy_graph(graph, execution_context)
    assert result.outputs.get("forward_factor").value == Decimal("0.2")
    assert result.outputs.get("verdict").value == "PASS"
    assert len(result.outputs.get("structures").value) == 2


def test_stock_momentum_manifest_stops_before_portfolio_policy() -> None:
    candidates = SecurityCollection((security("MSFT"), security()))
    execution_context = context(
        **{
            "universe.candidates": (SECURITY_COLLECTION, candidates),
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
    graph = compile_strategy_graph(STOCK_MOMENTUM_MANIFEST, registry())
    result = execute_strategy_graph(graph, execution_context)
    assert result.outputs.get("candidates").value == candidates
    assert result.outputs.get("score").value == Decimal("68.33333333333333333333333333")
    assert result.outputs.get("verdict").value == "PASS"


def test_manifest_module_contains_no_execution_or_strategy_functions() -> None:
    text = (Path(__file__).parents[2] / "strategies" / "stonk_manifests.py").read_text(
        encoding="utf-8"
    )
    assert "def evaluate" not in text
    assert "execute_strategy_graph" not in text
    assert "providers" not in text
    assert "PortfolioSnapshot" not in text
    assert "date.today" not in text
