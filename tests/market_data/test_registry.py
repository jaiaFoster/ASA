from __future__ import annotations

from datetime import datetime, timezone

import pytest

from domain import MarketCapability
from domain.values import DomainInvariantError
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
from market_data.registry import (
    CapabilityRegistry,
    ProviderPriority,
    ProviderPriorityPolicy,
    ProviderRegistry,
)

NOW = datetime(2026, 7, 21, tzinfo=timezone.utc)


class FakeProvider:
    def __init__(self, provider_id: str, capabilities: tuple[MarketCapability, ...]) -> None:
        self._provider_id = provider_id
        self._metadata = ProviderMetadata(
            ProviderIdentity(provider_id, provider_id, "v1"), capabilities, (), capabilities, "v1"
        )

    @property
    def provider_id(self) -> str:
        return self._provider_id

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


def providers() -> ProviderRegistry:
    quote = MarketCapability.REAL_TIME_QUOTE_V1
    bars = MarketCapability.HISTORICAL_BARS_V1
    return ProviderRegistry(
        (
            FakeProvider("finnhub", (quote, bars)),
            FakeProvider("tradier", (quote, bars, MarketCapability.OPTION_CHAIN_V1)),
            FakeProvider("alpha_vantage", (bars,)),
        )
    )


def policy() -> ProviderPriorityPolicy:
    return ProviderPriorityPolicy(
        "v1",
        (
            ProviderPriority(MarketCapability.REAL_TIME_QUOTE_V1, ("tradier", "finnhub")),
            ProviderPriority(
                MarketCapability.HISTORICAL_BARS_V1,
                ("tradier", "finnhub", "alpha_vantage"),
            ),
            ProviderPriority(MarketCapability.OPTION_CHAIN_V1, ("tradier",)),
        ),
    )


def test_provider_inventory_is_canonical_and_closed() -> None:
    registry = providers()
    assert tuple(value.provider_id for value in registry.providers) == (
        "alpha_vantage",
        "finnhub",
        "tradier",
    )
    with pytest.raises(AttributeError):
        registry.register  # type: ignore[attr-defined]


def test_capability_lookup_uses_configured_priority_not_registration_order() -> None:
    registry = CapabilityRegistry(providers(), policy())
    candidates = registry.lookup(MarketCapability.HISTORICAL_BARS_V1)
    assert tuple(value.provider_id for value in candidates) == (
        "tradier",
        "finnhub",
        "alpha_vantage",
    )
    assert tuple(value.priority for value in candidates) == (1, 2, 3)


def test_unavailable_provider_remains_visible() -> None:
    registry = CapabilityRegistry(providers(), policy())
    reports = (
        ProviderHealthReport("tradier", ProviderStatus.UNAVAILABLE, NOW, "OUTAGE", None),
    )
    candidates = registry.lookup(MarketCapability.REAL_TIME_QUOTE_V1, reports)
    assert candidates[0].provider_id == "tradier"
    assert candidates[0].status is ProviderStatus.UNAVAILABLE
    assert candidates[1].status is ProviderStatus.UNKNOWN


def test_duplicate_provider_and_unknown_priority_fail_closed() -> None:
    fixture = FakeProvider("fixture", (MarketCapability.REAL_TIME_QUOTE_V1,))
    with pytest.raises(DomainInvariantError, match="unique"):
        ProviderRegistry((fixture, fixture))
    bad = ProviderPriorityPolicy(
        "v1", (ProviderPriority(MarketCapability.REAL_TIME_QUOTE_V1, ("missing",)),)
    )
    with pytest.raises(DomainInvariantError, match="unknown"):
        CapabilityRegistry(providers(), bad)


def test_missing_capability_policy_fails_explicitly() -> None:
    registry = CapabilityRegistry(providers(), policy())
    with pytest.raises(DomainInvariantError, match="No priority policy"):
        registry.lookup(MarketCapability.EARNINGS_CALENDAR_V1)
