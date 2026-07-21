"""Closed deterministic Strategy Type System (STRAT-006, ASA-ARCH-003)."""
from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal
from enum import Enum

from domain import (
    CanonicalFact,
    EvidenceReference,
    ExpectedOutcomeMetrics,
    Indicator,
    Instrument,
    Opportunity,
)
from strategies.errors import ComponentContractError
from strategies.manifest import (
    ManifestObject,
    canonical_strategy_json,
    validate_semantic_version,
    validate_strategy_identifier,
)

TYPE_SYSTEM_VERSION = "1.0.0"


class StrategyTypeKind(str, Enum):
    PRIMITIVE = "primitive"
    FINANCIAL = "financial"
    DOMAIN = "domain"
    ENUM = "enum"
    OPTIONAL = "optional"
    LIST = "list"
    MAP = "map"


@dataclass(frozen=True, slots=True)
class StrategyTypeReference:
    name: str
    version: str
    arguments: tuple[StrategyTypeReference, ...] = field(default_factory=tuple)
    qualifiers: ManifestObject = field(default_factory=lambda: ManifestObject(()))

    def __post_init__(self) -> None:
        validate_strategy_identifier(self.name, "type.name")
        validate_semantic_version(self.version, "type.version")
        if not all(isinstance(item, StrategyTypeReference) for item in self.arguments):
            raise ComponentContractError("type.arguments must be StrategyTypeReference records")
        if not isinstance(self.qualifiers, ManifestObject):
            raise ComponentContractError("type.qualifiers must be a ManifestObject")


@dataclass(frozen=True, slots=True)
class StrategyTypeDefinition:
    name: str
    version: str
    kind: StrategyTypeKind

    def __post_init__(self) -> None:
        validate_strategy_identifier(self.name, "type_definition.name")
        validate_semantic_version(self.version, "type_definition.version")
        if not isinstance(self.kind, StrategyTypeKind):
            raise ComponentContractError("type_definition.kind must be a StrategyTypeKind")


@dataclass(frozen=True, slots=True)
class TypedValue:
    type_ref: StrategyTypeReference
    value: object

    def __post_init__(self) -> None:
        if not isinstance(self.type_ref, StrategyTypeReference):
            raise ComponentContractError("typed_value.type_ref must be a StrategyTypeReference")
        if _contains_mutable_container(self.value):
            raise ComponentContractError("typed_value.value must not contain mutable containers")


def _contains_mutable_container(value: object) -> bool:
    if isinstance(value, (list, dict, set, bytearray)):
        return True
    if isinstance(value, tuple):
        return any(_contains_mutable_container(item) for item in value)
    return False


@dataclass(frozen=True, slots=True)
class ComponentValues:
    """Immutable named typed values passed across Component ports."""

    entries: tuple[tuple[str, TypedValue], ...]

    def __post_init__(self) -> None:
        normalized = tuple(sorted(self.entries, key=lambda item: item[0]))
        names = tuple(name for name, _ in normalized)
        if any(not isinstance(value, TypedValue) for _, value in normalized):
            raise ComponentContractError("component values must contain TypedValue records")
        for name in names:
            validate_strategy_identifier(name, "component_value.name")
        if len(names) != len(set(names)):
            raise ComponentContractError("component values contain duplicate names")
        object.__setattr__(self, "entries", normalized)

    def get(self, name: str) -> TypedValue:
        for item_name, value in self.entries:
            if item_name == name:
                return value
        raise KeyError(name)


class StrategyTypeSystem:
    """Immutable exact-version type catalog and compatibility validator."""

    __slots__ = ("_definitions", "_identity")

    def __init__(self, definitions: tuple[StrategyTypeDefinition, ...]) -> None:
        ordered = tuple(sorted(definitions, key=lambda item: (item.name, item.version)))
        keys = tuple((item.name, item.version) for item in ordered)
        if len(keys) != len(set(keys)):
            raise ComponentContractError("type system contains duplicate definitions")
        self._definitions = ordered
        payload = [
            {"name": item.name, "version": item.version, "kind": item.kind.value}
            for item in ordered
        ]
        self._identity = hashlib.sha256(
            canonical_strategy_json(
                {
                    "identity_namespace": "asa.strategy_type_system",
                    "type_system_version": TYPE_SYSTEM_VERSION,
                    "definitions": payload,
                }
            )
        ).hexdigest()

    def __setattr__(self, name: str, value: object) -> None:
        if hasattr(self, name):
            raise AttributeError("StrategyTypeSystem is immutable")
        object.__setattr__(self, name, value)

    @property
    def definitions(self) -> tuple[StrategyTypeDefinition, ...]:
        return self._definitions

    @property
    def identity(self) -> str:
        return self._identity

    def resolve(self, reference: StrategyTypeReference) -> StrategyTypeDefinition:
        for definition in self._definitions:
            if (definition.name, definition.version) == (reference.name, reference.version):
                self._validate_shape(reference, definition.kind)
                return definition
        raise ComponentContractError(
            f"unknown Strategy Type: {reference.name}@{reference.version}"
        )

    def compatible(
        self, source: StrategyTypeReference, target: StrategyTypeReference
    ) -> bool:
        self.resolve(source)
        self.resolve(target)
        return source == target

    def validate_value(self, typed: TypedValue) -> None:
        definition = self.resolve(typed.type_ref)
        value = typed.value
        name = definition.name
        valid = _value_matches(name, definition.kind, typed.type_ref, value, self)
        if not valid:
            raise ComponentContractError(
                f"value does not satisfy {typed.type_ref.name}@{typed.type_ref.version}"
            )

    def _validate_shape(
        self, reference: StrategyTypeReference, kind: StrategyTypeKind
    ) -> None:
        expected_arguments = {
            StrategyTypeKind.OPTIONAL: 1,
            StrategyTypeKind.LIST: 1,
            StrategyTypeKind.MAP: 2,
        }.get(kind, 0)
        if len(reference.arguments) != expected_arguments:
            raise ComponentContractError(
                f"{reference.name} requires {expected_arguments} type arguments"
            )
        for argument in reference.arguments:
            self.resolve(argument)
        qualifiers = dict(reference.qualifiers.entries)
        if reference.name == "Money":
            currency = qualifiers.get("currency")
            if not isinstance(currency, str) or len(currency) != 3 or not currency.isupper():
                raise ComponentContractError("Money requires an uppercase ISO currency qualifier")
        elif reference.name == "Enum":
            values = qualifiers.get("values")
            if not isinstance(values, tuple) or not values or not all(
                isinstance(item, str) for item in values
            ):
                raise ComponentContractError("Enum requires a non-empty string values qualifier")
            if len(values) != len(set(values)):
                raise ComponentContractError("Enum values must be unique")
        elif qualifiers:
            raise ComponentContractError(f"{reference.name} does not accept qualifiers")


def _value_matches(
    name: str,
    kind: StrategyTypeKind,
    reference: StrategyTypeReference,
    value: object,
    system: StrategyTypeSystem,
) -> bool:
    if kind is StrategyTypeKind.OPTIONAL:
        if value is None:
            return True
        nested = TypedValue(reference.arguments[0], value)
        try:
            system.validate_value(nested)
        except ComponentContractError:
            return False
        return True
    if kind is StrategyTypeKind.LIST:
        if not isinstance(value, tuple):
            return False
        return all(_valid_nested(system, reference.arguments[0], item) for item in value)
    if kind is StrategyTypeKind.MAP:
        if not isinstance(value, tuple):
            return False
        return all(
            isinstance(item, tuple)
            and len(item) == 2
            and _valid_nested(system, reference.arguments[0], item[0])
            and _valid_nested(system, reference.arguments[1], item[1])
            for item in value
        )
    if name == "Boolean":
        return isinstance(value, bool)
    if name == "Integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if name in {"Decimal", "Ratio", "Quantity", "Money"}:
        return isinstance(value, Decimal) and value.is_finite()
    if name == "Probability":
        return isinstance(value, Decimal) and value.is_finite() and Decimal(0) <= value <= Decimal(1)
    if name == "Text":
        return isinstance(value, str)
    if name == "Date":
        return isinstance(value, date) and not isinstance(value, datetime)
    if name == "Instant":
        return isinstance(value, datetime) and value.tzinfo is not None and value.utcoffset() is not None
    if name == "Currency":
        return isinstance(value, str) and len(value) == 3 and value.isupper()
    if name == "Enum":
        values = dict(reference.qualifiers.entries).get("values")
        return isinstance(value, str) and isinstance(values, tuple) and value in values
    domain_types: dict[str, type[object]] = {
        "Instrument": Instrument,
        "CanonicalFact": CanonicalFact,
        "IndicatorValue": Indicator,
        "Evidence": EvidenceReference,
        "ExpectedOutcomeMetrics": ExpectedOutcomeMetrics,
        "Opportunity": Opportunity,
    }
    expected = domain_types.get(name)
    return expected is not None and isinstance(value, expected)


def _valid_nested(
    system: StrategyTypeSystem, reference: StrategyTypeReference, value: object
) -> bool:
    try:
        system.validate_value(TypedValue(reference, value))
    except ComponentContractError:
        return False
    return True


def build_default_type_system() -> StrategyTypeSystem:
    primitive = ("Boolean", "Integer", "Decimal", "Text", "Date", "Instant")
    financial = ("Currency", "Money", "Ratio", "Probability", "Quantity")
    domain = (
        "Instrument",
        "CanonicalFact",
        "IndicatorValue",
        "Evidence",
        "ExpectedOutcomeMetrics",
        "Opportunity",
    )
    definitions = tuple(
        StrategyTypeDefinition(name, "1.0.0", StrategyTypeKind.PRIMITIVE)
        for name in primitive
    ) + tuple(
        StrategyTypeDefinition(name, "1.0.0", StrategyTypeKind.FINANCIAL)
        for name in financial
    ) + tuple(
        StrategyTypeDefinition(name, "1.0.0", StrategyTypeKind.DOMAIN)
        for name in domain
    ) + (
        StrategyTypeDefinition("Enum", "1.0.0", StrategyTypeKind.ENUM),
        StrategyTypeDefinition("Optional", "1.0.0", StrategyTypeKind.OPTIONAL),
        StrategyTypeDefinition("List", "1.0.0", StrategyTypeKind.LIST),
        StrategyTypeDefinition("Map", "1.0.0", StrategyTypeKind.MAP),
    )
    return StrategyTypeSystem(definitions)


DEFAULT_TYPE_SYSTEM = build_default_type_system()
