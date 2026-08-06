"""Generic phased subject planning (SPRINT-014 S14-PR-05A).

Replaces the strategy-specific acquisition orchestrator PR #292 built for
its one migrated strategy (reverted -- Architect review finding B1, PR
#292 review 4877473757: "the approved architecture says screening plans
generically and never owns strategy-specific acquisition"). This module
owns exactly one generic execution shape and nothing else:

    collect consumer declarations
    -> union phase-one CapabilityDemand values
    -> resolve through one SubjectAcquisitionPlan
    -> expose immutable resolved evidence
    -> invoke pure consumer expansion functions
    -> union phase-two CapabilityDemand values
    -> resolve through the same plan
    -> seal one subject snapshot
    -> return immutable subject evidence

It must never import any strategy's manifest, requirement type, fact ID,
or selection function; never branch on a strategy/consumer identity;
never construct DTE policy, richness formulas, score inputs, or verdicts;
never give an expansion function access to the plan, fulfiller, provider
metadata, transport, budget, or repository; and never create more than
one plan per subject per cycle (the caller supplies exactly one, already
built, and this module only ever calls ``.resolve()`` on it).

Every strategy's own pure demand-declaration/expansion policy lives in
strategies/ and is registered here only as an opaque
``SubjectPlanConsumer`` -- this module never sees any strategy's own
manifest, DTE policy, or scoring formula.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import datetime
from types import MappingProxyType

from domain import CapabilityDemand, DemandExpansion, EvidenceUsability, MarketCapability
from domain.resolved_evidence import ResolvedCapabilityEvidence
from market_data.fulfillment import CapabilityFulfillmentResult
from market_data.providers import CapabilityRequest, ProviderMetadata
from market_data.resolution import ResolutionPolicy
from market_data.session_calendar import MarketSessionStatus, UsEquitySessionCalendar
from market_data.snapshot import MarketSnapshot
from market_data.subject_plan import SubjectAcquisitionPlan
from market_data.subject_snapshot import seal_subject_snapshot
from market_data.temporal import FreshnessRequirement, UsabilityStatus, evaluate_temporal_usability
from screening.live_context import build_capability_subject

# Read-only view over every demand this cycle has resolved so far --
# domain.ResolvedCapabilityEvidence only, never the raw
# CapabilityFulfillmentResult, the plan, a fulfiller, provider metadata,
# transport, budget, or repository. Keyed by CapabilityDemand.demand_id,
# never by consumer. This is deliberately narrower than what the planner
# retains internally (see RawResolvedEvidence/SubjectPlanResult.
# resolved_evidence below) -- a pure expansion function receives only this
# restricted projection.
ResolvedEvidenceView = Mapping[str, ResolvedCapabilityEvidence]

# The planner's own internal, full-fidelity view -- raw
# CapabilityFulfillmentResult, retained for sealing and for
# SubjectPlanResult's own diagnostics (e.g. a composition root's request/
# attempt accounting). Never handed to a consumer's expand() function.
RawResolvedEvidence = Mapping[str, CapabilityFulfillmentResult]

# A pure function: given phase-one's resolved, restricted evidence, return
# whatever additional exact demands, selection outputs, and/or typed
# UNKNOWN reasons this consumer's own policy determines. Registered here
# already bound to its own strategy-specific, manifest-derived requirement
# (e.g. via functools.partial over a strategies/-owned expansion function
# and its own typed requirement object) by the caller -- this module never
# sees that binding's own inputs. Returns domain.DemandExpansion, never a
# screening-owned type, so a strategies/-owned function can satisfy this
# signature without importing screening/ at all.
DemandExpansionFunction = Callable[[ResolvedEvidenceView], DemandExpansion]

# Reduces N CapabilityFulfillmentResults sharing one capability (e.g.
# Earnings Calendar's own front/back expiration-scoped option-chain
# demands) into the single result seal_subject_snapshot requires per
# capability. Capability-owned, never consumer-owned (market_data.
# capability_coalescing.coalesce_option_chain_results, adapted to this
# shape by the caller, is the one real implementation so far) -- this
# module only ever dispatches to whatever reducer the caller registered
# for a given capability; it builds none of the reduction logic itself.
CapabilityResultReducer = Callable[
    [tuple[CapabilityFulfillmentResult, ...]], CapabilityFulfillmentResult
]


@dataclass(frozen=True, slots=True)
class SubjectPlanConsumer:
    """One phased-planning participant, collected before phase one ever
    executes. ``consumer_id`` is opaque: carried only for provenance (see
    SubjectPlanResult.demand_ids_by_consumer), never branched on by this
    module's own control flow -- the exact same code path runs for every
    consumer, real or synthetic/test.
    """

    consumer_id: str
    bootstrap_demands: tuple[CapabilityDemand, ...]
    expand: DemandExpansionFunction

    def __post_init__(self) -> None:
        if not self.consumer_id or self.consumer_id != self.consumer_id.strip():
            raise ValueError("SubjectPlanConsumer.consumer_id must be normalized")


@dataclass(frozen=True, slots=True)
class SubjectPlanResult:
    """Immutable subject evidence: a sealed snapshot plus enough
    provenance to prove which demands, and therefore which consumers,
    contributed to it -- never a strategy verdict, never fact-projection
    output (that stays consumer-owned, applied by the caller against
    ``snapshot``/``resolved_evidence`` after this function returns).
    """

    snapshot: MarketSnapshot
    resolved_evidence: RawResolvedEvidence
    expansions_by_consumer: Mapping[str, DemandExpansion]
    demand_ids_by_consumer: Mapping[str, tuple[str, ...]]


def _to_capability_request(
    symbol: str, demand: CapabilityDemand, *, now: datetime
) -> CapabilityRequest:
    subject = build_capability_subject(
        symbol,
        demand.capability,
        now,
        effective_start=demand.effective_start,
        effective_end=demand.effective_end,
        required_fields=demand.required_fields,
        expiration=demand.expiration,
    )
    maximum_age_seconds = (
        demand.maximum_age_seconds if demand.maximum_age_seconds is not None else 3600
    )
    return CapabilityRequest(
        demand.capability,
        (subject,),
        demand.effective_start,
        demand.effective_end,
        demand.required_fields,
        maximum_age_seconds,
    )


def _project(
    demand_id: str,
    demand: CapabilityDemand,
    result: CapabilityFulfillmentResult,
    *,
    now: datetime,
    market_is_open: bool,
) -> ResolvedCapabilityEvidence:
    """Build the one restricted, provider-blind view a consumer's own
    expansion function ever receives for one demand -- and the one place
    a demand's own declared temporal policy (require_open_session/
    allow_prior_session/maximum_age_seconds/maximum_input_skew_seconds)
    is actually applied. A demand whose provider fetch technically
    succeeded but whose evidence fails this check is projected UNKNOWN
    here, never RESOLVED (Architect checkpoint: "before production use,
    the generic planner must apply the declared temporal policy").

    Each individual demand's own CapabilityFulfillmentResult carries at
    most one observation at this point in the flow (CapabilityFulfillment
    Service.fulfill() itself returns on the first successful provider
    attempt; capability-owned coalescing into a multi-source combined
    observation, market_data.capability_coalescing, only ever happens
    later, at sealing time) -- so this function never needs to reconcile
    more than one.
    """
    if not result.observations:
        return ResolvedCapabilityEvidence(
            demand_id, demand.capability, EvidenceUsability.UNKNOWN, None, (), None
        )
    observation = result.observations[0]
    requirement = FreshnessRequirement(
        require_open_session=demand.require_open_session,
        allow_prior_session=demand.allow_prior_session,
        maximum_age_seconds=demand.maximum_age_seconds,
        maximum_input_skew_seconds=demand.maximum_input_skew_seconds,
    )
    decision = evaluate_temporal_usability(
        observation.freshness, requirement, market_is_open=market_is_open
    )
    if decision.status is UsabilityStatus.REJECTED:
        return ResolvedCapabilityEvidence(
            demand_id,
            demand.capability,
            EvidenceUsability.UNKNOWN,
            None,
            (),
            observation.freshness.status,
        )
    return ResolvedCapabilityEvidence(
        demand_id,
        demand.capability,
        EvidenceUsability.RESOLVED,
        observation.value,
        (observation.observation_id,),
        observation.freshness.status,
    )


def _resolve_new_demands(
    plan: SubjectAcquisitionPlan,
    symbol: str,
    now: datetime,
    demand_by_id: dict[str, CapabilityDemand],
    resolved: dict[str, CapabilityFulfillmentResult],
) -> None:
    # Sorted by demand_id so the underlying plan's own call sequence is
    # deterministic regardless of consumer registration order (invariant:
    # expansion/consumer order never changes phase-two demand identity or
    # call count).
    for demand_id in sorted(demand_by_id):
        if demand_id in resolved:
            continue
        demand = demand_by_id[demand_id]
        request = _to_capability_request(symbol, demand, now=now)
        resolved[demand_id] = plan.resolve(request, required=demand.required)


def _seal(
    demand_by_id: dict[str, CapabilityDemand],
    resolved: dict[str, CapabilityFulfillmentResult],
    *,
    now: datetime,
    resolution_policy_by_capability: dict[MarketCapability, ResolutionPolicy],
    provider_metadata: tuple[ProviderMetadata, ...],
    capability_reducer_by_capability: Mapping[MarketCapability, CapabilityResultReducer],
) -> MarketSnapshot:
    results_by_capability: dict[MarketCapability, list[CapabilityFulfillmentResult]] = (
        defaultdict(list)
    )
    for demand_id, result in resolved.items():
        results_by_capability[demand_by_id[demand_id].capability].append(result)

    sealed_results: list[CapabilityFulfillmentResult] = []
    for capability, results in results_by_capability.items():
        if len(results) == 1:
            sealed_results.append(results[0])
            continue
        reducer = capability_reducer_by_capability.get(capability)
        if reducer is None:
            raise ValueError(
                f"{len(results)} demands resolved to {capability.value}, which requires "
                "exactly one sealed result -- no capability_reducer_by_capability entry "
                "was registered to coalesce them"
            )
        sealed_results.append(reducer(tuple(results)))

    required_capabilities = tuple(
        sorted(
            {
                demand.capability
                for demand_id, demand in demand_by_id.items()
                if demand.required
            },
            key=lambda item: item.value,
        )
    )
    return seal_subject_snapshot(
        tuple(sealed_results),
        as_of=now,
        required_capabilities=required_capabilities,
        resolution_policy_by_capability=resolution_policy_by_capability,
        provider_metadata=provider_metadata,
    )


def run_subject_plan(
    plan: SubjectAcquisitionPlan,
    now: datetime,
    consumers: tuple[SubjectPlanConsumer, ...],
    *,
    provider_metadata: tuple[ProviderMetadata, ...],
    resolution_policy_by_capability: dict[MarketCapability, ResolutionPolicy],
    capability_reducer_by_capability: Mapping[MarketCapability, CapabilityResultReducer]
    | None = None,
) -> SubjectPlanResult:
    """Run one subject's generic phased plan against every registered
    consumer. ``consumers`` must be the complete, final set -- every
    consumer is collected before phase one executes; there is no
    mechanism to register one later, mid-run.

    Never raises for a capability a consumer's own pure logic declares
    (required or not) that a provider ultimately cannot fulfill -- that is
    an ordinary FAILED CapabilityFulfillmentResult, already-typed data a
    caller reads out of ``resolved_evidence``/``snapshot.completeness``.
    Does raise, and lets propagate unmodified, whatever
    SubjectAcquisitionPlan.resolve() or seal_subject_snapshot() itself
    raises for a genuine persistence, domain-invariant, or configuration
    failure -- this function performs no exception handling of its own,
    so a real defect is never silently downgraded into missing evidence
    (Architect review finding B4).
    """
    if not consumers:
        raise ValueError("run_subject_plan requires at least one consumer")
    consumer_ids = [consumer.consumer_id for consumer in consumers]
    if len(consumer_ids) != len(set(consumer_ids)):
        raise ValueError("run_subject_plan requires unique consumer_id values")
    reducers = capability_reducer_by_capability or {}

    symbol = plan.subject
    demand_by_id: dict[str, CapabilityDemand] = {}
    demand_ids_by_consumer: dict[str, list[str]] = {
        consumer.consumer_id: [] for consumer in consumers
    }

    # Phase 1: union every consumer's own bootstrap demands; resolve once.
    for consumer in consumers:
        for demand in consumer.bootstrap_demands:
            demand_by_id.setdefault(demand.demand_id, demand)
            demand_ids_by_consumer[consumer.consumer_id].append(demand.demand_id)
    resolved: dict[str, CapabilityFulfillmentResult] = {}
    _resolve_new_demands(plan, symbol, now, demand_by_id, resolved)

    # Phase 2: each consumer's own pure expansion over the immutable,
    # provider-neutral, temporal-policy-applied phase-one evidence; union
    # again, resolve only what phase one has not already resolved.
    market_is_open = UsEquitySessionCalendar().status_at(now) is MarketSessionStatus.OPEN
    read_only_evidence: ResolvedEvidenceView = MappingProxyType(
        {
            demand_id: _project(
                demand_id, demand_by_id[demand_id], result, now=now, market_is_open=market_is_open
            )
            for demand_id, result in resolved.items()
        }
    )
    expansions_by_consumer: dict[str, DemandExpansion] = {}
    for consumer in consumers:
        expansion = consumer.expand(read_only_evidence)
        expansions_by_consumer[consumer.consumer_id] = expansion
        for demand in expansion.demands:
            demand_by_id.setdefault(demand.demand_id, demand)
            demand_ids_by_consumer[consumer.consumer_id].append(demand.demand_id)
    _resolve_new_demands(plan, symbol, now, demand_by_id, resolved)

    snapshot = _seal(
        demand_by_id,
        resolved,
        now=now,
        resolution_policy_by_capability=resolution_policy_by_capability,
        provider_metadata=provider_metadata,
        capability_reducer_by_capability=reducers,
    )

    return SubjectPlanResult(
        snapshot=snapshot,
        resolved_evidence=MappingProxyType(dict(resolved)),
        expansions_by_consumer=MappingProxyType(expansions_by_consumer),
        demand_ids_by_consumer=MappingProxyType(
            {key: tuple(value) for key, value in demand_ids_by_consumer.items()}
        ),
    )
