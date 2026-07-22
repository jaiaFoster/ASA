"""Deterministic, network-free Market Data Provider (MD-007)."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from domain import (
    AnnouncementTime,
    CompletenessMetadata,
    EarningsEvent,
    EvidenceKind,
    EvidenceReference,
    FreshnessMetadata,
    FreshnessStatus,
    MarketCapability,
    MarketDataSubject,
    MarketObservation,
    OHLCVBar,
    OptionChain,
    OptionContract,
    OptionType,
    ProviderProvenance,
    Quote,
    Security,
    SecurityAssetType,
    market_observation_identity,
)
from domain.operational import CanonicalInstrumentIdentity
from market_data.config import ProviderConfig
from market_data.factory import ProviderDependencies, ProviderRegistration
from market_data.providers import (
    CapabilityRequest,
    HealthProbe,
    ProviderAttemptMetadata,
    ProviderErrorCode,
    ProviderFetchResult,
    ProviderHealthReport,
    ProviderIdentity,
    ProviderLimitDeclaration,
    ProviderMetadata,
    ProviderResponseMetadata,
    ProviderShutdownReport,
    ProviderStatus,
    ProviderValidationPlan,
    ProviderValidationReport,
    RequestBudgetAuthorization,
    ValidationCheckResult,
    ValidationCheckStatus,
    normalized_provider_error,
)

FIXTURE_PROVIDER_ID = "deterministic_fixture"
FIXTURE_ADAPTER_VERSION = "v1"
FIXTURE_CAPABILITIES = (
    MarketCapability.REAL_TIME_QUOTE_V1,
    MarketCapability.HISTORICAL_BARS_V1,
    MarketCapability.OPTION_CHAIN_V1,
    MarketCapability.EARNINGS_CALENDAR_V1,
)


@dataclass(frozen=True, slots=True)
class FixtureScenario:
    """Explicit controls for deterministic failure and quality simulation."""

    failures: tuple[tuple[MarketCapability, ProviderErrorCode], ...] = ()
    latency_milliseconds: int = 0
    staleness_seconds: int = 0
    missing_fields: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if self.latency_milliseconds < 0 or self.staleness_seconds < 0:
            raise ValueError("Fixture scenario timing must be non-negative")
        if len(dict(self.failures)) != len(self.failures):
            raise ValueError("Fixture scenario has duplicate capability failures")
        object.__setattr__(self, "failures", tuple(sorted(self.failures, key=lambda x: x[0].value)))
        object.__setattr__(self, "missing_fields", tuple(sorted(set(self.missing_fields))))


class DeterministicFixtureProvider:
    """A complete offline provider driven only by input and an injected clock."""

    def __init__(
        self,
        config: ProviderConfig,
        dependencies: ProviderDependencies,
        scenario: FixtureScenario = FixtureScenario(),
    ) -> None:
        if config.provider_id != FIXTURE_PROVIDER_ID:
            raise ValueError("Fixture provider configuration identity mismatch")
        self._config = config
        self._dependencies = dependencies
        self._scenario = scenario
        identity = ProviderIdentity(config.provider_id, config.adapter_type, config.adapter_version)
        self._metadata = ProviderMetadata(
            identity,
            FIXTURE_CAPABILITIES,
            (ProviderLimitDeclaration("network_requests", "0", "fixture"),),
            FIXTURE_CAPABILITIES,
            "v1",
        )

    @property
    def provider_id(self) -> str:
        return self._config.provider_id

    @property
    def metadata(self) -> ProviderMetadata:
        return self._metadata

    @property
    def capabilities(self) -> tuple[MarketCapability, ...]:
        return self.metadata.capabilities

    def fetch(
        self, request: CapabilityRequest, budget: RequestBudgetAuthorization
    ) -> ProviderFetchResult:
        if budget.provider_id != self.provider_id:
            raise ValueError("Request budget is authorized for a different provider")
        received_at = self._dependencies.clock.now().astimezone(timezone.utc)
        reference = self._request_reference(request)
        response = ProviderResponseMetadata(
            self.provider_id,
            reference,
            received_at,
            "fixture",
            self._scenario.latency_milliseconds,
            0,
            (("network_requests", "0"),),
        )
        attempt = ProviderAttemptMetadata(self.provider_id, request.capability, 1, 1, response)
        failure = dict(self._scenario.failures).get(request.capability)
        if failure is not None:
            error = normalized_provider_error(
                failure,
                f"deterministic fixture simulated {failure.value}",
                self.provider_id,
                request.capability,
                reference,
            )
            return ProviderFetchResult((), error, (attempt,))
        if request.capability not in self.capabilities:
            error = normalized_provider_error(
                ProviderErrorCode.UNSUPPORTED_CAPABILITY,
                "deterministic fixture does not implement this capability",
                self.provider_id,
                request.capability,
                reference,
            )
            return ProviderFetchResult((), error, (attempt,))
        observations = tuple(
            self._observation(subject, received_at, reference, request.maximum_age_seconds)
            for subject in request.subjects
        )
        return ProviderFetchResult(observations, None, (attempt,))

    def health(self, probe: HealthProbe) -> ProviderHealthReport:
        return ProviderHealthReport(
            self.provider_id,
            ProviderStatus.AVAILABLE,
            probe.requested_at,
            "FIXTURE_AVAILABLE",
            None,
        )

    def validate(self, plan: ProviderValidationPlan) -> ProviderValidationReport:
        now = self._dependencies.clock.now().astimezone(timezone.utc)
        checks = tuple(
            ValidationCheckResult(
                f"capability:{capability.value}",
                ValidationCheckStatus.PASS
                if capability in self.capabilities
                else ValidationCheckStatus.NOT_SUPPORTED,
                "FIXTURE_CAPABILITY_AVAILABLE"
                if capability in self.capabilities
                else "FIXTURE_CAPABILITY_UNSUPPORTED",
                "offline fixture capability declaration checked",
            )
            for capability in plan.capabilities
        )
        report_id = hashlib.sha256(
            f"{plan.plan_id}:{self.provider_id}:{now.isoformat()}".encode()
        ).hexdigest()
        return ProviderValidationReport(
            report_id, plan.plan_id, self.provider_id, FIXTURE_ADAPTER_VERSION, now, now, checks, ()
        )

    def shutdown(self) -> ProviderShutdownReport:
        return ProviderShutdownReport(self.provider_id, self._dependencies.clock.now())

    def _observation(
        self,
        subject: MarketDataSubject,
        received_at: datetime,
        request_reference: str,
        freshness_threshold: int,
    ) -> MarketObservation:
        projection = subject.projection_for(
            self.provider_id, "symbol", subject.request_context.semantic_end
        )
        observed_at = received_at - timedelta(seconds=self._scenario.staleness_seconds)
        evidence = (EvidenceReference(EvidenceKind.OBSERVATION, projection.projection_identity),)
        value = self._value(subject, projection.address_value, observed_at, evidence)
        present_fields = tuple(
            field
            for field in subject.request_context.required_fields
            if field not in self._scenario.missing_fields
        )
        missing_fields = tuple(
            field
            for field in subject.request_context.required_fields
            if field in self._scenario.missing_fields
        )
        age = self._scenario.staleness_seconds
        status = FreshnessStatus.FRESH if age <= freshness_threshold else FreshnessStatus.STALE
        provenance = ProviderProvenance(self.provider_id, request_reference, evidence)
        identity = market_observation_identity(
            self.provider_id,
            subject.requested_capability,
            subject,
            observed_at,
            value,
            "v1",
        )
        return MarketObservation(
            identity,
            subject.requested_capability,
            subject,
            observed_at,
            received_at,
            value,
            "v1",
            provenance,
            FreshnessMetadata(received_at, observed_at, freshness_threshold, age, status),
            CompletenessMetadata(
                subject.request_context.required_fields, present_fields, missing_fields
            ),
        )

    def _value(
        self,
        subject: MarketDataSubject,
        address: str,
        observed_at: datetime,
        evidence: tuple[EvidenceReference, ...],
    ) -> Quote | OHLCVBar | OptionChain | EarningsEvent:
        instrument = subject.canonical_instrument
        capability = subject.requested_capability
        if capability is MarketCapability.REAL_TIME_QUOTE_V1:
            return Quote(
                instrument,
                Decimal("209.90"),
                Decimal("210.10"),
                Decimal("210.00"),
                Decimal("100"),
                Decimal("120"),
                Decimal("1000000"),
                instrument.currency,
            )
        if capability is MarketCapability.HISTORICAL_BARS_V1:
            return OHLCVBar(
                instrument,
                86400,
                observed_at - timedelta(days=1),
                observed_at,
                Decimal("205"),
                Decimal("212"),
                Decimal("204"),
                Decimal("210"),
                Decimal("50000000"),
            )
        security = Security(instrument, address.upper(), SecurityAssetType.EQUITY, "XNAS")
        if capability is MarketCapability.EARNINGS_CALENDAR_V1:
            event_date = observed_at.date() + timedelta(days=30)
            return EarningsEvent(
                f"fixture:{address}:{event_date.isoformat()}",
                security,
                event_date,
                AnnouncementTime.AFTER_CLOSE,
                Decimal("0.05"),
                True,
                (),
                observed_at,
                evidence,
            )
        expiration = observed_at.date() + timedelta(days=30)
        contracts = tuple(
            OptionContract(
                CanonicalInstrumentIdentity("fixture-option", f"{address}-{kind.value}"),
                security,
                expiration,
                Decimal("210"),
                kind,
                Decimal("4.90"),
                Decimal("5.10"),
                Decimal("5.00"),
                1000,
                5000,
                Decimal("0.50") if kind is OptionType.CALL else Decimal("-0.50"),
                Decimal("0.03"),
                Decimal("-0.10"),
                Decimal("0.20"),
                Decimal("0.01"),
                Decimal("0.25"),
                observed_at,
                evidence,
            )
            for kind in (OptionType.CALL, OptionType.PUT)
        )
        return OptionChain(
            f"fixture:{address}:{expiration.isoformat()}",
            security,
            observed_at,
            contracts,
            evidence,
        )

    def _request_reference(self, request: CapabilityRequest) -> str:
        source = ":".join(
            (request.capability.value, *(subject.subject_identity for subject in request.subjects))
        )
        return f"fixture-{hashlib.sha256(source.encode()).hexdigest()[:20]}"


def fixture_provider_registration() -> ProviderRegistration:
    return ProviderRegistration(
        "deterministic_fixture", FIXTURE_ADAPTER_VERSION, DeterministicFixtureProvider
    )
