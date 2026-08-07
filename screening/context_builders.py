"""Strategy execution context builders (ANALYTICS-003).

Constructs each target strategy's frozen manifest execution context from
canonical market data. Forward Factor's builder uses analytics/ for the
implied-forward-volatility inputs SPRINT-006 found missing (ANALYTICS-002)
instead of any hardcoded external constant.

Earnings Calendar and Skew Momentum's scoring inputs were hardcoded constants
until SPRINT-011-CLOSEOUT/CLOSE-002 found them. SPRINT-012 replaces their
positional tuple API with explicit named inputs. Strategy-owned normalization
is invoked by orchestration; screening contains no financial formula.

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
from strategies.earnings_calendar_evaluation import (
    build_earnings_calendar_context as _strategy_owned_earnings_calendar_context,
)
from strategies.stonk_components import (
    DATE,
    EXPIRATION_COLLECTION,
    OPTION_CHAIN,
    B,
    D,
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
    front_strike: Decimal,
    back_strike: Decimal,
    earnings_eligible: bool,
    confirmed_earnings_date: date | None = None,
    option_type: OptionType = OptionType.CALL,
) -> ComponentValues:
    """front_strike/back_strike -- SPRINT-011-CLOSEOUT/CLOSE-001: previously
    one shared `strike` was looked up at the front expiration only and
    reused verbatim for the back expiration's own IV lookup. Real chains
    frequently list a different strike ladder at the back (longer-dated)
    expiration than the front, especially for wide-strike-increment names
    (GS, NFLX confirmed in production) -- reusing the front's strike at
    the back expiration then raised NoMatchingContractError whenever that
    exact strike wasn't also listed there. The actual traded structure
    (double_calendar.chain, below) is unaffected -- it selects its own
    strikes internally via delta targeting; this only fixes the two IV
    values compute_option_implied_volatility looks up for the
    implied-forward-volatility inputs.
    """
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
            "strike": front_strike,
            "option_type": option_type,
        }
    )
    back_iv = compute_option_implied_volatility(
        {
            "chain": chain,
            "expiration": back.expiration_date,
            "strike": back_strike,
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
            "factor.front_iv": (D, front_iv),
            "eligibility.earnings_eligible": (B, earnings_eligible),
            "eligibility.confirmed_earnings_date": (
                StrategyTypeReference("Optional", "1.0.0", (DATE,)),
                confirmed_earnings_date,
            ),
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
    term_structure_richness: Decimal,
    iv_realized_volatility_richness: Decimal,
) -> ComponentValues:
    """Compatibility shim (SPRINT-014 S14-PR-05A, Architect checkpoint,
    seventh review, item 4: "do not retain two implementations").

    Owner: strategies/earnings_calendar_evaluation.py, which now holds
    the one real Earnings Calendar context-construction formula.
    Deletion gate: S14-PR-07 (delete the superseded live path) -- at that
    point screening/live_adapters.py, this shim's only remaining caller,
    is deleted along with it. Delegates rather than duplicating so this
    module never drifts out of sync with the strategies-owned original.
    """
    return _strategy_owned_earnings_calendar_context(
        chain,
        event,
        front,
        back,
        as_of,
        target_strike=target_strike,
        term_structure_richness=term_structure_richness,
        iv_realized_volatility_richness=iv_realized_volatility_richness,
    )


def build_skew_momentum_context(
    chain: OptionChain,
    expiration: date,
    *,
    normalized_call_skew: Decimal,
    normalized_put_skew: Decimal,
    call_skew_zscore: Decimal | None,
    put_skew_zscore: Decimal | None,
    historical_valid_observations: int,
    call_atm_iv_minus_rv: Decimal,
    put_atm_iv_minus_rv: Decimal,
    call_wing_iv_minus_rv: Decimal,
    put_wing_iv_minus_rv: Decimal,
    call_wing_iv_minus_atm_iv: Decimal,
    put_wing_iv_minus_atm_iv: Decimal,
    time_series_return: Decimal,
    cross_sectional_percentile: Decimal | None,
    comparison_peer_count: int,
    sector_relative_return: Decimal | None,
) -> ComponentValues:
    """Build the complete named Skew Momentum v2 input boundary."""

    optional_decimal = StrategyTypeReference("Optional", "1.0.0", (D,))
    return _context(
        **{
            "decision.chain": (OPTION_CHAIN, chain),
            "decision.expiration": (DATE, expiration),
            "decision.normalized_call_skew": (D, normalized_call_skew),
            "decision.normalized_put_skew": (D, normalized_put_skew),
            "decision.call_skew_zscore": (optional_decimal, call_skew_zscore),
            "decision.put_skew_zscore": (optional_decimal, put_skew_zscore),
            "decision.historical_valid_observations": (
                _INTEGER,
                historical_valid_observations,
            ),
            "decision.call_atm_iv_minus_rv": (D, call_atm_iv_minus_rv),
            "decision.put_atm_iv_minus_rv": (D, put_atm_iv_minus_rv),
            "decision.call_wing_iv_minus_rv": (D, call_wing_iv_minus_rv),
            "decision.put_wing_iv_minus_rv": (D, put_wing_iv_minus_rv),
            "decision.call_wing_iv_minus_atm_iv": (D, call_wing_iv_minus_atm_iv),
            "decision.put_wing_iv_minus_atm_iv": (D, put_wing_iv_minus_atm_iv),
            "decision.time_series_return": (D, time_series_return),
            "decision.cross_sectional_percentile": (
                optional_decimal,
                cross_sectional_percentile,
            ),
            "decision.comparison_peer_count": (_INTEGER, comparison_peer_count),
            "decision.sector_relative_return": (
                optional_decimal,
                sector_relative_return,
            ),
        }
    )
