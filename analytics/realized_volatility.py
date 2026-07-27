"""Realized volatility and price momentum from a historical close series
(SPRINT-011-CLOSEOUT/CLOSE-002).

Pure functions over an already-acquired, already-canonical close-price
series (domain.OHLCVBar.close) -- no acquisition, no provider knowledge,
matching this package's own established convention (analytics/
forward_factor.py's identical shape). Used by screening/live_adapters.py
to replace hardcoded score inputs (screening/context_builders.py's
build_skew_momentum_context()/build_earnings_calendar_context(), until
this ticket both silently disconnected from any live market data --
see project/reports/SPRINT-011.md) with real, symbol-specific signals.
"""

from __future__ import annotations

from collections.abc import Sequence
from decimal import Decimal

_TRADING_DAYS_PER_YEAR = Decimal(252)


class InsufficientPriceHistoryError(ValueError):
    """Fewer than two closes were supplied; no return is computable."""


def compute_log_returns(closes: Sequence[Decimal]) -> tuple[Decimal, ...]:
    if len(closes) < 2:
        raise InsufficientPriceHistoryError("at least two closes are required")
    if any(value <= 0 for value in closes):
        raise InsufficientPriceHistoryError("closes must be strictly positive")
    return tuple((closes[i] / closes[i - 1]).ln() for i in range(1, len(closes)))


def compute_realized_volatility(closes: Sequence[Decimal]) -> Decimal:
    """Annualized realized volatility: stdev of daily log returns * sqrt(252),
    the standard, well-known estimator this codebase has no prior
    implementation of (grepped before writing this, per root_cause_policy's
    own do_not_repeat_repository_history_already_available rule) -- not
    ported from anywhere, since there is nowhere to port it from.
    """
    returns = compute_log_returns(closes)
    mean = sum(returns, Decimal(0)) / len(returns)
    variance = sum(((value - mean) ** 2 for value in returns), Decimal(0)) / len(returns)
    return variance.sqrt() * _TRADING_DAYS_PER_YEAR.sqrt()


def compute_trailing_return(closes: Sequence[Decimal]) -> Decimal:
    """Simple time-series momentum: total return from the oldest to the
    newest close in the supplied window (Volatility Vibes, "How to Spot
    10x Vertical Spreads BEFORE They Take Off", 17:10 "Gaining a
    Directional Edge From Momentum" -- time series momentum is "whether a
    stock's recent return is positive or negative").
    """
    if len(closes) < 2:
        raise InsufficientPriceHistoryError("at least two closes are required")
    if closes[0] <= 0:
        raise InsufficientPriceHistoryError("closes must be strictly positive")
    return (closes[-1] - closes[0]) / closes[0]
