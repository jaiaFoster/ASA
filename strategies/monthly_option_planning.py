"""Shared monthly-chain mechanics; consumers own diagnostic vocabulary."""

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


def next_month_expiration(expirations: tuple[ExpirationCycle, ...], today: date) -> date | None:
    year, month = (today.year + 1, 1) if today.month == 12 else (today.year, today.month + 1)
    candidates = sorted(
        {
            item.expiration_date
            for item in expirations
            if item.monthly
            and (item.expiration_date.year, item.expiration_date.month) == (year, month)
        }
    )
    # Exact standard-contract identity remains checked after chain acquisition.
    return candidates[0] if candidates else None


def expand_monthly_chain_demands(
    evidence: Mapping[str, ResolvedCapabilityEvidence], *, now: datetime, unknown_code: str
) -> DemandExpansion:
    resolved = evidence.get(expirations_demand(now).demand_id)
    if (
        resolved is None
        or resolved.usability is not EvidenceUsability.RESOLVED
        or not isinstance(resolved.value, ExpirationCollection)
    ):
        return DemandExpansion(unknown_reasons=(UnknownReason(unknown_code),))
    selected = next_month_expiration(resolved.value.cycles, now.date())
    if selected is None:
        return DemandExpansion(unknown_reasons=(UnknownReason(unknown_code),))
    return DemandExpansion(
        demands=(chain_demand(now, selected),), selections=(("expiration", selected.isoformat()),)
    )
