"""Seal a subject's resolved acquisition into a MarketSnapshot (SPRINT-014
S14-PR-04).

Wires two already-existing, already-frozen ASA-ARCH-007 primitives together
-- ObservationResolver (market_data/resolution.py) and MarketSnapshotBuilder
(market_data/snapshot.py) -- over a SubjectAcquisitionPlan's own resolved
CapabilityFulfillmentResults (market_data/subject_plan.py, SPRINT-014
S14-PR-03). Neither primitive is modified, extended, or reimplemented here;
this module only supplies the missing composition step between "a subject's
plan finished resolving its capabilities" and "here is one sealed,
content-addressed snapshot of that subject's evidence."
"""

from __future__ import annotations

from datetime import datetime

from domain import MarketCapability
from market_data.budget import RequestAccountingEntry
from market_data.fulfillment import CapabilityFulfillmentResult
from market_data.providers import ProviderMetadata
from market_data.resolution import ObservationResolver, ResolutionPolicy, ResolutionResult
from market_data.snapshot import (
    MarketSnapshot,
    MarketSnapshotBuilder,
    SnapshotRequest,
    SnapshotValidationMetadata,
)


def seal_subject_snapshot(
    results: tuple[CapabilityFulfillmentResult, ...],
    *,
    as_of: datetime,
    required_capabilities: tuple[MarketCapability, ...],
    resolution_policy_by_capability: dict[MarketCapability, ResolutionPolicy],
    provider_metadata: tuple[ProviderMetadata, ...],
    request_accounting: tuple[RequestAccountingEntry, ...] = (),
    validation_metadata: tuple[SnapshotValidationMetadata, ...] = (),
) -> MarketSnapshot:
    """Seal one subject's resolved capability results into a MarketSnapshot.

    ``results`` is normally a subject's own SubjectAcquisitionPlan.resolve()
    outputs, one per requested capability -- this function does not call
    the plan itself, it only consumes what the plan already resolved, so
    a caller decides exactly when in a cycle a subject's evidence is
    considered final and worth sealing.

    A capability whose fulfillment FAILED contributes no observations to
    resolve and is correctly reflected in the sealed snapshot's own
    ``completeness.unresolved_capabilities`` -- MarketSnapshotBuilder
    already enforces this; this function performs no completeness logic
    of its own.
    """
    resolutions: list[ResolutionResult] = []
    for result in results:
        capability = result.request.capability
        observations = tuple(
            observation
            for attempt in result.attempts
            for observation in attempt.observations
        )
        if not observations:
            continue
        policy = resolution_policy_by_capability[capability]
        resolutions.append(ObservationResolver().resolve(observations, policy, as_of=as_of))

    requested = tuple(result.request.capability for result in results)
    snapshot_request = SnapshotRequest(
        as_of=as_of,
        requested_capabilities=requested,
        required_capabilities=required_capabilities,
    )
    # MarketSnapshotBuilder requires exactly one fulfillment per requested
    # capability, success or failure alike -- a FAILED result contributes
    # zero observations above but must still be present here so the
    # snapshot's own completeness accounting sees it as a genuine,
    # attempted, unresolved capability rather than one silently omitted.
    return MarketSnapshotBuilder().build(
        snapshot_request,
        results,
        tuple(resolutions),
        provider_metadata,
        validation_metadata,
        request_accounting,
    )
