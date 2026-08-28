from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from uuid import UUID


class ValueAuthority(StrEnum):
    BROKER_OBSERVED = "broker_observed"
    DERIVED = "derived"
    UNKNOWN = "unknown"


@dataclass(frozen=True, slots=True)
class MonetaryValue:
    amount: Decimal | None
    currency: str
    authority: ValueAuthority
    observed_at: datetime
    unknown_reason: str | None = None

    def __post_init__(self) -> None:
        if self.authority is ValueAuthority.UNKNOWN:
            if self.amount is not None or not self.unknown_reason:
                raise ValueError("unknown value requires no amount and a typed reason")
        elif self.amount is None or self.unknown_reason is not None:
            raise ValueError("known value requires an amount and no unknown reason")


@dataclass(frozen=True, slots=True)
class AccountValuation:
    account_id: UUID
    total_value: MonetaryValue
    profit_and_loss: MonetaryValue


@dataclass(frozen=True, slots=True)
class PositionValuation:
    position_key: str
    market_value: MonetaryValue
    profit_and_loss: MonetaryValue


@dataclass(frozen=True, slots=True)
class PortfolioValuationProjection:
    accounts: tuple[AccountValuation, ...]
    equity_positions: tuple[PositionValuation, ...]
    option_legs: tuple[PositionValuation, ...]


class ExitPolicyStatus(StrEnum):
    NOT_DEFINED = "not_defined"
    ACTIVE = "active"
    TRIGGERED = "triggered"
    UNKNOWN = "unknown"


@dataclass(frozen=True, slots=True)
class DeclaredExitState:
    policy_id: str
    policy_version: str
    status: ExitPolicyStatus
    reason: str
    evaluated_at: datetime

    def __post_init__(self) -> None:
        if self.status is ExitPolicyStatus.NOT_DEFINED:
            raise ValueError("a declared exit state cannot be not_defined")


@dataclass(frozen=True, slots=True)
class ExitStateProjection:
    status: ExitPolicyStatus
    policy_id: str | None
    policy_version: str | None
    reason: str
    evaluated_at: datetime
