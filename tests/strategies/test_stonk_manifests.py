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
from strategies.component_registry import ComponentRegistry
from strategies.plugins import build_plugin_registry
from strategies.stonk_components import (
    DATE,
    DECIMAL_LIST,
    EARNINGS_EVENT,
    EXPIRATION_COLLECTION,
    EXPIRATION_CYCLE,
    OPTION_CHAIN,
    OPTION_CONTRACT,
    SECURITY_COLLECTION,
    D,
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
        "earnings_calendar",
        "skew_momentum",
        "forward_factor",
        "asa.stonk.stock_momentum",
    )
    expected = {
        "earnings_calendar": "5052fe8c42072591a55925603d7941149d2516ec9181d7c76aea27a2269acfda",
        "skew_momentum": "ee5b2e50a1eecaa9c09f3789ecb203a117d3334689cede490cfc71cf8772a999",
        "forward_factor": "9828747d2ab5f2028e13e91834cebb370e56f11921f69021c75c8ea8144dea4b",
        "asa.stonk.stock_momentum": (
            "456a84aa09ca73c65c32490ebaa270beb5b85db273e9d0c10d987f434e13047d"
        ),
    }
    graph_ids = {
        "earnings_calendar": "d3858531b65e0f364172b3b1c77c6b3cf946dd94b138aea49bd7497d1ec7bdcc",
        "skew_momentum": "13eb87386c950861eb3fcf2306e93df3943e830b504119285b547fbc6fc01bc9",
        "forward_factor": "907c0afb87cdc2826e29fc5575ff66e9fd21bfcb82a6c3b7ab4bda95bd78676b",
        "asa.stonk.stock_momentum": (
            "1157f759f777089cd922d978be6e0d7c44e48f9548a812e1b16a3fd80de5f197"
        ),
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
            "forward_iv.front_iv": (D, Decimal("0.48")),
            "forward_iv.back_iv": (
                D,
                Decimal("0.4548992562461861547567860943472296"),
            ),
            "forward_iv.front_dte": (
                StrategyTypeReference("Integer", "1.0.0"),
                60,
            ),
            "forward_iv.back_dte": (
                StrategyTypeReference("Integer", "1.0.0"),
                90,
            ),
            "factor.front_iv": (D, Decimal("0.48")),
            "eligibility.left": (
                StrategyTypeReference("Boolean", "1.0.0"),
                True,
            ),
        }
    )
    graph = compile_strategy_graph(FORWARD_FACTOR_CALENDAR_MANIFEST, registry())
    result = execute_strategy_graph(graph, execution_context)
    assert result.outputs.get("forward_factor").value.quantize(Decimal("0.00000001")) == Decimal(
        "0.20000000"
    )
    assert result.outputs.get("verdict").value == "PASS"
    assert result.outputs.get("eligible").value is True
    assert result.outputs.get("liquidity_acceptable").value is True
    assert result.outputs.get("front_iv").value == Decimal("0.48")
    assert len(result.outputs.get("structures").value) == 2

    rejected_context = ComponentValues(
        tuple(
            (name, value) for name, value in execution_context.entries if name != "eligibility.left"
        )
        + (
            (
                "eligibility.left",
                TypedValue(StrategyTypeReference("Boolean", "1.0.0"), False),
            ),
        )
    )
    rejected = execute_strategy_graph(graph, rejected_context)
    assert rejected.outputs.get("eligible").value is False
    assert rejected.outputs.get("verdict").value == "FAIL"


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
