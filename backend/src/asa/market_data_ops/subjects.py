"""Fixed, safe validation subjects for bounded live Market Data checks (POST-005B-RAILWAY).

No symbol or endpoint is ever taken from the inbound request; every subject here is a
hard-coded, previously-reviewed, safe read (a single well-known liquid equity).
"""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta

from domain import (
    CanonicalInstrumentIdentity,
    EvidenceKind,
    EvidenceReference,
    Instrument,
    InstrumentKind,
    MarketCapability,
    MarketDataRequestContext,
    MarketDataSubject,
    MarketDataSubjectType,
    ProviderAddressProjection,
)

_SAFE_SYMBOL = "AAPL"
_SAFE_INSTRUMENT = Instrument(
    CanonicalInstrumentIdentity("figi", "BBG000B9XRY4"),
    InstrumentKind.EQUITY,
    _SAFE_SYMBOL,
    "USD",
)
_EVIDENCE = (EvidenceReference(EvidenceKind.OBSERVATION, "ops-validation:fixed-safe-subject"),)

_SUBJECT_TYPE_BY_CAPABILITY = {
    MarketCapability.REAL_TIME_QUOTE_V1: MarketDataSubjectType.INSTRUMENT,
    MarketCapability.HISTORICAL_BARS_V1: MarketDataSubjectType.INSTRUMENT,
    MarketCapability.OPTION_CHAIN_V1: MarketDataSubjectType.OPTION_UNDERLYING,
    MarketCapability.EARNINGS_CALENDAR_V1: MarketDataSubjectType.EARNINGS_SECURITY,
}

# Provider capabilities exercised by the bounded live validation endpoint, per ticket.
PROVIDER_CAPABILITIES: dict[str, tuple[MarketCapability, ...]] = {
    "tradier": (
        MarketCapability.REAL_TIME_QUOTE_V1,
        MarketCapability.HISTORICAL_BARS_V1,
        MarketCapability.OPTION_CHAIN_V1,
    ),
    "finnhub": (
        MarketCapability.REAL_TIME_QUOTE_V1,
        MarketCapability.HISTORICAL_BARS_V1,
        MarketCapability.EARNINGS_CALENDAR_V1,
    ),
    "alpha_vantage": (
        MarketCapability.HISTORICAL_BARS_V1,
        MarketCapability.EARNINGS_CALENDAR_V1,
    ),
}

_REQUIRED_FIELDS_BY_CAPABILITY = {
    MarketCapability.REAL_TIME_QUOTE_V1: ("last",),
    MarketCapability.HISTORICAL_BARS_V1: ("close",),
    MarketCapability.OPTION_CHAIN_V1: ("contracts",),
    MarketCapability.EARNINGS_CALENDAR_V1: ("earnings_date",),
}


def _next_monthly_expiration(as_of: datetime) -> date:
    """The next third-Friday-of-the-month strictly after as_of (a standard, liquid
    equity option expiration cycle), matching tradier._is_monthly_expiration.
    """
    year, month = as_of.year, as_of.month
    while True:
        third_friday = date(year, month, 15)
        third_friday += timedelta(days=(4 - third_friday.weekday()) % 7)
        if third_friday > as_of.date():
            return third_friday
        month, year = (1, year + 1) if month == 12 else (month + 1, year)


def build_validation_subject(
    provider_id: str, capability: MarketCapability, *, as_of: datetime
) -> MarketDataSubject:
    subject_type = _SUBJECT_TYPE_BY_CAPABILITY[capability]
    window_start = as_of - timedelta(days=30)
    projections = [
        ProviderAddressProjection(
            provider_id, "v1", "symbol", _SAFE_SYMBOL, window_start, None, _EVIDENCE
        )
    ]
    if capability is MarketCapability.OPTION_CHAIN_V1:
        expiration = _next_monthly_expiration(as_of)
        projections.append(
            ProviderAddressProjection(
                provider_id,
                "v1",
                "expiration",
                expiration.isoformat(),
                window_start,
                None,
                _EVIDENCE,
            )
        )
    context = MarketDataRequestContext(
        window_start,
        as_of,
        _REQUIRED_FIELDS_BY_CAPABILITY[capability],
        tuple(projections),
        _EVIDENCE,
    )
    return MarketDataSubject(_SAFE_INSTRUMENT, subject_type, capability, context)


def utcnow() -> datetime:
    return datetime.now(UTC)
