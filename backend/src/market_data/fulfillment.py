"""Deterministic, capability-driven provider fulfillment (MD-012)."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from domain import FreshnessStatus, MarketObservation
from domain.values import DomainInvariantError
from market_data.budget import (
    BudgetExhaustedError,
    BudgetScope,
    RequestBudgetManager,
    RequestOutcome,
)
from market_data.providers import (
    CapabilityRequest,
    NormalizedProviderError,
    ProviderAttemptMetadata,
    ProviderErrorCode,
    ProviderStatus,
    normalized_provider_error,
)
from market_data.registry import CapabilityRegistry, ProviderRegistry


class FulfillmentStatus(str, Enum):
    FULFILLED = "fulfilled"
    DEGRADED = "degraded"
    FAILED = "failed"


@dataclass(frozen=True, slots=True)
class ProviderFulfillmentAttempt:
    provider_id: str
    priority: int
    provider_status: ProviderStatus
    observations: tuple[MarketObservation, ...]
    error: NormalizedProviderError | None
    request_attempts: tuple[ProviderAttemptMetadata, ...]

    def __post_init__(self) -> None:
        if not self.provider_id or self.provider_id != self.provider_id.strip():
            raise DomainInvariantError("ProviderFulfillmentAttempt provider_id must be normalized")
        if type(self.priority) is not int or self.priority < 1:
            raise DomainInvariantError("ProviderFulfillmentAttempt priority must be positive")
        if bool(self.observations) == (self.error is not None):
            raise DomainInvariantError(
                "ProviderFulfillmentAttempt requires observations or one error, exclusively"
            )


@dataclass(frozen=True, slots=True)
class CapabilityFulfillmentResult:
    request: CapabilityRequest
    status: FulfillmentStatus
    selected_provider: str | None
    observations: tuple[MarketObservation, ...]
    attempts: tuple[ProviderFulfillmentAttempt, ...]
    required: bool

    def __post_init__(self) -> None:
        if not self.attempts:
            raise DomainInvariantError("CapabilityFulfillmentResult requires attempt evidence")
        successful = bool(self.observations)
        if successful != (self.selected_provider is not None):
            raise DomainInvariantError("Fulfillment provider selection is inconsistent")
        if self.status is FulfillmentStatus.FAILED and successful:
            raise DomainInvariantError("Failed fulfillment cannot contain observations")
        if self.status is not FulfillmentStatus.FAILED and not successful:
            raise DomainInvariantError("Successful fulfillment requires observations")


class CapabilityFulfillmentService:
    """Per-run service with explicit fallback evidence and request de-duplication."""

    __slots__ = ("_providers", "_capabilities", "_budgets", "_results")

    def __init__(
        self,
        providers: ProviderRegistry,
        capabilities: CapabilityRegistry,
        budgets: RequestBudgetManager,
    ) -> None:
        self._providers = providers
        self._capabilities = capabilities
        self._budgets = budgets
        self._results: dict[tuple[CapabilityRequest, bool], CapabilityFulfillmentResult] = {}

    def fulfill(
        self, request: CapabilityRequest, *, required: bool = True
    ) -> CapabilityFulfillmentResult:
        key = (request, required)
        existing = self._results.get(key)
        if existing is not None:
            return existing

        audit: list[ProviderFulfillmentAttempt] = []
        for candidate in self._capabilities.lookup(request.capability):
            provider = self._providers.provider(candidate.provider_id)
            try:
                authorization = self._budgets.authorize(
                    provider.provider_id,
                    request.capability,
                    1,
                    BudgetScope.RUNTIME,
                )
            except BudgetExhaustedError:
                error = normalized_provider_error(
                    ProviderErrorCode.QUOTA_EXHAUSTED,
                    "finite provider request budget is unavailable or exhausted",
                    provider.provider_id,
                    request.capability,
                )
                audit.append(
                    ProviderFulfillmentAttempt(
                        provider.provider_id, candidate.priority, candidate.status, (), error, ()
                    )
                )
                continue

            fetched = provider.fetch(request, authorization)
            outcome = RequestOutcome.SUCCEEDED
            if fetched.error is not None:
                outcome = (
                    RequestOutcome.RATE_LIMITED
                    if fetched.error.code is ProviderErrorCode.RATE_LIMITED
                    else RequestOutcome.TIMEOUT
                    if fetched.error.code is ProviderErrorCode.TIMEOUT
                    else RequestOutcome.FAILED
                )
            self._budgets.complete(authorization.authorization_id, outcome)

            fetch_error = fetched.error or self._quality_error(
                provider.provider_id, request, fetched.observations
            )
            observations = fetched.observations if fetch_error is None else ()
            audit.append(
                ProviderFulfillmentAttempt(
                    provider.provider_id,
                    candidate.priority,
                    candidate.status,
                    observations,
                    fetch_error,
                    fetched.attempts,
                )
            )
            if fetch_error is None:
                status = (
                    FulfillmentStatus.FULFILLED if len(audit) == 1 else FulfillmentStatus.DEGRADED
                )
                result = CapabilityFulfillmentResult(
                    request, status, provider.provider_id, observations, tuple(audit), required
                )
                self._results[key] = result
                return result

            if fetch_error.code is ProviderErrorCode.UNSUPPORTED_CAPABILITY:
                continue

        result = CapabilityFulfillmentResult(
            request, FulfillmentStatus.FAILED, None, (), tuple(audit), required
        )
        self._results[key] = result
        return result

    @staticmethod
    def _quality_error(
        provider_id: str,
        request: CapabilityRequest,
        observations: tuple[MarketObservation, ...],
    ) -> NormalizedProviderError | None:
        if any(value.freshness.status is not FreshnessStatus.FRESH for value in observations):
            return normalized_provider_error(
                ProviderErrorCode.STALE_DATA,
                "provider observations do not satisfy the requested freshness requirement",
                provider_id,
                request.capability,
            )
        if any(value.completeness.missing_fields for value in observations):
            return normalized_provider_error(
                ProviderErrorCode.INCOMPLETE_DATA,
                "provider observations do not satisfy required field completeness",
                provider_id,
                request.capability,
            )
        return None
