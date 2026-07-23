"""Universal Options Framework (SPRINT-009/EPIC-4).

Adopts domain.financial's own OptionLeg/OptionStructure/OptionStructureType/
OptionLegPosition directly as this sprint's canonical option package
representation -- already fully generalized and already validated on
construction (OptionStructure.__post_init__'s own _validate_shape(),
domain/financial.py, unmodified by this ticket): exactly two legs sharing
an expiration for VERTICAL, exactly two legs sharing a strike for
CALENDAR, and so on for every structure kind domain/ already knows about.
Not rebuilt here, and not re-exported through this module either --
strategy_runtime adapters import these directly from domain, the same way
every other root package already does.

Re-exports analytics.expiration_selection's own already-generalized
expiration-pairing helpers (ExpirationCandidate, select_expiration_pair,
select_earnings_relative_expiration_pair, ANALYTICS-002) for discoverability
under strategy_runtime's own namespace -- the logic itself lives in and is
owned by analytics/, unmodified.

What is genuinely new here: standalone liquidity and debit calculations
operating directly on domain.OptionLeg/OptionStructure/OptionContract, for
a strategy_runtime adapter to call without going through strategies/'s own
manifest-graph execution engine at all (this sprint's adapters are meant
to bypass that graph entirely, per the declarative_strategies/
strategies_own_thesis principles). Both are ported, not reinvented, from
strategies/stonk_components.py's own OptionLegLiquidity and
OptionStructureDebit graph components -- the identical formula, so a
migrated strategy computes the same result the graph-based version
already proved correct.

Deliberately excluded: a payoff-at-expiration calculator. No existing
component anywhere in this codebase computes one to generalize from (only
debit/mark), and none of EPIC-7's three migration targets need one for
their own current verdict logic (forward_factor and skew_momentum score
from implied volatility/skew inputs, not a payoff diagram). Inventing
options-payoff math with no reference implementation and no proven
migration-target need is exactly the kind of speculative complexity this
sprint's own generalize_before_specialize principle argues against --
recorded as a deliberate scope decision, not an oversight.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from analytics.expiration_selection import (
    ExpirationCandidate,
    select_earnings_relative_expiration_pair,
    select_expiration_pair,
)
from domain import OptionContract, OptionLeg, OptionLegPosition, OptionStructure

__all__ = [
    "ExpirationCandidate",
    "LiquidityPolicy",
    "StructureDebit",
    "compute_structure_debit",
    "is_liquid",
    "liquidity_blockers",
    "select_earnings_relative_expiration_pair",
    "select_expiration_pair",
]


@dataclass(frozen=True, slots=True)
class LiquidityPolicy:
    maximum_spread_ratio: Decimal
    minimum_open_interest: int
    minimum_volume: int

    def __post_init__(self) -> None:
        if (
            self.maximum_spread_ratio < 0
            or self.minimum_open_interest < 0
            or self.minimum_volume < 0
        ):
            raise ValueError("LiquidityPolicy thresholds cannot be negative")


def is_liquid(contract: OptionContract, policy: LiquidityPolicy) -> bool:
    """Quote-width, open-interest, and volume check -- the same formula
    strategies/stonk_components.py::OptionLegLiquidity already established
    (spread = (ask - bid) / mark), ported to a standalone function.
    Missing data (no bid/ask/mark/open_interest/volume, or a non-positive
    mark) is never liquid and never raises -- the same fail-closed
    convention the original component uses.
    """
    if (
        contract.bid is None
        or contract.ask is None
        or contract.mark is None
        or contract.mark <= 0
        or contract.open_interest is None
        or contract.volume is None
    ):
        return False
    spread = (contract.ask - contract.bid) / contract.mark
    return (
        spread <= policy.maximum_spread_ratio
        and contract.open_interest >= policy.minimum_open_interest
        and contract.volume >= policy.minimum_volume
    )


def liquidity_blockers(structure: OptionStructure, policy: LiquidityPolicy) -> tuple[str, ...]:
    """One blocker string per illiquid leg in ``structure``, empty if every
    leg passes -- shaped to feed directly into
    strategy_runtime.result.UniversalScreeningResult.blockers.
    """
    return tuple(
        f"leg {leg.role} ({leg.contract.option_type.value} {leg.contract.strike} "
        f"{leg.contract.expiration.isoformat()}) fails liquidity policy"
        for leg in structure.legs
        if not is_liquid(leg.contract, policy)
    )


@dataclass(frozen=True, slots=True)
class StructureDebit:
    mid_debit: Decimal | None
    conservative_debit: Decimal | None


def _sum_signed(
    legs: tuple[OptionLeg, ...], values: tuple[Decimal | None, ...]
) -> Decimal | None:
    if any(value is None for value in values):
        return None
    total = Decimal(0)
    for leg, value in zip(legs, values, strict=True):
        assert value is not None  # narrowed by the check above
        sign = Decimal(1) if leg.position is OptionLegPosition.LONG else Decimal(-1)
        total += value * leg.quantity * sign
    return total


def compute_structure_debit(structure: OptionStructure) -> StructureDebit:
    """The same two-variant debit calculation
    strategies/stonk_components.py::OptionStructureDebit already
    established: ``mid_debit`` from each leg's own mark (None if any leg
    lacks one), ``conservative_debit`` from the worse-case fill price per
    leg's own position (the ask for a long leg, the bid for a short one).
    A positive debit means a net cost to open; a negative value is a net
    credit -- unchanged from the original component's own convention.
    """
    marks = tuple(leg.contract.mark for leg in structure.legs)
    conservative_values = tuple(
        leg.contract.ask if leg.position is OptionLegPosition.LONG else leg.contract.bid
        for leg in structure.legs
    )
    return StructureDebit(
        mid_debit=_sum_signed(structure.legs, marks),
        conservative_debit=_sum_signed(structure.legs, conservative_values),
    )
