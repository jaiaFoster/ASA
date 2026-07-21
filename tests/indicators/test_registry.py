"""ASA-CORE-004: indicator registry tests."""
from __future__ import annotations

from decimal import Decimal

import pytest

from indicators.errors import DuplicateIndicatorRegistrationError, UnknownIndicatorTypeError
from indicators.registry import DEFAULT_REGISTRY, IndicatorRegistry


def _stub_compute(facts, params):
    return Decimal("1"), facts


class TestExplicitRegistration:
    def test_register_and_get(self):
        reg = IndicatorRegistry()
        reg.register("custom_indicator", "v1", _stub_compute)
        definition = reg.get("custom_indicator")
        assert definition.indicator_type == "custom_indicator"
        assert definition.logic_version == "v1"
        assert definition.compute is _stub_compute

    def test_duplicate_registration_rejected(self):
        reg = IndicatorRegistry()
        reg.register("custom_indicator", "v1", _stub_compute)
        with pytest.raises(DuplicateIndicatorRegistrationError):
            reg.register("custom_indicator", "v2", _stub_compute)

    def test_unknown_type_lookup_raises(self):
        reg = IndicatorRegistry()
        with pytest.raises(UnknownIndicatorTypeError):
            reg.get("nonexistent")

    def test_is_registered(self):
        reg = IndicatorRegistry()
        assert not reg.is_registered("custom_indicator")
        reg.register("custom_indicator", "v1", _stub_compute)
        assert reg.is_registered("custom_indicator")

    def test_deterministic_lookup(self):
        reg = IndicatorRegistry()
        reg.register("a", "v1", _stub_compute)
        reg.register("b", "v1", _stub_compute)
        a1 = reg.get("a")
        a2 = reg.get("a")
        assert a1 is a2  # same registered definition, every lookup

    def test_registered_types_sorted_and_deterministic(self):
        reg = IndicatorRegistry()
        reg.register("zebra", "v1", _stub_compute)
        reg.register("alpha", "v1", _stub_compute)
        assert reg.registered_types() == ("alpha", "zebra")

    def test_separate_registries_are_independent(self):
        reg1 = IndicatorRegistry()
        reg2 = IndicatorRegistry()
        reg1.register("only_in_one", "v1", _stub_compute)
        assert reg1.is_registered("only_in_one")
        assert not reg2.is_registered("only_in_one")


class TestDefaultRegistry:
    def test_all_six_required_indicators_present(self):
        required = {
            "latest_price", "price_change_percent", "simple_moving_average",
            "exponential_moving_average", "rolling_high", "rolling_low",
        }
        assert required <= set(DEFAULT_REGISTRY.registered_types())

    def test_registering_a_duplicate_on_default_registry_rejected(self):
        with pytest.raises(DuplicateIndicatorRegistrationError):
            DEFAULT_REGISTRY.register("latest_price", "v2", _stub_compute)

    def test_default_registry_lookup_is_deterministic(self):
        a = DEFAULT_REGISTRY.get("simple_moving_average")
        b = DEFAULT_REGISTRY.get("simple_moving_average")
        assert a is b
