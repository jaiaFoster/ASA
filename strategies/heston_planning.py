"""Provider-neutral Heston phased acquisition demands."""

from datetime import date, datetime, timedelta
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


def expirations_demand(now: datetime) -> CapabilityDemand:
    return CapabilityDemand(MarketCapability.OPTION_CHAIN_V1, ("expirations",), now, now)


def historical_panel_demand(now: datetime) -> CapabilityDemand:
    return CapabilityDemand(
        MarketCapability.HISTORICAL_OPTION_PANEL_V1,
        ("contracts", "observed_at"),
        now - timedelta(days=400),
        now,
        maximum_age_seconds=int(timedelta(days=400).total_seconds()),
        required=False,
    )


def chain_demand(now: datetime, expiration: date) -> CapabilityDemand:
    return CapabilityDemand(
        MarketCapability.OPTION_CHAIN_V1,
        ("contracts",),
        now,
        now,
        expiration=expiration,
    )


def bootstrap_demands(now: datetime) -> tuple[CapabilityDemand, ...]:
    return expirations_demand(now), historical_panel_demand(now)


def expand_demands(
    evidence: Mapping[str, ResolvedCapabilityEvidence], *, now: datetime
) -> DemandExpansion:
    resolved = evidence.get(expirations_demand(now).demand_id)
    if (
        resolved is None
        or resolved.usability is not EvidenceUsability.RESOLVED
        or not isinstance(resolved.value, ExpirationCollection)
    ):
        return DemandExpansion(unknown_reasons=(UnknownReason("G_HES_FORMATION_DATE_UNKNOWN"),))
    candidates = tuple(
        sorted(
            cycle.expiration_date
            for cycle in resolved.value.cycles
            if cycle.expiration_date > now.date()
        )
    )
    if not candidates:
        return DemandExpansion(unknown_reasons=(UnknownReason("G_HES_FORMATION_DATE_UNKNOWN"),))
    selected = candidates[0]
    return DemandExpansion(
        demands=(chain_demand(now, selected),),
        selections=(("expiration", selected.isoformat()),),
    )


def resolved_field_requirements() -> dict[MarketCapability, tuple[tuple[str, ...], int]]:
    return {
        MarketCapability.OPTION_CHAIN_V1: (("contracts",), 3600),
        MarketCapability.HISTORICAL_OPTION_PANEL_V1: (
            ("contracts", "observed_at"),
            int(timedelta(days=400).total_seconds()),
        ),
    }
