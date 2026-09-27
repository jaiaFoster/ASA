"""SP-01E: three-state graph semantics and identity-bearing assumption provenance."""

from __future__ import annotations

import itertools
from dataclasses import replace
from decimal import Decimal

import pytest

from screening.explanations import build_graph_explanation
from strategies import (
    CORE_COMPONENTS,
    STONK_STRATEGY_PLUGINS,
    compile_strategy_graph,
    execute_strategy_graph,
)
from strategies.manifest import (
    AssumptionReference,
    ComponentReference,
    EdgeSpec,
    ManifestMetadata,
    ManifestValidationError,
    NodeSpec,
    OutputSpec,
    ParameterSpec,
    StrategyManifest,
    deserialize_manifest,
    serialize_manifest,
)
from strategies.plugins import build_plugin_registry
from strategies.put_credit_spread_manifest import SPY_PUT_CREDIT_SPREAD_MANIFEST
from strategies.tristate_components import TRISTATE_PLUGIN, tri_and, tri_or
from strategies.type_system import ComponentValues, StrategyTypeReference, TypedValue
from strategy_runtime.result import EvaluationState
from strategy_runtime.verdict_projection import (
    evaluation_state_for_verdict,
    unknown_gate_blockers,
)

STATES = ("PASS", "FAIL", "UNKNOWN")
OD = StrategyTypeReference("Optional", "1.0.0", (StrategyTypeReference("Decimal", "1.0.0"),))


def test_tri_and_truth_table_is_the_frozen_semantics() -> None:
    for left, right in itertools.product(STATES, repeat=2):
        pair = (left, right)
        expected = "FAIL" if "FAIL" in pair else "UNKNOWN" if "UNKNOWN" in pair else "PASS"
        assert tri_and(pair) == expected
    assert tri_or(("FAIL", "UNKNOWN")) == "UNKNOWN"
    assert tri_or(("PASS", "UNKNOWN")) == "PASS"
    assert tri_or(("FAIL", "FAIL")) == "FAIL"


def _node(node_id: str, name: str, *parameters: ParameterSpec) -> NodeSpec:
    return NodeSpec(node_id, ComponentReference("asa.tristate", name, "1.0.0"), parameters)


def _manifest(**changes: object) -> StrategyManifest:
    manifest = StrategyManifest(
        "1.1.0",
        "tristate_fixture",
        "1.0.0",
        ManifestMetadata("Tri-state fixture"),
        (),
        (),
        (
            _node("gate_a", "tri_compare", ParameterSpec("operator", "Enum", ">=")),
            _node("gate_b", "tri_compare", ParameterSpec("operator", "Enum", "<=")),
            _node("both", "tri_and"),
            _node("verdict", "tri_verdict"),
        ),
        (
            EdgeSpec("gate_a", "result", "both", "left"),
            EdgeSpec("gate_b", "result", "both", "right"),
            EdgeSpec("both", "result", "verdict", "gate"),
        ),
        (
            OutputSpec("gate_a", "gate_a", "result", "gate"),
            OutputSpec("gate_b", "gate_b", "result", "gate"),
            OutputSpec("verdict", "verdict", "verdict", "verdict"),
        ),
    )
    return replace(manifest, **changes) if changes else manifest


_REGISTRY = build_plugin_registry(CORE_COMPONENTS, (*STONK_STRATEGY_PLUGINS, TRISTATE_PLUGIN))


def _run(a: Decimal | None, b: Decimal | None) -> ComponentValues:
    graph = compile_strategy_graph(_manifest(), _REGISTRY)
    values = ComponentValues(
        (
            ("gate_a.left", TypedValue(OD, a)),
            ("gate_a.right", TypedValue(OD, Decimal("1"))),
            ("gate_b.left", TypedValue(OD, b)),
            ("gate_b.right", TypedValue(OD, Decimal("5"))),
        )
    )
    return execute_strategy_graph(graph, values).outputs


@pytest.mark.parametrize(
    ("a", "b", "verdict", "state"),
    [
        (Decimal("2"), Decimal("3"), "PASS", EvaluationState.PASS),
        (Decimal("0"), Decimal("3"), "FAIL", EvaluationState.NO_SIGNAL),
        (None, Decimal("3"), "UNKNOWN", EvaluationState.MISSING_DATA),
        # FAIL dominates UNKNOWN.
        (None, Decimal("9"), "FAIL", EvaluationState.NO_SIGNAL),
    ],
)
def test_graph_preserves_unknown_through_verdict_and_projection(
    a: Decimal | None, b: Decimal | None, verdict: str, state: EvaluationState
) -> None:
    outputs = _run(a, b)
    assert outputs.get("verdict").value == verdict
    assert evaluation_state_for_verdict(verdict) is state
    explanation = build_graph_explanation(_manifest(), outputs)
    gates = dict(explanation.gate_results)
    if a is None:
        assert gates["gate_a"] is None
        assert "typed unknown gate: gate_a" in unknown_gate_blockers(explanation.gate_results)
        assert "gate:gate_a:unknown" in explanation.reason_codes


def test_unknown_verdict_is_rejected_nowhere_and_bad_verdict_is_rejected() -> None:
    with pytest.raises(ValueError):
        evaluation_state_for_verdict("MAYBE")


def test_tristate_plugin_does_not_change_existing_graph_identity() -> None:
    # Pinned from main @ 1c5c7e2, before SP-01E: the opt-in plugin and the
    # optional assumptions field leave existing identities byte for byte.
    legacy = build_plugin_registry(CORE_COMPONENTS, STONK_STRATEGY_PLUGINS)
    assert SPY_PUT_CREDIT_SPREAD_MANIFEST.manifest_id == (
        "11bbc7f477ee03c67e96719d42a0a615fbe54ddeec603dd2709d3f02b5f3682c"
    )
    assert compile_strategy_graph(SPY_PUT_CREDIT_SPREAD_MANIFEST, legacy).graph_id == (
        "ba143ecea0d0e749fef07127c6d3735ab638b2fa3bcb95eedfb068d38964ab00"
    )


def test_assumptions_are_identity_bearing_and_disclosed() -> None:
    base = _manifest(
        parameters=(ParameterSpec("tie_policy", "Enum", "share_lowest_rank"),),
    )
    with_ra = replace(
        base, assumptions=(AssumptionReference("RA-XS-01", "research", ("tie_policy",)),)
    )
    assert base.manifest_id != with_ra.manifest_id
    changed_value = replace(
        with_ra, parameters=(ParameterSpec("tie_policy", "Enum", "other_policy"),)
    )
    assert changed_value.manifest_id != with_ra.manifest_id
    assert deserialize_manifest(serialize_manifest(with_ra)) == with_ra
    explanation = build_graph_explanation(with_ra, _run(Decimal("2"), Decimal("3")))
    assert "assumption:RA-XS-01:research[tie_policy]" in explanation.assumptions


def test_assumption_validation() -> None:
    with pytest.raises(ManifestValidationError):
        AssumptionReference("RA-XS-01", "implementation")
    with pytest.raises(ManifestValidationError):
        AssumptionReference("XX-1", "research")
    with pytest.raises(ManifestValidationError):
        _manifest(assumptions=(AssumptionReference("IA-PUT-01", "implementation", ("nope",)),))


def test_manifest_without_assumptions_keeps_identity() -> None:
    data = serialize_manifest(SPY_PUT_CREDIT_SPREAD_MANIFEST)
    assert b"assumptions" not in data


def test_semantics_changing_assumption_requires_version_change() -> None:
    from strategies.manifest_version_pins import version_pin_violations

    base = _manifest(
        parameters=(ParameterSpec("tie_policy", "Enum", "share_lowest_rank"),),
        assumptions=(AssumptionReference("RA-XS-01", "research", ("tie_policy",)),),
    )
    pins = {("tristate_fixture", "1.0.0"): base.manifest_id}
    assert version_pin_violations((base,), pins) == ()
    assert version_pin_violations((base,), {}) == (
        "tristate_fixture@1.0.0: assumption-bearing manifest has no version pin",
    )
    changed = replace(base, parameters=(ParameterSpec("tie_policy", "Enum", "other"),))
    assert version_pin_violations((changed,), pins) == (
        "tristate_fixture@1.0.0: semantics changed without a strategy_version change",
    )
    bumped = replace(changed, strategy_version="1.1.0")
    assert (
        version_pin_violations(
            (bumped,), {**pins, ("tristate_fixture", "1.1.0"): bumped.manifest_id}
        )
        == ()
    )
    # Manifests without assumptions are not subject to pins.
    assert version_pin_violations((SPY_PUT_CREDIT_SPREAD_MANIFEST,), {}) == ()


def test_unrecognised_gate_value_is_rejected_not_reported_unknown() -> None:
    from screening.explanations import _gate_value

    assert _gate_value("UNKNOWN") is None
    assert _gate_value("PASS") is True
    with pytest.raises(ValueError):
        _gate_value("WATCH")
