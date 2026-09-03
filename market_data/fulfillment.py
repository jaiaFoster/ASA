"""Deterministic, capability-driven provider fulfillment (MD-012).

SPRINT-013 S13-03B extends the existing per-instance request de-duplication
(``_results``) with two things a caller sharing one service across more
than one strategy evaluation needs: (1) a cached failed result is never
served from cache -- always retried fresh and independently, so one
evaluation's transient failure can never propagate onto every later
evaluation sharing this service (see ``_bypass_decision_for`` below); (2) an
append-only ``call_log`` recording, per ``fulfill()`` call, the exact
``ReuseDecision`` that call resolved to. A caller that shares one service
across several evaluations (e.g. several strategies for the same subject in
one screening cycle) can slice ``call_log`` around one evaluation to know
precisely which capability requests *that* evaluation actually triggered,
and whether each was a genuine provider attempt or a reuse -- without
reaching into this class's own internals.

A cached *successful* result needs no separate staleness re-check at reuse
time: ``CapabilityRequest.maximum_age_seconds`` is already baked into the
request's own identity and validated once, at the original fetch, against
whatever "now" the caller's own clock reported then. A caller sharing this
service across a bounded window of evaluations (SPRINT-013 S13-03B's own
cycle-scoped clock, frozen once per screening cycle -- see
asa/scheduled_screening.py) sees that exact same "now" for the whole
window by construction, so a successful cached result is definitionally
still exactly as fresh, by that same clock, as it was when it was fetched.
A caller that does *not* freeze its own clock across calls (e.g. a
single-use service built for one on-demand evaluation) never reuses across
enough elapsed time for this to matter in the first place.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from domain import FreshnessStatus, MarketCapability, MarketObservation
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


class ReuseDecision(str, Enum):
    """SPRINT-013 S13-03B: the exact disposition of one ``fulfill()`` call,
    recorded in ``CapabilityFulfillmentService.call_log`` -- never inferred
    after the fact from ``_results`` alone, since a cache entry a later
    call evicts (stale or failed) leaves no trace of *why* it was evicted.
    """

    REUSED = "reused"
    FRESH = "fresh"
    FRESH_AFTER_STALE_BYPASS = "fresh_after_stale_bypass"
    FRESH_AFTER_INCOMPLETE_BYPASS = "fresh_after_incomplete_bypass"
    FRESH_AFTER_OTHER_BYPASS = "fresh_after_other_bypass"


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

    __slots__ = ("_providers", "_capabilities", "_budgets", "_results", "_call_log")

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
        self._call_log: list[tuple[CapabilityFulfillmentResult, ReuseDecision]] = []

    def fulfill(
        self, request: CapabilityRequest, *, required: bool = True
    ) -> CapabilityFulfillmentResult:
        key = (request, required)
        existing = self._results.get(key)
        decision = ReuseDecision.FRESH
        if existing is not None:
            if existing.status is not FulfillmentStatus.FAILED:
                self._call_log.append((existing, ReuseDecision.REUSED))
                return existing
            # A failed attempt is never served from cache, regardless of
            # why: it always gets its own fresh, independently isolated
            # retry rather than propagating one evaluation's failure onto
            # every later evaluation that shares this service.
            del self._results[key]
            decision = self._bypass_decision_for(existing)

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
            except BudgetExhaustedError as exc:
                # SPRINT-013 S13-03A: exc.code distinguishes pair-local
                # (total/burst/retry) refusals from the shared provider
                # rolling-window refusal and an active cooldown -- never
                # collapsed into one generic code.
                error = normalized_provider_error(
                    exc.code,
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
                self._call_log.append((result, decision))
                return result

            if fetch_error.code is ProviderErrorCode.UNSUPPORTED_CAPABILITY:
                continue

        result = CapabilityFulfillmentResult(
            request, FulfillmentStatus.FAILED, None, (), tuple(audit), required
        )
        self._results[key] = result
        self._call_log.append((result, decision))
        return result

    @staticmethod
    def _bypass_decision_for(existing: CapabilityFulfillmentResult) -> ReuseDecision:
        last_error = existing.attempts[-1].error if existing.attempts else None
        if last_error is not None and last_error.code is ProviderErrorCode.STALE_DATA:
            return ReuseDecision.FRESH_AFTER_STALE_BYPASS
        if last_error is not None and last_error.code is ProviderErrorCode.INCOMPLETE_DATA:
            return ReuseDecision.FRESH_AFTER_INCOMPLETE_BYPASS
        return ReuseDecision.FRESH_AFTER_OTHER_BYPASS

    @property
    def call_log(self) -> tuple[tuple[CapabilityFulfillmentResult, ReuseDecision], ...]:
        """One entry per ``fulfill()`` call, in call order -- a caller that
        shares this service across more than one evaluation (SPRINT-013
        S13-03B) can slice this by index to recover exactly which requests
        one specific evaluation triggered and how each resolved, without
        reaching into ``_results``.
        """
        return tuple(self._call_log)

    @property
    def completed_results(self) -> tuple[CapabilityFulfillmentResult, ...]:
        """Return deterministic, immutable evidence from this acquisition run."""
        return tuple(
            self._results[key]
            for key in sorted(
                self._results,
                key=lambda item: (
                    item[0].capability.value,
                    tuple(
                        subject.subject_identity for subject in item[0].subjects
                    ),
                    item[1],
                ),
            )
        )

    @staticmethod
    def _quality_error(
        provider_id: str,
        request: CapabilityRequest,
        observations: tuple[MarketObservation, ...],
    ) -> NormalizedProviderError | None:
        # Resolution compares one canonical value from each provider. Reject
        # competing values from the same provider/subject here so audited
        # fallback can proceed instead of crashing the shared subject seal.
        provider_subjects = tuple(
            (value.provenance.provider_id, value.subject.subject_identity)
            for value in observations
        )
        if (
            request.capability is MarketCapability.EARNINGS_CALENDAR_V1
            and len(provider_subjects) != len(set(provider_subjects))
        ):
            return normalized_provider_error(
                ProviderErrorCode.SCHEMA_MISMATCH,
                "provider returned multiple canonical values for one subject and capability",
                provider_id,
                request.capability,
            )
        usable_freshness = {
            FreshnessStatus.FRESH,
            FreshnessStatus.DELAYED,
            FreshnessStatus.PRIOR_SESSION,
        }
        if any(value.freshness.status not in usable_freshness for value in observations):
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


def observations_from_fulfillment(
    fulfillment: CapabilityFulfillmentService,
) -> tuple[MarketObservation, ...]:
    """Flatten every observation a CapabilityFulfillmentService's own
    completed_results accumulated during a run into one provider-neutral
    tuple (SPRINT-014 S14-PR-05A). Lives here, not strategy_runtime/, because
    fulfillment-to-observation flattening is a market-data/integration
    concern -- strategy_runtime.service.refresh() itself only ever consumes
    the already-flattened provider-neutral tuple this produces (via its own
    ``observations`` callback parameter), never CapabilityFulfillmentService
    directly (Architect checkpoint: thirteenth review, corrective item 1).

    A transitional-legacy caller still driving acquisition through a raw
    CapabilityFulfillmentService (not yet a sealed MarketSnapshot) uses this
    at its own integration/composition-root boundary (asa/scheduled_screening.py,
    asa/api/screening_routes.py) to build that callback. A caller already
    holding a sealed MarketSnapshot passes its own ``.observations`` directly
    instead -- this helper exists only for the fulfillment-service-shaped
    case.
    """
    return tuple(
        observation
        for completed in fulfillment.completed_results
        for observation in completed.observations
    )
