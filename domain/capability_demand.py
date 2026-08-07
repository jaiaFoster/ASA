"""Generic subject-demand contract (SPRINT-014 S14-PR-05A).

CapabilityDemand is the one vocabulary a generic subject planner
(screening/subject_planning.py) operates over: "one consumer wants this
capability, over this window, with this freshness requirement, required or
optional, optionally scoped to one expiration." It carries no strategy
identity and no strategy-specific policy -- Earnings Calendar's own
front_min_dte/back_max_dte/target_gap_days/gap_tolerance_days
(strategies/requirements.py's EarningsCalendarExpirationPolicy) are applied
by strategy-owned pure selection code *before* a CapabilityDemand is ever
constructed, never encoded into this type (S14-PR-05A Architect review,
finding B1).

Lives in domain/, not market_data/, so strategies/ (which must construct
CapabilityDemand instances to express its own pure-selection output, per
the Architect's own "the pure Earnings expansion function ... may return
additional exact demands") never needs a new dependency on market_data/ --
domain/ already sits below every layer in this codebase, and every layer
already depends on it. Freshness fields mirror
market_data.temporal.FreshnessRequirement's own shape by value (not by
importing the type, which would create a domain -> market_data edge that
does not otherwise exist); market_data/screening code reconstructs a real
FreshnessRequirement from these fields only where evaluate_temporal_
usability() itself is actually called.

Deliberately excludes ``maximum_input_skew_seconds`` (S14-PR-05A Architect
checkpoint on PR s14-pr-05a-generic-subject-planning, second review): the
field existed on both this type and market_data.temporal.
FreshnessRequirement but had no actual enforcement anywhere -- an
identity-bearing policy field with no behavioral effect, which the
Architect's own review explicitly rejected keeping ("do not retain an
identity-bearing policy field that has no behavioral effect"). Multi-
input-skew semantics (comparing effective times *across* more than one
observation feeding one decision) has no real owner yet; re-add this only
alongside that owner, not before.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import UTC, date, datetime

from domain.market_data import MarketCapability
from domain.values import DomainInvariantError, require_tz_aware

CAPABILITY_DEMAND_CONTRACT_VERSION = "asa.capability_demand.v2"


@dataclass(frozen=True, slots=True)
class CapabilityDemand:
    """One consumer's declarative request for one capability.

    ``required`` distinguishes a demand a plan must satisfy (or record as
    exhausted) from one that is merely attempted; ``expiration`` is the one
    optional subject constraint a generic planner understands (an option-
    chain request scoped to a single expiration date) -- anything more
    specific than that belongs to strategy-owned policy, not this type.
    """

    capability: MarketCapability
    required_fields: tuple[str, ...]
    effective_start: datetime
    effective_end: datetime
    required: bool = True
    expiration: date | None = None
    require_open_session: bool = False
    allow_prior_session: bool = True
    maximum_age_seconds: int | None = None

    def __post_init__(self) -> None:
        require_tz_aware(self.effective_start, "CapabilityDemand", "effective_start")
        require_tz_aware(self.effective_end, "CapabilityDemand", "effective_end")
        if self.effective_start > self.effective_end:
            raise DomainInvariantError("CapabilityDemand time window is inverted")
        required_fields = tuple(sorted(set(self.required_fields)))
        if not required_fields or any(
            not value or value != value.strip() for value in required_fields
        ):
            raise DomainInvariantError("CapabilityDemand requires normalized required_fields")
        object.__setattr__(self, "required_fields", required_fields)
        if self.maximum_age_seconds is not None and (
            type(self.maximum_age_seconds) is not int or self.maximum_age_seconds < 0
        ):
            raise DomainInvariantError("CapabilityDemand.maximum_age_seconds must be non-negative")

    @property
    def demand_id(self) -> str:
        """Stable identity derived from the complete request -- never from
        which consumer asked for it. Two consumers issuing an identical
        demand always resolve to the same identity, which is exactly the
        property the generic planner's own demand-union step relies on to
        deduplicate before ever calling SubjectAcquisitionPlan.resolve().
        """
        payload = {
            "namespace": "asa.capability_demand",
            "version": CAPABILITY_DEMAND_CONTRACT_VERSION,
            "capability": self.capability.value,
            "required_fields": list(self.required_fields),
            "effective_start": self.effective_start.astimezone(UTC).isoformat(),
            "effective_end": self.effective_end.astimezone(UTC).isoformat(),
            "required": self.required,
            "expiration": self.expiration.isoformat() if self.expiration else None,
            "require_open_session": self.require_open_session,
            "allow_prior_session": self.allow_prior_session,
            "maximum_age_seconds": self.maximum_age_seconds,
        }
        encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
        return hashlib.sha256(encoded).hexdigest()
