"""Immutable Portfolio Engine policy inputs and outcomes."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from domain.execution import PortfolioDecisionState
from domain.values import require_finite_decimal, require_unit_interval
from portfolio.errors import InvalidPolicyOutcomeError, InvalidPortfolioParameterError

PORTFOLIO_ALGORITHM_VERSION = "v1"
PORTFOLIO_IDENTITY_NAMESPACE = "asa.portfolio_decision"
ALLOCATION_QUANTUM = Decimal("0.000000000001")
POLICY_VERSION = "v1"
POLICY_NAMES = (
    "buying_power_validation",
    "cash_reserve",
    "duplicate_position",
    "maximum_position_size",
    "maximum_sector_exposure",
    "maximum_single_asset_exposure",
)


@dataclass(frozen=True, slots=True)
class PortfolioParameters:
    """Complete v1 portfolio policy with no hidden runtime configuration."""

    cash_reserve_ratio: Decimal = Decimal("0.10")
    maximum_position_allocation: Decimal = Decimal("0.20")
    maximum_sector_exposure: Decimal = Decimal("0.40")
    maximum_single_asset_exposure: Decimal = Decimal("0.20")

    def __post_init__(self) -> None:
        for name in self.__dataclass_fields__:
            value = getattr(self, name)
            try:
                require_finite_decimal(value, "PortfolioParameters", name)
                require_unit_interval(value, "PortfolioParameters", name)
            except (TypeError, ValueError) as error:
                raise InvalidPortfolioParameterError(str(error)) from error
        if self.maximum_position_allocation == 0:
            raise InvalidPortfolioParameterError(
                "maximum_position_allocation must be greater than zero"
            )
        if self.maximum_sector_exposure == 0:
            raise InvalidPortfolioParameterError(
                "maximum_sector_exposure must be greater than zero"
            )
        if self.maximum_single_asset_exposure == 0:
            raise InvalidPortfolioParameterError(
                "maximum_single_asset_exposure must be greater than zero"
            )

    def canonical_items(self) -> tuple[tuple[str, Decimal], ...]:
        return tuple(sorted((name, getattr(self, name)) for name in self.__dataclass_fields__))


@dataclass(frozen=True, slots=True)
class PolicyOutcome:
    """One deterministic policy's allocation ceiling and disposition."""

    policy_name: str
    policy_version: str
    maximum_allocation: Decimal
    reason: str
    terminal_state: PortfolioDecisionState | None = None

    def __post_init__(self) -> None:
        if self.policy_name not in POLICY_NAMES:
            raise InvalidPolicyOutcomeError("policy outcome name is not registered in v1")
        if not self.policy_version or self.policy_version != self.policy_version.strip():
            raise InvalidPolicyOutcomeError("policy outcome version must be normalized text")
        if not self.reason or self.reason != self.reason.strip():
            raise InvalidPolicyOutcomeError("policy outcome reason must be normalized text")
        try:
            require_finite_decimal(
                self.maximum_allocation,
                "PolicyOutcome",
                "maximum_allocation",
            )
        except (TypeError, ValueError) as error:
            raise InvalidPolicyOutcomeError(str(error)) from error
        if self.maximum_allocation < 0:
            raise InvalidPolicyOutcomeError("policy outcome allocation cannot be negative")
        if self.terminal_state not in {None, PortfolioDecisionState.HOLD, PortfolioDecisionState.REJECT}:
            raise InvalidPolicyOutcomeError("policy terminal state must be HOLD or REJECT")
