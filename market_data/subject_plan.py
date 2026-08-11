"""Two-phase subject-first acquisition planning (SPRINT-014 S14-PR-03).

Confirmed root cause (S14-PR-01, project/reports/SPRINT-014-S14-PR-01-root-cause.md):
market_data/fulfillment.py's CapabilityFulfillmentService deliberately never
reuses a cached *failed* result -- correct for isolating one strategy
evaluation's transient failure from another's, but it means there is no
durable, shared "this datum is UNKNOWN for this cycle" fact two consumers of
the same subject can share; each pays its own full provider round-trip for
an identical failure.

SubjectAcquisitionPlan is the missing layer: one plan per subject per cycle,
sitting above CapabilityFulfillmentService (never replacing or modifying
it). ``resolve()`` is idempotent for the plan's own lifetime -- the first
call for a given CapabilityRequest executes it (with one bounded plan-owned
retry on failure); every later call for the exact same request, whether
from the same or a different consumer, in any order, returns that same
fixed result with zero additional provider calls, success or failure alike.
This is the "durable shared failure history" S14-PR-01 found missing.

Two-phase acquisition is a *usage pattern* over this one primitive, not two
separate APIs: a caller resolves whatever bootstrap evidence a subject's own
strategy-owned selection logic needs (e.g. Earnings Calendar's earnings date
and available expirations) first, uses that evidence with an existing pure
selection function to decide the rest of its demand (no provider access
required for that decision -- ADR-010's own "strategies never gather
provider data" already holds for these selection functions), then resolves
the remaining union of capability requests through the same plan instance.

Every attempt (success and failure) is persisted through the existing
S13-02 durable attempt-record contract (market_data/attempts.py) -- reused
exactly as-is, never duplicated, per this sprint's own "no parallel
persistence system" rule. A SubjectAcquisitionPlan supplies its own
identity string (``plan_id``) as the attempt records' scoping identity;
callers are responsible for constructing a deterministic one (mirroring how
CapabilityFulfillmentService itself never owns cycle identity either).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Protocol

from market_data.attempts import AcquisitionAttemptRepository, attempt_records_for
from market_data.factory import Clock
from market_data.fulfillment import (
    CapabilityFulfillmentResult,
    CapabilityFulfillmentService,
    FulfillmentStatus,
)
from market_data.providers import CapabilityRequest

_LOGGER = logging.getLogger(__name__)


class SubjectAcquisitionPlan:
    """One subject's acquisition plan for one cycle.

    Not itself a Clock or a cache eviction policy -- it wraps an existing,
    already-constructed CapabilityFulfillmentService (which continues to
    own provider selection, fallback, and per-call de-duplication exactly
    as before) and adds the one property that service intentionally does
    not provide: a failed resolution, once the plan's own bounded retry is
    exhausted, stays fixed and shared for the rest of the plan's lifetime.
    """

    __slots__ = (
        "_subject",
        "_fulfillment",
        "_attempt_repository",
        "_plan_id",
        "_clock",
        "_maximum_attempts_per_request",
        "_resolved",
        "_sequence_offset",
        "_attempt_recording_degraded",
    )

    def __init__(
        self,
        subject: str,
        fulfillment: CapabilityFulfillmentService,
        *,
        attempt_repository: AcquisitionAttemptRepository,
        plan_id: str,
        clock: Clock,
        maximum_attempts_per_request: int = 2,
    ) -> None:
        if not subject or subject != subject.strip():
            raise ValueError("SubjectAcquisitionPlan.subject must be normalized")
        if not plan_id or plan_id != plan_id.strip():
            raise ValueError("SubjectAcquisitionPlan.plan_id must be normalized")
        if maximum_attempts_per_request < 1:
            raise ValueError(
                "SubjectAcquisitionPlan.maximum_attempts_per_request must be at least 1"
            )
        self._subject = subject
        self._fulfillment = fulfillment
        self._attempt_repository = attempt_repository
        self._plan_id = plan_id
        self._clock = clock
        self._maximum_attempts_per_request = maximum_attempts_per_request
        self._resolved: dict[tuple[CapabilityRequest, bool], CapabilityFulfillmentResult] = {}
        self._sequence_offset = 0
        self._attempt_recording_degraded = False

    @property
    def subject(self) -> str:
        return self._subject

    @property
    def plan_id(self) -> str:
        return self._plan_id

    @property
    def attempt_recording_degraded(self) -> bool:
        """True if any attempt-repository persistence call failed during
        this plan's own lifetime so far (SPRINT-014 S14-PR-05A, production-
        root wiring). This plan is now the single durable attempt owner
        for every consumer sharing it -- resolve() itself never raises an
        attempt-repository failure, so it also owns the resilience
        guarantee a caller's own now-retired per-pair recording block used
        to provide: a persistence outage for the attempt side-channel must
        never abort or corrupt a strategy evaluation sharing this plan
        (SPRINT-013 S13-02). Callers use this subject-scoped flag as their
        own "were this cycle's attempts durably recorded" signal instead.
        """
        return self._attempt_recording_degraded

    def resolve(
        self, request: CapabilityRequest, *, required: bool = True
    ) -> CapabilityFulfillmentResult:
        """Resolve one capability request as part of this subject's plan.

        Deterministic and idempotent within the plan's own lifetime: the
        same ``request`` resolved more than once -- by the same consumer
        twice, or by two different consumers, in any order -- executes at
        most ``maximum_attempts_per_request`` provider round trips in
        total, never once per consumer. Every attempt made is persisted,
        including a failed one, before this method returns.
        """
        key = (request, required)
        existing = self._resolved.get(key)
        if existing is not None:
            return existing
        result = self._fulfillment.fulfill(request, required=required)
        self._record_attempts(result)
        attempts_made = 1
        while (
            result.status is FulfillmentStatus.FAILED
            and attempts_made < self._maximum_attempts_per_request
        ):
            result = self._fulfillment.fulfill(request, required=required)
            self._record_attempts(result)
            attempts_made += 1
        self._resolved[key] = result
        return result

    def _record_attempts(self, result: CapabilityFulfillmentResult) -> None:
        records = attempt_records_for(
            result,
            screening_cycle_id=self._plan_id,
            pair_evaluation_id=self._plan_id,
            recorded_at=self._clock.now(),
            sequence_offset=self._sequence_offset,
        )
        self._sequence_offset += len(records)
        try:
            self._attempt_repository.record(records)
        except Exception:
            # Best-effort, exactly like the per-pair recording block this
            # plan now replaces as the single durable attempt owner: never
            # let an attempt-persistence outage abort or corrupt the
            # strategy evaluation that triggered this resolve() call
            # (SPRINT-013 S13-02). attempt_recording_degraded lets a
            # caller still report this honestly instead of silently.
            self._attempt_recording_degraded = True
            _LOGGER.warning(
                "subject_acquisition_plan_attempt_recording_failed",
                extra={"plan_id": self._plan_id, "subject": self._subject},
                exc_info=True,
            )


class CapabilityFulfiller(Protocol):
    """The one method every already-existing, unmodified acquisition
    function in this codebase actually calls on whatever it is given
    (screening/live_context.py's acquire_capability,
    screening/live_adapters.py's _acquire_or_raise, and everything built
    on them) -- CapabilityFulfillmentService already satisfies this
    structurally; formalized as a Protocol here (SPRINT-014 S14-PR-05A) so
    PlanBackedFulfillment below can be passed to the same call sites
    without changing any of them.
    """

    def fulfill(
        self, request: CapabilityRequest, *, required: bool = True
    ) -> CapabilityFulfillmentResult: ...


@dataclass(frozen=True, slots=True)
class PlanBackedFulfillment:
    """Adapts SubjectAcquisitionPlan.resolve() to CapabilityFulfillmentService's
    own fulfill() interface (SPRINT-014 S14-PR-05A, Architect review
    finding B3, PR #292 review 4877473757: "one exhausted request shared
    across migrated and legacy same-subject consumers").

    Forward Factor and Skew Momentum's own acquisition (screening/
    live_adapters.py's build_live_forward_factor_adapter/
    build_live_skew_momentum_adapter, unmodified) call ``.fulfill()``
    directly on whatever CapabilityFulfiller they are given. Wrapping one
    subject's own SubjectAcquisitionPlan in this class and passing the
    wrapper instead of the subject's raw CapabilityFulfillmentService
    means every one of those unmodified calls transparently routes
    through the same plan Earnings Calendar's own generic subject
    planning (screening/subject_planning.py) already uses for that
    subject this cycle -- so a capability request either strategy makes
    is resolved once, shared, and exhausted-or-successful for every
    consumer, migrated or legacy, regardless of which one asks first.

    Introduces no new persistence or identity authority of its own: every
    call is a pure pass-through to the wrapped plan's own resolve(), which
    already owns idempotency and durable attempt persistence (S14-PR-03).
    Never carried on RuntimeContext (I-09) -- only closed over by the
    legacy composition binding at registry-construction time, exactly like
    the raw CapabilityFulfillmentService it replaces.
    """

    plan: SubjectAcquisitionPlan

    def fulfill(
        self, request: CapabilityRequest, *, required: bool = True
    ) -> CapabilityFulfillmentResult:
        return self.plan.resolve(request, required=required)
