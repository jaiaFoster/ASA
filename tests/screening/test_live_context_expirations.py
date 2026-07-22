"""TRADIER-PATCH-001: canonical expiration discovery acquisition tests.

acquire_expirations() must normalize two distinct, both-legitimate live
provider response shapes into one canonical, deterministic result:
Tradier's real shape (one MarketObservation per expiration, each wrapping a
bare ExpirationCycle, returned only for an expirations-only request) and a
provider/fixture that doesn't distinguish an expirations-only request from
a full chain request (one MarketObservation wrapping a complete
OptionChain). TradierShapedExpirationsProvider below reproduces Tradier's
actual required_fields branching (market_data/tradier.py's own
_endpoint()/_normalize()) without needing real Tradier code or network
access -- it's a deterministic_fixture-identified provider whose only
difference from DeterministicFixtureProvider is that one response shape.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from domain import (
    CompletenessMetadata,
    EvidenceKind,
    EvidenceReference,
    ExpirationCycle,
    FreshnessMetadata,
    FreshnessStatus,
    MarketCapability,
    MarketObservation,
    ProviderProvenance,
    market_observation_identity,
)
from market_data import (
    CapabilityFulfillmentService,
    ProviderDependencies,
    ProviderRegistry,
    load_market_data_config,
)
from market_data.fixture import DeterministicFixtureProvider
from market_data.providers import (
    ProviderAttemptMetadata,
    ProviderErrorCode,
    ProviderFetchResult,
    ProviderResponseMetadata,
    normalized_provider_error,
)
from screening.live_acquisition import build_capability_registry, build_request_budget_manager
from screening.live_context import acquire_expirations
from screening.results import ScreeningOutcomeStatus
from screening.runner import StrategyAdapterError

NOW = datetime(2026, 7, 22, 16, 0, tzinfo=UTC)
SYMBOL = "AAPL"


class FixedClock:
    def __init__(self, start: datetime = NOW) -> None:
        self._next = start

    def now(self) -> datetime:
        current = self._next
        self._next = current + timedelta(microseconds=1)
        return current


class TradierShapedExpirationsProvider(DeterministicFixtureProvider):
    """Returns Tradier's real expirations-only response shape (multiple
    bare-ExpirationCycle observations) for required_fields=("expirations",)
    with no "contracts"; everything else defers to the normal fixture
    behavior, unmodified.
    """

    def fetch(self, request, budget):  # noqa: ANN001
        if (
            request.capability is MarketCapability.OPTION_CHAIN_V1
            and "expirations" in request.required_fields
            and "contracts" not in request.required_fields
        ):
            received_at = self._dependencies.clock.now().astimezone(UTC)
            reference = self._request_reference(request)
            response = ProviderResponseMetadata(
                self.provider_id, reference, received_at, "fixture", 0, 0, (("network_requests", "0"),)
            )
            attempt = ProviderAttemptMetadata(self.provider_id, request.capability, 1, 1, response)
            (subject,) = request.subjects
            as_of = received_at.date()
            evidence = (EvidenceReference(EvidenceKind.OBSERVATION, "test:tradier-shaped-expirations"),)
            # Deliberately unsorted and with a duplicate date -- proves
            # acquire_expirations() sorts and dedupes rather than trusting
            # provider response order.
            raw_cycles = (
                ExpirationCycle(as_of + timedelta(days=25), 25, False, True, as_of, evidence),
                ExpirationCycle(as_of + timedelta(days=10), 10, False, True, as_of, evidence),
                ExpirationCycle(as_of + timedelta(days=10), 10, False, True, as_of, evidence),
            )
            observations = tuple(
                MarketObservation(
                    market_observation_identity(
                        self.provider_id, request.capability, subject, received_at, cycle, "v1"
                    ),
                    request.capability,
                    subject,
                    received_at,
                    received_at,
                    cycle,
                    "v1",
                    ProviderProvenance(self.provider_id, reference, evidence),
                    FreshnessMetadata(received_at, received_at, request.maximum_age_seconds, 0, FreshnessStatus.FRESH),
                    CompletenessMetadata(request.required_fields, request.required_fields, ()),
                )
                for cycle in raw_cycles
            )
            return ProviderFetchResult(observations, None, (attempt,))
        return super().fetch(request, budget)


class EmptyExpirationsProvider(DeterministicFixtureProvider):
    """Returns an EMPTY_PAYLOAD error for an expirations-only request -- a
    legitimate, if unhelpful, real response shape (e.g. a symbol with no
    listed options), matching real Tradier's own "no observations -> empty
    payload error" convention (market_data/tradier.py's fetch()).
    """

    def fetch(self, request, budget):  # noqa: ANN001
        if (
            request.capability is MarketCapability.OPTION_CHAIN_V1
            and "expirations" in request.required_fields
            and "contracts" not in request.required_fields
        ):
            received_at = self._dependencies.clock.now().astimezone(UTC)
            reference = self._request_reference(request)
            response = ProviderResponseMetadata(
                self.provider_id, reference, received_at, "fixture", 0, 0, (("network_requests", "0"),)
            )
            attempt = ProviderAttemptMetadata(self.provider_id, request.capability, 1, 1, response)
            error = normalized_provider_error(
                ProviderErrorCode.EMPTY_PAYLOAD,
                "no expirations listed",
                self.provider_id,
                request.capability,
                reference,
            )
            return ProviderFetchResult((), error, (attempt,))
        return super().fetch(request, budget)


class MalformedExpirationsProvider(DeterministicFixtureProvider):
    """Returns two OptionChain-valued observations for an expirations-only
    request -- neither a clean Tradier-shaped expiration list (every value
    an ExpirationCycle) nor a single chain-shaped response. Not a real
    provider behavior, but acquire_expirations() must still fail cleanly,
    not crash, if a provider ever produced something this malformed.
    """

    def fetch(self, request, budget):  # noqa: ANN001
        if (
            request.capability is MarketCapability.OPTION_CHAIN_V1
            and "expirations" in request.required_fields
            and "contracts" not in request.required_fields
        ):
            received_at = self._dependencies.clock.now().astimezone(UTC)
            reference = self._request_reference(request)
            (subject,) = request.subjects
            observation = self._observation(subject, received_at, reference, request.maximum_age_seconds)
            response = ProviderResponseMetadata(
                self.provider_id, reference, received_at, "fixture", 0, 0, (("network_requests", "0"),)
            )
            attempt = ProviderAttemptMetadata(self.provider_id, request.capability, 1, 1, response)
            return ProviderFetchResult((observation, observation), None, (attempt,))
        return super().fetch(request, budget)


def _fulfillment(provider_cls=DeterministicFixtureProvider):
    clock = FixedClock()
    config = load_market_data_config({})
    (fixture_config,) = tuple(item for item in config.providers if item.enabled)
    budget_manager = build_request_budget_manager((fixture_config,), clock)
    provider = provider_cls(fixture_config, ProviderDependencies(object(), clock, budget_manager))
    registry = ProviderRegistry((provider,))
    capability_registry = build_capability_registry(registry)
    return CapabilityFulfillmentService(registry, capability_registry, budget_manager), clock


class TestTradierShapedExpirationListResponse:
    def test_normalizes_multiple_expiration_cycle_observations(self) -> None:
        fulfillment, clock = _fulfillment(TradierShapedExpirationsProvider)
        result = acquire_expirations(fulfillment, SYMBOL, clock.now())
        assert [cycle.days_to_expiration for cycle in result] == [10, 25]

    def test_deduplicates_and_sorts_deterministically(self) -> None:
        fulfillment, clock = _fulfillment(TradierShapedExpirationsProvider)
        result = acquire_expirations(fulfillment, SYMBOL, clock.now())
        dates = [cycle.expiration_date for cycle in result]
        assert dates == sorted(set(dates))
        assert len(dates) == len(set(dates))


class TestChainShapedExpirationResponse:
    def test_derives_expirations_from_a_single_option_chain_observation(self) -> None:
        fulfillment, clock = _fulfillment(DeterministicFixtureProvider)
        result = acquire_expirations(fulfillment, SYMBOL, clock.now())
        assert len(result) == 1
        assert result[0].expiration_date > clock.now().date()


class TestEmptyAndMalformedResponses:
    def test_zero_observations_raises_missing_data(self) -> None:
        fulfillment, clock = _fulfillment(EmptyExpirationsProvider)
        try:
            acquire_expirations(fulfillment, SYMBOL, clock.now())
            raise AssertionError("expected StrategyAdapterError")
        except StrategyAdapterError as error:
            assert error.outcome_status is ScreeningOutcomeStatus.MISSING_DATA

    def test_neither_expiration_list_nor_single_chain_raises_missing_data_not_a_crash(self) -> None:
        fulfillment, clock = _fulfillment(MalformedExpirationsProvider)
        try:
            acquire_expirations(fulfillment, SYMBOL, clock.now())
            raise AssertionError("expected StrategyAdapterError")
        except StrategyAdapterError as error:
            assert error.outcome_status is ScreeningOutcomeStatus.MISSING_DATA
            assert "neither a clean expiration list nor a single option chain" in str(error)
