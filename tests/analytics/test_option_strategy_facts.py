"""SP-01E pinned vectors for the reusable option-strategy facts."""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

import pytest

from analytics.calendar_facts import (
    TradingCalendarView,
    first_trading_day_of_month,
    last_trading_day_of_month,
    monthly_expiration_day,
    third_friday_roll_date,
    trading_session_offset,
)
from analytics.capital import cboe_tbill_daily_accrual
from analytics.formulas import OPTION_STRATEGY_FORMULAS
from analytics.option_facts import (
    calendar_days_to_expiration,
    delta_neutral_hedge_quantity,
    moneyness_spot_over_strike,
    moneyness_strike_over_spot,
    option_effective_price,
    option_holding_return,
    option_mid,
    option_relative_spread,
    option_weighted_spread,
)
from analytics.option_returns import (
    StraddleWeights,
    straddle_return,
    value_straddle_weights,
    zero_cost_option_return,
    zero_delta_straddle_weights,
)
from analytics.quantile_assignment import QuantilePolicy, assign_quantiles
from domain import UnknownReason

D = Decimal


def test_every_formula_has_id_version_unit_and_time_semantics() -> None:
    ids = OPTION_STRATEGY_FORMULAS.registered_ids()
    assert len(ids) == 19
    for formula_id in ids:
        definition = OPTION_STRATEGY_FORMULAS.get(formula_id)
        assert definition.formula_version and definition.unit and definition.time_semantics
    assert OPTION_STRATEGY_FORMULAS.get("DF-XS-QUANTILE-ASSIGNMENT").formula_version == "1.1.0"


def test_midpoint_and_spreads() -> None:
    assert option_mid(D("3"), D("4")) == D("3.5")
    assert option_mid(None, D("4")) == UnknownReason("missing_bid_or_ask")
    assert option_mid(D("5"), D("4")) == UnknownReason("crossed_quote")
    assert option_relative_spread(D("3"), D("4")) == D(1) / D("3.5")
    assert option_relative_spread(D("0"), D("0")) == UnknownReason("zero_midpoint")
    assert option_weighted_spread(((D(1), D("1"), D("2")), (D(-2), D("3"), D("4")))) == D(3) / D(
        "8.5"
    )
    assert option_weighted_spread(((D(1), D("1"), None),)) == UnknownReason("missing_bid_or_ask")


def test_effective_price_matches_gxz_footnote_vector() -> None:
    assert option_effective_price(D("3"), D("4"), D("0.5"), buy=True) == D("3.75")
    assert option_effective_price(D("3"), D("4"), D("0.5"), buy=False) == D("3.25")
    with pytest.raises(ValueError):
        option_effective_price(D("3"), D("4"), D("1.5"), buy=True)


def test_moneyness_dte_holding_return_and_hedge() -> None:
    assert moneyness_strike_over_spot(D("90"), D("100")) == D("0.9")
    assert moneyness_spot_over_strike(D("90"), None) == UnknownReason("missing_underlying_price")
    assert calendar_days_to_expiration(date(2026, 10, 16), date(2026, 9, 28)) == 18
    assert isinstance(
        calendar_days_to_expiration(date(2026, 9, 1), date(2026, 9, 28)), UnknownReason
    )
    assert option_holding_return(D("2"), D("3")) == D("0.5")
    assert option_holding_return(D("0"), D("3")) == UnknownReason("non_positive_entry_price")
    # A written call hedges long: +delta * n * multiplier.
    assert delta_neutral_hedge_quantity(D("0.5"), D(1), D(100), long_option=False) == D("50")
    assert delta_neutral_hedge_quantity(D("0.5"), D(1), D(100), long_option=True) == D("-50")
    assert delta_neutral_hedge_quantity(None, D(1), D(100), long_option=True) == UnknownReason(
        "missing_delta"
    )


def test_zero_delta_straddle_weights_are_delta_neutral() -> None:
    weights = zero_delta_straddle_weights(D("5"), D("4"), D("0.6"), D("-0.4"))
    assert isinstance(weights, StraddleWeights)
    assert weights.call + weights.put == 1
    n_call, n_put = weights.call / D(5), weights.put / D(4)
    assert abs(n_call * D("0.6") + n_put * D("-0.4")) < D("1e-20")
    assert zero_delta_straddle_weights(D("5"), D("4"), D("-0.1"), D("-0.4")) == UnknownReason(
        "invalid_delta_sign"
    )
    assert zero_delta_straddle_weights(None, D("4"), D("0.6"), D("-0.4")) == UnknownReason(
        "missing_straddle_input"
    )


def test_straddle_and_zero_cost_returns() -> None:
    weights = value_straddle_weights(D("3"), D("1"))
    assert weights == StraddleWeights(D("0.75"), D("0.25"))
    assert straddle_return(weights, D("0.2"), D("-0.4")) == D("0.05")
    assert straddle_return(weights, UnknownReason("x"), D("0")) == UnknownReason("x")
    # Santa-Clara-Saretto worked example: (12.65 - 12.80)/12.80 - 0.92% = -2.09%.
    long = zero_cost_option_return(D("12.80"), D("12.65"), D("0.0092"), short=False)
    assert isinstance(long, Decimal)
    assert long.quantize(D("0.0001")) == D("-0.0209")
    assert zero_cost_option_return(D("12.80"), D("12.65"), D("0.0092"), short=True) == -long
    assert zero_cost_option_return(
        D("1"), D("1"), UnknownReason("rf"), short=True
    ) == UnknownReason("rf")


def test_cboe_tbill_accrual() -> None:
    one_day = cboe_tbill_daily_accrual(D("0.05"), 28, 1)
    assert isinstance(one_day, Decimal)
    expected = (D(1) / (D(1) - D(28) / D(360) * D("0.05"))) ** (D(1) / D(28)) - 1
    assert one_day == expected
    assert cboe_tbill_daily_accrual(D("0.05"), 91, 0) == 0
    assert cboe_tbill_daily_accrual(None, 28, 1) == UnknownReason(
        "missing_treasury_bank_discount_rate"
    )
    with pytest.raises(ValueError):
        cboe_tbill_daily_accrual(D("0.05"), 30, 1)


def _calendar(holidays: frozenset[date] = frozenset()) -> TradingCalendarView:
    return TradingCalendarView(
        lambda day: day.weekday() < 5 and day not in holidays,
        date(2026, 1, 1),
        date(2026, 12, 31),
    )


def test_calendar_facts() -> None:
    calendar = _calendar(frozenset({date(2026, 4, 17)}))
    assert third_friday_roll_date(calendar, 2026, 10) == date(2026, 10, 16)
    # A holiday third Friday rolls to the preceding business day.
    assert third_friday_roll_date(calendar, 2026, 4) == date(2026, 4, 16)
    assert monthly_expiration_day(calendar, 2026, 4) == date(2026, 4, 16)
    assert first_trading_day_of_month(calendar, 2026, 10) == date(2026, 10, 1)
    assert last_trading_day_of_month(calendar, 2026, 10) == date(2026, 10, 30)
    assert trading_session_offset(calendar, date(2026, 10, 1), -3) == date(2026, 9, 28)
    assert trading_session_offset(calendar, date(2026, 9, 28), 0) == date(2026, 9, 28)
    assert trading_session_offset(calendar, date(2026, 9, 27), 1) == UnknownReason(
        "not_a_trading_day"
    )
    assert third_friday_roll_date(calendar, 2027, 1) == UnknownReason(
        "trading_calendar_not_covered"
    )
    edge = TradingCalendarView(lambda day: day.weekday() < 5, date(2026, 1, 1), date(2026, 1, 5))
    assert trading_session_offset(edge, date(2026, 1, 5), 2) == UnknownReason(
        "trading_calendar_not_covered"
    )
    assert date(2026, 1, 5) + timedelta(days=1) > edge.coverage_end


def test_quantile_assignment_ra_xs_01() -> None:
    values: dict[str, Decimal | UnknownReason] = {
        f"S{index:02d}": D(index) for index in range(1, 11)
    }
    values["S03"] = D(2)  # tie with S02 shares the lowest rank
    values["X"] = UnknownReason("missing_price")
    result = assign_quantiles(values, QuantilePolicy(groups=5))
    assert not isinstance(result, UnknownReason)
    assert result.eligible_count == 10
    assert result.group_of("S01") == 1
    assert result.group_of("S02") == result.group_of("S03") == 1
    assert result.group_of("S10") == 5
    assert result.group_of("X") is None
    assert result.excluded == (("X", "missing_price"),)
    assert assign_quantiles({}, QuantilePolicy(groups=10)) == UnknownReason("empty_eligible_set")
    with pytest.raises(ValueError):
        QuantilePolicy(groups=1)


def test_single_formula_owners_and_input_guards() -> None:
    from decimal import localcontext

    from analytics.derived_facts import compute_bid_ask_spread_ratio

    assert option_relative_spread(D("3"), D("4")) == compute_bid_ask_spread_ratio(D("3"), D("4"))
    assert option_relative_spread(D("-1"), D("4")) == UnknownReason("invalid_bid_or_ask")
    with pytest.raises(ValueError):
        moneyness_spot_over_strike(D("0"), D("100"))
    with pytest.raises(TypeError):
        assign_quantiles({"A": None}, QuantilePolicy(groups=2))  # type: ignore[dict-item]
    with pytest.raises(ValueError):
        assign_quantiles({"A": D("NaN")}, QuantilePolicy(groups=2))
    reference = cboe_tbill_daily_accrual(D("0.05"), 28, 1)
    with localcontext() as context:
        context.prec = 10
        assert cboe_tbill_daily_accrual(D("0.05"), 28, 1) == reference
