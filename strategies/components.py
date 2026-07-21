"""Pure immutable Strategy Component framework (STRAT-003, ASA-ARCH-003).

Components own bounded financial transformations. Core owns orchestration,
validation, lifecycle traces, and replay. A component has one stateless pure
``evaluate`` entrypoint; lifecycle callbacks and service dependencies are not
part of this contract.
"""

from __future__ import annotations

import hashlib
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum

from strategies.errors import ComponentContractError
from strategies.manifest import (
    CapabilityRequirement,
    ManifestObject,
    ManifestValue,
    ParameterSpec,
    canonical_strategy_json,
    freeze_manifest_value,
    manifest_value_to_data,
    validate_semantic_version,
    validate_strategy_identifier,
)
from strategies.type_system import ComponentValues, StrategyTypeReference

COMPONENT_IDENTITY_NAMESPACE = "asa.strategy_component"
COMPONENT_IDENTITY_VERSION = "v1"


class ComponentCategory(str, Enum):
    """Closed v1 Component Type taxonomy."""

    SOURCE = "source"
    TRANSFORM = "transform"
    PREDICATE = "predicate"
    AGGREGATE = "aggregate"
    SCORE = "score"
    RANK = "rank"
    CONSTRAINT = "constraint"
    PROPOSAL = "proposal"
    UTILITY = "utility"


class PortCardinality(str, Enum):
    """Closed input/output cardinality contract."""

    SINGLE = "single"
    OPTIONAL = "optional"
    MANY = "many"


@dataclass(frozen=True, slots=True, order=True)
class PortDefinition:
    """One named typed Component port."""

    name: str
    type_ref: StrategyTypeReference
    cardinality: PortCardinality = PortCardinality.SINGLE

    def __post_init__(self) -> None:
        validate_strategy_identifier(self.name, "port.name")
        if not isinstance(self.type_ref, StrategyTypeReference):
            raise ComponentContractError("port.type_ref must be a StrategyTypeReference")
        if not isinstance(self.cardinality, PortCardinality):
            raise ComponentContractError("port.cardinality must be a PortCardinality")


@dataclass(frozen=True, slots=True)
class ParameterDefinition:
    """One typed parameter declaration and optional canonical default."""

    name: str
    type_ref: StrategyTypeReference
    required: bool = True
    has_default: bool = False
    default: ManifestValue = None

    def __post_init__(self) -> None:
        validate_strategy_identifier(self.name, "parameter.name")
        if not isinstance(self.type_ref, StrategyTypeReference):
            raise ComponentContractError("parameter.type_ref must be a StrategyTypeReference")
        if not isinstance(self.required, bool) or not isinstance(self.has_default, bool):
            raise ComponentContractError("parameter required/default flags must be Boolean")
        if self.required and self.has_default:
            raise ComponentContractError("a required parameter cannot declare a default")
        if not self.has_default and self.default is not None:
            raise ComponentContractError("parameter default requires has_default=true")
        if self.has_default:
            frozen = freeze_manifest_value(self.default)
            canonical = ParameterSpec(self.name, self.type_ref.name, frozen).value
            object.__setattr__(self, "default", canonical)


@dataclass(frozen=True, slots=True)
class ComponentDefinition:
    """Complete immutable metadata contract for one Component Type."""

    namespace: str
    name: str
    version: str
    category: ComponentCategory
    input_ports: tuple[PortDefinition, ...]
    output_ports: tuple[PortDefinition, ...]
    parameters: tuple[ParameterDefinition, ...] = field(default_factory=tuple)
    capabilities: tuple[CapabilityRequirement, ...] = field(default_factory=tuple)
    algorithm_version: str = "1.0.0"
    explanation_template: ManifestObject = field(default_factory=lambda: ManifestObject(()))
    resource_limits: ManifestObject = field(default_factory=lambda: ManifestObject(()))

    def __post_init__(self) -> None:
        validate_strategy_identifier(self.namespace, "component.namespace")
        validate_strategy_identifier(self.name, "component.name")
        validate_semantic_version(self.version, "component.version")
        validate_semantic_version(self.algorithm_version, "component.algorithm_version")
        if not isinstance(self.category, ComponentCategory):
            raise ComponentContractError("component.category must be a ComponentCategory")

        inputs = tuple(sorted(self.input_ports, key=lambda item: item.name))
        outputs = tuple(sorted(self.output_ports, key=lambda item: item.name))
        parameters = tuple(sorted(self.parameters, key=lambda item: item.name))
        capabilities = tuple(sorted(self.capabilities))

        _require_unique_names(tuple(item.name for item in inputs), "input ports")
        _require_unique_names(tuple(item.name for item in outputs), "output ports")
        _require_unique_names(tuple(item.name for item in parameters), "parameters")
        _require_unique_names(tuple(item.name for item in capabilities), "capabilities")
        if not outputs:
            raise ComponentContractError("a component must declare at least one output port")
        if not isinstance(self.explanation_template, ManifestObject):
            raise ComponentContractError("component.explanation_template must be a ManifestObject")
        if not isinstance(self.resource_limits, ManifestObject):
            raise ComponentContractError("component.resource_limits must be a ManifestObject")

        object.__setattr__(self, "input_ports", inputs)
        object.__setattr__(self, "output_ports", outputs)
        object.__setattr__(self, "parameters", parameters)
        object.__setattr__(self, "capabilities", capabilities)

    @property
    def component_id(self) -> str:
        """Deterministic identity over complete semantic definition metadata."""
        return component_identity(self)


def _require_unique_names(names: tuple[str, ...], field_name: str) -> None:
    if len(names) != len(set(names)):
        raise ComponentContractError(f"component {field_name} contain duplicate names")


def _type_data(value: StrategyTypeReference) -> dict[str, object]:
    data: dict[str, object] = {"name": value.name, "version": value.version}
    if value.arguments:
        data["arguments"] = [_type_data(item) for item in value.arguments]
    if value.qualifiers.entries:
        data["qualifiers"] = manifest_value_to_data(value.qualifiers)
    return data


def _port_data(value: PortDefinition) -> dict[str, object]:
    return {
        "name": value.name,
        "type": _type_data(value.type_ref),
        "cardinality": value.cardinality.value,
    }


def _parameter_data(value: ParameterDefinition) -> dict[str, object]:
    return {
        "name": value.name,
        "type": _type_data(value.type_ref),
        "required": value.required,
        "has_default": value.has_default,
        "default": manifest_value_to_data(value.default) if value.has_default else None,
    }


def component_definition_data(definition: ComponentDefinition) -> dict[str, object]:
    """Return complete canonical identity material for one Component Type."""
    return {
        "namespace": definition.namespace,
        "name": definition.name,
        "version": definition.version,
        "category": definition.category.value,
        "input_ports": [_port_data(item) for item in definition.input_ports],
        "output_ports": [_port_data(item) for item in definition.output_ports],
        "parameters": [_parameter_data(item) for item in definition.parameters],
        "capabilities": [
            {"name": item.name, "version": item.version} for item in definition.capabilities
        ],
        "algorithm_version": definition.algorithm_version,
        "explanation_template": manifest_value_to_data(definition.explanation_template),
        "resource_limits": manifest_value_to_data(definition.resource_limits),
    }


def component_identity(definition: ComponentDefinition) -> str:
    """Derive the pinned v1 deterministic Component Type identity."""
    payload = {
        "identity_namespace": COMPONENT_IDENTITY_NAMESPACE,
        "identity_version": COMPONENT_IDENTITY_VERSION,
        "component": component_definition_data(definition),
    }
    return hashlib.sha256(canonical_strategy_json(payload)).hexdigest()


class BaseComponent(ABC):
    """Stateless pure evaluator contract implemented by every Component Type.

    Implementations must declare ``__slots__ = ()``, retain no mutable or
    hidden state, and derive outputs only from the supplied immutable inputs
    and effective parameters. Core invokes this method exactly once per node.
    """

    __slots__ = ()
    definition: ComponentDefinition

    @abstractmethod
    def evaluate(self, inputs: ComponentValues, parameters: ComponentValues) -> ComponentValues:
        """Return complete immutable typed outputs or raise a deterministic error."""
        raise NotImplementedError
