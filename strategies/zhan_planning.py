"""Provider-neutral phased acquisition demands for Zhan SP-05C."""

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

RISK_FREE_SERIES = "US_TBILL_4WK_COUPON_EQUIVALENT"


def bars_demand(now: datetime) -> CapabilityDemand:
    return CapabilityDemand(
        MarketCapability.HISTORICAL_BARS_V1,
        ("close",),
        now - timedelta(days=10),
        now,
        maximum_age_seconds=int(timedelta(days=10).total_seconds()),
    )


def expirations_demand(now: datetime) -> CapabilityDemand:
    return CapabilityDemand(MarketCapability.OPTION_CHAIN_V1, ("expirations",), now, now)


def security_master_demand(now: datetime) -> CapabilityDemand:
    return CapabilityDemand(
        MarketCapability.SECURITY_MASTER_V1,
        ("effective_date", "security_type", "shares_outstanding"),
        now - timedelta(days=31),
        now,
        required=False,
        maximum_age_seconds=int(timedelta(days=31).total_seconds()),
    )


def rate_demand(now: datetime) -> CapabilityDemand:
    return CapabilityDemand(
        MarketCapability.RATE_OBSERVATION_V1,
        ("value",),
        now - timedelta(days=10),
        now,
        required=False,
        maximum_age_seconds=int(timedelta(days=10).total_seconds()),
        subject_symbol=RISK_FREE_SERIES,
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
    return bars_demand(now), expirations_demand(now), security_master_demand(now), rate_demand(now)


def expand_demands(
    evidence: Mapping[str, ResolvedCapabilityEvidence], *, now: datetime
) -> DemandExpansion:
    resolved = evidence.get(expirations_demand(now).demand_id)
    if (
        resolved is None
        or resolved.usability is not EvidenceUsability.RESOLVED
        or not isinstance(resolved.value, ExpirationCollection)
    ):
        return DemandExpansion(unknown_reasons=(UnknownReason("G_ZHAN_MATURITY_UNKNOWN"),))
    next_month = now.date().replace(year=now.year + (now.month == 12), month=now.month % 12 + 1)
    candidates = tuple(
        sorted(
            cycle.expiration_date
            for cycle in resolved.value.cycles
            if cycle.expiration_date > next_month
        )
    )
    if not candidates:
        return DemandExpansion(unknown_reasons=(UnknownReason("G_ZHAN_MATURITY_UNKNOWN"),))
    selected = candidates[0]
    return DemandExpansion(
        demands=(chain_demand(now, selected),),
        selections=(("expiration", selected.isoformat()),),
    )


def resolved_field_requirements() -> dict[MarketCapability, tuple[tuple[str, ...], int]]:
    return {
        MarketCapability.HISTORICAL_BARS_V1: (("close",), int(timedelta(days=10).total_seconds())),
        MarketCapability.OPTION_CHAIN_V1: (("contracts",), 3600),
        MarketCapability.SECURITY_MASTER_V1: (
            ("effective_date", "security_type", "shares_outstanding"),
            int(timedelta(days=31).total_seconds()),
        ),
        MarketCapability.RATE_OBSERVATION_V1: (("value",), int(timedelta(days=10).total_seconds())),
    }
