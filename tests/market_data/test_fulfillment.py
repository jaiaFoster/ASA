from __future__ import annotations

import dataclasses
from dataclasses import dataclass
from datetime import datetime, timezone

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
    ProviderProvenance,
    market_observation_identity,
)
from market_data import (
    BudgetScope,
    CapabilityFulfillmentService,
    CapabilityRegistry,
    CapabilityRequest,
    DeterministicFixtureProvider,
    FixtureScenario,
    FulfillmentStatus,
    ProviderDependencies,
    ProviderErrorCode,
    ProviderPriority,
    ProviderPriorityPolicy,
    ProviderRegistry,
    ProviderIdentity,
    ProviderMetadata,
    ProviderFetchResult,
    ProviderAttemptMetadata,
    ProviderResponseMetadata,
    ProviderHealthReport,
    ProviderStatus,
    ProviderShutdownReport,
    ProviderValidationPlan,
    ProviderValidationReport,
    HealthProbe,
    normalized_provider_error,
    RequestBudgetManager,
    RequestBudgetPolicy,
    RequestBudgetAuthorization,
    load_market_data_config,
)

NOW = datetime(2026, 7, 21, 16, 0, tzinfo=timezone.utc)
CAPABILITY = MarketCapability.REAL_TIME_QUOTE_V1
EVIDENCE = (EvidenceReference(EvidenceKind.OBSERVATION, "instrument-reference:AAPL"),)
INSTRUMENT = Instrument(
    CanonicalInstrumentIdentity("figi", "BBG000B9XRY4"),
    InstrumentKind.EQUITY,
    "AAPL",
    "USD",
)


@dataclass
class Clock:
    value: datetime = NOW

    def now(self) -> datetime:
        return self.value


class UnusedBudget:
    def authorize(
        self, provider_id: str, capability: MarketCapability, request_units: int
    ) -> RequestBudgetAuthorization:
        raise AssertionError("fixture receives the fulfillment authorization")


def request() -> CapabilityRequest:
    fields = ("last",)
    projection = ProviderAddressProjection(
        "deterministic_fixture", "v1", "symbol", "AAPL", NOW, None, EVIDENCE
    )
    subject = MarketDataSubject(
        INSTRUMENT,
        MarketDataSubjectType.INSTRUMENT,
        CAPABILITY,
        MarketDataRequestContext(NOW, NOW, fields, (projection,), EVIDENCE),
    )
    return CapabilityRequest(CAPABILITY, (subject,), NOW, NOW, fields, 60)


class ScriptedProvider:
    def __init__(self, provider_id: str, scenario: FixtureScenario) -> None:
        self.provider_id = provider_id
        self._scenario = scenario
        self.metadata = ProviderMetadata(
            ProviderIdentity(provider_id, "test_provider", "v1"),
            (CAPABILITY,),
            (),
            (CAPABILITY,),
            "v1",
        )

    @property
    def capabilities(self) -> tuple[MarketCapability, ...]:
        return self.metadata.capabilities

    def fetch(
        self, capability_request: CapabilityRequest, budget: RequestBudgetAuthorization
    ) -> ProviderFetchResult:
        response = ProviderResponseMetadata(
            self.provider_id, f"{self.provider_id}-request", NOW, "fixture", 0, 0
        )
        attempt = ProviderAttemptMetadata(self.provider_id, CAPABILITY, 1, 1, response)
        failure = dict(self._scenario.failures).get(CAPABILITY)
        if failure is not None:
            return ProviderFetchResult(
                (),
                normalized_provider_error(
                    failure, "simulated provider failure", self.provider_id, CAPABILITY
                ),
                (attempt,),
            )
        base = (
            fixture_provider(self._scenario)
            .fetch(
                capability_request,
                RequestBudgetAuthorization("fixture", "deterministic_fixture", 1, 1),
            )
            .observations[0]
        )
        provenance = ProviderProvenance(
            self.provider_id, response.provider_request_reference, base.provenance.evidence
        )
        observation = dataclasses.replace(
            base,
            provenance=provenance,
            observation_id=market_observation_identity(
                self.provider_id,
                base.capability,
                base.subject,
                base.effective_time,
                base.value,
                base.schema_version,
            ),
        )
        return ProviderFetchResult((observation,), None, (attempt,))

    def health(self, probe: HealthProbe) -> ProviderHealthReport:
        return ProviderHealthReport(self.provider_id, ProviderStatus.AVAILABLE, NOW, "OK", None)

    def validate(self, plan: ProviderValidationPlan) -> ProviderValidationReport:
        raise NotImplementedError

    def shutdown(self) -> ProviderShutdownReport:
        return ProviderShutdownReport(self.provider_id, NOW)


def fixture_provider(scenario: FixtureScenario) -> DeterministicFixtureProvider:
    base = next(
        item
        for item in load_market_data_config({}).providers
        if item.provider_id == "deterministic_fixture"
    )
    return DeterministicFixtureProvider(
        base, ProviderDependencies(object(), Clock(), UnusedBudget()), scenario
    )


def provider(provider_id: str, scenario: FixtureScenario = FixtureScenario()) -> ScriptedProvider:
    return ScriptedProvider(provider_id, scenario)


def service(
    first: ScriptedProvider,
    second: ScriptedProvider | None = None,
    *,
    maximum: int = 4,
) -> tuple[CapabilityFulfillmentService, RequestBudgetManager]:
    providers = (first,) if second is None else (first, second)
    registry = ProviderRegistry(providers)
    ids = tuple(item.provider_id for item in providers)
    capabilities = CapabilityRegistry(
        registry,
        ProviderPriorityPolicy("v1", (ProviderPriority(CAPABILITY, ids),)),
    )
    budgets = RequestBudgetManager(
        tuple(
            RequestBudgetPolicy(item, BudgetScope.RUNTIME, maximum, maximum, 0, "v1")
            for item in ids
        ),
        Clock(),
    )
    return CapabilityFulfillmentService(registry, capabilities, budgets), budgets


def test_primary_success_is_selected_without_fallback() -> None:
    fulfillment, budgets = service(provider("primary"))
    result = fulfillment.fulfill(request())
    assert result.status is FulfillmentStatus.FULFILLED
    assert result.selected_provider == "primary"
    assert tuple(item.provider_id for item in result.attempts) == ("primary",)
    assert len(budgets.accounting) == 1


def test_primary_failure_secondary_success_is_explicitly_degraded() -> None:
    primary = provider(
        "primary", FixtureScenario(failures=((CAPABILITY, ProviderErrorCode.TIMEOUT),))
    )
    fulfillment, budgets = service(primary, provider("secondary"))
    result = fulfillment.fulfill(request())
    assert result.status is FulfillmentStatus.DEGRADED
    assert result.selected_provider == "secondary"
    assert result.attempts[0].error is not None
    assert result.attempts[0].error.code is ProviderErrorCode.TIMEOUT
    assert result.attempts[1].observations
    assert len(budgets.accounting) == 2


def test_all_providers_fail_closed_with_aggregated_evidence() -> None:
    failed = FixtureScenario(failures=((CAPABILITY, ProviderErrorCode.NO_DATA),))
    fulfillment, _ = service(provider("primary", failed), provider("secondary", failed))
    result = fulfillment.fulfill(request(), required=False)
    assert result.status is FulfillmentStatus.FAILED
    assert result.selected_provider is None
    assert tuple(item.error.code for item in result.attempts if item.error) == (
        ProviderErrorCode.NO_DATA,
        ProviderErrorCode.NO_DATA,
    )
    assert result.required is False


def test_stale_primary_uses_fresh_secondary_without_silent_fallback() -> None:
    stale = FixtureScenario(staleness_seconds=120)
    fulfillment, _ = service(provider("primary", stale), provider("secondary"))
    result = fulfillment.fulfill(request())
    assert result.selected_provider == "secondary"
    assert result.attempts[0].error is not None
    assert result.attempts[0].error.code is ProviderErrorCode.STALE_DATA


def test_exhausted_budget_is_recorded_and_duplicate_request_is_not_reissued() -> None:
    first = provider("primary")
    fulfillment, budgets = service(first, maximum=1)
    initial = fulfillment.fulfill(request())
    duplicate = fulfillment.fulfill(request())
    assert duplicate is initial
    assert len(budgets.accounting) == 1

    other_service, other_budgets = service(first, maximum=1)
    other_budgets.authorize("primary", CAPABILITY, 1)
    exhausted = other_service.fulfill(request())
    assert exhausted.status is FulfillmentStatus.FAILED
    assert exhausted.attempts[0].error is not None
    assert exhausted.attempts[0].error.code is ProviderErrorCode.QUOTA_EXHAUSTED
