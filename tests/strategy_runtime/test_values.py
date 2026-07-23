"""SPRINT-009R/EPIC-R2: TypedValue -- round-tripping every supported_type
(decimal, integer, boolean, string, datetime, duration, structured)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from domain.values import DomainInvariantError
from strategy_runtime.values import TypedValue, ValueType


class TestRoundTrip:
    def test_decimal_round_trips(self) -> None:
        value = TypedValue.of_decimal(Decimal("12.50"))
        assert value.value_type is ValueType.DECIMAL
        assert value.native() == Decimal("12.50")

    def test_integer_round_trips(self) -> None:
        assert TypedValue.of_integer(42).native() == 42

    def test_boolean_true_and_false_round_trip(self) -> None:
        assert TypedValue.of_boolean(True).native() is True
        assert TypedValue.of_boolean(False).native() is False

    def test_string_round_trips_including_empty(self) -> None:
        assert TypedValue.of_string("hello").native() == "hello"
        assert TypedValue.of_string("").native() == ""

    def test_datetime_round_trips(self) -> None:
        value = datetime(2026, 1, 1, 12, 30, tzinfo=UTC)
        assert TypedValue.of_datetime(value).native() == value

    def test_naive_datetime_is_rejected(self) -> None:
        with pytest.raises(DomainInvariantError):
            TypedValue.of_datetime(datetime(2026, 1, 1))

    def test_duration_round_trips(self) -> None:
        value = timedelta(hours=1, minutes=30)
        assert TypedValue.of_duration(value).native() == value

    def test_structured_mapping_round_trips(self) -> None:
        value = {"legs": [{"strike": 100, "side": "long"}], "count": 2}
        assert TypedValue.of_structured(value).native() == value

    def test_structured_sequence_round_trips(self) -> None:
        value = [1, "two", False, None]
        assert TypedValue.of_structured(value).native() == value


class TestJsonEncoding:
    def test_to_json_and_from_json_round_trip_for_every_kind(self) -> None:
        originals = (
            TypedValue.of_decimal(Decimal("3.14")),
            TypedValue.of_integer(-7),
            TypedValue.of_boolean(True),
            TypedValue.of_string("plain"),
            TypedValue.of_datetime(datetime(2026, 3, 4, tzinfo=UTC)),
            TypedValue.of_duration(timedelta(seconds=90)),
            TypedValue.of_structured({"a": 1}),
        )
        for original in originals:
            restored = TypedValue.from_json(original.to_json())
            assert restored == original
            assert restored.native() == original.native()

    def test_from_json_rejects_an_unknown_type(self) -> None:
        with pytest.raises(DomainInvariantError):
            TypedValue.from_json({"type": "not_a_real_type", "value": "x"})


class TestConstructionValidation:
    def test_invalid_decimal_encoding_is_rejected_at_construction(self) -> None:
        with pytest.raises(DomainInvariantError):
            TypedValue(ValueType.DECIMAL, "not-a-number")

    def test_invalid_boolean_encoding_is_rejected_at_construction(self) -> None:
        with pytest.raises(DomainInvariantError):
            TypedValue(ValueType.BOOLEAN, "yes")

    def test_empty_encoding_is_rejected_for_non_string_kinds(self) -> None:
        with pytest.raises(DomainInvariantError):
            TypedValue(ValueType.INTEGER, "")

    def test_empty_encoding_is_accepted_for_string(self) -> None:
        assert TypedValue(ValueType.STRING, "").native() == ""
