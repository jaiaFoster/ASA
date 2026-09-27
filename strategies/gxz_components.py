"""Strategy-owned graph component for the frozen GXZ verdict precedence."""

from __future__ import annotations

from strategies.components import (
    BaseComponent,
    ComponentCategory,
    ComponentDefinition,
    PortDefinition,
)
from strategies.manifest import ManifestObject
from strategies.plugins import PluginMetadata, StrategyPlugin
from strategies.tristate_components import FAIL, PASS, TRISTATE, UNKNOWN
from strategies.type_system import ComponentValues, StrategyTypeReference, TypedValue

NO_ACTION = "NO_ACTION"
TEXT = StrategyTypeReference("Text", "1.0.0")


class GXZVerdict(BaseComponent):  # type: ignore[misc]
    """Entry-session precedence plus three-state financial gate projection."""

    __slots__ = ()
    definition = ComponentDefinition(
        "asa.gxz",
        "verdict",
        "1.0.0",
        ComponentCategory.PREDICATE,
        (
            PortDefinition("entry_session", TRISTATE),
            PortDefinition("financial_gates", TRISTATE),
        ),
        (PortDefinition("verdict", TEXT),),
        algorithm_version="1.0.0",
        explanation_template=ManifestObject((("operation", "gxz_verdict_precedence"),)),
    )

    def evaluate(self, inputs: ComponentValues, parameters: ComponentValues) -> ComponentValues:
        entry = inputs.get("entry_session").value
        gates = inputs.get("financial_gates").value
        if entry not in (PASS, FAIL, UNKNOWN) or gates not in (PASS, FAIL, UNKNOWN):
            raise ValueError("GXZ verdict inputs must be three-state values")
        verdict = NO_ACTION if entry == FAIL else UNKNOWN if entry == UNKNOWN else gates
        return ComponentValues((("verdict", TypedValue(TEXT, verdict)),))


GXZ_PLUGIN = StrategyPlugin(
    PluginMetadata(
        "asa.gxz",
        "gxz_components",
        "1.0.0",
        "Frozen GXZ entry-session and financial-gate verdict precedence.",
    ),
    (GXZVerdict(),),
)
