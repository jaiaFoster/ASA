"""STRAT-006: closed deterministic Strategy Type System tests."""
from __future__ import annotations

from dataclasses import FrozenInstanceError
from datetime import date, datetime, timezone
from decimal import Decimal

import pytest

from strategies import (
    DEFAULT_TYPE_SYSTEM,
    TYPE_SYSTEM_VERSION,
    ComponentContractError,
    ComponentValues,
    ManifestObject,
    StrategyTypeDefinition,
    StrategyTypeKind,
    StrategyTypeReference,
    StrategyTypeSystem,
    TypedValue,
    build_default_type_system,
)
from tests.instrument_helpers import TEST_INSTRUMENT


def ref(
    name: str,
    *arguments: StrategyTypeReference,
    qualifiers: ManifestObject | None = None,
) -> StrategyTypeReference:
    return StrategyTypeReference(
        name,
        "1.0.0",
        arguments,
        qualifiers or ManifestObject(()),
    )


class TestCatalog:
    def test_version_and_closed_v1_catalog_are_pinned(self):
        assert TYPE_SYSTEM_VERSION == "1.0.0"
        assert {item.name for item in DEFAULT_TYPE_SYSTEM.definitions} == {
            "Boolean", "Integer", "Decimal", "Text", "Date", "Instant",
            "Currency", "Money", "Ratio", "Probability", "Quantity",
            "Instrument", "CanonicalFact", "IndicatorValue", "Evidence",
            "ExpectedOutcomeMetrics", "Opportunity", "Enum", "Optional", "List", "Map",
        }

    def test_catalog_identity_is_deterministic_and_order_independent(self):
        first = build_default_type_system()
        second = StrategyTypeSystem(tuple(reversed(first.definitions)))
        assert first.definitions == second.definitions
        assert first.identity == second.identity
        assert first.identity == (
            "a495534099091cbee2d0a4293091f45312b16ab151344d86e6d0da29271aeb79"
        )

    def test_duplicate_exact_definition_is_rejected(self):
        definition = StrategyTypeDefinition("Text", "1.0.0", StrategyTypeKind.PRIMITIVE)
        with pytest.raises(ComponentContractError, match="duplicate"):
            StrategyTypeSystem((definition, definition))

    def test_catalog_is_immutable_after_construction(self):
        system = build_default_type_system()
        with pytest.raises(AttributeError, match="immutable"):
            system._definitions = ()  # type: ignore[misc]

    def test_unknown_or_inexact_version_fails_closed(self):
        with pytest.raises(ComponentContractError, match="unknown"):
            DEFAULT_TYPE_SYSTEM.resolve(StrategyTypeReference("Text", "2.0.0"))


class TestCompatibility:
    def test_exact_nominal_type_is_compatible(self):
        assert DEFAULT_TYPE_SYSTEM.compatible(ref("Decimal"), ref("Decimal"))

    def test_no_implicit_integer_to_decimal_widening(self):
        assert not DEFAULT_TYPE_SYSTEM.compatible(ref("Integer"), ref("Decimal"))

    def test_no_optional_unwrapping(self):
        optional = ref("Optional", ref("Text"))
        assert not DEFAULT_TYPE_SYSTEM.compatible(optional, ref("Text"))

    def test_money_compatibility_requires_equal_currency(self):
        usd = ref("Money", qualifiers=ManifestObject((("currency", "USD"),)))
        eur = ref("Money", qualifiers=ManifestObject((("currency", "EUR"),)))
        assert DEFAULT_TYPE_SYSTEM.compatible(usd, usd)
        assert not DEFAULT_TYPE_SYSTEM.compatible(usd, eur)

    @pytest.mark.parametrize(
        "value",
        [
            ref("Optional"),
            ref("Optional", ref("Text"), ref("Text")),
            ref("List"),
            ref("Map", ref("Text")),
        ],
    )
    def test_container_arity_is_exact(self, value: StrategyTypeReference):
        with pytest.raises(ComponentContractError, match="arguments"):
            DEFAULT_TYPE_SYSTEM.resolve(value)

    def test_non_parameterized_types_reject_arguments(self):
        with pytest.raises(ComponentContractError, match="arguments"):
            DEFAULT_TYPE_SYSTEM.resolve(ref("Text", ref("Text")))

    def test_qualifiers_are_closed(self):
        qualified_text = ref("Text", qualifiers=ManifestObject((("format", "x"),)))
        with pytest.raises(ComponentContractError, match="qualifiers"):
            DEFAULT_TYPE_SYSTEM.resolve(qualified_text)


class TestValueValidation:
    @pytest.mark.parametrize(
        ("type_ref", "value"),
        [
            (ref("Boolean"), True),
            (ref("Integer"), 4),
            (ref("Decimal"), Decimal("1.25")),
            (ref("Text"), "value"),
            (ref("Date"), date(2026, 7, 21)),
            (ref("Instant"), datetime(2026, 7, 21, tzinfo=timezone.utc)),
            (ref("Currency"), "USD"),
            (ref("Probability"), Decimal("0.5")),
            (ref("Instrument"), TEST_INSTRUMENT),
            (ref("Optional", ref("Text")), None),
            (ref("List", ref("Integer")), (1, 2, 3)),
            (ref("Map", ref("Text"), ref("Integer")), (("a", 1), ("b", 2))),
        ],
    )
    def test_valid_values(self, type_ref: StrategyTypeReference, value: object):
        DEFAULT_TYPE_SYSTEM.validate_value(TypedValue(type_ref, value))

    @pytest.mark.parametrize(
        ("type_ref", "value"),
        [
            (ref("Boolean"), 1),
            (ref("Integer"), True),
            (ref("Decimal"), "1.25"),
            (ref("Decimal"), Decimal("NaN")),
            (ref("Date"), datetime(2026, 7, 21)),
            (ref("Instant"), datetime(2026, 7, 21)),
            (ref("Currency"), "usd"),
            (ref("Probability"), Decimal("1.1")),
            (ref("List", ref("Integer")), [1, 2]),
        ],
    )
    def test_invalid_values_fail_closed(self, type_ref: StrategyTypeReference, value: object):
        with pytest.raises(ComponentContractError):
            DEFAULT_TYPE_SYSTEM.validate_value(TypedValue(type_ref, value))

    def test_enum_values_are_bounded(self):
        enum = ref("Enum", qualifiers=ManifestObject((("values", ("BUY", "SELL")),)))
        DEFAULT_TYPE_SYSTEM.validate_value(TypedValue(enum, "BUY"))
        with pytest.raises(ComponentContractError):
            DEFAULT_TYPE_SYSTEM.validate_value(TypedValue(enum, "HOLD"))


class TestTypedComponentValues:
    def test_named_values_are_immutable_and_sorted(self):
        values = ComponentValues(
            (("z", TypedValue(ref("Integer"), 2)), ("a", TypedValue(ref("Text"), "x")))
        )
        assert tuple(name for name, _ in values.entries) == ("a", "z")
        assert values.get("z").value == 2
        with pytest.raises(FrozenInstanceError):
            values.entries = ()  # type: ignore[misc]

    def test_duplicate_names_are_rejected(self):
        value = TypedValue(ref("Text"), "x")
        with pytest.raises(ComponentContractError, match="duplicate"):
            ComponentValues((("same", value), ("same", value)))

    @pytest.mark.parametrize("value", [[1], {"x": 1}, {1}, (1, [2])])
    def test_typed_values_reject_mutable_nested_containers(self, value: object):
        with pytest.raises(ComponentContractError, match="mutable"):
            TypedValue(ref("List", ref("Integer")), value)
