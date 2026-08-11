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
    ExpirationCollection,
    ExpirationCycle,
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
    OHLCVSeries,
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
from domain.market_data import MarketObservationValue

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


def series(*bars: OHLCVBar) -> OHLCVSeries:
    return OHLCVSeries(INSTRUMENT, 86400, NOW, bars or (bar(),))


def expiration_cycle(expiration_date: date = date(2026, 8, 21)) -> ExpirationCycle:
    return ExpirationCycle(expiration_date, 31, True, False, NOW.date(), EVIDENCE)


def expiration_collection() -> ExpirationCollection:
    return ExpirationCollection(NOW.date(), (expiration_cycle(),))


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
        series(),
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


class TestOHLCVSeries:
    """SPRINT-014 S14-PR-05A, Founder-approved bounded contract extension:
    one historical-bars request legitimately produces many bars, but the
    generic subject planner and ObservationResolver both assume at most
    one observation per provider per capability. OHLCVSeries bundles every
    bar from one request into one value, mirroring domain.financial.
    ExpirationCollection's own established shape for OPTION_CHAIN_V1.
    """

    def test_requires_at_least_one_bar(self) -> None:
        with pytest.raises(DomainInvariantError, match="at least one bar"):
            OHLCVSeries(INSTRUMENT, 86400, NOW, ())

    def test_bars_are_sorted_oldest_first_regardless_of_construction_order(self) -> None:
        older = bar()
        newer = dataclasses.replace(
            bar(), start_at=NOW + timedelta(days=1), end_at=NOW + timedelta(days=2)
        )
        forward = OHLCVSeries(INSTRUMENT, 86400, NOW + timedelta(days=2), (older, newer))
        backward = OHLCVSeries(INSTRUMENT, 86400, NOW + timedelta(days=2), (newer, older))
        assert forward.bars == backward.bars == (older, newer)

    def test_bars_must_share_the_series_instrument(self) -> None:
        other = Instrument(
            CanonicalInstrumentIdentity("figi", "BBG000B9ZJ35"),
            InstrumentKind.EQUITY,
            "MSFT",
            "USD",
        )
        mismatched = dataclasses.replace(bar(), instrument=other)
        with pytest.raises(DomainInvariantError, match="share the series instrument"):
            OHLCVSeries(INSTRUMENT, 86400, NOW, (mismatched,))

    def test_bars_must_share_interval_seconds(self) -> None:
        with pytest.raises(DomainInvariantError, match="share interval_seconds"):
            OHLCVSeries(INSTRUMENT, 3600, NOW, (bar(),))

    def test_as_of_must_not_precede_a_bar(self) -> None:
        with pytest.raises(DomainInvariantError, match="as_of precedes"):
            OHLCVSeries(INSTRUMENT, 86400, NOW - timedelta(days=1), (bar(),))

    def test_duplicate_start_at_values_are_rejected(self) -> None:
        with pytest.raises(DomainInvariantError, match="duplicate bar start_at"):
            OHLCVSeries(INSTRUMENT, 86400, NOW, (bar(), bar()))

    def test_round_trips_through_serialize_market_data(self) -> None:
        assert deserialize_market_data(serialize_market_data(series())) == series()


class TestCollectionValuedObservations:
    """The observation-level round-trip that actually matters: a
    MarketObservation wrapping the new collection values serializes and
    deserializes correctly, and MarketObservation's own capability
    validation accepts each collection for its established capability.
    """

    def _observation_with(
        self,
        capability: MarketCapability,
        value: MarketObservationValue,
        required_fields: tuple[str, ...],
    ) -> MarketObservation:
        subject_type = {
            MarketCapability.OPTION_CHAIN_V1: MarketDataSubjectType.OPTION_UNDERLYING,
        }.get(capability, MarketDataSubjectType.INSTRUMENT)
        request_subject = MarketDataSubject(
            INSTRUMENT,
            subject_type,
            capability,
            MarketDataRequestContext(NOW, NOW, required_fields, (), EVIDENCE),
        )
        identity = market_observation_identity(
            "fixture", capability, request_subject, NOW, value, "v1"
        )
        return MarketObservation(
            identity,
            capability,
            request_subject,
            NOW,
            NOW + timedelta(seconds=1),
            value,
            "v1",
            ProviderProvenance("fixture", "request-1", EVIDENCE),
            FreshnessMetadata(NOW + timedelta(seconds=10), NOW, 60, 10, FreshnessStatus.FRESH),
            CompletenessMetadata(required_fields, required_fields, ()),
        )

    def test_ohlcv_series_is_accepted_for_historical_bars(self) -> None:
        value = series()
        built = self._observation_with(MarketCapability.HISTORICAL_BARS_V1, value, ("close",))
        assert deserialize_market_data(serialize_market_data(built)) == built

    def test_ohlcv_series_rejected_for_a_mismatched_capability(self) -> None:
        with pytest.raises(DomainInvariantError, match="capability mismatch|does not match"):
            self._observation_with(MarketCapability.REAL_TIME_QUOTE_V1, series(), ("close",))

    def test_expiration_collection_is_accepted_for_option_chain(self) -> None:
        value = expiration_collection()
        built = self._observation_with(MarketCapability.OPTION_CHAIN_V1, value, ("expirations",))
        assert deserialize_market_data(serialize_market_data(built)) == built

    def test_expiration_collection_rejected_for_a_mismatched_capability(self) -> None:
        with pytest.raises(DomainInvariantError, match="capability mismatch|does not match"):
            self._observation_with(
                MarketCapability.HISTORICAL_BARS_V1, expiration_collection(), ("expirations",)
            )


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
