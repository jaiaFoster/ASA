"""Provider-neutral two-phase SPX demands for SCS."""

from datetime import date, datetime
from typing import Mapping  # noqa: UP035

from domain import (
    CapabilityDemand,
    DemandExpansion,
    EvidenceUsability,
    ExpirationCollection,
    MarketCapability,
    ResolvedCapabilityEvidence,
    UnknownReason,
)


def quote_demand(now: datetime) -> CapabilityDemand:
    return CapabilityDemand(MarketCapability.REAL_TIME_QUOTE_V1, ("last",), now, now)


def expirations_demand(now: datetime) -> CapabilityDemand:
    return CapabilityDemand(MarketCapability.OPTION_CHAIN_V1, ("expirations",), now, now)


def chain_demand(now: datetime, expiration: date) -> CapabilityDemand:
    return CapabilityDemand(
        MarketCapability.OPTION_CHAIN_V1, ("contracts",), now, now, expiration=expiration
    )


def bootstrap_demands(now: datetime) -> tuple[CapabilityDemand, ...]:
    return quote_demand(now), expirations_demand(now)


def expand_demands(
    evidence: Mapping[str, ResolvedCapabilityEvidence], *, now: datetime
) -> DemandExpansion:
    resolved = evidence.get(expirations_demand(now).demand_id)
    if (
        resolved is None
        or resolved.usability is not EvidenceUsability.RESOLVED
        or not isinstance(resolved.value, ExpirationCollection)
    ):
        return DemandExpansion(unknown_reasons=(UnknownReason("G_SCS_EXPIRY_UNIQUE_UNKNOWN"),))
    candidates = tuple(item for item in resolved.value.cycles if item.monthly)
    if not candidates:
        return DemandExpansion(unknown_reasons=(UnknownReason("G_SCS_EXPIRY_UNIQUE_UNKNOWN"),))
    distances = {item.expiration_date: abs(item.days_to_expiration - 45) for item in candidates}
    minimum = min(distances.values())
    selected = tuple(sorted(day for day, distance in distances.items() if distance == minimum))
    if len(selected) != 1:
        return DemandExpansion(unknown_reasons=(UnknownReason("AMBIGUOUS_SELECTION"),))
    expiration = selected[0]
    return DemandExpansion(
        demands=(chain_demand(now, expiration),),
        selections=(("expiration", expiration.isoformat()),),
    )


def resolved_field_requirements() -> dict[MarketCapability, tuple[tuple[str, ...], int]]:
    return {
        MarketCapability.REAL_TIME_QUOTE_V1: (("last",), 3600),
        MarketCapability.OPTION_CHAIN_V1: (("contracts",), 3600),
    }
