"""Restricted, immutable evidence projection for pure strategy expansion
(SPRINT-014 S14-PR-05A, Architect checkpoint on PR
s14-pr-05a-generic-subject-planning: "strategy expansion currently
receives too much acquisition detail").

ResolvedCapabilityEvidence is deliberately narrower than
``market_data.fulfillment.CapabilityFulfillmentResult``: it carries only
what a pure, provider-blind selection function needs -- a capability's
resolved domain value, its observation identities, a generic freshness
status, and a typed usability verdict -- never a provider id, a raw
provider attempt, a ``CapabilityRequest``, or any transport/budget/
repository/fulfillment type. The generic subject planner (screening/
subject_planning.py) may retain the full ``CapabilityFulfillmentResult``
internally for sealing and diagnostics; only this restricted projection
ever reaches a consumer's own ``expand()`` function.

Lives in domain/ (not screening/ or market_data/) specifically so
strategies/ -- which must never import screening/ or market_data/ -- can
receive and construct against this type directly, with no strategy-named
wrapper module in screening/ standing between the two.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from domain.market_data import FreshnessStatus, MarketCapability, MarketObservationValue
from domain.values import DomainInvariantError


class EvidenceUsability(str, Enum):
    """The one verdict a pure expansion function ever acts on -- never a
    raw ``FulfillmentStatus`` (which exposes acquisition mechanics like
    DEGRADED multi-provider fallback, not evidence usability). A demand
    whose provider fetch technically succeeded but whose evidence fails
    its own declared temporal policy (CapabilityDemand's own
    require_open_session/allow_prior_session/maximum_age_seconds/
    maximum_input_skew_seconds) is projected UNKNOWN here, not RESOLVED.
    """

    RESOLVED = "resolved"
    UNKNOWN = "unknown"


@dataclass(frozen=True, slots=True)
class ResolvedCapabilityEvidence:
    """One demand's restricted, provider-blind resolved evidence.

    ``value`` is required when ``usability`` is RESOLVED and forbidden
    when UNKNOWN -- there is no partial or degraded value a pure
    selection function could meaningfully act on; a demand is either
    usable domain evidence or it is not.
    """

    demand_id: str
    capability: MarketCapability
    usability: EvidenceUsability
    value: MarketObservationValue | None
    observation_ids: tuple[str, ...]
    freshness_status: FreshnessStatus | None

    def __post_init__(self) -> None:
        if not self.demand_id or self.demand_id != self.demand_id.strip():
            raise DomainInvariantError(
                "ResolvedCapabilityEvidence.demand_id must be normalized"
            )
        if self.usability is EvidenceUsability.RESOLVED and self.value is None:
            raise DomainInvariantError(
                "ResolvedCapabilityEvidence.value is required when usability is RESOLVED"
            )
        if self.usability is EvidenceUsability.UNKNOWN and self.value is not None:
            raise DomainInvariantError(
                "ResolvedCapabilityEvidence.value must be absent when usability is UNKNOWN"
            )
        object.__setattr__(self, "observation_ids", tuple(self.observation_ids))
