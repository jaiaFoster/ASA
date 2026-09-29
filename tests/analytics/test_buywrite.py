from decimal import Decimal

from analytics.buywrite import cboe_buywrite_daily_return
from domain import UnknownReason


def test_non_roll_buywrite_daily_return_matches_source_formula() -> None:
    result = cboe_buywrite_daily_return(
        roll_day=False,
        prior_index_close=Decimal("100"),
        prior_call_close=Decimal("4"),
        index_close=Decimal("102"),
        call_close=Decimal("5"),
        dividend_points=Decimal("1"),
    )
    assert result == Decimal("98") / Decimal("96") - Decimal(1)


def test_roll_buywrite_daily_return_compounds_three_source_segments() -> None:
    result = cboe_buywrite_daily_return(
        roll_day=True,
        prior_index_close=Decimal("100"),
        prior_call_close=Decimal("4"),
        index_close=Decimal("103"),
        call_close=Decimal("5"),
        dividend_points=Decimal("1"),
        old_strike=Decimal("98"),
        settlement_value=Decimal("101"),
        index_vwav=Decimal("102"),
        call_vwap=Decimal("4"),
    )
    ra = Decimal("99") / Decimal("96") - Decimal(1)
    rb = Decimal("102") / Decimal("101") - Decimal(1)
    rc = Decimal("98") / Decimal("98") - Decimal(1)
    assert result == (Decimal(1) + ra) * (Decimal(1) + rb) * (Decimal(1) + rc) - Decimal(1)


def test_buywrite_return_missing_required_input_is_typed_unknown() -> None:
    result = cboe_buywrite_daily_return(
        roll_day=True,
        prior_index_close=None,
        prior_call_close=Decimal("4"),
        index_close=Decimal("103"),
        call_close=Decimal("5"),
        dividend_points=Decimal("1"),
    )
    assert isinstance(result, UnknownReason)
    assert result.code == "missing_cboe_buywrite_daily_return_input"
