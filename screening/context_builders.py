"""Strategy execution context builders (ANALYTICS-003).

Constructs each target strategy's frozen manifest execution context from
canonical market data. Forward Factor's builder uses analytics/ for the
implied-forward-volatility inputs SPRINT-006 found missing (ANALYTICS-002)
instead of any hardcoded external constant; Earnings Calendar and Skew
Momentum need no derived analytics, so their builders just isolate the
context-construction logic previously inline in screening/adapters.py into
separately testable functions.

Adapters only: no strategy modification, no provider import. Every builder
here takes already-canonical domain objects and produces a ComponentValues
context for the existing, unmodified manifest to consume verbatim -- this
is exactly what lets LIVE-001/002 later supply live-acquired canonical data
to the same builders without changing anything here.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from analytics.expiration_selection import ExpirationCandidate, select_expiration_pair
from analytics.forward_factor import compute_days_to_expiration, compute_option_implied_volatility
from domain import EarningsEvent, ExpirationCollection, ExpirationCycle, OptionChain, OptionType
from strategies.stonk_components import (
    D,
    DATE,
    DECIMAL_LIST,
    EARNINGS_EVENT,
    EXPIRATION_COLLECTION,
    EXPIRATION_CYCLE,
    OPTION_CHAIN,
    OPTION_CONTRACT,
)
from strategies.type_system import ComponentValues, StrategyTypeReference, TypedValue

# Mirrors FORWARD_FACTOR_CALENDAR_MANIFEST's own frozen dte_pair_selector
# node parameters (strategies/stonk_manifests.py). The manifest exposes no
# queryable API for these, so the policy is deliberately duplicated here
# to select a consistent pair for this separate, non-graph-connected branch
# -- not invented, and not a modification of the manifest itself.
FORWARD_FACTOR_DTE_POLICY = {
    "front_min_dte": 35,
    "front_max_dte": 90,
    "back_min_dte": 49,
    "back_max_dte": 139,
    "minimum_gap_days": 14,
    "maximum_gap_days": 49,
    "target_front_dte": 60,
    "target_gap_days": 30,
}

_INTEGER = StrategyTypeReference("Integer", "1.0.0")


class NoValidExpirationPairError(ValueError):
    """No front/back expiration pair in the available pool satisfies the
    target strategy's DTE and gap policy.
    """


def _context(**items: tuple[StrategyTypeReference, object]) -> ComponentValues:
    return ComponentValues(
        tuple((name, TypedValue(type_ref, value)) for name, (type_ref, value) in items.items())
    )


def build_forward_factor_context(
    chain: OptionChain,
    available_expirations: tuple[ExpirationCycle, ...],
    as_of: date,
    *,
    strike: Decimal,
    option_type: OptionType = OptionType.CALL,
) -> ComponentValues:
    candidates = tuple(
        ExpirationCandidate(cycle.expiration_date, cycle.days_to_expiration)
        for cycle in available_expirations
    )
    selected = select_expiration_pair(candidates, **FORWARD_FACTOR_DTE_POLICY)
    if selected is None:
        raise NoValidExpirationPairError(
            "no front/back expiration pair satisfies Forward Factor's DTE policy"
        )
    front, back = selected
    front_cycle = next(
        cycle for cycle in available_expirations if cycle.expiration_date == front.expiration_date
    )
    back_cycle = next(
        cycle for cycle in available_expirations if cycle.expiration_date == back.expiration_date
    )

    front_dte = compute_days_to_expiration({"expiration": front.expiration_date, "as_of": as_of})
    back_dte = compute_days_to_expiration({"expiration": back.expiration_date, "as_of": as_of})
    front_iv = compute_option_implied_volatility(
        {
            "chain": chain,
            "expiration": front.expiration_date,
            "strike": strike,
            "option_type": option_type,
        }
    )
    back_iv = compute_option_implied_volatility(
        {
            "chain": chain,
            "expiration": back.expiration_date,
            "strike": strike,
            "option_type": option_type,
        }
    )

    expirations = ExpirationCollection(as_of, (front_cycle, back_cycle))
    return _context(
        **{
            "expiration_select.expirations": (EXPIRATION_COLLECTION, expirations),
            "double_calendar.chain": (OPTION_CHAIN, chain),
            "forward_iv.front_iv": (D, front_iv),
            "forward_iv.back_iv": (D, back_iv),
            "forward_iv.front_dte": (_INTEGER, int(front_dte)),
            "forward_iv.back_dte": (_INTEGER, int(back_dte)),
            "factor.front_ex_earnings_iv": (D, front_iv),
        }
    )


def build_earnings_calendar_context(
    chain: OptionChain,
    event: EarningsEvent,
    front: ExpirationCycle,
    back: ExpirationCycle,
    as_of: date,
    *,
    target_strike: Decimal,
) -> ComponentValues:
    return _context(
        **{
            "event_window.event": (EARNINGS_EVENT, event),
            "event_window.front": (EXPIRATION_CYCLE, front),
            "event_window.back": (EXPIRATION_CYCLE, back),
            "expiration_select.expirations": (
                EXPIRATION_COLLECTION,
                ExpirationCollection(as_of, (back, front)),
            ),
            "expiration_select.event": (EARNINGS_EVENT, event),
            "calendar.chain": (OPTION_CHAIN, chain),
            "calendar.target_strike": (D, target_strike),
            "score.values": (DECIMAL_LIST, (Decimal("80"), Decimal("60"))),
            "score.weights": (DECIMAL_LIST, (Decimal("3"), Decimal("1"))),
        }
    )


def build_skew_momentum_context(
    chain: OptionChain,
    expiration: date,
    *,
    strike: Decimal,
    option_type: OptionType = OptionType.CALL,
) -> ComponentValues:
    (contract,) = chain.find(expiration=expiration, strike=strike, option_type=option_type)
    return _context(
        **{
            "vertical.chain": (OPTION_CHAIN, chain),
            "vertical.expiration": (DATE, expiration),
            "liquidity.contract": (OPTION_CONTRACT, contract),
            "score.values": (DECIMAL_LIST, (Decimal("80"), Decimal("70"))),
            "score.weights": (DECIMAL_LIST, (Decimal("2"), Decimal("1"))),
        }
    )
