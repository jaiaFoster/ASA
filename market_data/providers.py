"""Provider-neutral ports, metadata, and normalized errors (MD-003)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Protocol, runtime_checkable

from domain import (
    MarketCapability,
    MarketDataSubject,
    MarketObservation,
    ProviderErrorKind,
)
from domain.values import DomainInvariantError, require_tz_aware


def _text(value: str, owner: str, field_name: str) -> None:
    if not value or value != value.strip():
        raise DomainInvariantError(f"{owner}.{field_name} must be non-empty normalized text")


class ProviderStatus(str, Enum):
    UNKNOWN = "unknown"
    AVAILABLE = "available"
    DEGRADED = "degraded"
    UNAVAILABLE = "unavailable"
    SHUTDOWN = "shutdown"


class ValidationCheckStatus(str, Enum):
    PASS = "pass"
    FAIL = "fail"
    SKIPPED = "skipped"
    NOT_SUPPORTED = "not_supported"


class ProviderErrorCode(str, Enum):
    CONFIGURATION_ERROR = "configuration_error"
    AUTHENTICATION_FAILED = "authentication_failed"
    AUTHORIZATION_FAILED = "authorization_failed"
    ENTITLEMENT_MISSING = "entitlement_missing"
    INVALID_REQUEST = "invalid_request"
    UNSUPPORTED_CAPABILITY = "unsupported_capability"
    UNSUPPORTED_SYMBOL = "unsupported_symbol"
    NO_DATA = "no_data"
    EMPTY_PAYLOAD = "empty_payload"
    SCHEMA_MISMATCH = "schema_mismatch"
    RATE_LIMITED = "rate_limited"
    QUOTA_EXHAUSTED = "quota_exhausted"
    TIMEOUT = "timeout"
    PROVIDER_UNAVAILABLE = "provider_unavailable"
    TRANSPORT_ERROR = "transport_error"
    STALE_DATA = "stale_data"
    INCOMPLETE_DATA = "incomplete_data"
    UNKNOWN_PROVIDER_ERROR = "unknown_provider_error"


_ERROR_POLICY: dict[ProviderErrorCode, tuple[ProviderErrorKind, bool]] = {
    ProviderErrorCode.CONFIGURATION_ERROR: (ProviderErrorKind.UNKNOWN, False),
    ProviderErrorCode.AUTHENTICATION_FAILED: (ProviderErrorKind.AUTHENTICATION, False),
    ProviderErrorCode.AUTHORIZATION_FAILED: (ProviderErrorKind.AUTHORIZATION, False),
    ProviderErrorCode.ENTITLEMENT_MISSING: (ProviderErrorKind.AUTHORIZATION, False),
    ProviderErrorCode.INVALID_REQUEST: (ProviderErrorKind.UNKNOWN, False),
    ProviderErrorCode.UNSUPPORTED_CAPABILITY: (ProviderErrorKind.UNKNOWN, False),
    ProviderErrorCode.UNSUPPORTED_SYMBOL: (ProviderErrorKind.UNKNOWN, False),
    ProviderErrorCode.NO_DATA: (ProviderErrorKind.UNAVAILABLE, False),
    ProviderErrorCode.EMPTY_PAYLOAD: (ProviderErrorKind.SCHEMA, False),
    ProviderErrorCode.SCHEMA_MISMATCH: (ProviderErrorKind.SCHEMA, False),
    ProviderErrorCode.RATE_LIMITED: (ProviderErrorKind.RATE_LIMIT, True),
    ProviderErrorCode.QUOTA_EXHAUSTED: (ProviderErrorKind.RATE_LIMIT, False),
    ProviderErrorCode.TIMEOUT: (ProviderErrorKind.TIMEOUT, True),
    ProviderErrorCode.PROVIDER_UNAVAILABLE: (ProviderErrorKind.UNAVAILABLE, True),
    ProviderErrorCode.TRANSPORT_ERROR: (ProviderErrorKind.TRANSPORT, True),
    ProviderErrorCode.STALE_DATA: (ProviderErrorKind.UNAVAILABLE, False),
    ProviderErrorCode.INCOMPLETE_DATA: (ProviderErrorKind.SCHEMA, False),
    ProviderErrorCode.UNKNOWN_PROVIDER_ERROR: (ProviderErrorKind.UNKNOWN, False),
}


@dataclass(frozen=True, slots=True)
class ProviderIdentity:
    provider_id: str
    adapter_type: str
    adapter_version: str

    def __post_init__(self) -> None:
        for name in ("provider_id", "adapter_type", "adapter_version"):
            _text(getattr(self, name), "ProviderIdentity", name)


@dataclass(frozen=True, slots=True)
class ProviderLimitDeclaration:
    name: str
    value: str
    source: str

    def __post_init__(self) -> None:
        for field_name in ("name", "value", "source"):
            _text(getattr(self, field_name), "ProviderLimitDeclaration", field_name)


@dataclass(frozen=True, slots=True)
class ProviderMetadata:
    identity: ProviderIdentity
    capabilities: tuple[MarketCapability, ...]
    declared_limits: tuple[ProviderLimitDeclaration, ...]
    fixture_coverage: tuple[MarketCapability, ...]
    documentation_version: str

    def __post_init__(self) -> None:
        capabilities = tuple(sorted(set(self.capabilities), key=lambda value: value.value))
        coverage = tuple(sorted(set(self.fixture_coverage), key=lambda value: value.value))
        if not capabilities:
            raise DomainInvariantError("ProviderMetadata requires capabilities")
        if not set(coverage).issubset(capabilities):
            raise DomainInvariantError("Provider fixture coverage must be declared capabilities")
        limits = tuple(sorted(self.declared_limits, key=lambda value: value.name))
        if len({value.name for value in limits}) != len(limits):
            raise DomainInvariantError("Provider limit names must be unique")
        _text(self.documentation_version, "ProviderMetadata", "documentation_version")
        object.__setattr__(self, "capabilities", capabilities)
        object.__setattr__(self, "fixture_coverage", coverage)
        object.__setattr__(self, "declared_limits", limits)


@dataclass(frozen=True, slots=True)
class CapabilityRequest:
    capability: MarketCapability
    subjects: tuple[MarketDataSubject, ...]
    effective_start: datetime
    effective_end: datetime
    required_fields: tuple[str, ...]
    maximum_age_seconds: int

    def __post_init__(self) -> None:
        require_tz_aware(self.effective_start, "CapabilityRequest", "effective_start")
        require_tz_aware(self.effective_end, "CapabilityRequest", "effective_end")
        if self.effective_start > self.effective_end:
            raise DomainInvariantError("CapabilityRequest time window is inverted")
        subjects = tuple(sorted(set(self.subjects), key=lambda value: value.subject_identity))
        if not subjects:
            raise DomainInvariantError("CapabilityRequest requires canonical subjects")
        if any(subject.requested_capability is not self.capability for subject in subjects):
            raise DomainInvariantError("CapabilityRequest subject capability mismatch")
        if any(
            subject.request_context.semantic_start != self.effective_start
            or subject.request_context.semantic_end != self.effective_end
            for subject in subjects
        ):
            raise DomainInvariantError("CapabilityRequest subject time window mismatch")
        required = tuple(sorted(set(self.required_fields)))
        if not required or any(not value or value != value.strip() for value in required):
            raise DomainInvariantError("CapabilityRequest requires normalized required_fields")
        if type(self.maximum_age_seconds) is not int or self.maximum_age_seconds < 0:
            raise DomainInvariantError("CapabilityRequest maximum_age_seconds must be non-negative")
        if any(subject.request_context.required_fields != required for subject in subjects):
            raise DomainInvariantError("CapabilityRequest subject required fields mismatch")
        object.__setattr__(self, "subjects", subjects)
        object.__setattr__(self, "required_fields", required)


@dataclass(frozen=True, slots=True)
class RequestBudgetAuthorization:
    authorization_id: str
    provider_id: str
    allowed_request_units: int
    allowed_attempts: int

    def __post_init__(self) -> None:
        _text(self.authorization_id, "RequestBudgetAuthorization", "authorization_id")
        _text(self.provider_id, "RequestBudgetAuthorization", "provider_id")
        for name in ("allowed_request_units", "allowed_attempts"):
            if type(getattr(self, name)) is not int or getattr(self, name) <= 0:
                raise DomainInvariantError(f"RequestBudgetAuthorization.{name} must be positive")


@dataclass(frozen=True, slots=True)
class ProviderResponseMetadata:
    provider_id: str
    provider_request_reference: str
    received_at: datetime
    status_category: str
    latency_milliseconds: int
    retry_count: int
    quota_metadata: tuple[tuple[str, str], ...] = ()

    def __post_init__(self) -> None:
        for name in ("provider_id", "provider_request_reference", "status_category"):
            _text(getattr(self, name), "ProviderResponseMetadata", name)
        require_tz_aware(self.received_at, "ProviderResponseMetadata", "received_at")
        if type(self.latency_milliseconds) is not int or self.latency_milliseconds < 0:
            raise DomainInvariantError("ProviderResponseMetadata latency must be non-negative")
        if type(self.retry_count) is not int or self.retry_count < 0:
            raise DomainInvariantError("ProviderResponseMetadata retry_count must be non-negative")
        quota = tuple(sorted(set(self.quota_metadata)))
        if any(not key or not value for key, value in quota):
            raise DomainInvariantError("ProviderResponseMetadata quota metadata must be non-empty")
        object.__setattr__(self, "quota_metadata", quota)


@dataclass(frozen=True, slots=True)
class ProviderAttemptMetadata:
    provider_id: str
    capability: MarketCapability
    attempt_number: int
    request_units: int
    response: ProviderResponseMetadata | None

    def __post_init__(self) -> None:
        _text(self.provider_id, "ProviderAttemptMetadata", "provider_id")
        for name in ("attempt_number", "request_units"):
            if type(getattr(self, name)) is not int or getattr(self, name) <= 0:
                raise DomainInvariantError(f"ProviderAttemptMetadata.{name} must be positive")
        if self.response is not None and self.response.provider_id != self.provider_id:
            raise DomainInvariantError("ProviderAttemptMetadata response provider mismatch")


@dataclass(frozen=True, slots=True)
class NormalizedProviderError:
    kind: ProviderErrorKind
    code: ProviderErrorCode
    retryable: bool
    safe_summary: str
    provider_id: str
    capability: MarketCapability
    provider_request_reference: str | None = None

    def __post_init__(self) -> None:
        expected_kind, expected_retryable = _ERROR_POLICY[self.code]
        if self.kind is not expected_kind or self.retryable is not expected_retryable:
            raise DomainInvariantError("NormalizedProviderError policy is inconsistent")
        _text(self.safe_summary, "NormalizedProviderError", "safe_summary")
        _text(self.provider_id, "NormalizedProviderError", "provider_id")
        if self.provider_request_reference is not None:
            _text(
                self.provider_request_reference,
                "NormalizedProviderError",
                "provider_request_reference",
            )


def normalized_provider_error(
    code: ProviderErrorCode,
    safe_summary: str,
    provider_id: str,
    capability: MarketCapability,
    provider_request_reference: str | None = None,
) -> NormalizedProviderError:
    kind, retryable = _ERROR_POLICY[code]
    return NormalizedProviderError(
        kind,
        code,
        retryable,
        safe_summary,
        provider_id,
        capability,
        provider_request_reference,
    )


@dataclass(frozen=True, slots=True)
class ProviderFetchResult:
    observations: tuple[MarketObservation, ...]
    error: NormalizedProviderError | None
    attempts: tuple[ProviderAttemptMetadata, ...]

    def __post_init__(self) -> None:
        if bool(self.observations) == (self.error is not None):
            raise DomainInvariantError(
                "ProviderFetchResult requires observations or one error, exclusively"
            )
        if not self.attempts:
            raise DomainInvariantError("ProviderFetchResult requires attempt metadata")


@dataclass(frozen=True, slots=True)
class HealthProbe:
    requested_at: datetime
    maximum_request_units: int = 1

    def __post_init__(self) -> None:
        require_tz_aware(self.requested_at, "HealthProbe", "requested_at")
        if self.maximum_request_units != 1:
            raise DomainInvariantError("HealthProbe maximum_request_units must equal one")


@dataclass(frozen=True, slots=True)
class ProviderHealthReport:
    provider_id: str
    status: ProviderStatus
    checked_at: datetime
    detail_code: str
    attempt: ProviderAttemptMetadata | None

    def __post_init__(self) -> None:
        _text(self.provider_id, "ProviderHealthReport", "provider_id")
        _text(self.detail_code, "ProviderHealthReport", "detail_code")
        require_tz_aware(self.checked_at, "ProviderHealthReport", "checked_at")


@dataclass(frozen=True, slots=True)
class ValidationCheckResult:
    check_id: str
    status: ValidationCheckStatus
    detail_code: str
    safe_summary: str

    def __post_init__(self) -> None:
        for name in ("check_id", "detail_code", "safe_summary"):
            _text(getattr(self, name), "ValidationCheckResult", name)


@dataclass(frozen=True, slots=True)
class ProviderValidationPlan:
    plan_id: str
    provider_id: str
    capabilities: tuple[MarketCapability, ...]
    maximum_requests: int
    maximum_request_units: int
    timeout_seconds: int
    subjects: tuple[MarketDataSubject, ...] = ()

    def __post_init__(self) -> None:
        _text(self.plan_id, "ProviderValidationPlan", "plan_id")
        _text(self.provider_id, "ProviderValidationPlan", "provider_id")
        capabilities = tuple(sorted(set(self.capabilities), key=lambda value: value.value))
        if not capabilities:
            raise DomainInvariantError("ProviderValidationPlan requires capabilities")
        for name in ("maximum_requests", "maximum_request_units", "timeout_seconds"):
            if type(getattr(self, name)) is not int or getattr(self, name) <= 0:
                raise DomainInvariantError(f"ProviderValidationPlan.{name} must be positive")
        object.__setattr__(self, "capabilities", capabilities)
        subjects = tuple(sorted(set(self.subjects), key=lambda item: item.subject_identity))
        if any(subject.requested_capability not in capabilities for subject in subjects):
            raise DomainInvariantError("ProviderValidationPlan subject capability is not planned")
        object.__setattr__(self, "subjects", subjects)


@dataclass(frozen=True, slots=True)
class ProviderValidationReport:
    report_id: str
    plan_id: str
    provider_id: str
    adapter_version: str
    started_at: datetime
    completed_at: datetime
    checks: tuple[ValidationCheckResult, ...]
    attempts: tuple[ProviderAttemptMetadata, ...]

    def __post_init__(self) -> None:
        for name in ("report_id", "plan_id", "provider_id", "adapter_version"):
            _text(getattr(self, name), "ProviderValidationReport", name)
        require_tz_aware(self.started_at, "ProviderValidationReport", "started_at")
        require_tz_aware(self.completed_at, "ProviderValidationReport", "completed_at")
        if self.completed_at < self.started_at:
            raise DomainInvariantError("ProviderValidationReport completion precedes start")
        if not self.checks:
            raise DomainInvariantError("ProviderValidationReport requires checks")
        if len({value.check_id for value in self.checks}) != len(self.checks):
            raise DomainInvariantError("ProviderValidationReport check IDs must be unique")


@dataclass(frozen=True, slots=True)
class ProviderShutdownReport:
    provider_id: str
    shutdown_at: datetime
    status: ProviderStatus = ProviderStatus.SHUTDOWN

    def __post_init__(self) -> None:
        _text(self.provider_id, "ProviderShutdownReport", "provider_id")
        require_tz_aware(self.shutdown_at, "ProviderShutdownReport", "shutdown_at")
        if self.status is not ProviderStatus.SHUTDOWN:
            raise DomainInvariantError("ProviderShutdownReport status must be shutdown")


@runtime_checkable
class MarketDataProvider(Protocol):
    @property
    def provider_id(self) -> str: ...

    @property
    def metadata(self) -> ProviderMetadata: ...

    @property
    def capabilities(self) -> tuple[MarketCapability, ...]: ...

    def fetch(
        self, request: CapabilityRequest, budget: RequestBudgetAuthorization
    ) -> ProviderFetchResult: ...

    def health(self, probe: HealthProbe) -> ProviderHealthReport: ...

    def validate(self, plan: ProviderValidationPlan) -> ProviderValidationReport: ...

    def shutdown(self) -> ProviderShutdownReport: ...
