"""Canonical reusable financial calculations for SPRINT-012."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import date
from decimal import ROUND_HALF_EVEN, Context, Decimal, localcontext

from analytics.registry import AnalyticsFeatureDefinition, AnalyticsRegistry
from domain import (
    ComparisonUniverseReturns,
    HistoricalSkewObservations,
    MarketCapability,
    SectorReferenceReturns,
)

DERIVED_FACT_DECIMAL_CONTEXT = Context(prec=34, rounding=ROUND_HALF_EVEN)

REALIZED_VOLATILITY = "realized_volatility"
IMPLIED_FORWARD_VOLATILITY = "implied_forward_volatility"
FORWARD_FACTOR = "forward_factor"
DAYS_TO_EARNINGS = "days_to_earnings"
EARNINGS_INSIDE_TRADE_WINDOW = "earnings_inside_trade_window"
NO_CONFIRMED_EARNINGS_THROUGH_EXPIRATION = "no_confirmed_earnings_through_expiration"
EXPIRATION_GAP_DAYS = "expiration_gap_days"
EXPIRATION_GAP_DISTANCE = "expiration_gap_distance_from_target"
NORMALIZED_CALL_SKEW = "normalized_call_skew"
NORMALIZED_PUT_SKEW = "normalized_put_skew"
SKEW_HISTORICAL_PERCENTILE = "skew_historical_percentile"
SKEW_HISTORICAL_ZSCORE = "skew_historical_zscore"
ATM_IV_VS_REALIZED = "atm_iv_vs_realized_volatility"
CALL_WING_IV_VS_REALIZED = "call_wing_iv_vs_realized_volatility"
PUT_WING_IV_VS_REALIZED = "put_wing_iv_vs_realized_volatility"
NAMED_MOMENTUM_DIMENSIONS = "named_momentum_dimensions"
CROSS_SECTIONAL_MOMENTUM = "cross_sectional_momentum"
SECTOR_RELATIVE_MOMENTUM = "sector_relative_momentum"
OPTION_VOLUME_BAND = "option_volume_band"
SPREAD_QUALITY = "spread_quality"
OPEN_INTEREST_QUALITY = "open_interest_quality"


def compute_implied_forward_volatility(
    front_iv: Decimal,
    back_iv: Decimal,
    front_dte: int,
    back_dte: int,
) -> Decimal:
    """Forward volatility implied between two expirations."""

    if min(front_iv, back_iv) <= 0:
        raise ValueError("implied volatilities must be positive")
    if front_dte <= 0 or back_dte <= front_dte:
        raise ValueError("DTE values must be positive and strictly increasing")
    with localcontext(DERIVED_FACT_DECIMAL_CONTEXT):
        variance = (back_iv**2 * Decimal(back_dte) - front_iv**2 * Decimal(front_dte)) / Decimal(
            back_dte - front_dte
        )
        if variance <= 0:
            raise ValueError("forward variance must be positive")
        return variance.sqrt()


def compute_forward_factor(front_iv: Decimal, implied_forward_volatility: Decimal) -> Decimal:
    if implied_forward_volatility <= 0:
        raise ValueError("implied forward volatility must be positive")
    with localcontext(DERIVED_FACT_DECIMAL_CONTEXT):
        return front_iv / implied_forward_volatility - Decimal(1)


def compute_days_to_earnings(as_of: date, earnings_date: date) -> int:
    return (earnings_date - as_of).days


def compute_earnings_inside_trade_window(
    earnings_date: date, front_expiration: date, back_expiration: date
) -> bool:
    if back_expiration <= front_expiration:
        raise ValueError("back expiration must follow front expiration")
    return front_expiration < earnings_date <= back_expiration


def compute_no_confirmed_earnings_through_expiration(
    *,
    confirmed: bool,
    earnings_date: date,
    as_of: date,
    back_expiration: date,
) -> bool:
    if back_expiration < as_of:
        raise ValueError("back expiration cannot precede as_of")
    return not (confirmed and as_of <= earnings_date <= back_expiration)


def compute_expiration_gap_days(front_expiration: date, back_expiration: date) -> int:
    gap = (back_expiration - front_expiration).days
    if gap <= 0:
        raise ValueError("back expiration must follow front expiration")
    return gap


def compute_expiration_gap_distance(
    front_expiration: date, back_expiration: date, target_days: int
) -> int:
    if target_days < 0:
        raise ValueError("target_days must be non-negative")
    return abs(compute_expiration_gap_days(front_expiration, back_expiration) - target_days)


def compute_normalized_skew(atm_iv: Decimal, wing_iv: Decimal) -> Decimal:
    if atm_iv <= 0 or wing_iv < 0:
        raise ValueError("implied volatilities must be valid")
    return (wing_iv - atm_iv) / atm_iv


def compute_historical_percentile(current: Decimal, history: Sequence[Decimal]) -> Decimal:
    if not history:
        raise ValueError("history cannot be empty")
    less_or_equal = sum(1 for value in history if value <= current)
    return Decimal(less_or_equal) / Decimal(len(history))


def compute_historical_zscore(current: Decimal, history: Sequence[Decimal]) -> Decimal:
    if len(history) < 2:
        raise ValueError("at least two historical values are required")
    with localcontext(DERIVED_FACT_DECIMAL_CONTEXT):
        mean = sum(history, Decimal(0)) / Decimal(len(history))
        variance = sum(((value - mean) ** 2 for value in history), Decimal(0)) / Decimal(
            len(history)
        )
        if variance == 0:
            raise ValueError("historical variance must be positive")
        return (current - mean) / variance.sqrt()


def compute_skew_stretch_distributions(
    current_call_skew: Decimal,
    current_put_skew: Decimal,
    history: HistoricalSkewObservations,
) -> tuple[Decimal, Decimal, Decimal, Decimal]:
    """Return call/put percentile and z-score without choosing strategy policy."""

    call_history = tuple(item.call_skew for item in history.observations)
    put_history = tuple(item.put_skew for item in history.observations)
    return (
        compute_historical_percentile(current_call_skew, call_history),
        compute_historical_zscore(current_call_skew, call_history),
        compute_historical_percentile(current_put_skew, put_history),
        compute_historical_zscore(current_put_skew, put_history),
    )


def compute_cross_sectional_momentum(
    subject_return: Decimal,
    comparison_returns: ComparisonUniverseReturns,
) -> Decimal:
    """Exact empirical percentile against an explicitly supplied universe."""

    return compute_historical_percentile(
        subject_return,
        tuple(item.return_value for item in comparison_returns.returns),
    )


def compute_sector_relative_momentum(
    subject_return: Decimal,
    sector_returns: SectorReferenceReturns,
) -> Decimal:
    """Subject return minus the equally weighted explicit sector reference."""

    values = tuple(item.return_value for item in sector_returns.returns)
    with localcontext(DERIVED_FACT_DECIMAL_CONTEXT):
        return subject_return - sum(values, Decimal(0)) / Decimal(len(values))


def compute_iv_realized_spread(
    implied_volatility: Decimal, realized_volatility: Decimal
) -> Decimal:
    if min(implied_volatility, realized_volatility) < 0:
        raise ValueError("volatilities must be non-negative")
    return implied_volatility - realized_volatility


def compute_bid_ask_spread_ratio(bid: Decimal | None, ask: Decimal | None) -> Decimal:
    if bid is None or ask is None or bid < 0 or ask < bid:
        raise ValueError("valid ordered bid and ask are required")
    midpoint = (bid + ask) / Decimal(2)
    if midpoint <= 0:
        raise ValueError("bid/ask midpoint must be positive")
    return (ask - bid) / midpoint


def compute_option_volume_band(volume: int | None) -> int:
    """Raw coarse order-of-magnitude band; interpretation belongs to strategy."""

    if volume is None:
        return 0
    if volume < 0:
        raise ValueError("volume must be non-negative")
    if volume == 0:
        return 0
    return len(str(volume))


def compute_open_interest_quality(open_interest: int | None) -> int:
    """Canonical raw open interest; thresholds belong to strategy policy."""

    if open_interest is None:
        return 0
    if open_interest < 0:
        raise ValueError("open_interest must be non-negative")
    return open_interest


def compute_momentum_dimensions(
    closes: Sequence[Decimal],
) -> tuple[Decimal, Decimal]:
    from analytics.realized_volatility import (
        compute_realized_volatility,
        compute_trailing_return,
    )

    return compute_trailing_return(closes), compute_realized_volatility(closes)


def _definition(
    feature_id: str,
    description: str,
    *capabilities: MarketCapability,
) -> AnalyticsFeatureDefinition:
    return AnalyticsFeatureDefinition(feature_id, "1.0.0", description, tuple(capabilities))


DERIVED_FACT_DEFINITIONS = (
    _definition(
        REALIZED_VOLATILITY,
        "Annualized population volatility of canonical daily log returns.",
        MarketCapability.HISTORICAL_BARS_V1,
    ),
    _definition(
        IMPLIED_FORWARD_VOLATILITY,
        "Forward volatility implied by two canonical expiration IVs.",
        MarketCapability.OPTION_CHAIN_V1,
    ),
    _definition(
        FORWARD_FACTOR,
        "Front implied volatility divided by implied forward volatility minus one.",
        MarketCapability.OPTION_CHAIN_V1,
    ),
    _definition(
        DAYS_TO_EARNINGS,
        "Calendar days from effective date to confirmed earnings.",
        MarketCapability.EARNINGS_CALENDAR_V1,
    ),
    _definition(
        EARNINGS_INSIDE_TRADE_WINDOW,
        "Whether earnings occurs after front and through back expiration.",
        MarketCapability.EARNINGS_CALENDAR_V1,
        MarketCapability.OPTION_CHAIN_V1,
    ),
    _definition(
        NO_CONFIRMED_EARNINGS_THROUGH_EXPIRATION,
        "Whether no confirmed earnings occurs from as-of through back expiration.",
        MarketCapability.EARNINGS_CALENDAR_V1,
        MarketCapability.OPTION_CHAIN_V1,
    ),
    _definition(
        EXPIRATION_GAP_DAYS,
        "Calendar-day distance between selected expirations.",
        MarketCapability.OPTION_CHAIN_V1,
    ),
    _definition(
        EXPIRATION_GAP_DISTANCE,
        "Absolute distance between actual and target expiration gap.",
        MarketCapability.OPTION_CHAIN_V1,
    ),
    _definition(
        CROSS_SECTIONAL_MOMENTUM,
        "Subject return empirical percentile within an explicit comparison universe.",
        MarketCapability.HISTORICAL_BARS_V1,
    ),
    _definition(
        SECTOR_RELATIVE_MOMENTUM,
        "Subject return minus an explicit equally weighted sector reference.",
        MarketCapability.HISTORICAL_BARS_V1,
    ),
    *(
        _definition(
            identifier,
            "Provider-neutral normalized option skew.",
            MarketCapability.OPTION_CHAIN_V1,
        )
        for identifier in (NORMALIZED_CALL_SKEW, NORMALIZED_PUT_SKEW)
    ),
    *(
        _definition(
            identifier,
            "Historical location of normalized skew.",
            MarketCapability.OPTION_CHAIN_V1,
        )
        for identifier in (
            SKEW_HISTORICAL_PERCENTILE,
            SKEW_HISTORICAL_ZSCORE,
        )
    ),
    *(
        _definition(
            identifier,
            "Implied volatility minus realized volatility.",
            MarketCapability.OPTION_CHAIN_V1,
            MarketCapability.HISTORICAL_BARS_V1,
        )
        for identifier in (
            ATM_IV_VS_REALIZED,
            CALL_WING_IV_VS_REALIZED,
            PUT_WING_IV_VS_REALIZED,
        )
    ),
    _definition(
        NAMED_MOMENTUM_DIMENSIONS,
        "Trailing return and realized volatility over canonical closes.",
        MarketCapability.HISTORICAL_BARS_V1,
    ),
    *(
        _definition(
            identifier,
            "Raw option-liquidity dimension without strategy thresholds.",
            MarketCapability.OPTION_CHAIN_V1,
        )
        for identifier in (
            OPTION_VOLUME_BAND,
            SPREAD_QUALITY,
            OPEN_INTEREST_QUALITY,
        )
    ),
)

DERIVED_FACT_REGISTRY = AnalyticsRegistry(DERIVED_FACT_DEFINITIONS)
