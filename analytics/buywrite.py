"""Versioned provider-neutral Cboe buy-write return accounting."""

from decimal import Decimal

from domain import UnknownReason

CBOE_BUYWRITE_DAILY_RETURN_ID = "DF-CBOE-BUYWRITE-DAILY-RETURN"
CBOE_BUYWRITE_DAILY_RETURN_VERSION = "1.0.0"


def cboe_buywrite_daily_return(
    *,
    roll_day: bool,
    prior_index_close: Decimal | None,
    prior_call_close: Decimal | None,
    index_close: Decimal | None,
    call_close: Decimal | None,
    dividend_points: Decimal | None,
    old_strike: Decimal | None = None,
    settlement_value: Decimal | None = None,
    index_vwav: Decimal | None = None,
    call_vwap: Decimal | None = None,
) -> Decimal | UnknownReason:
    """Cboe BXM simple daily return, including the three roll-day segments."""
    common = (prior_index_close, prior_call_close, index_close, call_close, dividend_points)
    if any(value is None for value in common):
        return UnknownReason("missing_cboe_buywrite_daily_return_input")
    prior_spot, prior_call, spot, call, dividends = common
    assert prior_spot is not None
    assert prior_call is not None
    assert spot is not None
    assert call is not None
    assert dividends is not None
    prior_net = prior_spot - prior_call
    if min(prior_spot, spot) <= 0 or min(prior_call, call, dividends) < 0 or prior_net <= 0:
        return UnknownReason("invalid_cboe_buywrite_daily_return_input")
    if not roll_day:
        return (spot + dividends - call) / prior_net - Decimal(1)
    roll_inputs = (old_strike, settlement_value, index_vwav, call_vwap)
    if any(value is None for value in roll_inputs):
        return UnknownReason("missing_cboe_buywrite_roll_return_input")
    strike, soq, vwav, premium = roll_inputs
    assert strike is not None
    assert soq is not None
    assert vwav is not None
    assert premium is not None
    if min(strike, soq, vwav, premium) < 0:
        return UnknownReason("invalid_cboe_buywrite_roll_return_input")
    entry_net = vwav - premium
    if soq <= 0 or entry_net <= 0:
        return UnknownReason("invalid_cboe_buywrite_roll_return_input")
    ra = (soq + dividends - max(Decimal(0), soq - strike)) / prior_net - Decimal(1)
    rb = vwav / soq - Decimal(1)
    rc = (spot - call) / entry_net - Decimal(1)
    return (Decimal(1) + ra) * (Decimal(1) + rb) * (Decimal(1) + rc) - Decimal(1)
