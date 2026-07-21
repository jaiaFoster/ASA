"""Portfolio policy registry tests."""

from decimal import Decimal

import pytest

from domain.execution import PortfolioDecisionState
from portfolio.errors import (
    DuplicatePolicyRegistrationError,
    InvalidPolicyOutcomeError,
    InvalidPolicyRegistryError,
)
from portfolio.models import POLICY_NAMES, POLICY_VERSION, PolicyOutcome
from portfolio.policies import buying_power_validation
from portfolio.registry import PolicyRegistry, build_default_registry


def test_default_registry_is_complete_and_canonically_ordered() -> None:
    registry = build_default_registry()
    assert tuple(item.name for item in registry.definitions()) == POLICY_NAMES


def test_duplicate_registration_is_rejected() -> None:
    registry = PolicyRegistry()
    registry.register("buying_power_validation", buying_power_validation)
    with pytest.raises(DuplicatePolicyRegistrationError):
        registry.register("buying_power_validation", buying_power_validation)


def test_incomplete_registry_is_rejected() -> None:
    registry = PolicyRegistry()
    registry.register("buying_power_validation", buying_power_validation)
    with pytest.raises(InvalidPolicyRegistryError):
        registry.validate()


def test_policy_outcome_rejects_invalid_provenance_and_terminal_state() -> None:
    with pytest.raises(InvalidPolicyOutcomeError):
        PolicyOutcome("unknown", POLICY_VERSION, Decimal("0"), "invalid")
    with pytest.raises(InvalidPolicyOutcomeError):
        PolicyOutcome(
            "cash_reserve",
            POLICY_VERSION,
            Decimal("0"),
            "invalid terminal state",
            PortfolioDecisionState.ACCEPT,
        )
