from __future__ import annotations

import dataclasses
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

import pytest

from domain import (
    CanonicalInstrumentIdentity,
    EvidenceKind,
    EvidenceReference,
    FreshnessStatus,
    Instrument,
    InstrumentKind,
    MarketCapability,
    MarketDataRequestContext,
    MarketDataSubject,
    MarketDataSubjectType,
    OptionChain,
    ProviderAddressProjection,
)
from market_data import (
    CapabilityRequest,
    DeterministicFixtureProvider,
    FixtureScenario,
    ProviderDependencies,
    ProviderErrorCode,
    ProviderFactory,
    ProviderValidationPlan,
    RequestBudgetAuthorization,
    fixture_provider_registration,
    load_market_data_config,
)

NOW = datetime(2026, 7, 21, 16, 0, tzinfo=timezone.utc)
EVIDENCE = (EvidenceReference(EvidenceKind.OBSERVATION, "instrument-reference:AAPL"),)
INSTRUMENT = Instrument(
    CanonicalInstrumentIdentity("figi", "BBG000B9XRY4"),
    InstrumentKind.EQUITY,
    "AAPL",
    "USD",
)


@dataclass(frozen=True)
class Clock:
    value: datetime = NOW

    def now(self) -> datetime:
        return self.value


class NoBudgetCalls:
    def authorize(
        self, provider_id: str, capability: MarketCapability, request_units: int
    ) -> RequestBudgetAuthorization:
        raise AssertionError("fixture fetch uses explicit pre-authorized budget")


def subject(capability: MarketCapability, fields: tuple[str, ...]) -> MarketDataSubject:
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
        MarketDataRequestContext(NOW, NOW, fields, (projection,), EVIDENCE),
    )


def request(capability: MarketCapability, fields: tuple[str, ...]) -> CapabilityRequest:
    return CapabilityRequest(capability, (subject(capability, fields),), NOW, NOW, fields, 60)


def provider(scenario: FixtureScenario = FixtureScenario()) -> DeterministicFixtureProvider:
    config = next(
        value
        for value in load_market_data_config({}).providers
        if value.provider_id == "deterministic_fixture"
    )
    return DeterministicFixtureProvider(
        config, ProviderDependencies(object(), Clock(), NoBudgetCalls()), scenario
    )


def budget() -> RequestBudgetAuthorization:
    return RequestBudgetAuthorization("fixture-budget", "deterministic_fixture", 1, 1)


@pytest.mark.parametrize(
    ("capability", "fields"),
    (
        (MarketCapability.REAL_TIME_QUOTE_V1, ("last",)),
        (MarketCapability.HISTORICAL_BARS_V1, ("open", "close")),
        (
            MarketCapability.OPTION_CHAIN_V1,
            ("contracts", "greeks", "implied_volatility", "volume", "open_interest"),
        ),
        (MarketCapability.EARNINGS_CALENDAR_V1, ("earnings_date",)),
    ),
)
def test_fixture_supports_every_required_capability_deterministically(
    capability: MarketCapability, fields: tuple[str, ...]
) -> None:
    first = provider().fetch(request(capability, fields), budget())
    second = provider().fetch(request(capability, fields), budget())
    assert first == second
    assert first.error is None
    assert first.observations[0].subject.canonical_instrument == INSTRUMENT
    assert first.observations[0].provenance.provider_id == "deterministic_fixture"
    if capability is MarketCapability.OPTION_CHAIN_V1:
        chain = first.observations[0].value
        assert isinstance(chain, OptionChain)
        assert len(chain.contracts) == 2
        assert all(contract.implied_volatility is not None for contract in chain.contracts)


def test_fixture_simulates_failure_staleness_and_incompleteness() -> None:
    failure = provider(
        FixtureScenario(((MarketCapability.REAL_TIME_QUOTE_V1, ProviderErrorCode.RATE_LIMITED),))
    ).fetch(request(MarketCapability.REAL_TIME_QUOTE_V1, ("last",)), budget())
    assert failure.error is not None and failure.error.code is ProviderErrorCode.RATE_LIMITED

    degraded = provider(FixtureScenario((), 17, 61, ("last",))).fetch(
        request(MarketCapability.REAL_TIME_QUOTE_V1, ("last",)), budget()
    )
    observation = degraded.observations[0]
    assert observation.freshness.status is FreshnessStatus.STALE
    assert observation.completeness.missing_fields == ("last",)
    assert degraded.attempts[0].response is not None
    assert degraded.attempts[0].response.latency_milliseconds == 17


def test_fixture_has_no_network_or_wall_clock_dependency_and_factory_constructs_it() -> None:
    config = next(
        value
        for value in load_market_data_config({}).providers
        if value.provider_id == "deterministic_fixture"
    )
    marker_transport = object()
    built = ProviderFactory((fixture_provider_registration(),)).create(
        config, ProviderDependencies(marker_transport, Clock(), NoBudgetCalls())
    )
    assert isinstance(built, DeterministicFixtureProvider)
    assert built.metadata.fixture_coverage == built.capabilities
    assert not any(
        name in DeterministicFixtureProvider.__dict__
        for name in ("session", "client", "get", "post")
    )


def test_fixture_validation_is_offline_closed_and_immutable() -> None:
    report = provider().validate(
        ProviderValidationPlan(
            "fixture-plan",
            "deterministic_fixture",
            (MarketCapability.REAL_TIME_QUOTE_V1, MarketCapability.TRADING_CALENDAR_V1),
            2,
            2,
            1,
        )
    )
    assert tuple(check.status.value for check in report.checks) == ("pass", "not_supported")
    assert dataclasses.is_dataclass(report) and report.__dataclass_params__.frozen


def test_subject_rejects_missing_or_ambiguous_effective_projection() -> None:
    item = subject(MarketCapability.REAL_TIME_QUOTE_V1, ("last",))
    with pytest.raises(ValueError, match="one effective"):
        item.projection_for("tradier", "symbol", NOW)
    duplicate = dataclasses.replace(
        item.request_context.provider_address_projections[0], projection_schema_version="v2"
    )
    ambiguous = dataclasses.replace(
        item,
        request_context=dataclasses.replace(
            item.request_context,
            provider_address_projections=item.request_context.provider_address_projections
            + (duplicate,),
        ),
    )
    with pytest.raises(ValueError, match="one effective"):
        ambiguous.projection_for("deterministic_fixture", "symbol", NOW)


def test_request_rejects_subject_capability_or_window_mismatch() -> None:
    item = subject(MarketCapability.REAL_TIME_QUOTE_V1, ("last",))
    with pytest.raises(ValueError, match="capability mismatch"):
        CapabilityRequest(MarketCapability.HISTORICAL_BARS_V1, (item,), NOW, NOW, ("last",), 60)
    with pytest.raises(ValueError, match="time window mismatch"):
        CapabilityRequest(
            MarketCapability.REAL_TIME_QUOTE_V1,
            (item,),
            NOW - timedelta(seconds=1),
            NOW,
            ("last",),
            60,
        )
