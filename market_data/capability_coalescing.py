"""Capability-owned coalescing of multiple observations/results for the
same capability into one (SPRINT-014 S14-PR-05A requirement #4).

A subject demand model may legitimately issue more than one
CapabilityRequest for the same capability -- Earnings Calendar's own
front/back expiration-specific option-chain requests being the motivating
case (Tradier's real option-chain endpoint scopes each request to one
expiration, TRADIER-PATCH-002/#156). seal_subject_snapshot/
MarketSnapshotBuilder (market_data/subject_snapshot.py,
market_data/snapshot.py) require exactly one CapabilityFulfillmentResult
per requested capability, so a generic subject planner needs one
capability-owned place to reduce N results sharing a capability into one
before sealing -- never dropping any of their own provenance in the
process (Architect review finding B7, PR #292 review 4877473757: "the
back fulfillment result is omitted from the fulfillment shell used to
build the snapshot").

``combine_option_chains`` moves here from screening/live_context.py
verbatim (ADR-010: acquisition/normalization belongs to market_data/, not
screening/) -- chain combination is normalization, not strategy policy;
screening/live_context.py now imports it from here.
"""

from __future__ import annotations

import dataclasses
from datetime import datetime

from domain import MarketCapability
from domain.financial import ExpirationCollection, OptionChain, OptionContract
from domain.market_data import (
    MarketDataSubject,
    MarketObservation,
    market_observation_identity,
)
from domain.references import EvidenceKind, EvidenceReference
from domain.values import DomainInvariantError
from market_data.fulfillment import (
    CapabilityFulfillmentResult,
    FulfillmentStatus,
    ProviderFulfillmentAttempt,
)
from market_data.providers import CapabilityRequest


def combine_option_chains(
    chains: tuple[OptionChain, ...], observed_at: datetime
) -> OptionChain:
    """Combine one or more per-expiration OptionChain acquisitions into a
    single OptionChain a strategy manifest can query across all of them
    (TRADIER-PATCH-003).

    OptionChain's own invariant requires every contract to share the
    chain's own observed_at exactly. Contracts from separately-timed
    acquisitions are rebuilt with one canonical observed_at (this
    combination's own caller-supplied timestamp) -- never their raw
    prices, strikes, or greeks -- the same modeling choice as treating
    near-simultaneous per-expiration reads as one logical market-data
    snapshot, not fabricating data.

    Deduplicates by contract identity after normalizing observed_at: a
    provider that (like the offline fixture) doesn't actually scope its
    response to the requested expiration and returns the same contracts
    for both requests would otherwise violate OptionCollection's own
    duplicate-contract invariant on merge.
    """
    if not chains:
        raise ValueError("combine_option_chains requires at least one chain")
    underlying = chains[0].underlying
    for chain in chains[1:]:
        if chain.underlying.identity != underlying.identity:
            raise ValueError("combine_option_chains requires every chain to share one underlying")
    deduplicated: dict[str, OptionContract] = {}
    for chain in chains:
        for contract in chain.contracts:
            normalized = dataclasses.replace(contract, observed_at=observed_at)
            deduplicated[normalized.identity] = normalized
    evidence = tuple(dict.fromkeys(item for chain in chains for item in chain.evidence))
    chain_id = "combined:" + ":".join(chain.option_chain_id for chain in chains)
    return OptionChain(
        chain_id, underlying, observed_at, tuple(deduplicated.values()), evidence
    )


def coalesce_option_chain_results(
    results: tuple[CapabilityFulfillmentResult, ...],
    *,
    subject: MarketDataSubject,
    combined_request: CapabilityRequest,
    observed_at: datetime,
) -> CapabilityFulfillmentResult:
    """Coalesce N OPTION_CHAIN_V1 results (one per expiration-scoped
    request) into one.

    Every source result's own attempts survive unconditionally in the
    combined result's own ``attempts`` -- successful or failed, front or
    back -- so a failed side is never silently dropped (finding B7). When
    at least one side succeeded, the surviving chains are merged via
    combine_option_chains() and wrapped in one new MarketObservation whose
    own evidence references *both* source observations (never just the
    winning side's), and whose observation_id is recomputed from the
    combined value (a MarketObservation's observation_id must always be
    content-derived, domain/market_data.py's own invariant -- reusing a
    source observation's stale id here would violate it). A capability
    with zero successful sides among its results is represented as one
    FAILED result, exactly like an ordinary single-provider failure.
    """
    if not results:
        raise ValueError("coalesce_option_chain_results requires at least one result")
    if any(item.request.capability is not MarketCapability.OPTION_CHAIN_V1 for item in results):
        raise ValueError("coalesce_option_chain_results requires OPTION_CHAIN_V1 results")
    attempts: tuple[ProviderFulfillmentAttempt, ...] = tuple(
        attempt for item in results for attempt in item.attempts
    )
    successful_observations: tuple[MarketObservation, ...] = tuple(
        observation for item in results for observation in item.observations
    )
    if not successful_observations:
        return CapabilityFulfillmentResult(
            combined_request, FulfillmentStatus.FAILED, None, (), attempts, True
        )

    chains: list[OptionChain] = []
    for observation in successful_observations:
        if not isinstance(observation.value, OptionChain):
            raise DomainInvariantError(
                "coalesce_option_chain_results received a nominally successful "
                f"OPTION_CHAIN_V1 observation whose value is {type(observation.value).__name__}, "
                "not OptionChain -- a real defect upstream, never silently dropped"
            )
        chains.append(observation.value)
    combined_chain = combine_option_chains(tuple(chains), observed_at)
    primary = successful_observations[0]
    provider_id = primary.provenance.provider_id
    observation_id = market_observation_identity(
        provider_id,
        MarketCapability.OPTION_CHAIN_V1,
        subject,
        primary.effective_time,
        combined_chain,
        primary.schema_version,
    )
    combined_evidence = tuple(
        dict.fromkeys(
            EvidenceReference(EvidenceKind.OBSERVATION, observation.observation_id)
            for observation in successful_observations
        )
    )
    combined_observation = dataclasses.replace(
        primary,
        subject=subject,
        value=combined_chain,
        observation_id=observation_id,
        provenance=dataclasses.replace(primary.provenance, evidence=combined_evidence),
    )
    # Result-level success, not an observation count comparison -- a
    # single CapabilityFulfillmentResult can in principle carry more than
    # one observation (a DEGRADED multi-provider resolution feeding into
    # this coalescer, for instance), so comparing len(observations) to
    # len(results) would misclassify that case as partial failure even
    # when every source result individually succeeded.
    status = (
        FulfillmentStatus.FULFILLED
        if all(item.status is FulfillmentStatus.FULFILLED for item in results)
        else FulfillmentStatus.DEGRADED
    )
    return CapabilityFulfillmentResult(
        combined_request, status, provider_id, (combined_observation,), attempts, True
    )


def reduce_option_chain_results(
    results: tuple[CapabilityFulfillmentResult, ...],
) -> CapabilityFulfillmentResult:
    """The one OPTION_CHAIN_V1 ``capability_reducer_by_capability`` entry a
    generic subject planner (screening.subject_planning) needs whenever a
    subject's own phase-one/phase-two demands mix expiration discovery
    (``("expirations",)`` -> ExpirationCollection) with per-expiration
    contract acquisition (``("contracts",)`` -> OptionChain) -- Earnings
    Calendar's own SPRINT-014 S14-PR-05A shape, expressed generically here:
    this function never branches on a strategy identity, only on request
    shape.

    Matches ``screening.subject_planning.CapabilityResultReducer``'s exact
    one-argument signature directly, so a caller registers it with no
    adapter wrapper needed.

    Expiration-discovery results are supporting evidence only: every one
    of their own raw attempts -- successful or failed -- survives
    unconditionally into the returned result's own ``attempts`` (so
    MarketSnapshotBuilder's union of ``fulfillment.observations`` and
    every raw per-attempt observation still retains the
    ExpirationCollection in the sealed snapshot), but discovery
    observations never feed ``combine_option_chains()`` -- only contract
    results do, via the unmodified ``coalesce_option_chain_results()``.
    The selected/coalesced observation used for OPTION_CHAIN_V1
    resolution is always the combined OptionChain, never the
    ExpirationCollection.

    A lone expiration-discovery result with no contract results at all
    (Earnings Calendar's own "expansion found no valid pair" outcome,
    phase two never issuing chain demands) seals as its own unmodified
    ExpirationCollection result -- there is nothing to combine it with.

    Raises DomainInvariantError for a request whose ``required_fields``
    is neither ``("expirations",)`` nor ``("contracts",)``, or whose
    nominally successful observation's value does not match what that
    shape demands -- an unexpected demand/value combination is a real
    defect, never silently ignored.
    """
    if not results:
        raise ValueError("reduce_option_chain_results requires at least one result")
    if any(item.request.capability is not MarketCapability.OPTION_CHAIN_V1 for item in results):
        raise ValueError("reduce_option_chain_results requires OPTION_CHAIN_V1 results")

    discovery_results: list[CapabilityFulfillmentResult] = []
    contract_results: list[CapabilityFulfillmentResult] = []
    for item in results:
        fields = item.request.required_fields
        if fields == ("expirations",):
            for observation in item.observations:
                if not isinstance(observation.value, ExpirationCollection):
                    raise DomainInvariantError(
                        "reduce_option_chain_results received a nominally successful "
                        "('expirations',) OPTION_CHAIN_V1 observation whose value is "
                        f"{type(observation.value).__name__}, not ExpirationCollection"
                    )
            discovery_results.append(item)
        elif fields == ("contracts",):
            contract_results.append(item)
        else:
            raise DomainInvariantError(
                "reduce_option_chain_results received an OPTION_CHAIN_V1 request with "
                f"unexpected required_fields {fields!r} -- neither ('expirations',) nor "
                "('contracts',)"
            )

    discovery_attempts: tuple[ProviderFulfillmentAttempt, ...] = tuple(
        attempt for item in discovery_results for attempt in item.attempts
    )

    if not contract_results:
        if len(discovery_results) != 1:
            raise DomainInvariantError(
                "reduce_option_chain_results received no ('contracts',) results and "
                f"{len(discovery_results)} ('expirations',) results -- no reduction is "
                "defined for that shape"
            )
        return discovery_results[0]

    # A combined, expiration-unscoped subject/request for the merged
    # chain -- reusing one contract result's own subject/window (both
    # front and back already share one underlying and semantic window,
    # coalesce_option_chain_results' own invariant), but stripping the
    # expiration-specific address projection so the combined observation
    # never falsely claims one specific expiration.
    front_request = contract_results[0].request
    front_subject = front_request.subjects[0]
    combined_projections = tuple(
        projection
        for projection in front_subject.request_context.provider_address_projections
        if projection.address_type != "expiration"
    )
    combined_context = dataclasses.replace(
        front_subject.request_context,
        required_fields=("contracts",),
        provider_address_projections=combined_projections,
    )
    combined_subject = dataclasses.replace(front_subject, request_context=combined_context)
    combined_request = CapabilityRequest(
        MarketCapability.OPTION_CHAIN_V1,
        (combined_subject,),
        front_request.effective_start,
        front_request.effective_end,
        ("contracts",),
        front_request.maximum_age_seconds,
    )
    combined = coalesce_option_chain_results(
        tuple(contract_results),
        subject=combined_subject,
        combined_request=combined_request,
        observed_at=front_request.effective_end,
    )
    return dataclasses.replace(combined, attempts=combined.attempts + discovery_attempts)
