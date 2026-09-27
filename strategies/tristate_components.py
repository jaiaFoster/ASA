"""Three-state PASS / FAIL / UNKNOWN graph semantics (STRATEGY-PRODUCTION-001 SP-01E).

Frozen invariants (sprint `architecture_contract_freeze.three_state_semantics`):

- UNKNOWN is not boolean false;
- AND is FAIL if any input is FAIL, else UNKNOWN if any input is UNKNOWN, else PASS;
- the verdict preserves UNKNOWN as a value distinct from PASS, WATCH and FAIL.

These components ship as a separate plugin, so existing strategy graphs keep
their registry and graph identities byte for byte. A new strategy opts in by
building its registry with `TRISTATE_PLUGIN`.
"""

from __future__ import annotations

from decimal import Decimal
from typing import cast

from strategies.components import (
    BaseComponent,
    ComponentCategory,
    ComponentDefinition,
    ParameterDefinition,
    PortDefinition,
)
from strategies.errors import ComponentContractError
from strategies.manifest import ManifestObject
from strategies.plugins import PluginMetadata, StrategyPlugin
from strategies.type_system import ComponentValues, StrategyTypeReference, TypedValue

NAMESPACE = "asa.tristate"
PASS = "PASS"
FAIL = "FAIL"
UNKNOWN = "UNKNOWN"

TRISTATE = StrategyTypeReference(
    "Enum", "1.0.0", qualifiers=ManifestObject((("values", (PASS, FAIL, UNKNOWN)),))
)
TRISTATE_VERDICT = StrategyTypeReference(
    "Enum", "1.0.0", qualifiers=ManifestObject((("values", (PASS, "WATCH", FAIL, UNKNOWN)),))
)
_D = StrategyTypeReference("Decimal", "1.0.0")
_B = StrategyTypeReference("Boolean", "1.0.0")
_OD = StrategyTypeReference("Optional", "1.0.0", (_D,))
_OPERATOR = StrategyTypeReference(
    "Enum", "1.0.0", qualifiers=ManifestObject((("values", ("<", "<=", "==", ">=", ">")),))
)
_OPERATORS = {
    "<": lambda left, right: left < right,
    "<=": lambda left, right: left <= right,
    "==": lambda left, right: left == right,
    ">=": lambda left, right: left >= right,
    ">": lambda left, right: left > right,
}


def tri_and(values: tuple[str, ...]) -> str:
    """Frozen AND: FAIL dominates, then UNKNOWN, else PASS."""
    if not values:
        raise ComponentContractError("tri_and requires at least one input")
    if FAIL in values:
        return FAIL
    if UNKNOWN in values:
        return UNKNOWN
    return PASS


def tri_or(values: tuple[str, ...]) -> str:
    """Dual of tri_and: PASS dominates, then UNKNOWN, else FAIL."""
    if not values:
        raise ComponentContractError("tri_or requires at least one input")
    if PASS in values:
        return PASS
    if UNKNOWN in values:
        return UNKNOWN
    return FAIL


def _definition(
    name: str,
    inputs: tuple[PortDefinition, ...],
    outputs: tuple[PortDefinition, ...],
    parameters: tuple[ParameterDefinition, ...] = (),
) -> ComponentDefinition:
    return ComponentDefinition(
        NAMESPACE,
        name,
        "1.0.0",
        ComponentCategory.PREDICATE,
        inputs,
        outputs,
        parameters,
        algorithm_version="1.0.0",
        explanation_template=ManifestObject((("operation", name),)),
    )


def _state(inputs: ComponentValues, name: str) -> str:
    value = inputs.get(name).value
    if value not in (PASS, FAIL, UNKNOWN):
        raise ComponentContractError(f"{name} must be PASS, FAIL or UNKNOWN")
    return cast(str, value)


def _result(value: str, port: str = "result") -> ComponentValues:
    return ComponentValues(((port, TypedValue(TRISTATE, value)),))


class TriAnd(BaseComponent):
    __slots__ = ()
    definition = _definition(
        "tri_and",
        (PortDefinition("left", TRISTATE), PortDefinition("right", TRISTATE)),
        (PortDefinition("result", TRISTATE),),
    )

    def evaluate(self, inputs: ComponentValues, parameters: ComponentValues) -> ComponentValues:
        return _result(tri_and((_state(inputs, "left"), _state(inputs, "right"))))


class TriOr(BaseComponent):
    __slots__ = ()
    definition = _definition(
        "tri_or",
        (PortDefinition("left", TRISTATE), PortDefinition("right", TRISTATE)),
        (PortDefinition("result", TRISTATE),),
    )

    def evaluate(self, inputs: ComponentValues, parameters: ComponentValues) -> ComponentValues:
        return _result(tri_or((_state(inputs, "left"), _state(inputs, "right"))))


class TriCompare(BaseComponent):
    """Compare two optional decimals; a missing side is UNKNOWN, never FAIL."""

    __slots__ = ()
    definition = _definition(
        "tri_compare",
        (PortDefinition("left", _OD), PortDefinition("right", _OD)),
        (PortDefinition("result", TRISTATE),),
        (ParameterDefinition("operator", _OPERATOR),),
    )

    def evaluate(self, inputs: ComponentValues, parameters: ComponentValues) -> ComponentValues:
        left = inputs.get("left").value
        right = inputs.get("right").value
        operator = cast(str, parameters.get("operator").value)
        if left is None or right is None:
            return _result(UNKNOWN)
        holds = _OPERATORS[operator](cast(Decimal, left), cast(Decimal, right))
        return _result(PASS if holds else FAIL)


class TriFromBoolean(BaseComponent):
    """Lift a known Boolean into PASS/FAIL. It cannot produce UNKNOWN."""

    __slots__ = ()
    definition = _definition(
        "tri_from_boolean",
        (PortDefinition("value", _B),),
        (PortDefinition("result", TRISTATE),),
    )

    def evaluate(self, inputs: ComponentValues, parameters: ComponentValues) -> ComponentValues:
        return _result(PASS if inputs.get("value").value else FAIL)


class TriVerdict(BaseComponent):
    """Project a composed gate state into a verdict that keeps UNKNOWN distinct."""

    __slots__ = ()
    definition = _definition(
        "tri_verdict",
        (PortDefinition("gate", TRISTATE),),
        (PortDefinition("verdict", TRISTATE_VERDICT),),
    )

    def evaluate(self, inputs: ComponentValues, parameters: ComponentValues) -> ComponentValues:
        return ComponentValues((("verdict", TypedValue(TRISTATE_VERDICT, _state(inputs, "gate"))),))


TRISTATE_COMPONENTS: tuple[BaseComponent, ...] = (
    TriAnd(),
    TriOr(),
    TriCompare(),
    TriFromBoolean(),
    TriVerdict(),
)

TRISTATE_PLUGIN = StrategyPlugin(
    PluginMetadata(
        NAMESPACE,
        "tristate_components",
        "1.0.0",
        "PASS/FAIL/UNKNOWN gate composition and UNKNOWN-preserving verdict projection.",
    ),
    TRISTATE_COMPONENTS,
)
