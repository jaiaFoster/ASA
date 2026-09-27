"""Pure, provider-neutral two-phase demands for GXZ."""

from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Mapping  # noqa: UP035

from domain import (
    CapabilityDemand,
    DemandExpansion,
    EarningsEvent,
    EvidenceUsability,
    ExpirationCollection,
    MarketCapability,
    ResolvedCapabilityEvidence,
    UnknownReason,
)
from strategies.earnings_calendar_planning import earnings_demand


def quote_demand(now: datetime) -> CapabilityDemand:
    return CapabilityDemand(MarketCapability.REAL_TIME_QUOTE_V1, ("last",), now, now)


def calendar_demand(now: datetime) -> CapabilityDemand:
    return CapabilityDemand(
        MarketCapability.TRADING_CALENDAR_V1,
        ("trading_date",),
        now - timedelta(days=10),
        now + timedelta(days=14),
    )


def expirations_demand(now: datetime) -> CapabilityDemand:
    return CapabilityDemand(MarketCapability.OPTION_CHAIN_V1, ("expirations",), now, now)


def chain_demand(now: datetime, expiration: date) -> CapabilityDemand:
    return CapabilityDemand(
        MarketCapability.OPTION_CHAIN_V1, ("contracts",), now, now, expiration=expiration
    )


def bootstrap_demands(now: datetime) -> tuple[CapabilityDemand, ...]:
    # TRADING_CALENDAR_V1 is contractually required but no enabled production
    # provider currently publishes the range needed to prove a -3 session
    # offset. The binding therefore emits a typed deferral instead of asking
    # the planner to invent a provider or crashing the shared subject plan.
    return quote_demand(now), earnings_demand(now), expirations_demand(now)


def expand_demands(
    evidence: Mapping[str, ResolvedCapabilityEvidence], *, now: datetime
) -> DemandExpansion:
    earnings = evidence.get(earnings_demand(now).demand_id)
    expirations = evidence.get(expirations_demand(now).demand_id)
    if (
        earnings is None
        or earnings.usability is not EvidenceUsability.RESOLVED
        or not isinstance(earnings.value, EarningsEvent)
    ):
        return DemandExpansion(unknown_reasons=(UnknownReason("G_GXZ_EA_DATE_KNOWN_UNKNOWN"),))
    if not earnings.value.confirmed:
        return DemandExpansion(unknown_reasons=(UnknownReason("G_GXZ_EA_DATE_KNOWN_UNKNOWN"),))
    if (
        expirations is None
        or expirations.usability is not EvidenceUsability.RESOLVED
        or not isinstance(expirations.value, ExpirationCollection)
    ):
        return DemandExpansion(unknown_reasons=(UnknownReason("G_GXZ_HOLD_TO_EXPIRY_DTE_UNKNOWN"),))
    candidates = tuple(
        sorted(
            {
                cycle.expiration_date
                for cycle in expirations.value.cycles
                if cycle.expiration_date > earnings.value.earnings_date
                and 4 <= (cycle.expiration_date - now.date()).days <= 10
            }
        )
    )
    if not candidates:
        return DemandExpansion(unknown_reasons=(UnknownReason("G_GXZ_HOLD_TO_EXPIRY_DTE_FAIL"),))
    selected = candidates[0]
    return DemandExpansion(
        demands=(chain_demand(now, selected),), selections=(("expiration", selected.isoformat()),)
    )


def resolved_field_requirements() -> dict[MarketCapability, tuple[tuple[str, ...], int]]:
    return {
        MarketCapability.REAL_TIME_QUOTE_V1: (("last",), 3600),
        MarketCapability.EARNINGS_CALENDAR_V1: (("earnings_date",), 3600),
        MarketCapability.OPTION_CHAIN_V1: (("contracts",), 3600),
    }
