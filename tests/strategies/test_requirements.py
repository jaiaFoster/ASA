"""SPRINT-014 S14-PR-02: typed requirement projection tests."""

from __future__ import annotations

import pytest

from domain import MarketCapability
from strategies import (
    EARNINGS_CALENDAR_MANIFEST,
    CapabilityRequirement,
    ComponentReference,
    EarningsCalendarExpirationPolicy,
    ManifestMetadata,
    ManifestValidationError,
    NodeSpec,
    OutputSpec,
    ParameterSpec,
    StrategyManifest,
    earnings_calendar_requirement,
    node_parameter_value,
)


def _manifest_with_nodes(*nodes: NodeSpec) -> StrategyManifest:
    return StrategyManifest(
        "1.1.0",
        "test_strategy",
        "1.0.0",
        ManifestMetadata("Test"),
        (),
        (),
        nodes,
        (),
        (OutputSpec("value", nodes[0].node_id, "out", "value"),),
        required_market_capabilities=(CapabilityRequirement("real_time_quote_v1", "1.0.0"),),
    )


def _node(node_id: str, *parameters: ParameterSpec) -> NodeSpec:
    return NodeSpec(node_id, ComponentReference("ns", "component", "1.0.0"), parameters)


class TestNodeParameterValue:
    def test_reads_an_existing_parameter(self) -> None:
        node = _node("n", ParameterSpec("x", "Integer", 7))
        manifest = _manifest_with_nodes(node)
        assert node_parameter_value(manifest, "n", "x") == 7

    def test_unknown_node_raises(self) -> None:
        node = _node("n", ParameterSpec("x", "Integer", 7))
        manifest = _manifest_with_nodes(node)
        with pytest.raises(ManifestValidationError, match="no node"):
            node_parameter_value(manifest, "missing", "x")

    def test_unknown_parameter_raises(self) -> None:
        node = _node("n", ParameterSpec("x", "Integer", 7))
        manifest = _manifest_with_nodes(node)
        with pytest.raises(ManifestValidationError, match="no parameter"):
            node_parameter_value(manifest, "n", "missing")

    def test_order_independent(self) -> None:
        # Two nodes, parameters supplied in reverse order at construction --
        # StrategyManifest.__post_init__ already canonically sorts both, so
        # the lookup result must be identical regardless of input order.
        node_a = _node("a", ParameterSpec("y", "Integer", 2), ParameterSpec("x", "Integer", 1))
        node_b = _node("b", ParameterSpec("z", "Integer", 3))
        forward = _manifest_with_nodes(node_a, node_b)
        backward = _manifest_with_nodes(node_b, node_a)
        forward_value = node_parameter_value(forward, "a", "x")
        backward_value = node_parameter_value(backward, "a", "x")
        assert forward_value == backward_value == 1


class TestEarningsCalendarRequirement:
    def test_capabilities_match_the_manifest(self) -> None:
        requirement = earnings_calendar_requirement()
        assert set(requirement.capabilities) == {
            MarketCapability.EARNINGS_CALENDAR_V1,
            MarketCapability.REAL_TIME_QUOTE_V1,
            MarketCapability.OPTION_CHAIN_V1,
            MarketCapability.HISTORICAL_BARS_V1,
        }

    def test_expiration_policy_matches_the_manifests_expiration_select_node(
        self,
    ) -> None:
        requirement = earnings_calendar_requirement()
        assert requirement.expiration_policy == EarningsCalendarExpirationPolicy(
            front_min_dte=7,
            front_max_dte=21,
            back_min_dte=22,
            back_max_dte=75,
            target_gap_days=30,
            gap_tolerance_days=5,
        )

    def test_lookahead_days_is_derived_from_back_max_dte(self) -> None:
        requirement = earnings_calendar_requirement()
        assert requirement.lookahead_days == requirement.expiration_policy.back_max_dte

    def test_deterministic_across_calls(self) -> None:
        assert earnings_calendar_requirement() == earnings_calendar_requirement()

    def test_uses_the_real_earnings_calendar_manifest_by_default(self) -> None:
        default_call = earnings_calendar_requirement()
        explicit_call = earnings_calendar_requirement(EARNINGS_CALENDAR_MANIFEST)
        assert default_call == explicit_call

    def test_performs_no_provider_call(self) -> None:
        # Pure data transformation: the module this function lives in must
        # never import a transport, provider SDK, or database driver.
        import ast
        from pathlib import Path

        tree = ast.parse(Path("strategies/requirements.py").read_text())
        roots: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                roots.update(alias.name.split(".")[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                roots.add(node.module.split(".")[0])
        forbidden = {"requests", "httpx", "urllib", "sqlalchemy", "psycopg", "psycopg2"}
        assert not roots & forbidden
