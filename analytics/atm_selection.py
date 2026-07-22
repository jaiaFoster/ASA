"""At-the-money strike selection (LIVE-002).

Standard, provider-neutral option-analytics utility: given the set of
available strikes at one expiration and a spot price, return the strike
closest to spot. This is a textbook-defined, deterministic algorithm, not
a business policy choice -- unlike provider preference (see
screening/live_acquisition.py's own docstring), there is one universally
accepted definition of "at the money."
"""

from __future__ import annotations

from decimal import Decimal


def select_atm_strike(available_strikes: tuple[Decimal, ...], spot_price: Decimal) -> Decimal:
    if not available_strikes:
        raise ValueError("select_atm_strike requires at least one available strike")
    if spot_price <= 0:
        raise ValueError("select_atm_strike requires a positive spot_price")
    return min(available_strikes, key=lambda strike: (abs(strike - spot_price), strike))
