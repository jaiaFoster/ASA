"""Provider-blind subject demands for Skew Momentum."""

from __future__ import annotations

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

HISTORICAL_LOOKBACK_DAYS = 180


def quote_demand(now: datetime) -> CapabilityDemand:
    return CapabilityDemand(MarketCapability.REAL_TIME_QUOTE_V1, ("last",), now, now)


def expirations_demand(now: datetime) -> CapabilityDemand:
    return CapabilityDemand(MarketCapability.OPTION_CHAIN_V1, ("expirations",), now, now)


def bars_demand(now: datetime) -> CapabilityDemand:
    return CapabilityDemand(
        MarketCapability.HISTORICAL_BARS_V1,
        ("close",),
        now - timedelta(days=HISTORICAL_LOOKBACK_DAYS),
        now,
        maximum_age_seconds=int(timedelta(days=HISTORICAL_LOOKBACK_DAYS + 1).total_seconds()),
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
    return quote_demand(now), expirations_demand(now), bars_demand(now)


def expand_demands(
    evidence: Mapping[str, ResolvedCapabilityEvidence], *, now: datetime
) -> DemandExpansion:
    discovery = expirations_demand(now)
    resolved = evidence.get(discovery.demand_id)
    if (
        resolved is None
        or resolved.usability is not EvidenceUsability.RESOLVED
        or not isinstance(resolved.value, ExpirationCollection)
    ):
        return DemandExpansion(unknown_reasons=(UnknownReason("no_future_expiration"),))
    future = tuple(
        cycle.expiration_date
        for cycle in resolved.value.cycles
        if cycle.expiration_date > now.date()
    )
    if not future:
        return DemandExpansion(unknown_reasons=(UnknownReason("no_future_expiration"),))
    expiration = min(future)
    return DemandExpansion(
        demands=(chain_demand(now, expiration),),
        selections=(("expiration", expiration.isoformat()),),
    )


def resolved_field_requirements() -> dict[MarketCapability, tuple[tuple[str, ...], int]]:
    return {
        MarketCapability.REAL_TIME_QUOTE_V1: (("last",), 3600),
        MarketCapability.OPTION_CHAIN_V1: (("contracts",), 3600),
        MarketCapability.HISTORICAL_BARS_V1: (
            ("close",),
            int(timedelta(days=HISTORICAL_LOOKBACK_DAYS + 1).total_seconds()),
        ),
    }
