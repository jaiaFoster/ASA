"""Versioned generic margin and collateral facts (SP-03A)."""

from __future__ import annotations

from decimal import Decimal

from domain import UnknownReason

CASH_SECURED_PUT_COLLATERAL_ID = "DF-CASH-SECURED-PUT-COLLATERAL"
CASH_SECURED_PUT_COLLATERAL_VERSION = "1.0.0"
CBOE_PUT_CONTRACT_COUNT_ID = "DF-CBOE-PUT-CONTRACT-COUNT"
CBOE_PUT_CONTRACT_COUNT_VERSION = "1.0.0"


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


def cboe_put_contract_count(
    *,
    third_roll: bool,
    one_month_balance: Decimal | None,
    three_month_balance: Decimal | None,
    one_month_prior_accrual: Decimal | None,
    three_month_prior_accrual: Decimal | None,
    last_contract_count: Decimal | None,
    old_strike: Decimal | None,
    settlement_value: Decimal | None,
    new_strike: Decimal | None,
    entry_price: Decimal | None,
    one_month_return: Decimal | None,
    three_month_return: Decimal | None,
) -> Decimal | UnknownReason:
    """Cboe PUT methodology equations (6) and (8)-(14)."""
    values = (
        one_month_balance,
        three_month_balance,
        one_month_prior_accrual,
        three_month_prior_accrual,
        last_contract_count,
        old_strike,
        settlement_value,
        new_strike,
        entry_price,
        one_month_return,
        three_month_return,
    )
    if any(value is None for value in values):
        return UnknownReason("missing_cboe_put_contract_count_input")
    m1, m3, prior_r1, prior_r3, n_last, old_k, soq, new_k, premium, r1, r3 = values
    assert m1 is not None
    assert m3 is not None
    assert prior_r1 is not None
    assert prior_r3 is not None
    assert n_last is not None
    assert old_k is not None
    assert soq is not None
    assert new_k is not None
    assert premium is not None
    assert r1 is not None
    assert r3 is not None
    accrued_m1 = (Decimal(1) + prior_r1) * m1
    accrued_m3 = (Decimal(1) + prior_r3) * m3
    settlement_loss = n_last * max(Decimal(0), old_k - soq)
    if third_roll:
        numerator = accrued_m1 + accrued_m3 - settlement_loss
        denominator = new_k / (Decimal(1) + r3) - premium
    else:
        residual = accrued_m1 - settlement_loss
        m1_roll = max(Decimal(0), residual) * (Decimal(1) + r1)
        m3_roll = (accrued_m3 + min(Decimal(0), residual)) * (Decimal(1) + r3)
        numerator = m1_roll + m3_roll
        denominator = new_k - premium * (Decimal(1) + r1)
    if numerator < 0 or denominator <= 0:
        return UnknownReason("invalid_cboe_put_contract_count_input")
    return numerator / denominator
