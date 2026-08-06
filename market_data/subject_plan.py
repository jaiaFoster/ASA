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

from market_data.attempts import AcquisitionAttemptRepository, attempt_records_for
from market_data.factory import Clock
from market_data.fulfillment import (
    CapabilityFulfillmentResult,
    CapabilityFulfillmentService,
    FulfillmentStatus,
)
from market_data.providers import CapabilityRequest


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

    @property
    def subject(self) -> str:
        return self._subject

    @property
    def plan_id(self) -> str:
        return self._plan_id

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
        self._attempt_repository.record(records)
