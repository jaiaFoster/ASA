from __future__ import annotations

import dataclasses
import json
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

import pytest

from domain import (
    CanonicalInstrumentIdentity,
    CompletenessMetadata,
    CorporateActionPlaceholder,
    CorporateActionStatus,
    CorporateActionType,
    DomainInvariantError,
    EvidenceKind,
    EvidenceReference,
    FreshnessMetadata,
    FreshnessStatus,
    Instrument,
    InstrumentKind,
    MarketCapability,
    MarketDataRequestContext,
    MarketDataSubject,
    MarketDataSubjectType,
    MarketObservation,
    NormalizedProviderErrorMetadata,
    OHLCVBar,
    ProviderErrorKind,
    ProviderAddressProjection,
    ProviderProvenance,
    Quote,
    TradingCalendarEvent,
    TradingCalendarEventType,
    deserialize_market_data,
    market_observation_identity,
    serialize_market_data,
)

NOW = datetime(2026, 7, 21, 16, 0, tzinfo=timezone.utc)
INSTRUMENT = Instrument(
    CanonicalInstrumentIdentity("figi", "BBG000B9XRY4"),
    InstrumentKind.EQUITY,
    "AAPL",
    "USD",
)
EVIDENCE = (EvidenceReference(EvidenceKind.OBSERVATION, "provider-evidence"),)


def subject(
    capability: MarketCapability = MarketCapability.REAL_TIME_QUOTE_V1,
) -> MarketDataSubject:
    projection = ProviderAddressProjection("fixture", "v1", "symbol", "AAPL", NOW, None, EVIDENCE)
    return MarketDataSubject(
        INSTRUMENT,
        MarketDataSubjectType.INSTRUMENT,
        capability,
        MarketDataRequestContext(NOW, NOW, ("last",), (projection,), EVIDENCE),
    )


def quote() -> Quote:
    return Quote(
        INSTRUMENT,
        Decimal("210.10"),
        Decimal("210.20"),
        Decimal("210.15"),
        Decimal("100"),
        Decimal("120"),
        Decimal("1000000"),
        "USD",
    )


def bar() -> OHLCVBar:
    return OHLCVBar(
        INSTRUMENT,
        86400,
        NOW - timedelta(days=1),
        NOW,
        Decimal("205"),
        Decimal("212"),
        Decimal("204"),
        Decimal("210"),
        Decimal("50000000"),
    )


def observation() -> MarketObservation:
    value = quote()
    identity = market_observation_identity(
        "fixture", MarketCapability.REAL_TIME_QUOTE_V1, subject(), NOW, value, "v1"
    )
    return MarketObservation(
        identity,
        MarketCapability.REAL_TIME_QUOTE_V1,
        subject(),
        NOW,
        NOW + timedelta(seconds=1),
        value,
        "v1",
        ProviderProvenance("fixture", "request-1", EVIDENCE),
        FreshnessMetadata(NOW + timedelta(seconds=10), NOW, 60, 10, FreshnessStatus.FRESH),
        CompletenessMetadata(("last",), ("last",), ()),
    )


def contracts() -> tuple[object, ...]:
    return (
        quote(),
        bar(),
        TradingCalendarEvent("XNAS", TradingCalendarEventType.OPEN, NOW, NOW, date(2026, 7, 21)),
        CorporateActionPlaceholder(
            INSTRUMENT,
            CorporateActionType.DIVIDEND,
            date(2026, 8, 1),
            CorporateActionStatus.ANNOUNCED,
            "event-1",
        ),
        FreshnessMetadata(NOW, NOW, 60, 0, FreshnessStatus.FRESH),
        CompletenessMetadata(("bid", "last"), ("last",), ("bid",)),
        ProviderProvenance("fixture", "request-1", EVIDENCE),
        NormalizedProviderErrorMetadata(
            ProviderErrorKind.RATE_LIMIT, "QUOTA_EXHAUSTED", True, "quota exhausted"
        ),
        subject().request_context.provider_address_projections[0],
        subject().request_context,
        subject(),
        observation(),
    )


@pytest.mark.parametrize("value", contracts())
def test_market_data_contracts_are_immutable_and_round_trip(value: object) -> None:
    assert dataclasses.is_dataclass(value)
    assert value.__dataclass_params__.frozen  # type: ignore[attr-defined]
    payload = serialize_market_data(value)  # type: ignore[arg-type]
    assert deserialize_market_data(payload) == value
    assert (
        json.dumps(json.loads(payload), sort_keys=True, separators=(",", ":")).encode() == payload
    )
    with pytest.raises(dataclasses.FrozenInstanceError):
        setattr(value, dataclasses.fields(value)[0].name, "changed")


def test_quote_requires_price_and_preserves_decimal_precision() -> None:
    with pytest.raises(DomainInvariantError, match="at least one price"):
        Quote(INSTRUMENT, None, None, None, None, None, None, "USD")
    assert deserialize_market_data(serialize_market_data(quote())) == quote()
    assert b"210.10" not in serialize_market_data(quote())


def test_bar_requires_utc_aware_coherent_window_and_prices() -> None:
    with pytest.raises(DomainInvariantError, match="timezone-aware"):
        dataclasses.replace(bar(), start_at=NOW.replace(tzinfo=None))
    with pytest.raises(DomainInvariantError, match="high is incoherent"):
        dataclasses.replace(bar(), high=Decimal("200"))


def test_stale_evidence_can_never_report_fresh() -> None:
    with pytest.raises(DomainInvariantError, match="stale evidence"):
        FreshnessMetadata(NOW + timedelta(seconds=61), NOW, 60, 61, FreshnessStatus.FRESH)


def test_market_observation_identity_excludes_recorded_time_and_is_content_derived() -> None:
    first = observation()
    later = dataclasses.replace(first, recorded_time=first.recorded_time + timedelta(seconds=5))
    assert later.observation_id == first.observation_id
    with pytest.raises(DomainInvariantError, match="content-derived"):
        dataclasses.replace(first, observation_id="fabricated")


def test_observation_value_must_match_capability() -> None:
    with pytest.raises(DomainInvariantError, match="capability mismatch"):
        dataclasses.replace(observation(), capability=MarketCapability.HISTORICAL_BARS_V1)


def test_provider_neutral_contracts_have_no_sdk_or_secret_fields() -> None:
    names = {field.name for contract in contracts() for field in dataclasses.fields(contract)}
    assert not names & {"token", "api_key", "password", "cookie", "raw_payload", "sdk_response"}
