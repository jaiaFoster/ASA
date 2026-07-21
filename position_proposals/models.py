"""Immutable Position Proposal Engine policy inputs."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from domain.values import require_finite_decimal
from position_proposals.errors import InvalidProposalParameterError

PROPOSAL_ALGORITHM_VERSION = "v1"
PROPOSAL_IDENTITY_NAMESPACE = "asa.proposed_position"
ALLOCATION_QUANTUM = Decimal("0.000000000001")


@dataclass(frozen=True, slots=True)
class ProposalParameters:
    """Complete v1 sizing policy with no hidden module-level inputs."""

    allocation_floor: Decimal = Decimal("0.01")
    allocation_ceiling: Decimal = Decimal("0.10")
    reference_capital: Decimal = Decimal("100000")

    def __post_init__(self) -> None:
        for name in self.__dataclass_fields__:
            value = getattr(self, name)
            try:
                require_finite_decimal(value, "ProposalParameters", name)
            except (TypeError, ValueError) as error:
                raise InvalidProposalParameterError(str(error)) from error
        if not Decimal("0") < self.allocation_floor <= Decimal("1"):
            raise InvalidProposalParameterError("allocation_floor must be within (0, 1]")
        if not Decimal("0") < self.allocation_ceiling <= Decimal("1"):
            raise InvalidProposalParameterError("allocation_ceiling must be within (0, 1]")
        if self.allocation_floor > self.allocation_ceiling:
            raise InvalidProposalParameterError(
                "allocation_floor cannot exceed allocation_ceiling"
            )
        if self.reference_capital <= 0:
            raise InvalidProposalParameterError("reference_capital must be positive")

    def canonical_items(self) -> tuple[tuple[str, Decimal], ...]:
        return tuple(sorted((name, getattr(self, name)) for name in self.__dataclass_fields__))
