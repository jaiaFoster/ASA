from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

import pytest

from domain import MarketCapability
from market_data.config import ProviderConfig, load_market_data_config
from market_data.factory import (
    ProviderDependencies,
    ProviderFactory,
    ProviderFactoryError,
    ProviderRegistration,
)
from market_data.providers import (
    CapabilityRequest,
    HealthProbe,
    ProviderFetchResult,
    ProviderHealthReport,
    ProviderIdentity,
    ProviderMetadata,
    ProviderShutdownReport,
    ProviderStatus,
    ProviderValidationPlan,
    ProviderValidationReport,
    RequestBudgetAuthorization,
)

NOW = datetime(2026, 7, 21, tzinfo=timezone.utc)


@dataclass(frozen=True)
class FakeClock:
    def now(self) -> datetime:
        return NOW


@dataclass(frozen=True)
class FakeBudgetAuthorizer:
    def authorize(
        self, provider_id: str, capability: MarketCapability, request_units: int
    ) -> RequestBudgetAuthorization:
        return RequestBudgetAuthorization("authorization", provider_id, request_units, 1)


class FakeProvider:
    def __init__(self, config: ProviderConfig, dependencies: ProviderDependencies) -> None:
        self.config = config
        self.dependencies = dependencies
        self._metadata = ProviderMetadata(
            ProviderIdentity(config.provider_id, config.adapter_type, config.adapter_version),
            (MarketCapability.REAL_TIME_QUOTE_V1,),
            (),
            (MarketCapability.REAL_TIME_QUOTE_V1,),
            "v1",
        )

    @property
    def provider_id(self) -> str:
        return self.config.provider_id

    @property
    def metadata(self) -> ProviderMetadata:
        return self._metadata

    @property
    def capabilities(self) -> tuple[MarketCapability, ...]:
        return self.metadata.capabilities

    def fetch(
        self, request: CapabilityRequest, budget: RequestBudgetAuthorization
    ) -> ProviderFetchResult:
        raise NotImplementedError

    def health(self, probe: HealthProbe) -> ProviderHealthReport:
        return ProviderHealthReport(self.provider_id, ProviderStatus.AVAILABLE, NOW, "OK", None)

    def validate(self, plan: ProviderValidationPlan) -> ProviderValidationReport:
        raise NotImplementedError

    def shutdown(self) -> ProviderShutdownReport:
        return ProviderShutdownReport(self.provider_id, NOW)


def dependencies() -> ProviderDependencies:
    return ProviderDependencies(object(), FakeClock(), FakeBudgetAuthorizer())


def registrations() -> tuple[ProviderRegistration, ...]:
    return tuple(
        ProviderRegistration(name, "v1", FakeProvider)
        for name in ("deterministic_fixture", "tradier", "finnhub", "alpha_vantage")
    )


def test_factory_constructs_enabled_fixture_with_injected_dependencies() -> None:
    factory = ProviderFactory(registrations())
    config = load_market_data_config({})
    providers = factory.create_enabled(config, dependencies())
    assert tuple(value.provider_id for value in providers) == ("deterministic_fixture",)
    fixture = providers[0]
    assert isinstance(fixture, FakeProvider)
    assert fixture.dependencies.transport is not None
    assert fixture.dependencies.clock.now() == NOW


@pytest.mark.parametrize("provider_id", ("tradier", "finnhub", "alpha_vantage"))
def test_factory_can_construct_each_initial_live_provider(provider_id: str) -> None:
    prefix = provider_id.upper()
    values = {
        f"ASA_{prefix}_ENABLED": "true",
        {
            "tradier": "ASA_TRADIER_ACCESS_TOKEN",
            "finnhub": "ASA_FINNHUB_API_KEY",
            "alpha_vantage": "ASA_ALPHA_VANTAGE_API_KEY",
        }[provider_id]: "secret",
    }
    config = load_market_data_config(values)
    provider_config = next(item for item in config.providers if item.provider_id == provider_id)
    provider = ProviderFactory(registrations()).create(provider_config, dependencies())
    assert provider.provider_id == provider_id


def test_disabled_provider_is_not_constructed() -> None:
    config = load_market_data_config({})
    disabled = next(item for item in config.providers if item.provider_id == "finnhub")
    with pytest.raises(ProviderFactoryError, match="disabled"):
        ProviderFactory(registrations()).create(disabled, dependencies())


def test_duplicate_and_unknown_registrations_fail_closed() -> None:
    registration = ProviderRegistration("fixture", "v1", FakeProvider)
    with pytest.raises(ProviderFactoryError, match="Duplicate"):
        ProviderFactory((registration, registration))
    config = next(
        item for item in load_market_data_config({}).providers if item.provider_id == "deterministic_fixture"
    )
    with pytest.raises(ProviderFactoryError, match="No unique constructor"):
        ProviderFactory((registration,)).create(config, dependencies())


def test_factory_does_not_probe_or_fetch_during_construction() -> None:
    config = load_market_data_config({})
    first = ProviderFactory(registrations()).create_enabled(config, dependencies())
    second = ProviderFactory(tuple(reversed(registrations()))).create_enabled(config, dependencies())
    assert tuple(value.provider_id for value in first) == tuple(value.provider_id for value in second)
