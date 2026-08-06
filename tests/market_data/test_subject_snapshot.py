"""SPRINT-014 S14-PR-04: subject snapshot sealing tests."""

from __future__ import annotations

from datetime import UTC, datetime

from market_data.attempts import InMemoryAcquisitionAttemptRepository
from market_data.resolution import ResolutionPolicy
from market_data.subject_plan import SubjectAcquisitionPlan
from market_data.subject_snapshot import seal_subject_snapshot
from tests.market_data.test_fulfillment import (
    CAPABILITY,
    Clock,
    FixtureScenario,
    ProviderErrorCode,
    provider,
    request,
    service,
)

NOW = datetime(2026, 7, 21, 16, 0, tzinfo=UTC)


def _sealed_via_plan():
    source = provider("tradier")
    fulfillment, _ = service(source)
    plan = SubjectAcquisitionPlan(
        "AAPL",
        fulfillment,
        attempt_repository=InMemoryAcquisitionAttemptRepository(),
        plan_id="cycle-1:AAPL",
        clock=Clock(NOW),
    )
    result = plan.resolve(request())
    snapshot = seal_subject_snapshot(
        (result,),
        as_of=NOW,
        required_capabilities=(CAPABILITY,),
        resolution_policy_by_capability={
            CAPABILITY: ResolutionPolicy("v1", ("tradier",), 60, ("last",))
        },
        provider_metadata=(source.metadata,),
    )
    return snapshot, result


def test_seals_a_snapshot_from_a_plans_resolved_result() -> None:
    snapshot, result = _sealed_via_plan()
    assert snapshot.requested_capabilities == (CAPABILITY,)
    assert snapshot.completeness.resolved_capabilities == (CAPABILITY,)
    assert snapshot.completeness.unresolved_capabilities == ()
    assert snapshot.observations  # the plan's own successful observation made it in


def test_sealing_the_same_plan_result_twice_is_deterministic() -> None:
    snapshot, result = _sealed_via_plan()
    resealed = seal_subject_snapshot(
        (result,),
        as_of=NOW,
        required_capabilities=(CAPABILITY,),
        resolution_policy_by_capability={
            CAPABILITY: ResolutionPolicy("v1", ("tradier",), 60, ("last",))
        },
        provider_metadata=(provider("tradier").metadata,),
    )
    assert snapshot.snapshot_digest == resealed.snapshot_digest


def test_a_failed_capability_is_unresolved_not_silently_dropped() -> None:
    always_fails = FixtureScenario(failures=((CAPABILITY, ProviderErrorCode.NO_DATA),))
    fulfillment, _ = service(provider("tradier", always_fails))
    plan = SubjectAcquisitionPlan(
        "AAPL",
        fulfillment,
        attempt_repository=InMemoryAcquisitionAttemptRepository(),
        plan_id="cycle-1:AAPL",
        clock=Clock(NOW),
        maximum_attempts_per_request=1,
    )
    result = plan.resolve(request(), required=False)
    assert result.status.value == "failed"

    snapshot = seal_subject_snapshot(
        (result,),
        as_of=NOW,
        required_capabilities=(),
        resolution_policy_by_capability={
            CAPABILITY: ResolutionPolicy("v1", ("tradier",), 60, ("last",))
        },
        provider_metadata=(provider("tradier").metadata,),
    )
    # The failed capability is explicitly accounted for as unresolved --
    # never silently omitted from the sealed snapshot's own completeness.
    assert snapshot.completeness.unresolved_capabilities == (CAPABILITY,)
    assert snapshot.completeness.resolved_capabilities == ()
    assert not snapshot.observations
