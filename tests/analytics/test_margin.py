from decimal import Decimal

import pytest

from analytics.formulas import OPTION_STRATEGY_FORMULAS
from analytics.margin import (
    CASH_SECURED_PUT_COLLATERAL_ID,
    CASH_SECURED_PUT_COLLATERAL_VERSION,
    cash_secured_put_collateral,
    cboe_put_contract_count,
)
from domain import UnknownReason


def test_cash_secured_put_collateral_is_versioned_present_value() -> None:
    definition = OPTION_STRATEGY_FORMULAS.get(CASH_SECURED_PUT_COLLATERAL_ID)
    assert definition.formula_version == CASH_SECURED_PUT_COLLATERAL_VERSION
    assert cash_secured_put_collateral(
        strike=Decimal("5000"),
        quantity=Decimal("2.5"),
        contract_multiplier=Decimal("100"),
        collateral_return_to_expiry=Decimal("0.01"),
    ) == Decimal("1250000") / Decimal("1.01")


def test_cash_secured_put_collateral_fails_closed_without_treasury_return() -> None:
    assert cash_secured_put_collateral(
        strike=Decimal("5000"),
        quantity=Decimal("1"),
        contract_multiplier=Decimal("100"),
        collateral_return_to_expiry=None,
    ) == UnknownReason("missing_collateral_return_to_expiry")


def test_cash_secured_put_collateral_is_not_vertical_max_loss() -> None:
    with pytest.raises(ValueError, match="must be positive"):
        cash_secured_put_collateral(
            strike=Decimal("5000"),
            quantity=Decimal("0"),
            contract_multiplier=Decimal("100"),
            collateral_return_to_expiry=Decimal("0.01"),
        )


def test_cboe_put_contract_count_preserves_fractional_source_sizing() -> None:
    result = cboe_put_contract_count(
        third_roll=True,
        one_month_balance=Decimal("600000"),
        three_month_balance=Decimal("400000"),
        one_month_prior_accrual=Decimal("0.001"),
        three_month_prior_accrual=Decimal("0.002"),
        last_contract_count=Decimal("1"),
        old_strike=Decimal("4900"),
        settlement_value=Decimal("4800"),
        new_strike=Decimal("5000"),
        entry_price=Decimal("50"),
        one_month_return=Decimal("0.003"),
        three_month_return=Decimal("0.01"),
    )
    assert result == Decimal("1001300") / (Decimal("5000") / Decimal("1.01") - Decimal("50"))


def test_cboe_put_contract_count_fails_closed_without_sourced_input() -> None:
    result = cboe_put_contract_count(
        third_roll=False,
        one_month_balance=None,
        three_month_balance=Decimal("1"),
        one_month_prior_accrual=Decimal("0.01"),
        three_month_prior_accrual=Decimal("0.01"),
        last_contract_count=Decimal("0"),
        old_strike=Decimal("1"),
        settlement_value=Decimal("1"),
        new_strike=Decimal("1"),
        entry_price=Decimal("0.1"),
        one_month_return=Decimal("0.01"),
        three_month_return=Decimal("0.01"),
    )
    assert result == UnknownReason("missing_cboe_put_contract_count_input")
