"""Pinned v1 portfolio policies.

Each policy returns an allocation ceiling expressed in the ProposedPosition's
reference-capital frame. Policies never mutate or infer missing portfolio data.
"""

from __future__ import annotations

from decimal import Decimal, localcontext

from domain.execution import PortfolioDecisionState
from domain.operational import PortfolioSnapshot, ProposedPosition
from portfolio.models import ALLOCATION_QUANTUM, POLICY_VERSION, PolicyOutcome, PortfolioParameters


def _reference_capital(proposal: ProposedPosition) -> Decimal:
    return dict(proposal.effective_parameters)["reference_capital"]


def _allocation_for_amount(amount: Decimal, proposal: ProposedPosition) -> Decimal:
    if amount <= 0:
        return Decimal("0")
    with localcontext() as context:
        context.prec = 40
        return (amount / _reference_capital(proposal)).quantize(ALLOCATION_QUANTUM)


def buying_power_validation(
    proposal: ProposedPosition,
    snapshot: PortfolioSnapshot,
    parameters: PortfolioParameters,
) -> PolicyOutcome:
    del parameters
    ceiling = _allocation_for_amount(snapshot.buying_power.amount, proposal)
    return PolicyOutcome(
        "buying_power_validation",
        POLICY_VERSION,
        ceiling,
        "buying power limits new exposure" if ceiling < proposal.target_allocation else
        "buying power supports proposed exposure",
    )


def cash_reserve(
    proposal: ProposedPosition,
    snapshot: PortfolioSnapshot,
    parameters: PortfolioParameters,
) -> PolicyOutcome:
    reserve = snapshot.net_liquidation_value.amount * parameters.cash_reserve_ratio
    ceiling = _allocation_for_amount(snapshot.cash_balance.amount - reserve, proposal)
    return PolicyOutcome(
        "cash_reserve",
        POLICY_VERSION,
        ceiling,
        "cash reserve limits new exposure" if ceiling < proposal.target_allocation else
        "cash reserve remains satisfied",
    )


def duplicate_position(
    proposal: ProposedPosition,
    snapshot: PortfolioSnapshot,
    parameters: PortfolioParameters,
) -> PolicyOutcome:
    del parameters
    duplicate = any(
        holding.instrument.identity == proposal.instrument.identity
        for holding in snapshot.holdings
    )
    return PolicyOutcome(
        "duplicate_position",
        POLICY_VERSION,
        Decimal("0") if duplicate else proposal.target_allocation,
        "existing canonical instrument exposure requires hold" if duplicate else
        "no duplicate canonical instrument exposure",
        PortfolioDecisionState.HOLD if duplicate else None,
    )


def maximum_position_size(
    proposal: ProposedPosition,
    snapshot: PortfolioSnapshot,
    parameters: PortfolioParameters,
) -> PolicyOutcome:
    del snapshot
    ceiling = parameters.maximum_position_allocation
    return PolicyOutcome(
        "maximum_position_size",
        POLICY_VERSION,
        ceiling,
        "maximum position size limits proposed exposure" if ceiling < proposal.target_allocation
        else "proposed exposure is within maximum position size",
    )


def maximum_sector_exposure(
    proposal: ProposedPosition,
    snapshot: PortfolioSnapshot,
    parameters: PortfolioParameters,
) -> PolicyOutcome:
    sector = proposal.instrument.sector
    if sector is None:
        return PolicyOutcome(
            "maximum_sector_exposure",
            POLICY_VERSION,
            proposal.target_allocation,
            "sector policy is not applicable to an unclassified instrument",
        )
    current = sum(
        (
            holding.gross_exposure.amount
            for holding in snapshot.holdings
            if holding.instrument.sector == sector
        ),
        Decimal("0"),
    )
    capacity = snapshot.net_liquidation_value.amount * parameters.maximum_sector_exposure - current
    ceiling = _allocation_for_amount(capacity, proposal)
    return PolicyOutcome(
        "maximum_sector_exposure",
        POLICY_VERSION,
        ceiling,
        "sector exposure limit constrains diversification" if ceiling < proposal.target_allocation
        else "sector exposure remains diversified",
    )


def maximum_single_asset_exposure(
    proposal: ProposedPosition,
    snapshot: PortfolioSnapshot,
    parameters: PortfolioParameters,
) -> PolicyOutcome:
    current = sum(
        (
            holding.gross_exposure.amount
            for holding in snapshot.holdings
            if holding.instrument.identity == proposal.instrument.identity
        ),
        Decimal("0"),
    )
    capacity = (
        snapshot.net_liquidation_value.amount * parameters.maximum_single_asset_exposure - current
    )
    ceiling = _allocation_for_amount(capacity, proposal)
    return PolicyOutcome(
        "maximum_single_asset_exposure",
        POLICY_VERSION,
        ceiling,
        "single asset concentration limits new exposure" if ceiling < proposal.target_allocation
        else "single asset exposure remains within concentration limit",
    )
