"""Explicit deterministic portfolio-policy registry."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from domain.operational import PortfolioSnapshot, ProposedPosition
from portfolio.errors import DuplicatePolicyRegistrationError, InvalidPolicyRegistryError
from portfolio.models import POLICY_NAMES, PolicyOutcome, PortfolioParameters
from portfolio.policies import (
    buying_power_validation,
    cash_reserve,
    duplicate_position,
    maximum_position_size,
    maximum_sector_exposure,
    maximum_single_asset_exposure,
)

Policy = Callable[[ProposedPosition, PortfolioSnapshot, PortfolioParameters], PolicyOutcome]


@dataclass(frozen=True, slots=True)
class PolicyDefinition:
    name: str
    policy: Policy


class PolicyRegistry:
    def __init__(self) -> None:
        self._definitions: dict[str, PolicyDefinition] = {}

    def register(self, name: str, policy: Policy) -> None:
        if name in self._definitions:
            raise DuplicatePolicyRegistrationError(name)
        self._definitions[name] = PolicyDefinition(name, policy)

    def definitions(self) -> tuple[PolicyDefinition, ...]:
        return tuple(self._definitions[name] for name in sorted(self._definitions))

    def validate(self) -> None:
        if tuple(item.name for item in self.definitions()) != POLICY_NAMES:
            raise InvalidPolicyRegistryError("portfolio registry must contain all pinned v1 policies")


def build_default_registry() -> PolicyRegistry:
    registry = PolicyRegistry()
    registry.register("buying_power_validation", buying_power_validation)
    registry.register("cash_reserve", cash_reserve)
    registry.register("duplicate_position", duplicate_position)
    registry.register("maximum_position_size", maximum_position_size)
    registry.register("maximum_sector_exposure", maximum_sector_exposure)
    registry.register("maximum_single_asset_exposure", maximum_single_asset_exposure)
    registry.validate()
    return registry
