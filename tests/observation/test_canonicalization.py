"""ASA-CORE-002: canonical form and deterministic serialization tests."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest

from domain.values import DomainInvariantError
from observation.canonicalization import canonicalize_value, serialize_canonical

UTC_T = datetime(2026, 7, 21, 14, 30, tzinfo=timezone.utc)
EST_T = datetime(2026, 7, 21, 10, 30, tzinfo=timezone(timedelta(hours=-4)))  # same instant


class TestCanonicalForm:
    def test_mapping_keys_sorted(self):
        value = (("symbol", "AAPL"), ("currency", "USD"), ("price", 1))
        assert canonicalize_value(value) == (
            ("currency", "USD"), ("price", 1), ("symbol", "AAPL"))

    def test_nested_mapping_keys_sorted(self):
        value = (("outer", (("b", 2), ("a", 1))),)
        assert canonicalize_value(value) == (("outer", (("a", 1), ("b", 2))),)

    def test_sequence_order_preserved(self):
        assert canonicalize_value((3, 1, 2)) == (3, 1, 2)

    def test_scalars_unchanged(self):
        assert canonicalize_value(Decimal("1.5")) == Decimal("1.5")
        assert canonicalize_value(None) is None

    def test_equivalent_mappings_identical_canonical_representation(self):
        a = (("x", 1), ("y", 2))
        b = (("y", 2), ("x", 1))
        assert canonicalize_value(a) == canonicalize_value(b)
        assert serialize_canonical(a) == serialize_canonical(b)

    def test_non_normalized_value_rejected(self):
        with pytest.raises(DomainInvariantError):
            canonicalize_value([1, 2])

    def test_duplicate_keys_rejected(self):
        with pytest.raises(DomainInvariantError):
            canonicalize_value((("k", 1), ("k", 2)))


class TestSerialization:
    def test_bool_and_int_serialize_differently(self):
        assert serialize_canonical(True) != serialize_canonical(1)
        assert serialize_canonical(False) != serialize_canonical(0)

    def test_mapping_and_pair_sequence_serialize_differently(self):
        mapping = (("k", 1),)
        # A sequence containing a non-pair element is a sequence, not a mapping
        sequence = (("k", 1), 2)
        assert serialize_canonical(mapping).startswith("m:")
        assert serialize_canonical(sequence).startswith("l:")

    def test_decimal_never_passes_through_float(self):
        # A value only representable exactly in Decimal must round-trip exactly
        exact = Decimal("0.1000000000000000000000000000001")
        serialized = serialize_canonical(exact)
        assert "0.1000000000000000000000000000001" in serialized
        assert serialized != serialize_canonical(0.1)

    def test_decimal_exponent_forms_serialize_identically(self):
        assert serialize_canonical(Decimal("201.55")) == serialize_canonical(Decimal("201.550"))
        assert serialize_canonical(Decimal("1E+2")) == serialize_canonical(Decimal("100"))

    def test_timezone_equivalent_datetimes_serialize_identically(self):
        assert serialize_canonical(UTC_T) == serialize_canonical(EST_T)

    def test_different_instants_serialize_differently(self):
        assert serialize_canonical(UTC_T) != serialize_canonical(UTC_T + timedelta(seconds=1))

    def test_strings_are_length_prefixed(self):
        # Embedded separators cannot break framing
        tricky = 's:5:hello,("a"'
        assert serialize_canonical(tricky).startswith(
            f"s:{len(tricky.encode('utf-8'))}:")

    def test_none_serializes_distinctly(self):
        assert serialize_canonical(None) == "z:"
        assert serialize_canonical(None) != serialize_canonical("")
        assert serialize_canonical(None) != serialize_canonical(0)
