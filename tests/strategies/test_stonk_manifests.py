"""STONK-003 manifest-only migration acceptance and replay vectors."""

from __future__ import annotations

from dataclasses import replace
from datetime import timedelta
from decimal import Decimal
from pathlib import Path
from typing import cast

from domain import (
    ExpirationCollection,
    ExpirationCycle,
    OptionChain,
    OptionType,
    SecurityCollection,
)
from screening import fixtures as screening_fixtures
from screening.context_builders import build_skew_momentum_context
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
        "earnings_calendar": "27a570ccc830247d23c18069de9a20000ffccd8942874c79fe8ff22c841853ca",
        "skew_momentum": "3b71ead5141b4e3d6ebcd8c7e593ddad29f0b97357f54d94eef9c47a2c9b1496",
        "forward_factor": "9828747d2ab5f2028e13e91834cebb370e56f11921f69021c75c8ea8144dea4b",
        "asa.stonk.stock_momentum": (
            "456a84aa09ca73c65c32490ebaa270beb5b85db273e9d0c10d987f434e13047d"
        ),
    }
    graph_ids = {
        "earnings_calendar": "5539646873b7e314c293385d7a1265f7df2ecade810c98ec172673147a579df1",
        "skew_momentum": "6a0230283709a61d9d2606600e76e4858e8e9018de64b0917f9478235f6665e3",
        "forward_factor": "2dabd6b687f9d3f5c234fdcdca9aa18dd97c62142beaac6c7d4223faf5bd1d78",
        "asa.stonk.stock_momentum": (
            "b271f594470d17175fd0126baa137faa71b44680ff7eb46274ea18553518a16c"
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
            "score.primary": (D, Decimal("80")),
            "score.secondary": (D, Decimal("60")),
        }
    )
    graph = compile_strategy_graph(EARNINGS_CALENDAR_MANIFEST, registry())
    first = execute_strategy_graph(graph, execution_context)
    second = execute_strategy_graph(graph, execution_context)
    assert first == second
    assert first.outputs.get("eligible").value is True
    assert first.outputs.get("actual_gap_days").value == 35
    assert first.outputs.get("gap_deviation_days").value == 5
    assert first.outputs.get("gap_eligible").value is True
    assert first.outputs.get("liquidity_acceptable").value is True
    assert first.outputs.get("option_volume_band").value == "HIGH"
    assert first.outputs.get("score").value == Decimal("75")
    assert first.outputs.get("verdict").value == "PASS"
    assert first.outputs.get("structure").value.identity

    weak_volume_chain = replace(
        chain(),
        contracts=tuple(replace(item, volume=5) for item in chain().contracts),
    )
    weak_context = context(
        **{
            name: (
                typed.type_ref,
                weak_volume_chain if name == "calendar.chain" else typed.value,
            )
            for name, typed in execution_context.entries
        }
    )
    weak = execute_strategy_graph(graph, weak_context)
    assert weak.outputs.get("option_volume_band").value == "LOW"
    assert weak.outputs.get("verdict").value == "WATCH"

    illiquid_chain = replace(
        chain(),
        contracts=tuple(replace(item, open_interest=0) for item in chain().contracts),
    )
    illiquid_context = context(
        **{
            name: (
                typed.type_ref,
                illiquid_chain if name == "calendar.chain" else typed.value,
            )
            for name, typed in execution_context.entries
        }
    )
    illiquid = execute_strategy_graph(graph, illiquid_context)
    assert illiquid.outputs.get("liquidity_acceptable").value is False
    assert illiquid.outputs.get("verdict").value == "FAIL"


def test_skew_vertical_manifest_executes_without_portfolio_or_provider_context() -> None:
    base_chain = chain()
    option_chain = replace(
        base_chain,
        contracts=tuple(
            replace(
                item,
                bid=cast(Decimal, item.mark) - Decimal("0.05"),
                ask=cast(Decimal, item.mark) + Decimal("0.05"),
            )
            for item in base_chain.contracts
        ),
    )
    execution_context = context(
        **{
            "decision.chain": (OPTION_CHAIN, option_chain),
            "decision.expiration": (DATE, FRONT),
            "decision.normalized_call_skew": (D, Decimal("0.5")),
            "decision.normalized_put_skew": (D, Decimal("0.2")),
            "decision.call_skew_zscore": (
                StrategyTypeReference("Optional", "1.0.0", (D,)),
                Decimal("-2.1"),
            ),
            "decision.put_skew_zscore": (
                StrategyTypeReference("Optional", "1.0.0", (D,)),
                Decimal("-1"),
            ),
            "decision.historical_valid_observations": (
                StrategyTypeReference("Integer", "1.0.0"),
                60,
            ),
            "decision.call_atm_iv_minus_rv": (D, Decimal("-0.01")),
            "decision.put_atm_iv_minus_rv": (D, Decimal("0.01")),
            "decision.call_wing_iv_minus_rv": (D, Decimal("0.09")),
            "decision.put_wing_iv_minus_rv": (D, Decimal("0.07")),
            "decision.call_wing_iv_minus_atm_iv": (D, Decimal("0.1")),
            "decision.put_wing_iv_minus_atm_iv": (D, Decimal("0.06")),
            "decision.time_series_return": (D, Decimal("0.05")),
            "decision.cross_sectional_percentile": (
                StrategyTypeReference("Optional", "1.0.0", (D,)),
                Decimal("0.8"),
            ),
            "decision.comparison_peer_count": (
                StrategyTypeReference("Integer", "1.0.0"),
                5,
            ),
            "decision.sector_relative_return": (
                StrategyTypeReference("Optional", "1.0.0", (D,)),
                Decimal("-0.01"),
            ),
        }
    )
    graph = compile_strategy_graph(SKEW_MOMENTUM_VERTICAL_MANIFEST, registry())
    result = execute_strategy_graph(graph, execution_context)
    assert result.outputs.get("structure").value.identity
    assert result.outputs.get("liquidity_acceptable").value is True
    assert result.outputs.get("direction").value == "BULLISH"
    assert result.outputs.get("momentum_alignment_count").value == 2
    assert result.outputs.get("verdict").value == "PASS"


def _execute_skew_policy(**overrides: object) -> ComponentValues:
    inputs: dict[str, object] = {
        "normalized_call_skew": Decimal("0.5"),
        "normalized_put_skew": Decimal("0.3"),
        "call_skew_zscore": Decimal("-2.1"),
        "put_skew_zscore": Decimal("-1"),
        "historical_valid_observations": 60,
        "call_atm_iv_minus_rv": Decimal("-0.01"),
        "put_atm_iv_minus_rv": Decimal("0.01"),
        "call_wing_iv_minus_rv": Decimal("0.09"),
        "put_wing_iv_minus_rv": Decimal("0.07"),
        "call_wing_iv_minus_atm_iv": Decimal("0.1"),
        "put_wing_iv_minus_atm_iv": Decimal("0.06"),
        "time_series_return": Decimal("0.05"),
        "cross_sectional_percentile": Decimal("0.8"),
        "comparison_peer_count": 5,
        "sector_relative_return": Decimal("-0.01"),
    }
    inputs.update(overrides)
    execution_context = build_skew_momentum_context(
        screening_fixtures.skew_momentum_chain(),
        screening_fixtures.SKEW_EXPIRATION,
        **inputs,  # type: ignore[arg-type]
    )
    return execute_strategy_graph(
        compile_strategy_graph(SKEW_MOMENTUM_VERTICAL_MANIFEST, registry()),
        execution_context,
    ).outputs


def test_skew_research_policy_boundaries_and_unknown_evidence() -> None:
    assert _execute_skew_policy(call_atm_iv_minus_rv=Decimal("0")).get("verdict").value == "PASS"
    assert (
        _execute_skew_policy(historical_valid_observations=39).get("verdict").value
        == "WATCH"
    )
    assert _execute_skew_policy(comparison_peer_count=4).get("verdict").value == "WATCH"
    assert (
        _execute_skew_policy(
            put_skew_zscore=Decimal("-2"),
            put_atm_iv_minus_rv=Decimal("0"),
        )
        .get("verdict")
        .value
        == "WATCH"
    )
    bearish = _execute_skew_policy(
        call_skew_zscore=Decimal("-1"),
        call_atm_iv_minus_rv=Decimal("0.01"),
        put_skew_zscore=Decimal("-2"),
        put_atm_iv_minus_rv=Decimal("0"),
        time_series_return=Decimal("-0.05"),
        cross_sectional_percentile=Decimal("0.30"),
        sector_relative_return=Decimal("0.01"),
    )
    assert bearish.get("direction").value == "BEARISH"
    assert bearish.get("momentum_alignment_count").value == 2
    assert bearish.get("verdict").value == "PASS"
    assert (
        _execute_skew_policy(call_wing_iv_minus_rv=Decimal("0")).get("verdict").value
        == "FAIL"
    )


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
