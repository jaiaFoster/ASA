"""Pinned Portfolio Engine v1 parameters."""

from dataclasses import dataclass
from decimal import Decimal

from domain.values import DomainInvariantError

PORTFOLIO_ALGORITHM_VERSION = "v1"
PORTFOLIO_EVALUATION_NAMESPACE = "asa.portfolio_evaluation_result.v1"
PORTFOLIO_DELTA_NAMESPACE = "asa.portfolio_delta.v1"


@dataclass(frozen=True, slots=True)
class PortfolioParameters:
    decimal_precision: int = 34
    currency_quantum: Decimal = Decimal("0.01")
    quantity_rounding: str = "floor_to_increment"

    def __post_init__(self) -> None:
        if self.decimal_precision != 34:
            raise DomainInvariantError("Portfolio v1 decimal precision is 34")
        if self.currency_quantum <= 0:
            raise DomainInvariantError("currency_quantum must be positive")
        if self.quantity_rounding != "floor_to_increment":
            raise DomainInvariantError("Portfolio v1 rounds down to quantity increment")

    def canonical_items(self) -> tuple[tuple[str, str], ...]:
        return (
            ("currency_quantum", str(self.currency_quantum)),
            ("decimal_precision", str(self.decimal_precision)),
            ("quantity_rounding", self.quantity_rounding),
        )
