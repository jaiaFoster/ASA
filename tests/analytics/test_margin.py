from decimal import Decimal

import pytest

from analytics.formulas import OPTION_STRATEGY_FORMULAS
from analytics.margin import (
    CASH_SECURED_PUT_COLLATERAL_ID,
    CASH_SECURED_PUT_COLLATERAL_VERSION,
    cash_secured_put_collateral,
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
