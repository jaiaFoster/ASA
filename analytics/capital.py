"""Collateral accrual facts (SP-01E).

Margin and collateral *models* (A15) are added by SP-03A/SP-04A. This module
holds the reusable accrual formula they build on.
"""

from __future__ import annotations

from decimal import Decimal

from domain import UnknownReason

TBILL_TENOR_DAYS = frozenset({28, 91})


def cboe_tbill_daily_accrual(
    bank_discount_rate: Decimal | None, tenor_days: int, elapsed_calendar_days: int
) -> Decimal | UnknownReason:
    """DF-CBOE-TBILL-DAILY-ACCRUAL 1.0.0.

    r = (1 / (1 - (n/360)·USBR))^(d/n) - 1 with n = 28 (4-week) or 91 (13-week)
    and d the calendar days between closes.
    """
    if tenor_days not in TBILL_TENOR_DAYS:
        raise ValueError("tenor_days must be 28 or 91")
    if elapsed_calendar_days < 0:
        raise ValueError("elapsed_calendar_days must be non-negative")
    if bank_discount_rate is None:
        return UnknownReason("missing_treasury_bank_discount_rate")
    n = Decimal(tenor_days)
    price_ratio = Decimal(1) - n / Decimal(360) * bank_discount_rate
    if price_ratio <= 0:
        return UnknownReason("invalid_treasury_bank_discount_rate")
    growth: Decimal = (Decimal(1) / price_ratio) ** (Decimal(elapsed_calendar_days) / n)
    return growth - 1
