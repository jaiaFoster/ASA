"""Strategy-owned Cboe PUT verdict precedence."""

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


class CboePutVerdict(BaseComponent):  # type: ignore[misc]
    __slots__ = ()
    definition = ComponentDefinition(
        "asa.cboe_put",
        "verdict",
        "1.0.0",
        ComponentCategory.PREDICATE,
        (PortDefinition("roll_date", TRISTATE), PortDefinition("entry_gates", TRISTATE)),
        (PortDefinition("verdict", TEXT),),
        algorithm_version="1.0.0",
        explanation_template=ManifestObject((("operation", "cboe_put_verdict_precedence"),)),
    )

    def evaluate(self, inputs: ComponentValues, parameters: ComponentValues) -> ComponentValues:
        roll = inputs.get("roll_date").value
        gates = inputs.get("entry_gates").value
        if roll not in (PASS, FAIL, UNKNOWN) or gates not in (PASS, FAIL, UNKNOWN):
            raise ValueError("Cboe PUT verdict inputs must be three-state values")
        verdict = NO_ACTION if roll == FAIL else UNKNOWN if roll == UNKNOWN else gates
        return ComponentValues((("verdict", TypedValue(TEXT, verdict)),))


CBOE_PUT_PLUGIN = StrategyPlugin(
    PluginMetadata("asa.cboe_put", "cboe_put_components", "1.0.0", "Cboe PUT roll precedence."),
    (CboePutVerdict(),),
)
