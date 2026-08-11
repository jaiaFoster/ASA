"""SPRINT-014 S14-PR-05A, Architect checkpoint (third review): the
Founder-approved collection-valued observation extension (f1078c7) added
ExpirationCollection as an OPTION_CHAIN_V1 MarketObservationValue, but
market_data.resolution.ObservationResolver._value_data() still only
special-cased OptionContract/OptionChain/ExpirationCycle/EarningsEvent --
so an ExpirationCollection observation fell through to
market_data_to_data() instead of its own authoritative
financial_contract_to_data() serializer during reconciliation. Runtime-
permissive (market_data_to_data() introspects any dataclass), but the
wrong contract/version namespace for an identity computation that must
stay stable across replay.

Proves the fix at three levels: the resolver's own internal serialization
choice, full resolution (single-provider, exact agreement, and
disagreement), and sealing through market_data.subject_snapshot -- the
same "one logical request -> one logical observation -> generic
reconciliation -> sealed snapshot" path OHLCVSeries already exercises
unchanged.
"""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

from domain import (
    CanonicalInstrumentIdentity,
    CompletenessMetadata,
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
    OHLCVBar,
    OHLCVSeries,
    ProviderProvenance,
    financial_contract_to_data,
    market_observation_identity,
)
from market_data.fulfillment import (
    CapabilityFulfillmentResult,
    FulfillmentStatus,
    ProviderFulfillmentAttempt,
)
from market_data.providers import (
    CapabilityRequest,
    ProviderIdentity,
    ProviderMetadata,
    ProviderStatus,
)
from market_data.resolution import (
    ConfidenceClassification,
    ObservationResolver,
    ResolutionMethod,
    ResolutionPolicy,
)
from market_data.subject_snapshot import seal_subject_snapshot

NOW = datetime(2026, 8, 6, 15, 0, tzinfo=UTC)
EVIDENCE = (EvidenceReference(EvidenceKind.OBSERVATION, "instrument-reference:AAPL"),)
INSTRUMENT = Instrument(
    CanonicalInstrumentIdentity("figi", "BBG000B9XRY4"), InstrumentKind.EQUITY, "AAPL", "USD"
)


def _expirations_subject() -> MarketDataSubject:
    return MarketDataSubject(
        INSTRUMENT,
        MarketDataSubjectType.OPTION_UNDERLYING,
        MarketCapability.OPTION_CHAIN_V1,
        MarketDataRequestContext(NOW, NOW, ("expirations",), (), EVIDENCE),
    )


def _bars_subject() -> MarketDataSubject:
    return MarketDataSubject(
        INSTRUMENT,
        MarketDataSubjectType.INSTRUMENT,
        MarketCapability.HISTORICAL_BARS_V1,
        MarketDataRequestContext(NOW, NOW, ("close",), (), EVIDENCE),
    )


def _cycle(expiration_date: date) -> ExpirationCycle:
    as_of = NOW.date()
    return ExpirationCycle(
        expiration_date, (expiration_date - as_of).days, True, False, as_of, EVIDENCE
    )


def _collection_observation(
    provider_id: str, expiration_dates: tuple[date, ...]
) -> MarketObservation:
    value = ExpirationCollection(NOW.date(), tuple(_cycle(item) for item in expiration_dates))
    subject = _expirations_subject()
    identity = market_observation_identity(
        provider_id, MarketCapability.OPTION_CHAIN_V1, subject, NOW, value, "v1"
    )
    return MarketObservation(
        identity,
        MarketCapability.OPTION_CHAIN_V1,
        subject,
        NOW,
        NOW,
        value,
        "v1",
        ProviderProvenance(provider_id, f"{provider_id}-request", EVIDENCE),
        FreshnessMetadata(NOW, NOW, 3600, 0, FreshnessStatus.FRESH),
        CompletenessMetadata(("expirations",), ("expirations",), ()),
    )


def _bar() -> OHLCVBar:
    start = NOW - timedelta(days=1)
    return OHLCVBar(
        INSTRUMENT,
        86400,
        start,
        NOW,
        Decimal("205"),
        Decimal("212"),
        Decimal("204"),
        Decimal("210"),
        Decimal("50000000"),
    )


def _series_observation(provider_id: str) -> MarketObservation:
    value = OHLCVSeries(INSTRUMENT, 86400, NOW, (_bar(),))
    subject = _bars_subject()
    identity = market_observation_identity(
        provider_id, MarketCapability.HISTORICAL_BARS_V1, subject, NOW, value, "v1"
    )
    return MarketObservation(
        identity,
        MarketCapability.HISTORICAL_BARS_V1,
        subject,
        NOW,
        NOW,
        value,
        "v1",
        ProviderProvenance(provider_id, f"{provider_id}-request", EVIDENCE),
        FreshnessMetadata(NOW, NOW, 3600, 0, FreshnessStatus.FRESH),
        CompletenessMetadata(("close",), ("close",), ()),
    )


def _policy(
    capability: MarketCapability, *providers: str, required_fields: tuple[str, ...]
) -> ResolutionPolicy:
    return ResolutionPolicy("v1", providers, 3600, required_fields)


def _provider_metadata(provider_id: str, capability: MarketCapability) -> ProviderMetadata:
    return ProviderMetadata(
        ProviderIdentity(provider_id, "test_provider", "v1"),
        (capability,),
        (),
        (capability,),
        "v1",
    )


def _fulfillment_result(
    observation: MarketObservation, capability: MarketCapability, required_fields: tuple[str, ...]
) -> CapabilityFulfillmentResult:
    subject = observation.subject
    provider_id = observation.provenance.provider_id
    request = CapabilityRequest(capability, (subject,), NOW, NOW, required_fields, 3600)
    attempt = ProviderFulfillmentAttempt(
        provider_id, 1, ProviderStatus.AVAILABLE, (observation,), None, ()
    )
    return CapabilityFulfillmentResult(
        request, FulfillmentStatus.FULFILLED, provider_id, (observation,), (attempt,), True
    )


class TestExpirationCollectionValueData:
    def test_uses_the_financial_contract_serializer_not_market_data(self) -> None:
        observation = _collection_observation("tradier", (date(2026, 8, 21),))
        assert isinstance(observation.value, ExpirationCollection)
        data = ObservationResolver._value_data(observation)
        assert data == financial_contract_to_data(observation.value)


class TestExpirationCollectionResolution:
    def test_single_provider_resolves_and_seals(self) -> None:
        observation = _collection_observation("tradier", (date(2026, 8, 21), date(2026, 9, 18)))
        policy = _policy(
            MarketCapability.OPTION_CHAIN_V1, "tradier", required_fields=("expirations",)
        )
        result = ObservationResolver().resolve((observation,), policy, as_of=NOW)
        assert result.method is ResolutionMethod.SINGLE_AVAILABLE
        assert result.selected_observation == observation
        assert result.confidence.classification is ConfidenceClassification.SINGLE_SOURCE

        fulfillment = _fulfillment_result(
            observation, MarketCapability.OPTION_CHAIN_V1, ("expirations",)
        )
        snapshot = seal_subject_snapshot(
            (fulfillment,),
            as_of=NOW,
            required_capabilities=(MarketCapability.OPTION_CHAIN_V1,),
            resolution_policy_by_capability={MarketCapability.OPTION_CHAIN_V1: policy},
            provider_metadata=(_provider_metadata("tradier", MarketCapability.OPTION_CHAIN_V1),),
        )
        assert snapshot.completeness.resolved_capabilities == (MarketCapability.OPTION_CHAIN_V1,)
        assert snapshot.observations == (observation,)

    def test_two_identical_collections_produce_exact_agreement(self) -> None:
        tradier = _collection_observation("tradier", (date(2026, 8, 21), date(2026, 9, 18)))
        finnhub = _collection_observation("finnhub", (date(2026, 8, 21), date(2026, 9, 18)))
        policy = _policy(
            MarketCapability.OPTION_CHAIN_V1, "tradier", "finnhub", required_fields=("expirations",)
        )
        resolver = ObservationResolver()
        first = resolver.resolve((finnhub, tradier), policy, as_of=NOW)
        second = resolver.resolve((tradier, finnhub), policy, as_of=NOW)
        assert first == second
        assert first.method is ResolutionMethod.EXACT_AGREEMENT
        assert first.selected_observation == tradier
        assert first.disagreements == ()
        assert first.confidence.classification is ConfidenceClassification.EXACT_AGREEMENT

    def test_differing_collections_produce_the_expected_disagreement(self) -> None:
        tradier = _collection_observation("tradier", (date(2026, 8, 21), date(2026, 9, 18)))
        finnhub = _collection_observation("finnhub", (date(2026, 8, 21),))
        policy = _policy(
            MarketCapability.OPTION_CHAIN_V1, "tradier", "finnhub", required_fields=("expirations",)
        )
        result = ObservationResolver().resolve((finnhub, tradier), policy, as_of=NOW)
        assert result.method is ResolutionMethod.PROVIDER_PRIORITY
        assert result.selected_observation == tradier
        assert any("cycles" in item.field_path for item in result.disagreements)
        assert result.confidence.classification is ConfidenceClassification.DISAGREEMENT


class TestOHLCVSeriesResolution:
    def test_single_provider_resolves_and_seals(self) -> None:
        observation = _series_observation("tradier")
        policy = _policy(
            MarketCapability.HISTORICAL_BARS_V1, "tradier", required_fields=("close",)
        )
        result = ObservationResolver().resolve((observation,), policy, as_of=NOW)
        assert result.method is ResolutionMethod.SINGLE_AVAILABLE
        assert result.selected_observation == observation

        fulfillment = _fulfillment_result(
            observation, MarketCapability.HISTORICAL_BARS_V1, ("close",)
        )
        snapshot = seal_subject_snapshot(
            (fulfillment,),
            as_of=NOW,
            required_capabilities=(MarketCapability.HISTORICAL_BARS_V1,),
            resolution_policy_by_capability={MarketCapability.HISTORICAL_BARS_V1: policy},
            provider_metadata=(_provider_metadata("tradier", MarketCapability.HISTORICAL_BARS_V1),),
        )
        assert snapshot.completeness.resolved_capabilities == (MarketCapability.HISTORICAL_BARS_V1,)
        assert snapshot.observations == (observation,)
