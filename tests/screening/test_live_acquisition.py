from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

import pytest
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
from market_data import (
    BudgetExhaustedError,
    FulfillmentStatus,
    ProviderDependencies,
    ProviderRegistry,
    RequestBudgetAuthorization,
    load_market_data_config,
)
from market_data.fixture import fixture_provider_registration
from screening.live_acquisition import (
    acquire_capability,
    build_capability_registry,
    build_fulfillment_service,
    build_request_budget_manager,
    enabled_provider_configs,
)

NOW = datetime(2026, 7, 22, 16, 0, tzinfo=UTC)
EVIDENCE = (EvidenceReference(EvidenceKind.OBSERVATION, "live-acquisition-test"),)
INSTRUMENT = Instrument(
    CanonicalInstrumentIdentity("figi", "BBG000B9XRY4"), InstrumentKind.EQUITY, "AAPL", "USD"
)


@dataclass(frozen=True)
class FixedClock:
    fixed_at: datetime = NOW

    def now(self) -> datetime:
        return self.fixed_at


class _NoBudgetChecks:
    def authorize(
        self, provider_id: str, capability: MarketCapability, request_units: int
    ) -> RequestBudgetAuthorization:
        return RequestBudgetAuthorization("no-budget-check", provider_id, request_units, 1)


def _no_transport(_provider_id: str) -> object:
    """deterministic_fixture never touches its transport, so a placeholder
    is sufficient -- these tests exercise the orchestration wiring only,
    never real network access.
    """
    return object()


def _subject(capability: MarketCapability, required_fields: tuple[str, ...]) -> MarketDataSubject:
    subject_type = {
        MarketCapability.OPTION_CHAIN_V1: MarketDataSubjectType.OPTION_UNDERLYING,
        MarketCapability.EARNINGS_CALENDAR_V1: MarketDataSubjectType.EARNINGS_SECURITY,
    }.get(capability, MarketDataSubjectType.INSTRUMENT)
    projection = ProviderAddressProjection(
        "deterministic_fixture", "v1", "symbol", "AAPL", NOW - timedelta(days=2), None, EVIDENCE
    )
    return MarketDataSubject(
        INSTRUMENT,
        subject_type,
        capability,
        MarketDataRequestContext(NOW, NOW, required_fields, (projection,), EVIDENCE),
    )


class TestEnabledProviderConfigs:
    def test_deterministic_fixture_is_enabled_with_no_environment_variables(self) -> None:
        config = load_market_data_config({})
        enabled = enabled_provider_configs(config)
        assert {item.provider_id for item in enabled} == {"deterministic_fixture"}


class TestBuildCapabilityRegistry:
    def test_every_declared_capability_is_registered(self) -> None:
        config = load_market_data_config({})
        (fixture_config,) = enabled_provider_configs(config)
        registration = fixture_provider_registration()
        provider = registration.constructor(
            fixture_config, ProviderDependencies(object(), FixedClock(), _NoBudgetChecks())
        )
        registry = ProviderRegistry((provider,))
        capability_registry = build_capability_registry(registry)
        for capability in provider.capabilities:
            candidates = capability_registry.lookup(capability)
            assert candidates and candidates[0].provider_id == "deterministic_fixture"


class TestBuildRequestBudgetManager:
    def test_one_policy_per_enabled_provider(self) -> None:
        config = load_market_data_config({})
        enabled = enabled_provider_configs(config)
        manager = build_request_budget_manager(enabled, FixedClock())
        authorization = manager.authorize(
            "deterministic_fixture", MarketCapability.OPTION_CHAIN_V1, 1
        )
        assert authorization.provider_id == "deterministic_fixture"

    def test_unconfigured_provider_is_rejected(self) -> None:
        config = load_market_data_config({})
        enabled = enabled_provider_configs(config)
        manager = build_request_budget_manager(enabled, FixedClock())
        with pytest.raises(BudgetExhaustedError):
            manager.authorize("tradier", MarketCapability.OPTION_CHAIN_V1, 1)


_REQUIRED_FIELDS = {
    MarketCapability.REAL_TIME_QUOTE_V1: ("last",),
    MarketCapability.HISTORICAL_BARS_V1: ("close",),
    MarketCapability.OPTION_CHAIN_V1: ("contracts",),
    MarketCapability.EARNINGS_CALENDAR_V1: ("earnings_date",),
}


class TestBuildFulfillmentServiceAndAcquireCapability:
    def test_acquires_every_fixture_capability_successfully(self) -> None:
        # A fresh service per capability, matching realistic usage where a
        # real (advancing) clock is used -- FixedClock never advances, and
        # RequestBudgetPolicy's default burst_limit=1 keys bursts by exact
        # timestamp, so reusing one service across same-timestamp calls
        # would hit the burst limit after the first, not a bug in the
        # acquisition wiring itself.
        config = load_market_data_config({})
        for capability, fields in _REQUIRED_FIELDS.items():
            fulfillment = build_fulfillment_service(config, _no_transport, FixedClock())
            result = acquire_capability(
                fulfillment,
                capability,
                _subject(capability, fields),
                effective_start=NOW,
                effective_end=NOW,
                required_fields=fields,
                maximum_age_seconds=3600,
            )
            assert result.status is FulfillmentStatus.FULFILLED
            assert result.selected_provider == "deterministic_fixture"
            assert result.observations

    def test_request_budget_is_enforced_within_the_same_clock_tick(self) -> None:
        """Demonstrates real request-budget enforcement, not just that it's
        wired: a second, *distinct* request (a different capability -- an
        identical repeated request is memoized by CapabilityFulfillmentService
        and never re-authorized) in the same instant hits the provider's
        burst_limit=1 default and is refused, exactly as RequestBudgetPolicy
        is designed to do -- LIVE-001's request_budget_compliance deliverable
        proven, not merely assumed.
        """
        config = load_market_data_config({})
        fulfillment = build_fulfillment_service(config, _no_transport, FixedClock())
        first_capability = MarketCapability.REAL_TIME_QUOTE_V1
        second_capability = MarketCapability.HISTORICAL_BARS_V1
        first = acquire_capability(
            fulfillment,
            first_capability,
            _subject(first_capability, _REQUIRED_FIELDS[first_capability]),
            effective_start=NOW,
            effective_end=NOW,
            required_fields=_REQUIRED_FIELDS[first_capability],
            maximum_age_seconds=3600,
        )
        second = acquire_capability(
            fulfillment,
            second_capability,
            _subject(second_capability, _REQUIRED_FIELDS[second_capability]),
            effective_start=NOW,
            effective_end=NOW,
            required_fields=_REQUIRED_FIELDS[second_capability],
            maximum_age_seconds=3600,
        )
        assert first.status is FulfillmentStatus.FULFILLED
        assert second.status is FulfillmentStatus.FAILED

    def test_is_deterministic_for_identical_inputs_and_clock(self) -> None:
        config = load_market_data_config({})
        first_service = build_fulfillment_service(config, _no_transport, FixedClock())
        second_service = build_fulfillment_service(config, _no_transport, FixedClock())
        capability = MarketCapability.REAL_TIME_QUOTE_V1
        fields = _REQUIRED_FIELDS[capability]
        first = acquire_capability(
            first_service,
            capability,
            _subject(capability, fields),
            effective_start=NOW,
            effective_end=NOW,
            required_fields=fields,
            maximum_age_seconds=3600,
        )
        second = acquire_capability(
            second_service,
            capability,
            _subject(capability, fields),
            effective_start=NOW,
            effective_end=NOW,
            required_fields=fields,
            maximum_age_seconds=3600,
        )
        assert first.status == second.status
        assert first.selected_provider == second.selected_provider
