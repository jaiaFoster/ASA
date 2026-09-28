from decimal import Decimal

import pytest

from analytics.formulas import OPTION_STRATEGY_FORMULAS
from analytics.margin import (
    CASH_SECURED_PUT_COLLATERAL_ID,
    CASH_SECURED_PUT_COLLATERAL_VERSION,
    CBOE_NAKED_MARGIN_ID,
    CBOE_NAKED_MARGIN_VERSION,
    CBOE_STRADDLE_MARGIN_ID,
    CBOE_STRADDLE_MARGIN_VERSION,
    OPTION_PROCEEDS_ACCRUAL_ID,
    OPTION_PROCEEDS_ACCRUAL_VERSION,
    accrue_option_proceeds,
    cash_secured_put_collateral,
    cboe_naked_option_margin,
    cboe_put_contract_count,
    cboe_short_straddle_margin,
)
from domain import OptionType, UnknownReason


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


def test_cboe_naked_margin_equity_call_and_index_put_vectors() -> None:
    assert cboe_naked_option_margin(
        option_type=OptionType.CALL,
        option_value=Decimal("5"),
        spot=Decimal("100"),
        strike=Decimal("110"),
        alpha=Decimal("0.20"),
        beta=Decimal("0.10"),
    ) == Decimal("15")
    assert cboe_naked_option_margin(
        option_type=OptionType.PUT,
        option_value=Decimal("7"),
        spot=Decimal("100"),
        strike=Decimal("105"),
        alpha=Decimal("0.15"),
        beta=Decimal("0.10"),
    ) == Decimal("22")


def test_cboe_margin_inputs_fail_closed() -> None:
    unknown = cboe_naked_option_margin(
        option_type=OptionType.CALL,
        option_value=None,
        spot=Decimal("100"),
        strike=Decimal("100"),
        alpha=Decimal("0.15"),
        beta=Decimal("0.10"),
    )
    assert unknown == UnknownReason("missing_cboe_naked_margin_input")
    for alpha, beta in ((None, Decimal("0.10")), (Decimal("0.15"), None)):
        assert cboe_naked_option_margin(
            option_type=OptionType.CALL,
            option_value=Decimal("5"),
            spot=Decimal("100"),
            strike=Decimal("100"),
            alpha=alpha,
            beta=beta,
        ) == UnknownReason("missing_cboe_naked_margin_input")
    assert cboe_short_straddle_margin(
        call_margin=unknown,
        put_margin=Decimal("20"),
        call_value=Decimal("5"),
        put_value=Decimal("6"),
    ) == UnknownReason("missing_cboe_straddle_margin_input")


def test_cboe_short_straddle_adds_other_option_value_to_greater_leg() -> None:
    assert cboe_short_straddle_margin(
        call_margin=Decimal("25"),
        put_margin=Decimal("30"),
        call_value=Decimal("5"),
        put_value=Decimal("6"),
    ) == Decimal("35")
    assert cboe_short_straddle_margin(
        call_margin=Decimal("30"),
        put_margin=Decimal("30"),
        call_value=Decimal("8"),
        put_value=Decimal("4"),
    ) == Decimal("38")


def test_option_proceeds_require_explicit_financing_return() -> None:
    assert accrue_option_proceeds(
        proceeds=Decimal("100"), financing_return=Decimal("0.01")
    ) == Decimal("101")
    assert accrue_option_proceeds(proceeds=Decimal("100"), financing_return=None) == UnknownReason(
        "missing_option_proceeds_financing_input"
    )


def test_sp04a_formula_ids_are_pinned() -> None:
    assert OPTION_STRATEGY_FORMULAS.get(CBOE_NAKED_MARGIN_ID).formula_version == (
        CBOE_NAKED_MARGIN_VERSION
    )
    assert OPTION_STRATEGY_FORMULAS.get(CBOE_STRADDLE_MARGIN_ID).formula_version == (
        CBOE_STRADDLE_MARGIN_VERSION
    )
    assert OPTION_STRATEGY_FORMULAS.get(OPTION_PROCEEDS_ACCRUAL_ID).formula_version == (
        OPTION_PROCEEDS_ACCRUAL_VERSION
    )
