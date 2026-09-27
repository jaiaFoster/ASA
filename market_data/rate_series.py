"""Canonical published rate series (X04, SP-01B).

Provider-neutral semantics for each rate series ASA can request: its quoting
basis and tenor. A series with no registered provider (for example the
S&P 500 dividend yield, or a discontinued LIBOR tenor) is still declared,
so a consumer that requires it receives a typed UNKNOWN. It is never mapped
to a substitute series.
"""

from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType

from domain import (
    CanonicalInstrumentIdentity,
    Instrument,
    InstrumentKind,
    RateBasis,
)

RATE_SERIES_SCHEME = "rate_series"


@dataclass(frozen=True, slots=True)
class RateSeriesDefinition:
    series_id: str
    basis: RateBasis
    tenor_days: int | None
    description: str


_DEFINITIONS = (
    RateSeriesDefinition(
        "US_TBILL_4WK_BANK_DISCOUNT",
        RateBasis.BANK_DISCOUNT,
        28,
        "US Treasury 4-week bill closing bank-discount rate",
    ),
    RateSeriesDefinition(
        "US_TBILL_8WK_BANK_DISCOUNT",
        RateBasis.BANK_DISCOUNT,
        56,
        "US Treasury 8-week bill closing bank-discount rate",
    ),
    RateSeriesDefinition(
        "US_TBILL_13WK_BANK_DISCOUNT",
        RateBasis.BANK_DISCOUNT,
        91,
        "US Treasury 13-week bill closing bank-discount rate",
    ),
    RateSeriesDefinition(
        "US_TBILL_26WK_BANK_DISCOUNT",
        RateBasis.BANK_DISCOUNT,
        182,
        "US Treasury 26-week bill closing bank-discount rate",
    ),
    RateSeriesDefinition(
        "US_TBILL_4WK_COUPON_EQUIVALENT",
        RateBasis.COUPON_EQUIVALENT,
        28,
        "US Treasury 4-week bill coupon-equivalent yield",
    ),
    RateSeriesDefinition(
        "US_TBILL_8WK_COUPON_EQUIVALENT",
        RateBasis.COUPON_EQUIVALENT,
        56,
        "US Treasury 8-week bill coupon-equivalent yield",
    ),
    RateSeriesDefinition(
        "US_TBILL_13WK_COUPON_EQUIVALENT",
        RateBasis.COUPON_EQUIVALENT,
        91,
        "US Treasury 13-week bill coupon-equivalent yield",
    ),
    RateSeriesDefinition(
        "US_TBILL_26WK_COUPON_EQUIVALENT",
        RateBasis.COUPON_EQUIVALENT,
        182,
        "US Treasury 26-week bill coupon-equivalent yield",
    ),
    RateSeriesDefinition(
        "SP500_DIVIDEND_YIELD",
        RateBasis.DIVIDEND_YIELD,
        None,
        "S&P 500 index dividend yield (no registered provider: typed UNKNOWN)",
    ),
)

RATE_SERIES = MappingProxyType({item.series_id: item for item in _DEFINITIONS})


def is_rate_series(symbol: str) -> bool:
    return symbol in RATE_SERIES


def rate_series_instrument(series_id: str) -> Instrument:
    if series_id not in RATE_SERIES:
        raise ValueError(f"unknown rate series {series_id!r}")
    return Instrument(
        CanonicalInstrumentIdentity(RATE_SERIES_SCHEME, series_id),
        InstrumentKind.RATE,
        series_id,
        "USD",
    )
