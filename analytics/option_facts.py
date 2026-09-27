"""Reusable single-option and position facts (SP-01E).

Formula ids and versions are declared in `analytics.formulas`. `OptionContract.mark`
is the provider's last trade. It is never used here as a midpoint.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import date
from decimal import Decimal

from analytics.derived_facts import compute_bid_ask_spread_ratio
from analytics.forward_factor import compute_days_to_expiration
from domain import UnknownReason

TWO = Decimal(2)


def option_mid(bid: Decimal | None, ask: Decimal | None) -> Decimal | UnknownReason:
    """DF-OPT-MID 1.0.0: (bid + ask) / 2 from one snapshot."""
    if bid is None or ask is None:
        return UnknownReason("missing_bid_or_ask")
    if bid > ask:
        return UnknownReason("crossed_quote")
    return (bid + ask) / TWO


def option_relative_spread(bid: Decimal | None, ask: Decimal | None) -> Decimal | UnknownReason:
    """DF-OPT-RELATIVE-SPREAD 1.0.0: (ask - bid) / mid.

    One formula owner: delegates to the registered
    `compute_bid_ask_spread_ratio` and types its precondition failures as
    UNKNOWN instead of raising.
    """
    mid = option_mid(bid, ask)
    if isinstance(mid, UnknownReason):
        return mid
    if mid <= 0:
        return UnknownReason("zero_midpoint")
    try:
        return compute_bid_ask_spread_ratio(bid, ask)
    except ValueError:
        return UnknownReason("invalid_bid_or_ask")


def option_weighted_spread(
    legs: Sequence[tuple[Decimal, Decimal | None, Decimal | None]],
) -> Decimal | UnknownReason:
    """DF-OPT-WEIGHTED-SPREAD 1.0.0 over (weight, bid, ask) legs.

    sum |q| (ask - bid) / sum |q| mid. The source leaves value vs. contract
    weighting unstated; callers pass the weights their manifest declares.
    """
    if not legs:
        return UnknownReason("no_legs")
    spread_total = Decimal(0)
    mid_total = Decimal(0)
    for weight, bid, ask in legs:
        mid = option_mid(bid, ask)
        if isinstance(mid, UnknownReason):
            return mid
        assert bid is not None and ask is not None
        spread_total += abs(weight) * (ask - bid)
        mid_total += abs(weight) * mid
    if mid_total == 0:
        return UnknownReason("zero_midpoint")
    return spread_total / mid_total


def option_effective_price(
    bid: Decimal | None, ask: Decimal | None, k: Decimal, *, buy: bool
) -> Decimal | UnknownReason:
    """DF-OPT-EFFECTIVE-PRICE 1.0.0: mid ± k (ask - bid) / 2; k is an evaluation parameter."""
    if not Decimal(0) <= k <= Decimal(1):
        raise ValueError("effective spread ratio k must be within [0, 1]")
    mid = option_mid(bid, ask)
    if isinstance(mid, UnknownReason):
        return mid
    assert bid is not None and ask is not None
    half = k * (ask - bid) / TWO
    return mid + half if buy else mid - half


def _require_positive_strike(strike: Decimal) -> None:
    if strike <= 0:
        raise ValueError("strike must be positive")


def moneyness_strike_over_spot(strike: Decimal, spot: Decimal | None) -> Decimal | UnknownReason:
    """DF-OPT-MONEYNESS-KS 1.0.0: K / S."""
    _require_positive_strike(strike)
    if spot is None or spot <= 0:
        return UnknownReason("missing_underlying_price")
    return strike / spot


def moneyness_spot_over_strike(strike: Decimal, spot: Decimal | None) -> Decimal | UnknownReason:
    """DF-OPT-MONEYNESS-SK 1.0.0: S / K."""
    _require_positive_strike(strike)
    if spot is None or spot <= 0:
        return UnknownReason("missing_underlying_price")
    return spot / strike


def calendar_days_to_expiration(expiration: date, as_of: date) -> int | UnknownReason:
    """DF-OPT-DTE-CALENDAR 1.0.0.

    The research registry marks this EXISTING: it is the registered
    `days_to_expiration` 1.0.0 feature (`analytics/forward_factor.py`). This
    wrapper delegates to that single owner and types expiration < as-of as
    UNKNOWN instead of raising.
    """
    if expiration < as_of:
        return UnknownReason("expiration_before_as_of")
    return int(compute_days_to_expiration({"expiration": expiration, "as_of": as_of}))


def option_holding_return(
    entry_price: Decimal | None, exit_price: Decimal | None
) -> Decimal | UnknownReason:
    """DF-OPT-HOLDING-RETURN 1.0.0: V1 / V0 - 1."""
    if entry_price is None or exit_price is None:
        return UnknownReason("missing_option_price")
    if entry_price <= 0:
        return UnknownReason("non_positive_entry_price")
    return exit_price / entry_price - 1


def delta_neutral_hedge_quantity(
    delta: Decimal | None, option_quantity: Decimal, multiplier: Decimal, *, long_option: bool
) -> Decimal | UnknownReason:
    """DF-DELTA-NEUTRAL-HEDGE-QUANTITY 1.0.0: -sign · Δ · n · multiplier (static).

    A written call (sign -1) hedges with +Δ·n·multiplier underlying units.
    """
    if delta is None:
        return UnknownReason("missing_delta")
    if option_quantity <= 0 or multiplier <= 0:
        raise ValueError("option_quantity and multiplier must be positive")
    sign = Decimal(1) if long_option else Decimal(-1)
    return -sign * delta * option_quantity * multiplier
