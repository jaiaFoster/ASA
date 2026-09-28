"""Provider-neutral two-phase demands for Cboe PUT."""

from datetime import date, datetime
from typing import Mapping  # noqa: UP035

from domain import (
    CapabilityDemand,
    DemandExpansion,
    EvidenceUsability,
    ExpirationCollection,
    ExpirationCycle,
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


def _next_month_expiration(
    expirations: tuple[ExpirationCycle, ...], today: date
) -> date | UnknownReason:
    year, month = (today.year + 1, 1) if today.month == 12 else (today.year, today.month + 1)
    candidates = sorted(
        {
            item.expiration_date
            for item in expirations
            if item.monthly
            and (item.expiration_date.year, item.expiration_date.month) == (year, month)
        }
    )
    if not candidates:
        return UnknownReason("G_PUT_STRIKE_EXISTS_UNKNOWN")
    # Standard SPX identity is verified after the exact chain is acquired.
    return candidates[0]


def expand_demands(
    evidence: Mapping[str, ResolvedCapabilityEvidence], *, now: datetime
) -> DemandExpansion:
    resolved = evidence.get(expirations_demand(now).demand_id)
    if (
        resolved is None
        or resolved.usability is not EvidenceUsability.RESOLVED
        or not isinstance(resolved.value, ExpirationCollection)
    ):
        return DemandExpansion(unknown_reasons=(UnknownReason("G_PUT_STRIKE_EXISTS_UNKNOWN"),))
    selected = _next_month_expiration(resolved.value.cycles, now.date())
    if isinstance(selected, UnknownReason):
        return DemandExpansion(unknown_reasons=(selected,))
    return DemandExpansion(
        demands=(chain_demand(now, selected),), selections=(("expiration", selected.isoformat()),)
    )


def resolved_field_requirements() -> dict[MarketCapability, tuple[tuple[str, ...], int]]:
    return {
        MarketCapability.REAL_TIME_QUOTE_V1: (("last",), 3600),
        MarketCapability.OPTION_CHAIN_V1: (("contracts",), 3600),
    }
