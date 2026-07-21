"""ASA-CORE-002: deterministic Observation identity tests with pinned vectors."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest

from domain.values import DomainInvariantError
from observation import IDENTITY_NAMESPACE, IDENTITY_VERSION, observation_identity

T = datetime(2026, 7, 21, 14, 30, tzinfo=timezone.utc)
T_EST = datetime(2026, 7, 21, 10, 30, tzinfo=timezone(timedelta(hours=-4)))  # same instant

VALUE = (("currency", "USD"), ("price", Decimal("201.55")), ("symbol", "AAPL"))
VALUE_UNSORTED = (("symbol", "AAPL"), ("price", Decimal("201.550")), ("currency", "USD"))


class TestIdentityProperties:
    def test_same_input_same_id(self):
        a = observation_identity("prov-a", "market_price", T, VALUE)
        b = observation_identity("prov-a", "market_price", T, VALUE)
        assert a == b

    def test_mapping_order_does_not_change_id(self):
        a = observation_identity("prov-a", "market_price", T, VALUE)
        b = observation_identity("prov-a", "market_price", T, VALUE_UNSORTED)
        assert a == b

    def test_different_provider_changes_id(self):
        a = observation_identity("prov-a", "market_price", T, VALUE)
        b = observation_identity("prov-b", "market_price", T, VALUE)
        assert a != b

    def test_different_type_changes_id(self):
        a = observation_identity("prov-a", "market_price", T, VALUE)
        b = observation_identity("prov-a", "quote", T, VALUE)
        assert a != b

    def test_different_effective_time_changes_id(self):
        a = observation_identity("prov-a", "market_price", T, VALUE)
        b = observation_identity("prov-a", "market_price", T + timedelta(seconds=1), VALUE)
        assert a != b

    def test_different_value_changes_id(self):
        other = (("currency", "USD"), ("price", Decimal("201.56")), ("symbol", "AAPL"))
        a = observation_identity("prov-a", "market_price", T, VALUE)
        b = observation_identity("prov-a", "market_price", T, other)
        assert a != b

    def test_bool_and_int_produce_different_ids(self):
        a = observation_identity("prov-a", "flag", T, True)
        b = observation_identity("prov-a", "flag", T, 1)
        assert a != b

    def test_timezone_equivalent_datetimes_normalize_consistently(self):
        a = observation_identity("prov-a", "market_price", T, VALUE)
        b = observation_identity("prov-a", "market_price", T_EST, VALUE)
        assert a == b

    def test_output_is_lowercase_hex_sha256(self):
        identity = observation_identity("prov-a", "market_price", T, VALUE)
        assert len(identity) == 64
        assert identity == identity.lower()
        int(identity, 16)  # parses as hex

    def test_naive_effective_time_rejected(self):
        with pytest.raises(DomainInvariantError):
            observation_identity("prov-a", "market_price",
                                 datetime(2026, 7, 21), VALUE)

    def test_empty_provider_rejected(self):
        with pytest.raises(DomainInvariantError):
            observation_identity("", "market_price", T, VALUE)

    def test_algorithm_version_pinned(self):
        assert IDENTITY_NAMESPACE == "asa.observation"
        assert IDENTITY_VERSION == "v1"


class TestPinnedRegressionVectors:
    """Pinned v1 identity vectors. A failure here means the identity
    algorithm changed — which requires a new version, never a silent edit."""

    VECTORS = {
        # (provider_id, observation_type, effective_time, value) -> sha256 hex
        ("synthetic-deterministic", "market_price", "aapl"):
            "4978487ce14a049704f9c96dd4bf4e3f63263de35d7e9675b1f7a4334f9d9eca",
        ("prov-a", "count", "int"):
            "48200673daa4a1360d232756e6718fd7851ab00266b46428371ca246dbc58bc2",
        ("prov-a", "count", "bool"):
            "05bc3ee8b248edb2d53b8b470407d79a2821610a625d5983954ed2558d06597f",
        ("prov-a", "series", "seq"):
            "9fe69b6494965f99dbf1725211434e607bc3292dc4ff022220c465487f466de0",
        ("prov-a", "empty", "none"):
            "31616d9d04f92a7ec2700c33e376db71c5c2ceaec568a32efdb5cf0a0793be26",
    }

    def test_market_price_vector(self):
        assert observation_identity(
            "synthetic-deterministic", "market_price", T, VALUE
        ) == self.VECTORS[("synthetic-deterministic", "market_price", "aapl")]

    def test_scalar_int_vector(self):
        assert observation_identity("prov-a", "count", T, 1) == \
            self.VECTORS[("prov-a", "count", "int")]

    def test_scalar_bool_vector(self):
        assert observation_identity("prov-a", "count", T, True) == \
            self.VECTORS[("prov-a", "count", "bool")]

    def test_sequence_vector(self):
        assert observation_identity("prov-a", "series", T, (1, 2, 3)) == \
            self.VECTORS[("prov-a", "series", "seq")]

    def test_none_vector(self):
        assert observation_identity("prov-a", "empty", T, None) == \
            self.VECTORS[("prov-a", "empty", "none")]
