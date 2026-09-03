from __future__ import annotations

import dataclasses
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from domain import (
    CanonicalInstrumentIdentity,
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
    HealthProbe,
    ProviderAttemptMetadata,
    ProviderDependencies,
    ProviderErrorCode,
    ProviderFetchResult,
    ProviderHealthReport,
    ProviderIdentity,
    ProviderMetadata,
    ProviderPriority,
    ProviderPriorityPolicy,
    ProviderRegistry,
    ProviderResponseMetadata,
    ProviderShutdownReport,
    ProviderStatus,
    ProviderValidationPlan,
    ProviderValidationReport,
    RequestBudgetAuthorization,
    RequestBudgetManager,
    RequestBudgetPolicy,
    ReuseDecision,
    load_market_data_config,
    normalized_provider_error,
)

NOW = datetime(2026, 7, 21, 16, 0, tzinfo=UTC)
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


class DuplicateValueProvider(ScriptedProvider):
    """Adapter defect: two canonical values for one provider/subject."""

    def fetch(
        self, capability_request: CapabilityRequest, budget: RequestBudgetAuthorization
    ) -> ProviderFetchResult:
        fetched = super().fetch(capability_request, budget)
        assert fetched.error is None
        return dataclasses.replace(
            fetched,
            observations=(fetched.observations[0], fetched.observations[0]),
        )


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
    rolling_window: object | None = None,
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
        rolling_window=rolling_window,
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


def test_duplicate_earnings_values_fail_at_provider_quality_boundary() -> None:
    fetched = DuplicateValueProvider("primary", FixtureScenario()).fetch(
        request(), RequestBudgetAuthorization("auth", "primary", 1, 1)
    )
    base_request = request()
    earnings_subject = dataclasses.replace(
        base_request.subjects[0],
        requested_capability=MarketCapability.EARNINGS_CALENDAR_V1,
        subject_type=MarketDataSubjectType.EARNINGS_SECURITY,
    )
    earnings_request = dataclasses.replace(
        base_request,
        capability=MarketCapability.EARNINGS_CALENDAR_V1,
        subjects=(earnings_subject,),
    )

    error = CapabilityFulfillmentService._quality_error(
        "primary", earnings_request, fetched.observations
    )

    assert error is not None
    assert error.code is ProviderErrorCode.SCHEMA_MISMATCH


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


def test_prior_session_quote_is_usable_without_fallback() -> None:
    primary = provider("primary")
    original_fetch = primary.fetch

    def prior_session_fetch(
        capability_request: CapabilityRequest, budget: RequestBudgetAuthorization
    ) -> ProviderFetchResult:
        fetched = original_fetch(capability_request, budget)
        observation = fetched.observations[0]
        effective = observation.effective_time - timedelta(days=3)
        freshness = FreshnessMetadata(
            observation.recorded_time,
            effective,
            60,
            int((observation.recorded_time - effective).total_seconds()),
            FreshnessStatus.PRIOR_SESSION,
        )
        return dataclasses.replace(
            fetched,
            observations=(
                dataclasses.replace(
                    observation,
                    effective_time=effective,
                    freshness=freshness,
                    observation_id=market_observation_identity(
                        observation.provenance.provider_id,
                        observation.capability,
                        observation.subject,
                        effective,
                        observation.value,
                        observation.schema_version,
                    ),
                ),
            ),
        )

    primary.fetch = prior_session_fetch  # type: ignore[method-assign]
    fulfillment, _ = service(primary, provider("secondary"))
    result = fulfillment.fulfill(request())
    assert result.status is FulfillmentStatus.FULFILLED
    assert result.selected_provider == "primary"


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
    # SPRINT-013 S13-03A: the pair-local total ceiling now gets its own
    # distinct code instead of the generic QUOTA_EXHAUSTED.
    assert exhausted.attempts[0].error.code is ProviderErrorCode.PAIR_BUDGET_EXHAUSTED


# -- SPRINT-013 S13-03A: shared rolling-window request boundary -----------


def test_outbound_upstream_rejection_still_consumes_a_provider_unit() -> None:
    """A request that reaches the provider and comes back rate_limited
    consumes its shared-window unit exactly like a success would --
    authorize() reserves before the outcome is known, never after."""
    from market_data.rolling_window import ProviderRollingWindowTracker, RollingWindowPolicy

    window = ProviderRollingWindowTracker((RollingWindowPolicy("primary", 60, 5, "test"),), Clock())
    failed = FixtureScenario(failures=((CAPABILITY, ProviderErrorCode.RATE_LIMITED),))
    fulfillment, _ = service(provider("primary", failed), rolling_window=window)

    result = fulfillment.fulfill(request(), required=False)

    assert result.status is FulfillmentStatus.FAILED
    assert window.summary()["primary"] == 1


def test_fallback_consumes_the_fallback_providers_own_unit() -> None:
    """Primary fails locally-shaped, fallback succeeds -- each provider's
    rolling window is reserved independently, under its own provider_id."""
    from market_data.rolling_window import ProviderRollingWindowTracker, RollingWindowPolicy

    window = ProviderRollingWindowTracker(
        (
            RollingWindowPolicy("primary", 60, 5, "test"),
            RollingWindowPolicy("secondary", 60, 5, "test"),
        ),
        Clock(),
    )
    primary = provider(
        "primary", FixtureScenario(failures=((CAPABILITY, ProviderErrorCode.TIMEOUT),))
    )
    fulfillment, _ = service(primary, provider("secondary"), rolling_window=window)

    result = fulfillment.fulfill(request())

    assert result.status is FulfillmentStatus.DEGRADED
    assert window.summary() == {"primary": 1, "secondary": 1}


def test_shared_window_refusal_produces_a_distinct_diagnostic_reason() -> None:
    """The exact refusal reason (SPRINT-013 S13-03A) survives into the
    NormalizedProviderError -- never collapsed to generic QUOTA_EXHAUSTED,
    and distinguishable from a pair-local total/burst refusal."""
    from market_data.rolling_window import ProviderRollingWindowTracker, RollingWindowPolicy

    window = ProviderRollingWindowTracker((RollingWindowPolicy("primary", 60, 1, "test"),), Clock())
    window.try_reserve("primary")  # consume the one shared slot up front
    fulfillment, budgets = service(provider("primary"), rolling_window=window)

    result = fulfillment.fulfill(request(), required=False)

    assert result.status is FulfillmentStatus.FAILED
    assert result.attempts[0].error is not None
    assert result.attempts[0].error.code is ProviderErrorCode.PROVIDER_ROLLING_WINDOW_EXHAUSTED
    assert budgets.accounting == ()  # local ledger untouched by the shared refusal


# -- SPRINT-013 S13-03B: cycle-scoped request reuse -----------------------


def test_reuse_hit_is_logged_reused_and_costs_no_new_provider_request() -> None:
    fulfillment, budgets = service(provider("primary"))

    initial = fulfillment.fulfill(request())
    duplicate = fulfillment.fulfill(request())

    assert duplicate is initial
    assert len(budgets.accounting) == 1
    assert [decision for _, decision in fulfillment.call_log] == [
        ReuseDecision.FRESH,
        ReuseDecision.REUSED,
    ]


class _FailsOnceProvider:
    """A provider that fails its first fetch and succeeds every fetch
    after -- used to prove a cached failure is never reused (SPRINT-013
    S13-03B), unlike ScriptedProvider, whose scripted outcome is fixed for
    its whole lifetime.
    """

    def __init__(self, provider_id: str) -> None:
        self.provider_id = provider_id
        self._calls = 0
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
        self._calls += 1
        response = ProviderResponseMetadata(
            self.provider_id, f"{self.provider_id}-request-{self._calls}", NOW, "fixture", 0, 0
        )
        attempt = ProviderAttemptMetadata(self.provider_id, CAPABILITY, 1, 1, response)
        if self._calls == 1:
            return ProviderFetchResult(
                (),
                normalized_provider_error(
                    ProviderErrorCode.TRANSPORT_ERROR,
                    "simulated transient failure",
                    self.provider_id,
                    CAPABILITY,
                ),
                (attempt,),
            )
        base = (
            fixture_provider(FixtureScenario())
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


def test_a_failed_result_is_never_reused_and_gets_its_own_independent_retry() -> None:
    flaky = _FailsOnceProvider("primary")
    registry = ProviderRegistry((flaky,))
    capabilities = CapabilityRegistry(
        registry, ProviderPriorityPolicy("v1", (ProviderPriority(CAPABILITY, ("primary",)),))
    )
    budgets = RequestBudgetManager(
        (RequestBudgetPolicy("primary", BudgetScope.RUNTIME, 4, 4, 0, "v1"),), Clock()
    )
    fulfillment = CapabilityFulfillmentService(registry, capabilities, budgets)

    first = fulfillment.fulfill(request(), required=False)
    second = fulfillment.fulfill(request(), required=False)

    assert first.status is FulfillmentStatus.FAILED
    assert second.status is FulfillmentStatus.FULFILLED  # independent retry, not a cached failure
    assert len(budgets.accounting) == 2
    assert [decision for _, decision in fulfillment.call_log] == [
        ReuseDecision.FRESH,
        ReuseDecision.FRESH_AFTER_OTHER_BYPASS,
    ]


def test_different_subjects_never_share_a_cached_result() -> None:
    fulfillment, budgets = service(provider("primary"))

    fields = ("last",)
    other_projection = ProviderAddressProjection(
        "deterministic_fixture", "v1", "symbol", "MSFT", NOW, None, EVIDENCE
    )
    other_subject = MarketDataSubject(
        Instrument(
            CanonicalInstrumentIdentity("figi", "BBG000BPH459"),
            InstrumentKind.EQUITY,
            "MSFT",
            "USD",
        ),
        MarketDataSubjectType.INSTRUMENT,
        CAPABILITY,
        MarketDataRequestContext(NOW, NOW, fields, (other_projection,), EVIDENCE),
    )
    other_request = CapabilityRequest(CAPABILITY, (other_subject,), NOW, NOW, fields, 60)

    fulfillment.fulfill(request())
    fulfillment.fulfill(other_request)

    assert len(budgets.accounting) == 2  # no cross-symbol reuse
    assert [decision for _, decision in fulfillment.call_log] == [
        ReuseDecision.FRESH,
        ReuseDecision.FRESH,
    ]
