"""Versioned generic margin and collateral facts (SP-03A)."""

from __future__ import annotations

from decimal import Decimal

from domain import UnknownReason

CASH_SECURED_PUT_COLLATERAL_ID = "DF-CASH-SECURED-PUT-COLLATERAL"
CASH_SECURED_PUT_COLLATERAL_VERSION = "1.0.0"


def cash_secured_put_collateral(
    *,
    strike: Decimal,
    quantity: Decimal,
    contract_multiplier: Decimal,
    collateral_return_to_expiry: Decimal | None,
) -> Decimal | UnknownReason:
    """Present collateral funding the full strike obligation at expiration.

    C = quantity * strike * multiplier / (1 + R). This is collateral, not
    terminal max loss and not broker margin. Missing Treasury return remains
    UNKNOWN rather than silently becoming zero-return cash.
    """
    if strike <= 0 or quantity <= 0 or contract_multiplier <= 0:
        raise ValueError("strike, quantity and contract_multiplier must be positive")
    if collateral_return_to_expiry is None:
        return UnknownReason("missing_collateral_return_to_expiry")
    denominator = Decimal(1) + collateral_return_to_expiry
    if denominator <= 0:
        return UnknownReason("invalid_collateral_return_to_expiry")
    return quantity * strike * contract_multiplier / denominator
