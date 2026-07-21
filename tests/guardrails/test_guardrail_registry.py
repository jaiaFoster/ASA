"""ASA-CORE-006: guardrail registry tests."""
from __future__ import annotations

import pytest

from guardrails.errors import DuplicateGuardrailRegistrationError, UnknownGuardrailIdError
from guardrails.registry import DEFAULT_REGISTRY, GuardrailRegistry


def _stub_check(opportunity, params):
    return True, "stub"


class TestExplicitRegistration:
    def test_register_and_get(self):
        reg = GuardrailRegistry()
        reg.register("custom_guardrail", "v1", _stub_check)
        definition = reg.get("custom_guardrail")
        assert definition.guardrail_id == "custom_guardrail"
        assert definition.guardrail_version == "v1"
        assert definition.check is _stub_check

    def test_duplicate_registration_rejected(self):
        reg = GuardrailRegistry()
        reg.register("custom_guardrail", "v1", _stub_check)
        with pytest.raises(DuplicateGuardrailRegistrationError):
            reg.register("custom_guardrail", "v2", _stub_check)

    def test_unknown_id_lookup_raises(self):
        reg = GuardrailRegistry()
        with pytest.raises(UnknownGuardrailIdError):
            reg.get("nonexistent")

    def test_is_registered(self):
        reg = GuardrailRegistry()
        assert not reg.is_registered("custom_guardrail")
        reg.register("custom_guardrail", "v1", _stub_check)
        assert reg.is_registered("custom_guardrail")

    def test_deterministic_lookup(self):
        reg = GuardrailRegistry()
        reg.register("a", "v1", _stub_check)
        a1 = reg.get("a")
        a2 = reg.get("a")
        assert a1 is a2

    def test_registered_ids_sorted_and_deterministic(self):
        reg = GuardrailRegistry()
        reg.register("zebra", "v1", _stub_check)
        reg.register("alpha", "v1", _stub_check)
        assert reg.registered_ids() == ("alpha", "zebra")

    def test_separate_registries_are_independent(self):
        reg1 = GuardrailRegistry()
        reg2 = GuardrailRegistry()
        reg1.register("only_in_one", "v1", _stub_check)
        assert reg1.is_registered("only_in_one")
        assert not reg2.is_registered("only_in_one")


class TestDefaultRegistry:
    def test_all_five_required_guardrails_present(self):
        required = {
            "minimum_evidence_confidence", "maximum_capital_required",
            "maximum_loss", "allowed_time_horizon", "placeholder_metrics_rejection",
        }
        assert required <= set(DEFAULT_REGISTRY.registered_ids())

    def test_exactly_five_guardrails_registered(self):
        assert len(DEFAULT_REGISTRY.registered_ids()) == 5

    def test_registering_a_duplicate_on_default_registry_rejected(self):
        with pytest.raises(DuplicateGuardrailRegistrationError):
            DEFAULT_REGISTRY.register("maximum_loss", "v2", _stub_check)

    def test_default_registry_lookup_is_deterministic(self):
        a = DEFAULT_REGISTRY.get("maximum_loss")
        b = DEFAULT_REGISTRY.get("maximum_loss")
        assert a is b
