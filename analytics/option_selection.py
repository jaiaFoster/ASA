"""Deterministic selection over canonical option-chain coordinates."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from analytics.errors import NoMatchingContractError
from domain import OptionChain, OptionContract, OptionType


def select_canonical_contract(
    chain: OptionChain,
    expiration: date,
    strike: Decimal,
    option_type: OptionType,
) -> OptionContract:
    """Return the first canonical match at shared economic coordinates.

    Standard and adjusted contracts can have distinct canonical identities
    while sharing expiration, strike, and type. ``OptionChain`` already
    sorts those identities deterministically; no strategy may assume the
    economic coordinates themselves are unique.
    """
    matches = chain.find(
        expiration=expiration,
        strike=strike,
        option_type=option_type,
    )
    if not matches:
        raise NoMatchingContractError(expiration.isoformat(), str(strike))
    return matches[0]
