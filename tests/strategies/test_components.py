"""STRAT-003: pure immutable Strategy Component framework tests."""
from __future__ import annotations

from dataclasses import FrozenInstanceError, replace

import pytest

from strategies import (
    COMPONENT_IDENTITY_NAMESPACE,
    COMPONENT_IDENTITY_VERSION,
    BaseComponent,
    CapabilityRequirement,
    ComponentCategory,
    ComponentContractError,
    ComponentDefinition,
    ComponentValues,
    ManifestObject,
    ParameterDefinition,
    PortCardinality,
    PortDefinition,
    StrategyTypeReference,
    TypedValue,
)

DECIMAL = StrategyTypeReference("Decimal", "1.0.0")
BOOLEAN = StrategyTypeReference("Boolean", "1.0.0")


def _definition() -> ComponentDefinition:
    return ComponentDefinition(
        namespace="asa.core",
        name="Comparator",
        version="1.0.0",
        category=ComponentCategory.PREDICATE,
        input_ports=(
            PortDefinition("right", DECIMAL),
            PortDefinition("left", DECIMAL),
        ),
        output_ports=(PortDefinition("result", BOOLEAN),),
        parameters=(
            ParameterDefinition(
                "inclusive",
                BOOLEAN,
                required=False,
                has_default=True,
                default=True,
            ),
            ParameterDefinition("operator", StrategyTypeReference("Text", "1.0.0")),
        ),
        capabilities=(CapabilityRequirement("compare", "1.0.0"),),
        algorithm_version="1.0.0",
        explanation_template=ManifestObject(
            (("code", "comparison"), ("fields", ("left", "right")))
        ),
        resource_limits=ManifestObject((("maximum_inputs", 2),)),
    )


class ComparatorComponent(BaseComponent):
    __slots__ = ()
    definition = _definition()

    def evaluate(
        self, inputs: ComponentValues, parameters: ComponentValues
    ) -> ComponentValues:
        left = inputs.get("left").value
        right = inputs.get("right").value
        if not isinstance(left, int) or not isinstance(right, int):
            raise ComponentContractError("test comparator requires integer values")
        try:
            inclusive = parameters.get("inclusive").value
        except KeyError:
            inclusive = True
        result = left >= right if inclusive is True else left > right
        return ComponentValues((("result", TypedValue(BOOLEAN, result)),))


class TestComponentDefinition:
    def test_complete_definition_is_immutable_and_canonical(self):
        definition = _definition()
        assert tuple(port.name for port in definition.input_ports) == ("left", "right")
        assert tuple(item.name for item in definition.parameters) == ("inclusive", "operator")
        with pytest.raises(FrozenInstanceError):
            definition.name = "changed"  # type: ignore[misc]

    def test_component_identity_contract_is_pinned(self):
        definition = _definition()
        assert COMPONENT_IDENTITY_NAMESPACE == "asa.strategy_component"
        assert COMPONENT_IDENTITY_VERSION == "v1"
        assert definition.component_id == (
            "c40fcd12952ecf156dd9df57f9bd96fe360fd9ce4423c9a0ca4e6444ed7c2815"
        )

    def test_input_order_does_not_change_definition_or_identity(self):
        original = _definition()
        reordered = replace(
            original,
            input_ports=tuple(reversed(original.input_ports)),
            parameters=tuple(reversed(original.parameters)),
            capabilities=tuple(reversed(original.capabilities)),
        )
        assert reordered == original
        assert reordered.component_id == original.component_id

    @pytest.mark.parametrize(
        "field",
        ["version", "algorithm_version", "category", "input_ports", "parameters", "capabilities"],
    )
    def test_semantic_definition_changes_change_identity(self, field: str):
        original = _definition()
        replacements: dict[str, object] = {
            "version": "1.0.1",
            "algorithm_version": "1.0.1",
            "category": ComponentCategory.TRANSFORM,
            "input_ports": (PortDefinition("value", DECIMAL),),
            "parameters": (),
            "capabilities": (CapabilityRequirement("transform", "1.0.0"),),
        }
        changed = replace(original, **{field: replacements[field]})
        assert changed.component_id != original.component_id

    @pytest.mark.parametrize(
        ("field", "values"),
        [
            (
                "input_ports",
                (PortDefinition("value", DECIMAL), PortDefinition("value", BOOLEAN)),
            ),
            (
                "output_ports",
                (PortDefinition("value", DECIMAL), PortDefinition("value", BOOLEAN)),
            ),
            (
                "parameters",
                (
                    ParameterDefinition("value", DECIMAL),
                    ParameterDefinition("value", BOOLEAN),
                ),
            ),
            (
                "capabilities",
                (
                    CapabilityRequirement("same", "1.0.0"),
                    CapabilityRequirement("same", "2.0.0"),
                ),
            ),
        ],
    )
    def test_duplicate_contract_names_are_rejected(self, field: str, values: object):
        with pytest.raises(ComponentContractError, match="duplicate"):
            replace(_definition(), **{field: values})

    def test_at_least_one_output_is_required(self):
        with pytest.raises(ComponentContractError, match="output"):
            replace(_definition(), output_ports=())

    def test_all_categories_are_closed_and_pinned(self):
        assert {item.value for item in ComponentCategory} == {
            "source",
            "transform",
            "predicate",
            "aggregate",
            "score",
            "rank",
            "constraint",
            "proposal",
            "utility",
        }

    def test_port_cardinality_is_closed(self):
        assert {item.value for item in PortCardinality} == {"single", "optional", "many"}


class TestParameterDefaults:
    def test_optional_default_is_frozen(self):
        definition = ParameterDefinition(
            "bounds",
            StrategyTypeReference("Map.Decimal", "1.0.0"),
            required=False,
            has_default=True,
            default={"maximum": "1.00", "minimum": "0.00"},
        )
        assert isinstance(definition.default, ManifestObject)
        assert tuple(key for key, _ in definition.default.entries) == ("maximum", "minimum")

    def test_required_parameter_cannot_have_default(self):
        with pytest.raises(ComponentContractError, match="required"):
            ParameterDefinition("x", DECIMAL, required=True, has_default=True, default="1")

    def test_default_requires_explicit_presence_flag(self):
        with pytest.raises(ComponentContractError, match="has_default"):
            ParameterDefinition("x", DECIMAL, required=False, default="1")

    def test_float_default_is_rejected(self):
        with pytest.raises(Exception, match="floating-point"):
            ParameterDefinition("x", DECIMAL, required=False, has_default=True, default=1.2)

    def test_decimal_default_uses_manifest_canonicalization(self):
        definition = ParameterDefinition(
            "x", DECIMAL, required=False, has_default=True, default="1.2500"
        )
        assert definition.default == "1.25"


class TestBaseComponent:
    def test_stateless_component_evaluates_from_immutable_values(self):
        component = ComparatorComponent()
        result = component.evaluate(
            ComponentValues(
                (("left", TypedValue(DECIMAL, 3)), ("right", TypedValue(DECIMAL, 2)))
            ),
            ComponentValues((("inclusive", TypedValue(BOOLEAN, True)),)),
        )
        assert result == ComponentValues((("result", TypedValue(BOOLEAN, True)),))
        assert not hasattr(component, "__dict__")

    def test_component_does_not_mutate_inputs_or_parameters(self):
        component = ComparatorComponent()
        inputs = ComponentValues(
            (("left", TypedValue(DECIMAL, 2)), ("right", TypedValue(DECIMAL, 2)))
        )
        parameters = ComponentValues((("inclusive", TypedValue(BOOLEAN, False)),))
        before = (inputs, parameters)
        component.evaluate(inputs, parameters)
        assert (inputs, parameters) == before

    def test_component_contract_has_no_lifecycle_callbacks(self):
        prohibited = {
            "on_manifest_validated",
            "on_graph_compiled",
            "on_node_started",
            "on_node_completed",
            "on_node_failed",
        }
        assert not prohibited & set(dir(BaseComponent))

    def test_definition_is_separate_from_evaluator_instance(self):
        first = ComparatorComponent()
        second = ComparatorComponent()
        assert first.definition is second.definition
        assert first.definition.component_id == second.definition.component_id
