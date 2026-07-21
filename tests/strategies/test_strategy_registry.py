"""ASA-CORE-005: strategy registry tests."""
from __future__ import annotations

import pytest

from strategies.errors import DuplicateStrategyRegistrationError, UnknownStrategyIdError
from strategies.registry import DEFAULT_REGISTRY, StrategyRegistry


def _stub_compute(indicators, facts, params):
    return None


class TestExplicitRegistration:
    def test_register_and_get(self):
        reg = StrategyRegistry()
        reg.register("custom_strategy", "v1", _stub_compute)
        definition = reg.get("custom_strategy")
        assert definition.strategy_id == "custom_strategy"
        assert definition.strategy_version == "v1"
        assert definition.compute is _stub_compute

    def test_duplicate_registration_rejected(self):
        reg = StrategyRegistry()
        reg.register("custom_strategy", "v1", _stub_compute)
        with pytest.raises(DuplicateStrategyRegistrationError):
            reg.register("custom_strategy", "v2", _stub_compute)

    def test_unknown_id_lookup_raises(self):
        reg = StrategyRegistry()
        with pytest.raises(UnknownStrategyIdError):
            reg.get("nonexistent")

    def test_is_registered(self):
        reg = StrategyRegistry()
        assert not reg.is_registered("custom_strategy")
        reg.register("custom_strategy", "v1", _stub_compute)
        assert reg.is_registered("custom_strategy")

    def test_deterministic_lookup(self):
        reg = StrategyRegistry()
        reg.register("a", "v1", _stub_compute)
        a1 = reg.get("a")
        a2 = reg.get("a")
        assert a1 is a2

    def test_registered_ids_sorted_and_deterministic(self):
        reg = StrategyRegistry()
        reg.register("zebra", "v1", _stub_compute)
        reg.register("alpha", "v1", _stub_compute)
        assert reg.registered_ids() == ("alpha", "zebra")

    def test_separate_registries_are_independent(self):
        reg1 = StrategyRegistry()
        reg2 = StrategyRegistry()
        reg1.register("only_in_one", "v1", _stub_compute)
        assert reg1.is_registered("only_in_one")
        assert not reg2.is_registered("only_in_one")


class TestDefaultRegistry:
    def test_all_three_required_strategies_present(self):
        required = {"moving_average_crossover", "breakout", "momentum"}
        assert required <= set(DEFAULT_REGISTRY.registered_ids())

    def test_registering_a_duplicate_on_default_registry_rejected(self):
        with pytest.raises(DuplicateStrategyRegistrationError):
            DEFAULT_REGISTRY.register("breakout", "v2", _stub_compute)

    def test_default_registry_lookup_is_deterministic(self):
        a = DEFAULT_REGISTRY.get("momentum")
        b = DEFAULT_REGISTRY.get("momentum")
        assert a is b
